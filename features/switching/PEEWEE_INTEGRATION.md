# Ranh giới tích hợp Peewee trong Switching

Đối chiếu: **2026-08-22**.

Peewee được dùng có chọn lọc, không thay thế toàn bộ tầng SQLite của ứng dụng.
Mục tiêu là giảm SQL động và gom cập nhật lifecycle vào transaction rõ ràng mà
không thay đổi schema hay luồng dữ liệu của Router.

## Phần đang dùng Peewee

- `peewee_models.py` ánh xạ tối thiểu các cột định danh, ownership và lifecycle.
  Đây là projection lên schema hiện hữu, không phải nơi tạo hoặc migrate bảng.
- `peewee_context.py` tạo kết nối ngắn hạn theo path của workspace hiện tại.
  Model được tạo theo từng operation để worker đồng thời không bind nhầm DB.
- `policy_delete_repository.py` dùng biểu thức Peewee để stage xóa STP, VLAN
  Security, trusted uplink và static MAC, đồng thời luôn kiểm tra đúng `host`.
- `success_repository.py` dùng một transaction để xóa row sau Push hoặc cập
  nhật đồng thời `success`/`sync_status`, `device_present` và cleanup metadata.

## Phần chủ động giữ SQLite trực tiếp

- `schema.py` và các file SQL vẫn là nguồn sự thật duy nhất cho DDL/migration.
- Các repository VLAN, SVI, interface và EtherChannel có validation hoặc thay
  đổi nhiều bảng trong cùng transaction vẫn dùng `db._connect()` để không chia
  transaction giữa hai connection.
- Truy vấn tổng hợp cho Preview, desired state và pull-sync giữ SQL trực tiếp vì
  join/UPSERT hiện tại rõ hơn và đã có kiểm thử theo snapshot thiết bị.
- Parser CLI, renderer command và toàn bộ Router không phụ thuộc model Peewee.

## Quy tắc khi mở rộng

1. Không gọi `create_tables()` từ runtime; schema phải được sửa qua migration.
2. Chỉ thêm model/cột thực sự cần cho một workflow, không sao chép toàn schema.
3. Không mở Peewee connection bên trong transaction `sqlite3` đang hoạt động.
4. Mọi update/delete phải lọc bằng khóa chính; dữ liệu theo thiết bị phải kiểm
   tra thêm `host` trực tiếp hoặc qua quan hệ interface.
5. Workflow nhiều row phải dùng `database.atomic()` và rollback toàn bộ nếu một
   row đã bị xóa hoặc thay đổi ngoài dự kiến.

Kiểm thử hồi quy riêng nằm tại `tests/test_switching_peewee_persistence.py`.
