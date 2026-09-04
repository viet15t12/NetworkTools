# Switching

Trạng thái: **implemented** cho desired-state và View & Push Layer 2 Cisco IOS
qua SSH/Telnet; các transport/platform khác còn **partial**. Đối chiếu:
**2026-08-22**.

Workspace quản lý switch được bố trí theo trách nhiệm nhỏ:

- `vlan_repository.py`, `interface_repository.py`, `etherchannel_repository.py`,
  `stp_repository.py`, `security_repository.py`, `l3_repository.py` và
  `monitoring_repository.py`: CRUD/truy vấn desired state.
- `desired_state.py`: đọc và chuẩn hoá dữ liệu Layer 2 cho từng module.
- `interface_commands.py`: dựng lệnh riêng cho switch port, routed port và
  EtherChannel; `commands.py` giữ các renderer VLAN/SVI/STP/VTP/Security.
- `entity_rules.py`, `lifecycle.py`: kiểm tra tham chiếu/định danh và phân biệt
  local draft với cấu hình đã có trên thiết bị.
- `cli_validation.py`, `worker.py`: phân tích output rồi gửi tập lệnh qua phiên
  SSH/Telnet đang mở của app.
- `interface_task_builder.py`: tạo task interface và xử lý chuyển mode có Port
  Security mà không làm `view_push.py` gánh thêm logic chi tiết.
- `policy_task_builder.py`: tạo task STP, Port Security và L2 Security, bao gồm
  metadata xóa/synchronize cho từng policy row.
- `etherchannel_sync.py`, `interface_names.py`: parse/reconcile EtherChannel và
  chuẩn hoá tên interface dùng chung cho pull-sync.
- `policy_delete_repository.py`: stage các lệnh xóa STP/L2 Security/trust/static
  MAC trước khi xóa row sau Push thành công; các update lifecycle dùng Peewee.
- `success_repository.py`: cập nhật `success` đúng row nghiệp vụ sau khi thiết
  bị chấp nhận task trong một transaction Peewee; không dùng hash hoặc bảng
  trạng thái song song.
- `peewee_models.py`, `peewee_context.py`: model tối thiểu và kết nối ngắn hạn
  theo workspace, không bind toàn cục và không tạo/migrate schema.
- `view_push.py`: điều phối Preview/Push theo đúng tab và chỉ đánh dấu task đã
  đồng bộ sau khi thiết bị chấp nhận lệnh.
- `vtp_group.py`: lưu một VTP domain cho 2–5 switch theo từng transaction độc
  lập, cho phép retry/upsert và trả kết quả partial khi một member lỗi.
- `sync.py`: parse output Cisco IOS và transaction pull-sync VLAN,
  switchport/trunk, EtherChannel, VTP status; bảo toàn module local pending.

QML dùng `ViewPushButton` chung trên trang VLAN, Switch Ports, EtherChannel,
STP, L2 Security và Port Security. Trang EtherChannel tạo/cập nhật trực tiếp
bảng `t06_etherchannel` cũ. Trang STP quản lý mode toàn cục và root policy theo
VLAN. Trang L2 Security quản lý DHCP Snooping, DAI, trusted uplink và static
MAC; các bảng desired state cũ được giữ nguyên và được bổ sung cột `success`.
Trang VTP Group dùng `MultiHostViewPushDialog`: Save ghi desired state ở trạng
thái `pending_apply`, sau đó Preview/Push song song tối đa 5 switch và chỉ push
những member đã lưu thành công.
View & Push của mỗi tab chỉ thu thập row thay đổi thuộc tab đó. Chế độ `all` chỉ
dùng cho thao tác tổng hợp có chủ ý. SVI, routed port và IP routing trên switch
SW3 đã được đưa vào Preview/Push; QoS và storm-control không thuộc tích hợp này.

Schema nằm ở `infrastructure/database/schemas/device_network/06_l2_switching.sql`
và `09_vtp.sql`. `ensure_switch_schema()` chỉ bổ sung các cột lifecycle còn
thiếu, không dựng lại database. Bảng hash của project cũ (nếu có) không còn
được đọc hoặc ghi.

Hỗ trợ push và pull-sync nêu trên: Cisco IOS qua SSH/Telnet. Các giới hạn chưa thể tích hợp
an toàn được ghi tại [INTEGRATION_LIMITATIONS.md](INTEGRATION_LIMITATIONS.md).
Phạm vi dùng ORM và các quy tắc để không ảnh hưởng Router/toàn app được ghi tại
[PEEWEE_INTEGRATION.md](PEEWEE_INTEGRATION.md).

Kiểm thử:

```bash
.venv/bin/python -m unittest tests.test_switching_workspace \
  tests.test_switching_view_push tests.test_switching_peewee_persistence \
  tests.unit.test_switch_sync \
  tests.test_routing_group_fhrp
```
