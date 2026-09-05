#import "../config/commands.typ": front-heading, todo

#front-heading[LỜI CAM ĐOAN]

Chúng tôi xin cam đoan báo cáo nghiên cứu khoa học với đề tài *"Nghiên cứu và xây dựng hệ thống quản lý tập trung, tự động hóa cấu hình và giám sát an ninh mạng"*, với tên hệ thống *CAMS (Centralized Automation & Monitoring System)*, là công trình nghiên cứu do nhóm tác giả thực hiện dưới sự hướng dẫn khoa học của ThS. Phan Thanh Toản, Bộ môn Mạng Viễn thông, Học viện Công nghệ Bưu chính Viễn thông cơ sở tại TP. Hồ Chí Minh.

Kết quả trình bày trong báo cáo là trung thực, do nhóm tự thực hiện và chưa từng được công bố trong bất kỳ công trình nào khác. Các phần mã nguồn do nhóm tự xây dựng, các thư viện nguồn mở, tài liệu kỹ thuật và mã tham khảo sử dụng trong quá trình phát triển đều được phân biệt rõ ràng và trích dẫn đầy đủ theo đúng quy định.

*Phạm vi đóng góp của từng thành viên:*

#table(
  columns: (1.4fr, 0.9fr, 2.4fr),
  align: (center + horizon, center + horizon, left + horizon),
  stroke: 0.6pt + gray,
  inset: 8pt,
  table.header(
    table.cell(fill: rgb("#e8e8e8"))[*Thành viên*],
    table.cell(fill: rgb("#e8e8e8"))[*MSSV*],
    table.cell(fill: rgb("#e8e8e8"))[*Phạm vi đóng góp*],
  ),
  [
    Nguyễn Quốc Việt \
    #text(size: 9pt, style: "italic")[(Trưởng nhóm)]
  ],
  [N24DCVT113],
  [Kiến trúc dữ liệu, quản trị cơ sở dữ liệu SQLite, tích hợp backend – giao diện, mô-đun Syslog, phối hợp tích hợp SFTP, điều phối kỹ thuật và hợp nhất mã nguồn],

  [Nguyễn Phan Kiên],
  [N24DCVT046],
  [Nền tảng backend, API và logic nghiệp vụ cho Routing/DHCP/ACL/NAT/VLAN, mẫu cấu hình Jinja, đồng bộ Running Configuration, kiểm thử tích hợp],

  [Nguyễn Trần Đạt Phú],
  [N24DCVT072],
  [Thiết kế giao diện PyQt6/QML, trải nghiệm người dùng, biên soạn tài liệu, quản lý kho mã nguồn và tích hợp nhánh GitHub],
)

#pagebreak()
Nhóm tác giả xin chịu hoàn toàn trách nhiệm trước Học viện và Hội đồng đánh giá về tính trung thực và tính chính xác của nội dung báo cáo này.

#align(right)[
  TP. Hồ Chí Minh, ngày ... tháng ... năm 2026

  *Nhóm tác giả*

  _(Ký và ghi rõ họ tên)_
]
