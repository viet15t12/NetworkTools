# OSPF

**partial**, đối chiếu **2026-08-22**, cho process, area/range, network,
distance, interface, passive, redistribution và tuning. QML
`UI/qml/features/routing/ospf/OspfRoutingForm.qml`; API qua `dbManager`; DB nhóm
OSPF `t04_*`; worker `features/routing/ospf/worker.py`. Validate process/area/
prefix/cost và ghi parent-child atomically. Routing Group preview theo host và
push tối đa năm thiết bị đồng thời, lỗi một host không dừng các host còn lại.
Backlog: repository/service riêng và fake-session integration rộng hơn.

Payload từ `ListModel` được chuyển thành plain JavaScript object trước khi gọi
slot Python để các row area/range, redistribution, passive-interface và interface
setting không bị biến thành `QObject` rỗng. Backend validate toàn bộ payload trước
transaction (ID, IP, range số, duplicate và enum), nên payload lỗi không làm thay
đổi dữ liệu đang có. Distance/Tuning được hydrate lại khi load DB hoặc đổi process;
lỗi load/save được đưa vào `FormLayout.errorMessage` ngoài thông báo status bar.

Process table dùng `action_Cfg` bốn bit cho router-id, reference bandwidth,
passive-default và default-originate. Save chỉ bật bit của nhóm thực sự thay đổi;
dispatcher/worker bỏ qua các bit 0 và reset mask về `0000` sau push thành công.
Workspace cũ được bổ sung cột này bằng migration không phá dữ liệu.
