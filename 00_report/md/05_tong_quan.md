# CHƯƠNG 1. TỔNG QUAN ĐỀ TÀI

## 1.1. Bối cảnh và lý do chọn đề tài

Trong bối cảnh hạ tầng mạng viễn thông và công nghệ thông tin ngày càng phát triển, việc quản trị, vận hành và duy trì tính ổn định của hệ thống mạng đòi hỏi độ chính xác và tính đồng bộ cao. Tuy nhiên, trong môi trường học tập, nghiên cứu và tại các phòng thực hành mạng hiện nay, việc cấu hình thiết bị định tuyến (Router) và chuyển mạch (Switch) chủ yếu vẫn được thực hiện thủ công thông qua CLI. Phương pháp truyền thống này bộc lộ nhiều hạn chế rõ rệt: khi triển khai các topo mạng lớn hoặc cấu hình đồng loạt nhiều thiết bị, kỹ sư phải nhập lại từng khối lệnh tương tự nhau, làm giảm hiệu suất làm việc; việc gõ lệnh thủ công dễ dẫn đến nhầm lẫn địa chỉ IP, sai lệch Subnet Mask hoặc cấu hình sai giao diện mạng, gây gián đoạn đường truyền và khó khăn trong quá trình gỡ lỗi. Bên cạnh đó, việc thiếu một hệ thống ghi nhận cấu hình tập trung khiến trạng thái thực tế trên các thiết bị dễ bị phân tán, mất đồng bộ so với thiết kế ban đầu — hiện tượng thường gọi là sai lệch cấu hình (Configuration Drift) — trong khi phần lớn các phiên cấu hình CLI chỉ tồn tại cục bộ trên bộ nhớ thiết bị, không có cơ chế lưu trữ lịch sử hay theo dõi phiên bản.

Song song đó, xu hướng Tự động hóa mạng (Network Automation) và Quản lý hạ tầng bằng mã (Infrastructure as Code) đang trở thành tiêu chuẩn vận hành hiện đại. Việc kết hợp ngôn ngữ lập trình Python với giao diện đồ họa trực quan không chỉ giúp chuẩn hóa quy trình, giảm thiểu sai sót do con người mà còn nâng cao tính sẵn sàng của hệ thống. Xuất phát từ nhu cầu thực tiễn đó, ĐỀ TÀI: NGHIÊN CỨU VÀ XÂY DỰNG HỆ THỐNG QUẢN LÝ TẬP TRUNG, TỰ ĐỘNG HÓA CẤU HÌNH VÀ GIÁM SÁT AN NINH MẠNG (viết tắt là CAMS) được lựa chọn nghiên cứu nhằm tạo ra một giải pháp toàn diện, phục vụ công tác giảng dạy, học tập và quản trị phòng lab mạng Cisco.

## 1.2. Bài toán nghiên cứu

Vấn đề cốt lõi mà đề tài giải quyết là xây dựng một quy trình khép kín nhằm chuyển đổi từ mô hình cấu hình thủ công, phân tán sang mô hình quản lý tập trung dựa trên dữ liệu (Data-driven Network Management). Quy trình này được tự động hóa theo các giai đoạn tuần tự sau:

1. *Quản lý danh mục (Inventory Management):* Khai báo định danh thiết bị, địa chỉ IP quản trị, giao thức kết nối (SSH/Telnet) và thông tin xác thực một cách tập trung.
1. *Thu thập và đồng bộ trạng thái cơ sở (Baseline Sync):* Thiết lập phiên giao tiếp an toàn, thu thập cấu hình đang chạy (running-config) từ thiết bị, bóc tách dữ liệu có cấu trúc và lưu vào cơ sở dữ liệu SQLite làm trạng thái cơ sở.
1. *Định nghĩa trạng thái mong muốn (Desired State):* Người quản trị thiết lập các thông số cấu hình mạng mới thông qua giao diện đồ họa. Dữ liệu này được kiểm tra tính hợp lệ (Validation) và lưu ở trạng thái chờ (Pending).
1. *Xem trước và thực thi (View & Push):* Sử dụng engine Jinja2 để kết xuất dữ liệu chờ thành các tập lệnh CLI chuẩn xác. Người quản trị được quyền kiểm duyệt (Preview) mã lệnh trước khi các tiến trình nền đẩy lệnh xuống thiết bị.
1. *Xác minh và cập nhật (Verify & Update):* Đánh giá phản hồi từ thiết bị; nếu tác vụ thực thi thành công, hệ thống tự động chuyển trạng thái bản ghi sang đồng bộ hoàn tất (Applied).

