#pagebreak(weak: true)
= Tổng quan đề tài

== Bối cảnh và lý do chọn đề tài
Trong bối cảnh công nghệ mạng máy tính ngày càng phát triển, việc quản trị và vận hành hạ tầng đòi hỏi sự chính xác và tính đồng bộ cao. Tuy nhiên, trong môi trường học tập và các phòng thực hành (lab) hiện nay, việc cấu hình thiết bị (Router, Switch) chủ yếu vẫn được thực hiện thủ công thông qua Giao diện dòng lệnh (CLI - Command Line Interface). Phương pháp truyền thống này bộc lộ nhiều hạn chế: tạo ra các thao tác lặp đi lặp lại nhàm chán, rủi ro sai sót cú pháp cao, khó khăn trong việc kiểm soát sự sai lệch cấu hình (Configuration Drift) và thiếu một cơ sở dữ liệu tập trung để lưu trữ trạng thái của toàn bộ hệ thống mạng.

Bên cạnh đó, xu hướng Tự động hóa mạng (Network Automation) và Quản lý hạ tầng bằng mã (Infrastructure as Code) đang trở thành tiêu chuẩn mới trong ngành công nghiệp. Việc áp dụng ngôn ngữ lập trình vào quản trị mạng không chỉ giúp tiết kiệm thời gian mà còn nâng cao độ tin cậy. Xuất phát từ nhu cầu thực tiễn đó, đề tài lựa chọn hướng nghiên cứu và xây dựng một công cụ phần mềm desktop nhằm hỗ trợ quy trình quản trị, tập trung hóa dữ liệu và tự động hóa các tác vụ cấu hình thiết bị mạng trong phạm vi phòng lab, qua đó giúp sinh viên làm quen với tư duy quản trị mạng hiện đại.

== Bài toán nghiên cứu
Vấn đề cốt lõi mà đề tài cần giải quyết là xây dựng một quy trình khép kín nhằm chuyển đổi từ mô hình cấu hình thủ công, phân tán sang mô hình quản lý tập trung dựa trên dữ liệu (Data-driven). #let flow-box(title, desc) = block(
  width: 100%,
  inset: (x: 12pt, y: 10pt),
  radius: 6pt,
  stroke: 0.6pt + luma(150),
  fill: luma(250),
  [
    #strong(title): #desc
  ]
)

Vấn đề cốt lõi mà đề tài cần giải quyết là xây dựng một quy trình khép kín nhằm chuyển đổi từ mô hình cấu hình thủ công, phân tán sang mô hình quản lý tập trung dựa trên dữ liệu (Data-driven). Ứng dụng hướng đến việc tự động hóa luồng quy trình nghiệp vụ được mô tả trực quan qua sơ đồ các bước sau:

#v(4pt)
#align(center)[
  #block(width: 90%)[
    #flow-box("Quản lý và Khởi tạo", "Khai báo định danh thiết bị, địa chỉ IP và thiết lập các thông số xác thực.")
    #v(2pt) #text(fill: luma(100), weight: "bold")[↓] #v(2pt)
    
    #flow-box("Thu thập trạng thái (Sync)", "Thiết lập phiên giao tiếp an toàn, bóc tách (parse) cấu hình đang chạy (Running Configuration) từ thiết bị vật lý để lưu trữ vào cơ sở dữ liệu làm trạng thái cơ sở (Baseline).")
    #v(2pt) #text(fill: luma(100), weight: "bold")[↓] #v(2pt)
    
    #flow-box("Định nghĩa cấu hình (Desired State)", "Người quản trị thiết lập các thông số nghiệp vụ mới thông qua giao diện đồ họa. Dữ liệu này được lưu trữ tạm thời với trạng thái chờ (Pending).")
    #v(2pt) #text(fill: luma(100), weight: "bold")[↓] #v(2pt)
    
    #flow-box("Xem trước và Thực thi (View & Push)", "Hệ thống sử dụng engine Jinja2 để kết xuất dữ liệu thành các tập lệnh CLI chuẩn xác. Người quản trị được phép kiểm duyệt (Preview) mã lệnh trước khi các luồng thực thi nền (Worker) đẩy lệnh xuống thiết bị.")
    #v(2pt) #text(fill: luma(100), weight: "bold")[↓] #v(2pt)
    
    #flow-box("Xác minh và Cập nhật", "Đánh giá phản hồi từ thiết bị; nếu không có lỗi phát sinh, hệ thống tự động cập nhật trạng thái đồng bộ vào cơ sở dữ liệu tập trung.")
  ]
]
#v(4pt)

