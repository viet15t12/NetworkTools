#import "../config/tables.typ": report-table
#import "../config/commands.typ": report-note

#pagebreak(weak: true)
= Kết luận và hướng phát triển

== Kết quả đạt được

Đề tài nghiên cứu khoa học *"Xây dựng phần mềm quản lý tập trung và tự động hóa cấu hình thiết bị mạng"* (NetworkTools) đã hoàn thành xuất sắc các mục tiêu nghiên cứu và kỹ thuật đề ra ban đầu. Nhóm tác giả đã thiết kế và hiện thực hóa thành công một giải pháp phần mềm desktop hoàn chỉnh, kết hợp hài hòa giữa công nghệ giao diện đồ họa hiện đại, cơ sở dữ liệu quan hệ cục bộ và các thư viện tự động hóa mạng chuyên sâu.

#report-table(
  columns: (22%, 38%, 40%),
  header: ([Mục tiêu đề tài], [Nội dung kỹ thuật đã hoàn thành], [Bằng chứng kiểm chứng thực nghiệm]),
  rows: (
    ([Kiến trúc phần mềm & Giao diện người dùng], [Xây dựng ứng dụng desktop theo kiến trúc phân lớp Clean Architecture; giao diện Qt Quick/QML mượt mà, hỗ trợ Lazy Loading, đa tab thiết bị, chia đôi khung làm việc và Theme Dark/Light.], [256 tệp QML, 504/523 test tự động đạt, luồng UI đạt 60 FPS, không bị nghẽn khi chạy SSH.]),
    ([Kiến trúc dữ liệu & Quản lý phiên bản], [Thiết kế lược đồ SQLite chuẩn hóa gồm 93 bảng; phân định rõ giữa cấu hình mong muốn (Desired State) và dữ liệu thu thập (Observed State); tích hợp sao lưu Git bằng Dulwich.], [Hai tệp `device_network.db` và `info_collected.db` vận hành ổn định; lưu trữ lịch sử commit và so sánh Unified Diff trực quan.]),
    ([Tự động hóa cấu hình Lớp 2 & Lớp 3], [Hoàn thiện luồng Staged Save \rightarrow Jinja2 Rendering \rightarrow Preview \rightarrow Push cho Interface, DHCP, Static Route, OSPFv2, EIGRP, ACL, NAT/PAT, VLAN, EtherChannel, STP, VTP và L2 Security.], [Thực nghiệm thành công 100% trên 4 kịch bản lab EVE-NG; thiết bị nhận lệnh và xác nhận qua Terminal nhúng.]),
    ([Hệ sinh thái tiện ích mở rộng], [Tích hợp máy chủ Syslog Server thời gian thực (UDP/TCP), máy khách SFTP truyền tệp an toàn hai khung nhìn, và Terminal Alacritty nhúng giao tiếp qua socket IPC (NTTP/1).], [Thu nhận và lọc nhật ký sự kiện theo Severity; tải tệp nền an toàn; mở phiên CLI độc lập không gây xung đột.]),
    ([Đóng gói & An toàn hệ thống], [Đóng gói toàn bộ Workspace thành tệp `.ntp` chuẩn Zip v1 có kiểm tra mã băm SHA-256; hỗ trợ mã hóa Argon2id + AES-256-GCM; cơ chế Dev-mode Fail-Closed và Host Lock.], [Kiểm thử an toàn Dev-mode khóa hoàn toàn kết nối thật; bảo vệ dữ liệu dự án khi lưu trữ và chia sẻ.]),
  ),
  caption: [Bảng tổng hợp kết quả đạt được đối chiếu với các mục tiêu nghiên cứu],
) <tab-project-results-summary>

== Ý nghĩa khoa học và thực tiễn

=== Ý nghĩa khoa học

- Đề tài đóng góp một mô hình kiến trúc tham chiếu hoàn chỉnh về việc ứng dụng kỹ thuật phần mềm hiện đại (Clean Architecture, Qt Quick/QML, Python Asynchronous Workers, SQLite Persistence) vào lĩnh vực tự động hóa mạng máy tính.
- Minh chứng tính khả thi và ưu việt của mô hình quản lý cấu hình theo trạng thái (Data-driven State Management) so với mô hình quản trị dòng lệnh phân tán truyền thống.
- Cung cấp giải pháp xử lý đồng thời an toàn dựa trên nguyên tắc *"Tuần tự hóa trên cùng thiết bị (Host Lock), Xử lý song song giữa các thiết bị (Parallel Batch Execution)"*, loại trừ hoàn toàn hiện tượng tranh chấp luồng lệnh (Race Condition) trong quản trị mạng.

=== Ý nghĩa thực tiễn

- *Ứng dụng trong đào tạo và nghiên cứu:* Phần mềm là công cụ đắc lực hỗ trợ sinh viên ngành Công nghệ Kỹ thuật Viễn thông và Công nghệ Thông tin tại Học viện thực hành các môn học Mạng máy tính, Định tuyến và Chuyển mạch; giúp sinh viên sớm tiếp cận với tư duy Tự động hóa mạng (Network Automation) và Quản lý hạ tầng bằng mã (IaC).
- *Tối ưu hóa thời gian và nâng cao độ tin cậy:* Kết quả đo đạc thực nghiệm chứng minh NetworkTools giúp rút ngắn trên 90% thời gian thiết lập hạ tầng mạng phòng lab và giảm thiểu tối đa các sai sót cú pháp hoặc nhầm lẫn tham số so với cấu hình thủ công qua CLI.
- *Quản lý tập trung và kiểm soát phiên bản:* Tính năng sao lưu Git tự động và đóng gói dự án `.ntp` giúp giảng viên và quản trị viên dễ dàng lưu trữ, phục hồi và phân phối các kịch bản bài tập lab chuẩn hóa.

