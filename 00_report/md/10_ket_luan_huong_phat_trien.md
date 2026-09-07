# CHƯƠNG 6. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 6.1. Kết quả đạt được

Đề tài nghiên cứu khoa học "Nghiên cứu và xây dựng hệ thống quản lý tập trung, tự động hóa cấu hình và giám sát an ninh mạng" (CAMS) đã hoàn thành các mục tiêu nghiên cứu và kỹ thuật đề ra ban đầu. Nhóm tác giả đã thiết kế và hiện thực hóa thành công một hệ thống phần mềm hoàn chỉnh, kết hợp giao diện đồ họa hiện đại, cơ sở dữ liệu quan hệ cục bộ và các thư viện tự động hóa mạng chuyên sâu.

| Mục tiêu đề tài | Nội dung kỹ thuật đã hoàn thành | Bằng chứng kiểm chứng thực nghiệm |
| :--- | :--- | :--- |
| Kiến trúc phần mềm & giao diện | Clean Architecture; Qt Quick/QML; Lazy Loading; đa tab; chia đôi không gian làm việc; giao diện sáng/tối. | 256 tệp QML; 504/523 kiểm thử đạt; tác vụ SSH không làm nghẽn giao diện. |
| Kiến trúc dữ liệu & quản lý phiên bản | SQLite gồm 93 bảng; tách biệt Desired State và Observed State; sao lưu Git bằng Dulwich. | Hai cơ sở dữ liệu vận hành ổn định; lưu lịch sử commit; hỗ trợ so sánh Unified Diff. |
| Tự động hóa cấu hình Lớp 2 & Lớp 3 | Quy trình Staged Save → Jinja2 Rendering → Preview → Push cho các nghiệp vụ định tuyến, chuyển mạch và bảo mật. | Hoàn thành 100% trên 4 kịch bản EVE-NG; thiết bị nhận cấu hình và được xác minh qua terminal nhúng. |
| Hệ sinh thái tiện ích mở rộng | Syslog Server thời gian thực; SFTP hai khung nhìn; terminal Alacritty giao tiếp IPC (NTTP/1). | Lọc nhật ký theo Severity; truyền tệp nền an toàn; mở phiên CLI độc lập, không xung đột. |
| Đóng gói & an toàn hệ thống | Tệp Workspace .ntp; kiểm tra SHA-256; mã hóa Argon2id + AES-256-GCM; Host Lock. | Dữ liệu dự án được bảo vệ khi lưu trữ và chia sẻ. |

*Bảng: Tổng hợp kết quả đạt được đối chiếu với mục tiêu nghiên cứu*

## 6.2. Ý nghĩa khoa học và thực tiễn

### 6.2.1. Ý nghĩa khoa học

Đề tài đóng góp một mô hình kiến trúc tham chiếu về việc ứng dụng kỹ thuật phần mềm hiện đại vào lĩnh vực tự động hóa mạng máy tính, đồng thời minh chứng tính khả thi của mô hình quản lý cấu hình theo trạng thái so với mô hình quản trị dòng lệnh phân tán truyền thống. Đề tài còn cung cấp giải pháp xử lý đồng thời an toàn dựa trên nguyên tắc "tuần tự hóa trên cùng thiết bị (Host Lock), xử lý song song giữa các thiết bị bằng Batch Executor", loại trừ hiện tượng tranh chấp luồng lệnh (Race Condition) trong quản trị mạng.

### 6.2.2. Ý nghĩa thực tiễn

CAMS là công cụ hỗ trợ sinh viên ngành Công nghệ Kỹ thuật Viễn thông và Công nghệ Thông tin tại Học viện thực hành các môn Mạng máy tính, Định tuyến và Chuyển mạch, giúp tiếp cận sớm với tư duy Tự động hóa mạng và IaC. Kết quả đo đạc thực nghiệm cho thấy hệ thống giúp rút ngắn trên 90% thời gian thiết lập hạ tầng mạng phòng lab và giảm thiểu sai sót cú pháp so với cấu hình thủ công qua CLI. Tính năng sao lưu Git tự động và đóng gói dự án .ntp giúp giảng viên, quản trị viên dễ dàng lưu trữ, phục hồi và phân phối các kịch bản bài tập lab chuẩn hóa.