Cụ thể, hệ thống phải đảm bảo khả năng duy trì kết nối an toàn với thiết bị, thu thập và bóc tách dữ liệu cấu hình đang chạy (Current State) về cơ sở dữ liệu, đồng thời cung cấp một giao diện trực quan để người quản trị thao tác trước khi đẩy hàng loạt lệnh xuống thiết bị vật lý.

Cụ thể, hệ thống phải đảm bảo khả năng duy trì kết nối an toàn với thiết bị, thu thập và bóc tách dữ liệu cấu hình đang chạy (Current State) về cơ sở dữ liệu, đồng thời cung cấp một giao diện trực quan để người quản trị thao tác trước khi đẩy hàng loạt lệnh xuống thiết bị vật lý.

== Mục tiêu
=== Mục tiêu tổng quát
Xây dựng hoàn thiện một nền tảng phần mềm desktop (CAMS) phục vụ công tác quản lý tập trung và tự động hóa các tác vụ cấu hình trên thiết bị định tuyến Cisco IOS, ứng dụng trực tiếp vào quá trình học tập và thực nghiệm thực tế tại phòng lab.

=== Mục tiêu cụ thể
- *Về giao diện và trải nghiệm:* Xây dựng giao diện đồ họa trực quan bằng framework Qt Quick/QML kết hợp với cầu nối PyQt6, đảm bảo không gây nghẽn luồng xử lý chính khi chạy các tác vụ nền.
- *Về dữ liệu:* Thiết kế và vận hành cơ sở dữ liệu nội bộ SQLite để quản lý thông tin thiết bị, lưu trữ cấu hình mong muốn và đồng bộ trạng thái thực tế.
- *Về logic nghiệp vụ:* Xây dựng và hoàn thiện luồng tự động hóa View & Push cho các tính năng cốt lõi bao gồm: Cấp phát IP động (DHCP), Định tuyến (Static, OSPF, EIGRP) và Biên dịch địa chỉ mạng (NAT/PAT).
- *Về kỹ thuật nền tảng:* Cài đặt cấu trúc lưu trữ (persistence) cho Interface và ACL làm tiền đề mở rộng; thiết lập hệ thống kiểm thử tự động hóa (logic dữ liệu, UI contract, dev-mode) nhằm giảm thiểu rủi ro khi tương tác với thiết bị thật.

== Đối tượng và phạm vi
- *Đối tượng nghiên cứu:* Tập trung vào các bộ định tuyến (Router) chạy hệ điều hành Cisco IOS trong môi trường mô phỏng và vật lý. Các tính năng cấu hình nằm trong phạm vi gồm: Interface, DHCP, Routing (OSPF, EIGRP), ACL và NAT/PAT.
- *Nền tảng công nghệ:* Phần mềm được phát triển dựa trên ngôn ngữ Python (3.11+), giao diện PyQt6/QML, cơ sở dữ liệu SQLite, kết xuất mã bằng engine Jinja2 và tương tác thiết bị qua Netmiko/Nornir. Ứng dụng được tối ưu hóa cho hệ điều hành Windows và hướng đến khả năng hoạt động trên Linux.
- *Giới hạn đề tài:* Kết quả nghiên cứu hiện tại chưa bao gồm việc triển khai ở quy mô mạng doanh nghiệp lớn, chưa hỗ trợ dự phòng độ sẵn sàng cao (HA), phân quyền người dùng phức tạp (RBAC hoàn chỉnh), mã hóa bảo mật chuỗi (secret) cấp cao, cũng như chưa tích hợp toàn diện hệ thống chuyển mạch (Switching end-to-end), Firewall và Syslog.      