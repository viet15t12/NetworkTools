# Database migrations

Cập nhật: **2026-08-16**. Thư mục hiện chưa chứa framework migration versioned
tổng quát; migrate trạng thái số legacy và repair object đang nằm trong
`scripts/build_databases.py`.

Đặt migration có version tại đây khi schema cần nâng cấp dữ liệu runtime. Migration phải idempotent hoặc có bảng version, backup trước thay đổi phá vỡ và có test upgrade/rollback.

## Ghi chú tương thích khi loại bỏ tính năng

Các schema tạo mới không còn bảng/cột dành riêng cho QoS, storm control, VRF và cấu hình YANG. App cũng không còn đọc hoặc ghi các đối tượng này.

Không chạy `DROP TABLE` tự động trên database runtime đã tồn tại. Các bảng/cột cũ
được giữ nguyên nhưng không còn được sử dụng, nhờ đó quá trình nâng cấp không làm
mất dữ liệu và không khiến app lỗi khi mở database từ phiên bản trước. Muốn có
database sạch theo schema mới, hãy sao lưu dữ liệu cần thiết rồi chạy
`uv run python scripts/build_databases.py`; đây là build sạch, không phải migration.

Các MIME type `application/yang-data+json` vẫn được giữ trong worker RESTCONF vì đây là yêu cầu của giao thức truyền tải, không phải tính năng lưu trữ hay quản lý YANG model.
