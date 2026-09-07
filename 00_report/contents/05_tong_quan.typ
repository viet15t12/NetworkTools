#pagebreak(weak: true)
= Tổng quan đề tài

== Bối cảnh và lý do chọn đề tài

Trong bối cảnh hạ tầng mạng viễn thông và công nghệ thông tin ngày càng phát triển, việc quản trị và duy trì tính ổn định của hệ thống mạng đòi hỏi độ chính xác và tính đồng bộ cao. Tuy nhiên, tại các phòng thực hành mạng hiện nay, việc cấu hình thiết bị định tuyến (Router) và chuyển mạch (Switch) chủ yếu vẫn được thực hiện thủ công qua CLI. Phương pháp này bộc lộ nhiều hạn chế: khi triển khai topo lớn hoặc cấu hình đồng loạt nhiều thiết bị, kỹ sư phải nhập lại nhiều khối lệnh tương tự nhau, làm giảm hiệu suất làm việc và dễ dẫn đến nhầm lẫn địa chỉ IP, sai Subnet Mask hoặc sai giao diện mạng, gây gián đoạn đường truyền và khó khăn khi gỡ lỗi. Bên cạnh đó, việc thiếu một hệ thống ghi nhận cấu hình tập trung khiến trạng thái thực tế trên thiết bị dễ phân tán, mất đồng bộ so với thiết kế ban đầu — hiện tượng gọi là sai lệch cấu hình — trong khi các phiên CLI thường chỉ tồn tại cục bộ trên thiết bị, không có cơ chế lưu trữ lịch sử hay theo dõi phiên bản.

Song song đó, xu hướng Tự động hóa mạng và Quản lý hạ tầng bằng mã (IaC) đang trở thành tiêu chuẩn vận hành hiện đại. Việc kết hợp Python với giao diện đồ họa trực quan giúp chuẩn hóa quy trình, giảm sai sót do con người và nâng cao tính sẵn sàng của hệ thống. Xuất phát từ nhu cầu đó, ĐỀ TÀI: NGHIÊN CỨU VÀ XÂY DỰNG HỆ THỐNG QUẢN LÝ TẬP TRUNG, TỰ ĐỘNG HÓA CẤU HÌNH VÀ GIÁM SÁT AN NINH MẠNG viết tắt là CAMS được lựa chọn nhằm tạo ra một giải pháp toàn diện, phục vụ công tác giảng dạy, học tập và quản trị phòng lab mạng Cisco.

== Bài toán nghiên cứu

Vấn đề cốt lõi mà đề tài giải quyết là xây dựng một quy trình khép kín để chuyển đổi từ mô hình cấu hình thủ công, phân tán sang mô hình quản lý tập trung dựa trên dữ liệu. Quy trình này được tự động hóa theo các giai đoạn tuần tự sau:

+ *Quản lý danh mục (Inventory Management):* khai báo định danh thiết bị, địa chỉ IP quản trị, giao thức kết nối và thông tin xác thực một cách tập trung.
+ *Thu thập và đồng bộ trạng thái cơ sở (Baseline Sync):* thiết lập phiên giao tiếp an toàn, thu thập running-config từ thiết bị, bóc tách dữ liệu có cấu trúc và lưu vào cơ sở dữ liệu SQLite làm trạng thái cơ sở.
+ *Định nghĩa trạng thái mong muốn (Desired State):* người quản trị thiết lập thông số cấu hình mới qua giao diện đồ họa; dữ liệu được kiểm tra tính hợp lệ (Validation) và lưu ở trạng thái chờ (Pending).
+ *Xem trước và thực thi (View & Push):* engine Jinja2 kết xuất dữ liệu chờ thành tập lệnh CLI; người quản trị kiểm duyệt (Preview) trước khi tiến trình nền đẩy lệnh xuống thiết bị.
+ *Xác minh và cập nhật (Verify & Update):* đánh giá phản hồi từ thiết bị; nếu thành công, hệ thống chuyển trạng thái bản ghi sang đồng bộ hoàn tất (Applied).

== Mục tiêu đề tài

=== Mục tiêu tổng quát

Xây dựng hoàn thiện hệ thống CAMS phục vụ quản lý tập trung và tự động hóa các tác vụ cấu hình trên thiết bị định tuyến, chuyển mạch Cisco IOS, đáp ứng các kịch bản triển khai mạng từ cơ bản đến nâng cao trong môi trường học tập và thực nghiệm phòng lab.

=== Mục tiêu cụ thể

Đề tài xác định năm nhóm mục tiêu cụ thể: xây dựng giao diện đồ họa trực quan bằng Qt Quick/QML kết hợp PyQt6, bảo đảm luồng giao diện chính không bị nghẽn khi thực thi tác vụ mạng nền; thiết kế cơ sở dữ liệu SQLite cục bộ lưu trữ cấu hình mong muốn và dữ liệu giám sát, tích hợp Dulwich để quản lý lịch sử sao lưu cấu hình theo chuẩn Git; hoàn thiện luồng View & Push cho các phân hệ cốt lõi gồm định tuyến, dịch vụ IP và chuyển mạch, an ninh Lớp 2; tích hợp các tiện ích vận hành và giám sát gồm Syslog Server, SFTP client và terminal nhúng; và bảo đảm an toàn hệ thống qua cơ chế khóa theo thiết bị (Host Lock) chống xung đột lệnh cùng mã hóa Argon2id kết hợp AES-256-GCM khi đóng gói dự án.

