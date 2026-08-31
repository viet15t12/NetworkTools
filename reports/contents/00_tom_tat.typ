#import "../config/commands.typ": front-heading

#front-heading[TÓM TẮT]

Trong công tác quản trị và thực hành mạng máy tính, phương thức cấu hình thiết bị truyền thống thông qua giao diện dòng lệnh (CLI) bộc lộ nhiều hạn chế về sự lặp lại thao tác, nguy cơ sai sót cú pháp, khó kiểm soát sự sai lệch cấu hình (Configuration Drift) và thiếu cơ sở dữ liệu quản trị tập trung. Nhằm giải quyết các vấn đề này, đề tài nghiên cứu và phát triển *CAMS (Centralized Automation & Monitoring System)* — một hệ thống quản lý tập trung, tự động hóa cấu hình và giám sát an ninh mạng cho thiết bị Cisco IOS trong môi trường học tập và thực nghiệm phòng lab.

Phần mềm được thiết kế theo kiến trúc phân lớp hướng module (Clean Architecture), kết hợp giữa giao diện đồ họa hiện đại khai báo bằng *Qt Quick/QML*, lớp điều phối và cầu nối *PyQt6*, hệ quản trị cơ sở dữ liệu quan hệ nhúng *SQLite* gồm 93 bảng dữ liệu chuẩn hóa, cùng các tiến trình thực thi nền sử dụng *Netmiko/Paramiko* và bộ tạo mẫu *Jinja2*. Hệ thống vận hành theo quy trình quản trị cấu hình chặt chẽ dựa trên trạng thái (Data-driven State Management): từ khâu quản lý danh mục thiết bị (Inventory), thu thập và sao lưu cấu hình đang chạy (`running-config`) vào kho Git cục bộ bằng *Dulwich*, định nghĩa trạng thái mong muốn (Desired State), đến cơ chế kiểm duyệt trực quan (*Preview*) và đẩy cấu hình an toàn (*Push*).

Phạm vi chức năng của CAMS bao phủ toàn diện từ cấu hình chuyển mạch Lớp 2 (VLAN, Trunking dot1q, EtherChannel LACP, STP, VTP, Port Security, DHCP Snooping, DAI) lên định tuyến và dịch vụ Lớp 3 (Interface IPv4, Subinterface, Static Route, OSPFv2, EIGRP, DHCP Server/Relay, NAT/PAT, HSRP). Đồng thời, phần mềm tích hợp các tiện ích vận hành nâng cao gồm máy chủ Syslog Server thu nhận nhật ký thời gian thực, máy khách truyền tệp SFTP an toàn và Terminal Alacritty nhúng. Kết quả thử nghiệm trên môi trường lab EVE-NG và bộ kiểm thử tự động xác minh tính ổn định, độ tin cậy và khả năng rút ngắn đáng kể thời gian triển khai cấu hình mạng so với phương pháp thủ công.

*Từ khóa:* Tự động hóa mạng, Quản lý tập trung, CAMS, Cisco IOS, Qt Quick/QML, PyQt6, SQLite, Jinja2, View & Push.