## 1.3. Mục tiêu đề tài

### 1.3.1. Mục tiêu tổng quát

Xây dựng hoàn thiện hệ thống CAMS phục vụ công tác quản lý tập trung và tự động hóa các tác vụ cấu hình trên thiết bị định tuyến và chuyển mạch Cisco IOS, đáp ứng đầy đủ các kịch bản triển khai mạng từ cơ bản đến nâng cao trong môi trường học tập và thực nghiệm phòng lab.

### 1.3.2. Mục tiêu cụ thể

Để đạt được mục tiêu tổng quát trên, đề tài xác định năm nhóm mục tiêu cụ thể sau: xây dựng giao diện đồ họa hiện đại, trực quan bằng Qt Quick/QML kết hợp cầu nối PyQt6, bảo đảm luồng giao diện chính luôn mượt mà và không bị nghẽn khi thực thi các tác vụ mạng nền; thiết kế cơ sở dữ liệu SQLite cục bộ phục vụ lưu trữ cấu hình mong muốn và dữ liệu giám sát, tích hợp thư viện Dulwich để quản lý lịch sử sao lưu cấu hình theo chuẩn Git; hoàn thiện luồng tự động hóa View & Push cho các phân hệ cốt lõi gồm định tuyến (Static Route, OSPF, EIGRP), dịch vụ IP (DHCP, NAT/PAT, FHRP) và chuyển mạch cùng an ninh Lớp 2 (VLAN, Trunking, EtherChannel, STP, VTP, Standard/Extended/Dynamic/Reflexive ACL, Port Security, DHCP Snooping, DAI); tích hợp các tiện ích vận hành và giám sát gồm máy chủ Syslog thu thập nhật ký thời gian thực, máy khách SFTP truyền tệp an toàn và một terminal nhúng phục vụ thao tác dòng lệnh trực tiếp; và cuối cùng bảo đảm an toàn hệ thống thông qua cơ chế khóa theo thiết bị (Host Lock) chống xung đột lệnh và đóng gói dự án an toàn với mã hóa Argon2id kết hợp AES-256-GCM.

## 1.4. Đối tượng và phạm vi nghiên cứu

Đối tượng nghiên cứu của đề tài là các thiết bị Router và Switch chạy hệ điều hành Cisco IOS, được thực nghiệm trên thiết bị ảo hóa Cisco vIOS L3 và vIOS L2 trong môi trường EVE-NG. Phạm vi nghiệp vụ bao phủ từ cấu hình chuyển mạch và an ninh Lớp 2 (VLAN, EtherChannel, STP, Port Security, DHCP Snooping, DAI) lên định tuyến và dịch vụ Lớp 3 (IPv4 Interface, Subinterface, Static Route, OSPFv2, EIGRP, DHCP Server/Relay, NAT/PAT, HSRP/GLBP), trên nền tảng công nghệ Python 3.11+, PyQt6/QML, SQLite, Jinja2, Netmiko/Paramiko và Dulwich.

Kết quả nghiên cứu hiện tại được tối ưu hóa cho môi trường lab và doanh nghiệp vừa/nhỏ; đề tài chưa bao gồm các kiến trúc cụm sẵn sàng cao phân tán (HA Cluster), phân quyền đa người dùng phức tạp (RBAC hoàn chỉnh) hay kho lưu trữ khóa bí mật chuyên dụng (Secret Vault). Về giao thức mạng, hệ thống tập trung vào thiết bị Cisco IOS, chưa mở rộng sang thiết bị đa hãng (Multi-vendor) hay giao thức định tuyến liên miền BGP; các nội dung này được định hướng phát triển ở các giai đoạn tiếp theo.

## 1.5. Phương pháp nghiên cứu

