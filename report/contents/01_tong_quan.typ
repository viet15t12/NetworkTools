#pagebreak(weak: true)
= Tổng quan đề tài

== Bối cảnh và lý do chọn đề tài

Trong bối cảnh hạ tầng mạng viễn thông và công nghệ thông tin ngày càng phát triển, việc quản trị, vận hành và duy trì tính ổn định của hệ thống đòi hỏi độ chính xác và tính đồng bộ cao. Tuy nhiên, trong môi trường học tập, nghiên cứu và tại các phòng thực hành (lab) mạng hiện nay, việc cấu hình thiết bị định tuyến (Router) và chuyển mạch (Switch) chủ yếu vẫn được thực hiện thủ công thông qua giao diện dòng lệnh (CLI - Command-Line Interface). Phương pháp truyền thống này bộc lộ nhiều hạn chế rõ rệt:

- *Thao tác lặp lại và tốn thời gian:* Khi triển khai các topo mạng lớn hoặc cấu hình đồng loạt nhiều thiết bị, kỹ sư phải nhập lại từng khối lệnh tương tự nhau, làm giảm hiệu suất làm việc.
- *Rủi ro sai sót cú pháp và logic:* Việc gõ lệnh thủ công dễ dẫn đến nhầm lẫn địa chỉ IP, sai lệch Subnet Mask, hoặc cấu hình sai giao diện mạng, gây gián đoạn đường truyền và khó khăn trong quá trình gỡ lỗi.
- *Hiện tượng sai lệch cấu hình (Configuration Drift):* Việc thiếu một hệ thống ghi nhận cấu hình tập trung khiến trạng thái thực tế trên các thiết bị dễ bị phân tán, mất đồng bộ so với thiết kế ban đầu.
- *Thiếu hụt cơ sở dữ liệu quản trị tập trung:* Hầu hết các phiên cấu hình CLI chỉ tồn tại cục bộ trên bộ nhớ thiết bị, không có cơ chế lưu trữ lịch sử, theo dõi phiên bản hay quản lý không gian làm việc đồng nhất.

Bên cạnh đó, xu hướng Tự động hóa mạng (Network Automation) và Quản lý hạ tầng bằng mã (Infrastructure as Code - IaC) đang trở thành tiêu chuẩn vận hành hiện đại trong kỷ nguyên số. Việc ứng dụng các ngôn ngữ lập trình mạnh mẽ như Python kết hợp với giao diện đồ họa trực quan không chỉ giúp chuẩn hóa quy trình, giảm thiểu sai sót do con người mà còn nâng cao tính sẵn sàng của hệ thống. Xuất phát từ nhu cầu thực tiễn đó, đề tài *"Nghiên cứu và xây dựng hệ thống quản lý tập trung, tự động hóa cấu hình và giám sát an ninh mạng"* (CAMS) được lựa chọn nghiên cứu nhằm tạo ra một giải pháp desktop toàn diện, phục vụ công tác giảng dạy, học tập và quản trị phòng lab mạng Cisco.

== Bài toán nghiên cứu

Vấn đề cốt lõi mà đề tài giải quyết là xây dựng một quy trình khép kín nhằm chuyển đổi từ mô hình cấu hình thủ công, phân tán sang mô hình quản lý tập trung dựa trên dữ liệu (Data-driven Network Management). Ứng dụng hướng đến việc tự động hóa toàn bộ luồng quy trình nghiệp vụ theo các giai đoạn tuần tự sau:

+ *Quản lý danh mục (Inventory Management):* Khai báo định danh thiết bị, địa chỉ IP quản trị, giao thức kết nối (SSH/Telnet) và thông tin xác thực một cách tập trung.
+ *Thu thập và đồng bộ trạng thái cơ sở (Baseline Sync):* Thiết lập phiên giao tiếp an toàn, thu thập cấu hình đang chạy (`running-config`) từ thiết bị, bóc tách dữ liệu có cấu trúc và lưu vào cơ sở dữ liệu SQLite làm trạng thái cơ sở.
+ *Định nghĩa trạng thái mong muốn (Desired State):* Người quản trị thiết lập các thông số cấu hình mạng mới thông qua giao diện đồ họa (GUI). Dữ liệu này được kiểm tra tính hợp lệ (Validation) và lưu ở trạng thái chờ (`Pending`).
+ *Xem trước và thực thi (View & Push):* Sử dụng engine Jinja2 để kết xuất dữ liệu chờ thành các tập lệnh CLI chuẩn xác. Người quản trị được quyền kiểm duyệt (Preview) mã lệnh trước khi các tiến trình nền (Worker) đẩy lệnh xuống thiết bị.
+ *Xác minh và cập nhật (Verify & Update):* Đánh giá phản hồi từ thiết bị; nếu tác vụ thực thi thành công, hệ thống tự động chuyển trạng thái bản ghi sang đồng bộ hoàn tất (`Applied`).