## 6.3. Hạn chế của đề tài

Bên cạnh các kết quả đạt được, nhóm tác giả ghi nhận một số hạn chế thực tế để định hướng hoàn thiện trong các phiên bản tiếp theo:

1. *Phạm vi hỗ trợ thiết bị:* hệ thống hiện chỉ tối ưu cho Cisco IOS trên các dòng Router và Switch phổ biến trong phòng lab; chưa có adapter giao tiếp cho các nhà sản xuất khác.
2. *Bảo mật thông tin xác thực:* mật khẩu đăng nhập thiết bị và khóa bí mật vẫn được lưu trực tiếp trong cơ sở dữ liệu SQLite cục bộ; chưa tích hợp Secret Vault hay chuẩn mã hóa phần cứng TPM/HSM.
3. *Phụ thuộc bộ phân tích cú pháp CLI:* một số tính năng thu thập trạng thái (Collector) vẫn dựa trên bóc tách chuỗi văn bản thô từ lệnh show, có thể bị ảnh hưởng nếu phiên bản Cisco IOS thay đổi định dạng hiển thị kết quả.
4. *Cơ chế Rollback tự động hoàn toàn:* hệ thống cung cấp cơ chế hoàn tác mức dự án (Project Snapshot Rollback) và sao lưu Git, nhưng chưa tích hợp engine tự động sinh và gửi các chuỗi lệnh hoàn tác (no ...) xuống thiết bị khi gặp sự cố thực thi một phần (Partial Failure).

## 6.4. Lộ trình phát triển ưu tiên

Nhằm mở rộng tính năng và nâng cao độ tin cậy của CAMS, nhóm nghiên cứu đề xuất lộ trình phát triển theo 7 giai đoạn ưu tiên:

1. *Nâng cấp bảo mật Secret:* tích hợp Secret Vault hoặc cơ chế mã hóa mật khẩu qua OS Keyring (Windows DPAPI, Linux Secret Service/Keyutils), bảo đảm không còn mật khẩu dạng bản rõ trong cơ sở dữ liệu.
2. *Xây dựng engine Rollback thông minh:* phát triển bộ điều khiển tự động tạo tập lệnh hoàn tác ngược (Reverse Command Generator) tương ứng với từng tác vụ Push, cho phép tự động khôi phục trạng thái thiết bị về điểm an toàn gần nhất khi phát sinh lỗi.
3. *Tự động khám phá Topology mạng:* ứng dụng CDP/LLDP để tự động quét, vẽ sơ đồ topo mạng và tính toán các tuyến đường định tuyến tĩnh tối ưu.
4. *Mở rộng giao thức định tuyến nâng cao:* bổ sung giao diện và mẫu Jinja2 cho BGP và VRF phục vụ các kịch bản mạng ISP/Enterprise Core.
5. *Hỗ trợ thiết bị đa nhà sản xuất:* xây dựng kiến trúc Driver/Plugin trừu tượng hóa, hỗ trợ MikroTik RouterOS, VyOS, Juniper và thiết bị Linux Router.
6. *Mở rộng giao thức quản trị hiện đại:* tích hợp NETCONF/RESTCONF dựa trên mô hình dữ liệu YANG (IETF/OpenConfig).
7. *Tích hợp phân tích thông minh và cảnh báo:* phát triển công cụ phân tích lưu lượng dựa trên Syslog, tự động phát hiện bất thường an ninh mạng và gửi cảnh báo qua Webhook/Email.

## 6.5. Tổng kết

Đề tài "Nghiên cứu và xây dựng hệ thống quản lý tập trung, tự động hóa cấu hình và giám sát an ninh mạng" đã hoàn thành các mục tiêu đặt ra, tạo nên hệ thống CAMS ổn định, trực quan và hiệu quả. Sản phẩm mang ý nghĩa thực tiễn trong việc hỗ trợ công tác học tập, giảng dạy tại Học viện Công nghệ Bưu chính Viễn thông, đồng thời là tiền đề cho các nghiên cứu chuyên sâu tiếp theo trong lĩnh vực Tự động hóa mạng và quản trị hạ tầng thông minh.
