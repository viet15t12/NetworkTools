# FHRP

Trạng thái: **implemented** cho Cisco IOS SSH/Telnet. Đối chiếu:
**2026-08-19**.

Feature FHRP cấu hình một Default Gateway ảo trên nhiều router/L3 switch cùng
lúc. QML entry là `UI/qml/features/fhrp/FhrpView.qml`, chia thành ba tab con
HSRP, VRRP và GLBP. Mỗi tab lazy-load một `FhrpProtocolPage.qml` và giữ draft,
host selection, group list riêng. Contract QML nằm trong `core/fhrp_slots.py`;
dữ liệu dùng các bảng `t08_fhrp_*`.

Luồng chuẩn:

1. Chọn từ hai đến năm host đang connected.
2. Nhập protocol, group/VRID và IP Default Gateway.
3. `FhrpService` lọc router interface/subinterface từ `t02_interface_name` và
   switch SVI từ `t06_svi_interface`. Chỉ endpoint đã synchronized, không
   shutdown và cùng subnet mask mới được chọn; gateway không được trùng IP
   interface, network address hoặc broadcast.
4. Nhập priority và preempt riêng cho từng host. Version, timer,
   authentication/key và policy cấp group phải giống nhau trên mọi member.
5. Repository lưu group/member/options trong transaction; member là đơn vị
   `sync_status`. Retry được phép thay thế đúng local draft `pending_apply`,
   nhưng không ghi đè group đã đồng bộ với thiết bị.
6. View & Push preview theo host, sau đó worker dùng session SSH/Telnet hiện có,
   kiểm tra output lỗi Cisco CLI, running-config và `show standby/vrrp/glbp
   brief`; chỉ cập nhật đúng member vượt qua verification.

Các file được tách theo trách nhiệm:

- `service.py`: validation và policy đa host.
- `repository.py`: inventory query và transaction SQLite.
- `collector.py`: đọc member pending.
- `commands.py` + `templates/cisco_ios/fhrp.j2`: render/redact lệnh.
- `worker.py`: device I/O.
- `verification.py`: xác minh desired config và operational FHRP sau push.
- `schema.py`: nâng cấp workspace cũ để member tham chiếu router interface/SVI.
- `push_state.py`: cập nhật trạng thái sau push.
- `view_push.py`: điều phối preview/push.

Hiện push hỗ trợ Cisco IOS qua SSH/Telnet cho HSRP, VRRPv2 và GLBP. VRRPv3
không được bật ngầm vì cần đổi FHRP mode toàn thiết bị và có thể ảnh hưởng group
ngoài phạm vi ứng dụng. RESTCONF, NETCONF, IPv6 và rollback tự động chưa được
tích hợp. Authentication secret được che trong preview, report command và CLI
output.