== Mục tiêu đề tài

=== Mục tiêu tổng quát

Xây dựng hoàn thiện một nền tảng phần mềm desktop (*CAMS*) phục vụ công tác quản lý tập trung và tự động hóa các tác vụ cấu hình trên thiết bị định tuyến (Router) và chuyển mạch (Switch) Cisco IOS, đáp ứng đầy đủ các kịch bản triển khai mạng từ cơ bản đến nâng cao trong môi trường học tập và thực nghiệm phòng lab.

=== Mục tiêu cụ thể

- *Về giao diện và trải nghiệm người dùng:* Xây dựng giao diện đồ họa hiện đại, trực quan bằng framework Qt Quick/QML kết hợp với cầu nối PyQt6, đảm bảo luồng giao diện chính luôn mượt mà và không bị nghẽn khi thực thi các tác vụ mạng nền.
- *Về kiến trúc dữ liệu và quản lý phiên bản:* Thiết kế cơ sở dữ liệu SQLite cục bộ phục vụ lưu trữ cấu hình mong muốn và dữ liệu giám sát; tích hợp thư viện Dulwich để quản lý lịch sử sao lưu cấu hình theo chuẩn Git.
- *Về logic nghiệp vụ mạng:* Hoàn thiện luồng tự động hóa View & Push cho các phân hệ cốt lõi: Định tuyến (Static Route, OSPF, EIGRP), Dịch vụ IP (DHCP, NAT/PAT, FHRP), Chuyển mạch (VLAN, Trunking, EtherChannel, STP, VTP) và An ninh Lớp 2/Lớp 3 (Standard/Extended/Dynamic/Reflexive ACL, Port Security, DHCP Snooping, DAI).
- *Về tiện ích vận hành và giám sát:* Tích hợp máy chủ Syslog Server thu thập nhật ký thời gian thực, máy khách SFTP truyền tệp an toàn và Terminal Companion nhúng phục vụ thao tác dòng lệnh trực tiếp.
- *Về an toàn hệ thống:* Xây dựng cơ chế Dev-mode cô lập kết nối thật, cơ chế khóa theo thiết bị (Host Lock) chống xung đột lệnh và đóng gói dự án an toàn với mã hóa Argon2id + AES-256-GCM.

== Đối tượng và phạm vi nghiên cứu

- *Đối tượng nghiên cứu:* Thiết bị Router và Switch chạy hệ điều hành Cisco IOS (thực nghiệm trên thiết bị ảo hóa Cisco vIOS L3 và vIOS L2 trong môi trường EVE-NG).
- *Phạm vi nghiệp vụ:* Bao phủ từ cấu hình chuyển mạch và an ninh Lớp 2 (VLAN, EtherChannel, STP, Port Security, DHCP Snooping, DAI) lên định tuyến và dịch vụ Lớp 3 (IPv4 Interface, Subinterface, Static Route, OSPFv2, EIGRP, DHCP Server/Relay, NAT/PAT, HSRP).
- *Nền tảng công nghệ:* Python 3.11+, PyQt6/QML, SQLite, Jinja2, Netmiko/Paramiko, Dulwich và Alacritty Terminal fork.
- *Giới hạn đề tài:* Kết quả nghiên cứu hiện tại được tối ưu hóa cho môi trường lab và doanh nghiệp vừa/nhỏ; chưa bao gồm các kiến trúc cụm sẵn sàng cao phân tán (HA Cluster), phân quyền đa người dùng phức tạp (RBAC hoàn chỉnh) hay kho lưu trữ khóa bí mật chuyên dụng (Secret Vault). Về giao thức mạng, hệ thống tập trung vào thiết bị Cisco IOS, chưa mở rộng sang thiết bị đa hãng (Multi-vendor) hay giao thức định tuyến liên miền BGP; các nội dung này được định hướng phát triển ở các giai đoạn tiếp theo.

== Phương pháp nghiên cứu

Để thực hiện đề tài, nhóm tác giả đã áp dụng kết hợp các phương pháp nghiên cứu khoa học và kỹ thuật phần mềm sau:

+ *Phương pháp khảo sát và phân tích nghiệp vụ:* Khảo sát thực tế các bài thực hành mạng tại Học viện; phân tích cấu trúc cú pháp dòng lệnh CLI, quy trình cấu hình và các lỗi thường gặp trong quá trình thao tác trên Cisco IOS.
+ *Phương pháp thiết kế hướng module (Clean Architecture):* Phân tách hệ thống thành 4 tầng rõ ràng (Giao diện QML, Cầu nối PyQt6, Dữ liệu SQLite và Thực thi mạng Netmiko), đảm bảo tính độc lập, dễ bảo trì và mở rộng.
+ *Phương pháp mô hình hóa dữ liệu quan hệ:* Chuẩn hóa lược đồ cơ sở dữ liệu SQLite thành các nhóm bảng quản lý trạng thái mong muốn (Desired State) và dữ liệu thu thập (Observed State).
+ *Phương pháp kiểm thử tự động (Automated Testing):* Xây dựng bộ test suite đa tầng gồm Unit Test (kiểm tra tính hợp lệ của dữ liệu), Contract Test (kiểm tra khớp nối giữa UI và Backend), Dev-mode Safety Test và QML Smoke Test.
+ *Phương pháp thực nghiệm và đánh giá so sánh:* Thiết lập các topo mạng thực tế trên môi trường mô phỏng EVE-NG để kiểm chứng tính đúng đắn của cấu hình sinh ra; đo đạc thời gian thực thi, tỷ lệ thành công và so sánh định lượng với phương pháp cấu hình thủ công qua CLI.

== Đóng góp của đề tài và Bố cục báo cáo

=== Đóng góp chính của đề tài

- Xây dựng thành công ứng dụng desktop *CAMS* với giao diện đồ họa trực quan, hỗ trợ quy trình quản trị cấu hình mạng an toàn thông qua cơ chế View & Push và quản lý trạng thái (Desired State vs. Current State).
- Hiện thực hóa cơ chế quản lý phiên kết nối thông minh với Host Lock và Batch Executor, cho phép xử lý đồng thời nhiều thiết bị nhưng đảm bảo tuần tự trên từng luồng CLI.
- Tích hợp kiểm soát phiên bản cấu hình thiết bị bằng Git thông qua thư viện Dulwich cục bộ, hỗ trợ xem lịch sử và so sánh sai lệch cấu hình trực quan.
- Cung cấp một bộ công cụ hoàn chỉnh phục vụ nghiên cứu và thực hành mạng, bao gồm quản lý thiết bị, cấu hình L2/L3, Syslog Server, SFTP Client và Terminal Alacritty nhúng.

=== Bố cục báo cáo

Nội dung báo cáo được tổ chức thành 6 chương chính như sau:
- *Chương 1: Tổng quan đề tài* — Giới thiệu bối cảnh, lý do chọn đề tài, bài toán nghiên cứu, mục tiêu, đối tượng, phạm vi và phương pháp thực hiện.
- *Chương 2: Cơ sở lý thuyết và công nghệ* — Trình bày các kiến thức nền tảng về mạng máy tính, giao thức định tuyến, chuyển mạch, an ninh mạng, cơ sở dữ liệu SQLite, framework Qt Quick/PyQt6 và các thư viện tự động hóa.
- *Chương 3: Phân tích và thiết kế hệ thống* — Phân tích các ca sử dụng, yêu cầu chức năng/phi chức năng, kiến trúc phân lớp, luồng dữ liệu cốt lõi, lược đồ cơ sở dữ liệu và thiết kế giao diện.
- *Chương 4: Xây dựng phần mềm* — Mô tả chi tiết quá trình hiện thực hóa các phân hệ chức năng từ mã nguồn trong ứng dụng desktop.
- *Chương 5: Thử nghiệm và đánh giá* — Trình bày kết quả kiểm thử tự động, 4 kịch bản thực nghiệm trên lab EVE-NG, số liệu đo đạc hiệu năng và đánh giá ưu/nhược điểm của sản phẩm.
- *Chương 6: Kết luận và hướng phát triển* — Tổng kết các kết quả đạt được, ý nghĩa thực tiễn, các hạn chế còn tồn tại và lộ trình phát triển trong tương lai.
- *Phụ lục và Tài liệu tham khảo* — Cung cấp cây cấu trúc mã nguồn, bảng ánh xạ module toàn hệ thống và danh mục tài liệu tham khảo.