== Đối tượng và phạm vi nghiên cứu

Đối tượng nghiên cứu là các thiết bị Router và Switch chạy Cisco IOS, thực nghiệm trên thiết bị ảo hóa Cisco vIOS L3 và vIOS L2 trong môi trường EVE-NG. Phạm vi nghiệp vụ bao phủ từ chuyển mạch và an ninh Lớp 2 đến định tuyến và dịch vụ Lớp 3, trên nền tảng Python 3.11+, PyQt6/QML, SQLite, Jinja2, Netmiko/Paramiko và Dulwich.

Kết quả nghiên cứu hiện được tối ưu cho môi trường lab và doanh nghiệp vừa/nhỏ; đề tài chưa bao gồm kiến trúc cụm sẵn sàng cao phân tán (HA Cluster), phân quyền đa người dùng hoàn chỉnh (RBAC) hay kho lưu trữ khóa bí mật chuyên dụng (Secret Vault). Hệ thống tập trung vào thiết bị Cisco IOS, chưa mở rộng sang thiết bị đa hãng hay giao thức BGP; các nội dung này được định hướng phát triển ở giai đoạn tiếp theo.

== Phương pháp nghiên cứu

Nhóm tác giả kết hợp các phương pháp sau: khảo sát và phân tích nghiệp vụ thực tế các bài thực hành mạng tại Học viện, phân tích cú pháp CLI và các lỗi thường gặp trên Cisco IOS; thiết kế hướng module (Clean Architecture) để phân tách hệ thống thành bốn tầng — giao diện, cầu nối, dữ liệu và mạng — bảo đảm tính độc lập, dễ bảo trì; mô hình hóa dữ liệu quan hệ để chuẩn hóa lược đồ SQLite thành các nhóm bảng quản lý trạng thái mong muốn (Desired State) và dữ liệu thu thập (Observed State); kiểm thử tự động với bộ test suite đa tầng gồm Unit Test, Integration Test, Contract Test và Smoke Test; và thực nghiệm, đánh giá so sánh bằng cách thiết lập các topo mạng thực tế trên EVE-NG để kiểm chứng tính đúng đắn của cấu hình sinh ra, đo thời gian thực thi, tỷ lệ thành công và so sánh với phương pháp cấu hình thủ công qua CLI.

== Đóng góp của đề tài và bố cục báo cáo

=== Đóng góp chính của đề tài

Đề tài xây dựng thành công hệ thống CAMS với giao diện đồ họa trực quan, hỗ trợ quy trình quản trị cấu hình mạng an toàn thông qua cơ chế View & Push và quản lý trạng thái (Desired State và Current State). Đề tài cũng hiện thực hóa cơ chế quản lý phiên kết nối với Host Lock và Batch Executor, cho phép xử lý đồng thời nhiều thiết bị nhưng vẫn bảo đảm tuần tự trên từng luồng CLI, đồng thời tích hợp kiểm soát phiên bản cấu hình bằng Git thông qua Dulwich, hỗ trợ xem lịch sử và so sánh sai lệch cấu hình trực quan. Sản phẩm cuối cùng là một bộ công cụ phục vụ nghiên cứu và thực hành mạng, gồm quản lý thiết bị, cấu hình Lớp 2/Lớp 3, Syslog Server, SFTP client và terminal nhúng.

=== Bố cục báo cáo

Báo cáo được tổ chức thành sáu chương. Chương 1 giới thiệu bối cảnh, bài toán nghiên cứu, mục tiêu, đối tượng, phạm vi và phương pháp thực hiện. Chương 2 trình bày cơ sở lý thuyết về mạng máy tính, giao thức định tuyến, chuyển mạch, an ninh mạng, SQLite, Qt Quick/PyQt6 và các thư viện tự động hóa. Chương 3 phân tích ca sử dụng, yêu cầu chức năng/phi chức năng, kiến trúc phân lớp, luồng dữ liệu, lược đồ cơ sở dữ liệu và thiết kế giao diện. Chương 4 mô tả quá trình hiện thực hóa các phân hệ chức năng. Chương 5 trình bày kết quả kiểm thử tự động, kịch bản thực nghiệm trên lab EVE-NG và đánh giá ưu, nhược điểm. Chương 6 tổng kết kết quả đạt được, ý nghĩa thực tiễn, hạn chế và hướng phát triển. Phần Phụ lục và Tài liệu tham khảo cung cấp cấu trúc mã nguồn, bảng ánh xạ module và danh mục tài liệu tham khảo.
