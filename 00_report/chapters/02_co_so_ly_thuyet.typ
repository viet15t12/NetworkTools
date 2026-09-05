#pagebreak(weak: true)
= Cơ sở lý thuyết và cô          ng nghệ

== Quản lý cấu hình và tự động hóa mạng

Báo cáo phân biệt các khái niệm *current state*, *desired state*, cấu hình pending, preview, apply và verify. CAMS không được mô tả là có rollback hoàn chỉnh nếu chưa có mã nguồn và kiểm thử chứng minh. Các khái niệm nền tảng về mạng máy tính và giao thức được tham khảo từ @tanenbaum2021computer.

== Giao thức truy cập và quản trị

- SSH/Telnet được sử dụng trong connector hiện tại.
- Telnet có rủi ro bảo mật; thiết kế ưu tiên SSH khi có thể.

== Nghiệp vụ mạng thuộc phạm vi

- Interface L3/WAN/Tunnel và QoS cơ bản.
- DHCP pool, excluded address và helper.
- Static route, OSPF và EIGRP.
- ACL và binding interface.
- Static NAT, Dynamic NAT, PAT, NAT ACL và route-map.

VLAN, BGP chỉ nên được giới thiệu như nền tảng cho hướng mở rộng nếu chưa có luồng sản phẩm hoàn chỉnh.

== Nền tảng phần mềm

- Python và mô hình module.
- Qt Quick/QML, PyQt6 signal/slot và context property.
- SQLite, khóa ngoại, quan hệ parent–child và soft delete.
- Jinja2 template.
- Netmiko, Nornir, ncclient và Requests tại các module thực tế sử dụng chúng.

== Nguyên tắc kiểm thử

Hệ thống sử dụng các nhóm kiểm thử gồm unit/contract test, QML smoke test, dev-mode safety test và thử nghiệm tích hợp trên lab.
