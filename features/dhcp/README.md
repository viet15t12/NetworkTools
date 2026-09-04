# DHCP

DHCP pool, excluded address và helper address. **implemented** với QML
`UI/qml/features/dhcp/DhcpView.qml`, slots `core/dhcp_slots.py`, persistence và
worker trong `features/dhcp`. Desired state dùng `t03_*`; dữ liệu DHCP quan sát
dùng `t09_info_dhcp_*` trong database khác. Validation kiểm tra network/mask,
range, gateway, DNS và foreign key interface. View chỉ preview; Push chạy nền và
`dev = 1` không mở session thật. Parser RESTCONF thử nghiệm chưa phải đường hỗ
trợ end-to-end. Test: `test_dhcp_acl_persistence.py`, `test_dev_mode_workers.py`
và QML smoke.