== Hạn chế của đề tài

Bên cạnh những kết quả tích cực đã đạt được, nhóm tác giả thẳng thắn ghi nhận các hạn chế thực tế còn tồn tại để định hướng hoàn thiện trong các phiên bản tiếp theo:

+ *Phạm vi hỗ trợ thiết bị:* Hệ thống hiện tại mới chỉ tập trung tối ưu hóa cho hệ điều hành Cisco IOS trên các dòng Router và Switch phổ biến trong phòng lab; chưa xây dựng các adapter giao tiếp chuyên dụng cho các nhà sản xuất khác (như Juniper Junos, MikroTik RouterOS, Arista EOS).
+ *Bảo mật thông tin xác thực (Credential Management):* Mật khẩu đăng nhập thiết bị và khóa bí mật hiện vẫn được lưu trữ trực tiếp trong các bảng của cơ sở dữ liệu SQLite cục bộ; chưa tích hợp kho lưu trữ khóa bí mật chuyên dụng (Secret Vault) hoặc các chuẩn mã hóa phần cứng TPM/HSM.
+ *Phụ thuộc vào bộ phân tích cú pháp CLI (Text Parser):* Một số tính năng thu thập trạng thái (Collector) vẫn dựa trên việc bóc tách chuỗi văn bản thô từ lệnh `show`, do đó có thể bị ảnh hưởng nếu phiên bản Cisco IOS thay đổi định dạng hiển thị kết quả.
+ *Cơ chế Rollback tự động hoàn toàn:* Hệ thống hiện tại cung cấp cơ chế hoàn tác mức dự án (Project Snapshot Rollback) và sao lưu Git, nhưng chưa tích hợp bộ engine tự động sinh và gửi các chuỗi lệnh hoàn tác (`no ...`) xuống thiết bị mạng khi gặp sự cố thực thi một phần (Partial Failure).

== Lộ trình phát triển ưu tiên

Nhằm mở rộng tính năng và nâng cao độ tin cậy của phần mềm NetworkTools, nhóm nghiên cứu đề xuất lộ trình phát triển theo 7 giai đoạn ưu tiên sau:

+ *Giai đoạn 1 (Nâng cấp Bảo mật Secret):* Tích hợp kho quản lý khóa bí mật chuyên dụng (Secret Vault) hoặc tích hợp hoàn toàn cơ chế mã hóa mật khẩu qua OS Keyring (Windows DPAPI, Linux Secret Service / Keyutils), đảm bảo không còn mật khẩu dạng bản rõ trong cơ sở dữ liệu.
+ *Giai đoạn 2 (Xây dựng Engine Rollback thông minh):* Phát triển bộ điều khiển tự động tạo tập lệnh hoàn tác ngược (Reverse Command Generator) tương ứng với từng tác vụ Push, cho phép tự động khôi phục trạng thái thiết bị về điểm an toàn gần nhất khi phát sinh lỗi.
+ *Giai đoạn 3 (Tự động khám phá Topology mạng):* Ứng dụng các giao thức khám phá láng giềng (CDP - Cisco Discovery Protocol, LLDP - Link Layer Discovery Protocol) để tự động quét, vẽ sơ đồ topo mạng trực quan và tự động tính toán các tuyến đường định tuyến tĩnh tối ưu.
+ *Giai đoạn 4 (Mở rộng giao thức định tuyến nâng cao):* Bổ sung giao diện và bộ mẫu Jinja2 cho giao thức định tuyến liên miền BGP (Border Gateway Protocol) và công nghệ mạng riêng ảo VRF (Virtual Routing and Forwarding) phục vụ các kịch bản mạng nhà cung cấp dịch vụ (ISP / Enterprise Core).
+ *Giai đoạn 5 (Hỗ trợ thiết bị Đa nhà sản xuất - Multi-Vendor):* Xây dựng kiến trúc Driver / Plugin trừu tượng hóa, hỗ trợ cấu hình cho các thiết bị chạy MikroTik RouterOS, VyOS, Juniper và thiết bị Linux Router.
+ *Giai đoạn 6 (Mở rộng giao thức quản trị hiện đại):* Tích hợp sâu các giao thức quản trị hướng mô hình dữ liệu (Model-driven Programmability) như NETCONF / RESTCONF dựa trên các mô hình dữ liệu chuẩn hóa YANG (IETF / OpenConfig).
+ *Giai đoạn 7 (Tích hợp phân tích thông minh và Cảnh báo):* Phát triển bộ công cụ phân tích lưu lượng thông minh dựa trên Syslog và luồng gói tin, tự động phát hiện bất thường an ninh mạng (như bão broadcast, tấn công ARP Spoofing) và gửi thông báo cảnh báo tức thời qua Webhook / Email.

== Tổng kết

Đề tài nghiên cứu khoa học *"Xây dựng phần mềm quản lý tập trung và tự động hóa cấu hình thiết bị mạng"* đã hoàn thành toàn diện các mục tiêu đặt ra, tạo nên một công cụ desktop *NetworkTools* ổn định, trực quan và hiệu quả. Sản phẩm không chỉ mang ý nghĩa thực tiễn cao trong việc hỗ trợ công tác học tập, giảng dạy tại Học viện Công nghệ Bưu chính Viễn thông mà còn là tiền đề vững chắc cho các nghiên cứu chuyên sâu tiếp theo trong kỷ nguyên Tự động hóa mạng và Quản trị hạ tầng thông minh.
