#import "../config/commands.typ": front-heading

#front-heading[TÓM TẮT]

Trong công tác quản trị và thực hành mạng máy tính, phương thức cấu hình thiết bị truyền thống qua giao diện dòng lệnh (CLI) bộc lộ nhiều hạn chế: thao tác lặp lại, nguy cơ sai cú pháp, khó kiểm soát sai lệch cấu hình và thiếu cơ sở dữ liệu quản trị tập trung. Nhằm giải quyết các vấn đề này, ĐỀ TÀI: NGHIÊN CỨU VÀ XÂY DỰNG HỆ THỐNG QUẢN LÝ TẬP TRUNG, TỰ ĐỘNG HÓA CẤU HÌNH VÀ GIÁM SÁT AN NINH MẠNG viết tắt là CAMS hướng đến xây dựng một hệ thống quản lý tập trung, tự động hóa cấu hình và giám sát an ninh mạng cho thiết bị Cisco IOS trong môi trường học tập và thực nghiệm phòng lab.

CAMS được thiết kế theo kiến trúc phân lớp hướng module (Clean Architecture), kết hợp giao diện đồ họa khai báo bằng Qt Quick/QML, lớp điều phối PyQt6, cơ sở dữ liệu quan hệ nhúng SQLite gồm 93 bảng chuẩn hóa, cùng các tiến trình nền sử dụng Netmiko/Paramiko và bộ tạo mẫu Jinja2. Hệ thống vận hành theo quy trình quản trị cấu hình dựa trên trạng thái: quản lý danh mục thiết bị, thu thập và sao lưu running-config vào kho Git cục bộ bằng Dulwich, định nghĩa trạng thái mong muốn (Desired State), kiểm duyệt (Preview) và đẩy cấu hình an toàn (Push).

Phạm vi chức năng của CAMS bao phủ từ chuyển mạch Lớp 2 đến định tuyến và dịch vụ Lớp 3. Hệ thống còn tích hợp máy chủ Syslog thu nhận nhật ký thời gian thực, máy khách SFTP truyền tệp an toàn và một terminal nhúng phục vụ thao tác dòng lệnh thủ công. Kết quả thử nghiệm trên môi trường lab EVE-NG và bộ kiểm thử tự động xác nhận tính ổn định, độ tin cậy và khả năng rút ngắn đáng kể thời gian triển khai cấu hình mạng so với phương pháp thủ công.

*Từ khóa:* Tự động hóa mạng, Quản lý tập trung, CAMS, Cisco IOS, Qt Quick/QML, PyQt6, SQLite, Jinja2, View & Push.
