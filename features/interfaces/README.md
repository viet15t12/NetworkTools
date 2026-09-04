# Router Interfaces

Trạng thái: **implemented** cho Cisco IOS SSH/Telnet trong phạm vi dưới đây;
multi-vendor, IPv6, RESTCONF/NETCONF, verify và rollback còn **partial**.
Đối chiếu: **2026-08-18**.

Router Interface đã có luồng QML → slot → `InterfaceService` → repository / IOS
generator. Backend sở hữu quy tắc tên, validation và quyền create/delete; QML
không sinh tên interface ảo và không ghép lệnh IOS.

Phạm vi hiện được triển khai cho Router Interface:

- Physical: chỉ load/edit interface đã được đồng bộ từ running-config và
  `show ip interface brief`; không có catalog port dựng sẵn, không cho tạo hoặc
  xóa thủ công.
- Loopback: tạo theo số (`Loopback<number>`), edit và xóa.
- Tunnel: tạo theo số (`Tunnel<number>`), validate source/destination, edit và xóa.
- 802.1Q Subinterface: tạo từ parent + số, validate VLAN 1–4094, edit và xóa.
- L3/WAN profile, IPv4 primary/secondary, MTU/bandwidth/delay và trạng thái shutdown.

SVI và Port-channel/EtherChannel do `features/switching` sở hữu để không tạo hai
nguồn desired state cho cùng cấu hình thiết bị.

UI được tách theo trách nhiệm:

- `InterfaceView.qml`: điều phối host, model, selection, context menu và shortcut;
  lọc dữ liệu theo subfeature đang mở.
- `InterfaceSubBar.qml`: thanh con kiểu Routing gồm Physical, Loopback, Tunnel và
  Subinterface.
- `InterfaceEditorPane.qml`: chọn loại virtual, form L3/WAN/Tunnel/Subinterface và
  tạo payload; loại virtual lấy từ subfeature nên không còn dropdown type trùng lặp.
- `InterfaceSavedPanel.qml`: danh sách, type badge và row action theo capability.

Backend được tách theo trách nhiệm:

- `models.py`: enum, canonical/short name và capability metadata.
- `validation.py`: IPv4/mask, tên, type/profile, tunnel và VLAN validation.
- `service.py`: use case save/create virtual/capability với kết quả có cấu trúc.
- `repository.py`: transaction trên schema canonical `t02_*` hiện hữu.

`interface_name` luôn read-only trong QML. Với Physical, người dùng chọn row đã
đồng bộ trong danh sách bên trái. Với interface ảo, tên được backend sinh từ loại,
số và parent; parent của Subinterface cũng phải chọn từ danh sách Physical đã
đồng bộ, không nhập text tự do. Luồng device sync thay thế snapshot interface trong DB: interface
không còn xuất hiện ở cả running-config lẫn interface brief sẽ bị xóa khỏi DB,
không bị biến thành một lệnh `no interface` pending ngoài ý muốn.

Device Sync nhận diện tên có dấu `.` là Subinterface và parse riêng
`encapsulation dot1Q|isl <vlan> [native]`. Snapshot được ghi vào
`t02_router_iface_subif`, không tạo profile L3 vật lý. Profile L3 legacy bị gắn
nhầm trên Subinterface không được tính là pending và không được sinh các lệnh
`default speed`, `default duplex`, `default mtu`, `default bandwidth` hoặc
`default delay`. Khi đồng bộ snapshot mới, child profile không còn được thiết
bị báo về sẽ bị xóa cục bộ thay vì biến thành tác vụ View & Push.

Pipeline push được tách theo trách nhiệm:

- `collector.py`: đọc pending state ở bảng interface chính và profile
  L3/WAN/Tunnel/Subinterface.
- `commands.py`: dựng lệnh Cisco IOS thuần và redaction mật khẩu PPP.
- `worker.py`: gửi một batch interface qua session SSH/Telnet do app sở hữu.
- `push_state.py`: chỉ cập nhật/xóa đúng row sau khi thiết bị chấp nhận lệnh.
- `view_push.py`: kiểm tra platform, điều phối preview/push và tạo report theo interface.

Nguồn tham khảo ban đầu là `archive/backend/PyCode/router_layer3/interface`, nhưng runtime
mới không tạo Nornir inventory hoặc file output tạm. Nó dùng chung
`DeviceSessionRegistry` với app để tránh mở hai kết nối cho cùng một thao tác.

Schema không được thay bằng bảng `interfaces` mới như bản thiết kế khái niệm vì
database runtime đã có class-table tương đương (`t02_interface_name` cùng các bảng
profile) và đang được các feature khác tham chiếu. Cách triển khai này giữ dữ liệu
và foreign key hiện hữu, đồng thời vẫn tách domain/service khỏi QML.

Hiện hỗ trợ Cisco IOS qua SSH/Telnet. Preview và report che mật khẩu PPP; một row
chỉ chuyển `synchronized` sau khi thiết bị chấp nhận batch. Xóa interface ảo sinh
`no interface <canonical-name>`; physical không đi vào luồng xóa. RESTCONF/NETCONF,
IPv6, device-model profile tự populate, verify sau push và rollback tự động chưa
nằm trong phạm vi tích hợp này.

Test chính: `test_router_interface_service.py`, `test_interface_view_push.py`,
`test_ui_contracts.py` và QML smoke.