Để thực hiện đề tài, nhóm tác giả áp dụng kết hợp các phương pháp sau. Trước hết là phương pháp khảo sát và phân tích nghiệp vụ, khảo sát thực tế các bài thực hành mạng tại Học viện, phân tích cú pháp CLI, quy trình cấu hình và các lỗi thường gặp khi thao tác trên Cisco IOS. Tiếp theo, phương pháp thiết kế hướng module (Clean Architecture) được sử dụng để phân tách hệ thống thành bốn tầng rõ ràng — giao diện, cầu nối, dữ liệu và mạng — bảo đảm tính độc lập, dễ bảo trì và mở rộng. Phương pháp mô hình hóa dữ liệu quan hệ được áp dụng để chuẩn hóa lược đồ cơ sở dữ liệu SQLite thành các nhóm bảng quản lý trạng thái mong muốn (Desired State) và dữ liệu thu thập (Observed State). Phương pháp kiểm thử tự động được sử dụng để xây dựng bộ test suite đa tầng gồm Unit Test, Integration Test, Contract Test và Smoke Test cho giao diện. Cuối cùng, phương pháp thực nghiệm và đánh giá so sánh được triển khai bằng cách thiết lập các topo mạng thực tế trên môi trường mô phỏng EVE-NG để kiểm chứng tính đúng đắn của cấu hình sinh ra, đo đạc thời gian thực thi, tỷ lệ thành công và so sánh định lượng với phương pháp cấu hình thủ công qua CLI.

## 1.6. Đóng góp của đề tài và bố cục báo cáo

### 1.6.1. Đóng góp chính của đề tài

Đề tài đã xây dựng thành công hệ thống CAMS với giao diện đồ họa trực quan, hỗ trợ quy trình quản trị cấu hình mạng an toàn thông qua cơ chế View & Push và quản lý trạng thái (Desired State và Current State). Đề tài cũng hiện thực hóa cơ chế quản lý phiên kết nối thông minh với Host Lock và Batch Executor, cho phép xử lý đồng thời nhiều thiết bị nhưng vẫn bảo đảm tuần tự trên từng luồng CLI, đồng thời tích hợp kiểm soát phiên bản cấu hình thiết bị bằng Git thông qua thư viện Dulwich cục bộ, hỗ trợ xem lịch sử và so sánh sai lệch cấu hình trực quan. Sản phẩm cuối cùng là một bộ công cụ hoàn chỉnh phục vụ nghiên cứu và thực hành mạng, bao gồm quản lý thiết bị, cấu hình Lớp 2/Lớp 3, máy chủ Syslog, máy khách SFTP và một terminal nhúng.

### 1.6.2. Bố cục báo cáo

Nội dung báo cáo được tổ chức thành sáu chương chính. Chương 1 giới thiệu bối cảnh, lý do chọn đề tài, bài toán nghiên cứu, mục tiêu, đối tượng, phạm vi và phương pháp thực hiện. Chương 2 trình bày các kiến thức nền tảng về mạng máy tính, giao thức định tuyến, chuyển mạch, an ninh mạng, cơ sở dữ liệu SQLite, framework Qt Quick/PyQt6 và các thư viện tự động hóa. Chương 3 phân tích các ca sử dụng, yêu cầu chức năng/phi chức năng, kiến trúc phân lớp, luồng dữ liệu cốt lõi, lược đồ cơ sở dữ liệu và thiết kế giao diện. Chương 4 mô tả chi tiết quá trình hiện thực hóa các phân hệ chức năng từ mã nguồn của hệ thống. Chương 5 trình bày kết quả kiểm thử tự động, các kịch bản thực nghiệm trên lab EVE-NG, số liệu đo đạc hiệu năng và đánh giá ưu, nhược điểm của sản phẩm. Chương 6 tổng kết các kết quả đạt được, ý nghĩa thực tiễn, các hạn chế còn tồn tại và lộ trình phát triển trong tương lai. Phần Phụ lục và Tài liệu tham khảo cung cấp cây cấu trúc mã nguồn, bảng ánh xạ module toàn hệ thống và danh mục tài liệu tham khảo.
