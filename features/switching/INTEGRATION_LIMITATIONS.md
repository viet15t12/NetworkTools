# Các phần Switch Layer 2 chưa thể tích hợp an toàn

Đối chiếu: **2026-08-22**.

Các phần dưới đây được chủ động chặn thay vì suy đoán cấu hình và gây ảnh hưởng
switch đang vận hành:

- Chỉ Cisco IOS qua SSH/Telnet được Preview/Push. RESTCONF, NETCONF và platform
  khác chưa có mapping lệnh đã kiểm chứng.
- Pull-sync đã có cho VLAN, switchport/trunk, EtherChannel và VTP status trên
  Cisco IOS. STP, L2 security, SVI/routed port và dữ liệu monitoring chưa có
  parser pull-sync đầy đủ; các module này chỉ đánh dấu đồng bộ sau khi IOS chấp
  nhận lệnh Push.
- Xóa VLAN, SVI, EtherChannel, STP policy, VLAN Security, trusted uplink và
  static MAC dùng trạng thái `pending_delete` rồi mới xóa row sau Push thành
  công. Interface vật lý và VTP domain không có nút xóa vì IOS không cung cấp
  một lệnh xóa tương đương, an toàn cho hai loại đối tượng này.
- Port `hybrid` bị chặn khi push vì schema hiện không lưu đủ native/allowed VLAN
  profile cho mode này.
- VTP password trong schema được yêu cầu mã hoá; app không chạy `show vtp
  password`, không import plaintext và vẫn chặn push authentication khi chưa có
  decryptor an toàn.
- MST cần instance-to-VLAN mapping chưa có trong schema nên bị chặn. Kích hoạt
  VTPv3 primary server và VTPv3 MST database cũng cần luồng xác nhận tương tác
  riêng nên chưa push tự động.
- EtherChannel hiện push member, protocol/mode và mô tả Port-channel. Schema
  chưa có switchport profile riêng cho Port-channel.
- Khi mọi VLAN security đều tắt, worker gỡ DHCP snooping/DAI theo từng VLAN
  nhưng không tự gỡ global feature để tránh ảnh hưởng cấu hình ngoài app.
- VTP đã có trang tạo/cập nhật group cho VLAN database mode không authentication.
  EtherChannel, STP và L2 Security có CRUD cùng Preview/Push riêng.

Ngoài phạm vi theo thiết kế: QoS, storm-control và YANG model.
