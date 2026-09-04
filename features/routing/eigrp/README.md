# EIGRP

**partial**, đối chiếu **2026-08-18**, cho process, network, interface, passive,
redistribution, distribute/offset list và key chain. QML
`UI/qml/features/routing/eigrp/EigrpRoutingForm.qml`; DB nhóm EIGRP `t04_*`;
worker dùng `features/routing/worker.py`. Validate ASN, prefix, metric và
parent-child transaction. Routing Group preview theo host và push tối đa năm
thiết bị đồng thời, lỗi một host không dừng các host còn lại. Backlog: service
boundary riêng và fake-session integration rộng hơn.
