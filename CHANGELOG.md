# Changelog

Mọi thay đổi đáng chú ý của CAMS được ghi lại trong tài liệu này.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
và dự án sử dụng [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Repository chưa có tag phát hành trước ngày 2026-07-20; vì vậy `0.1.0` được ghi
nhận là baseline phát triển đầu tiên, không phải tuyên bố sẵn sàng production.

## [Unreleased]

### Added

- Bổ sung bản đồ tài liệu `docs/README.md`, hướng dẫn SFTP chuyên sâu, README cho
  runtime data/templates và README phân định backend kế thừa.
- Bổ sung CAMS-side MVP cho CAMS Terminal fork Alacritty: session
  UUID, `QProcess` lifecycle, OpenSSH argv validation không chứa password,
  NTTP/1 JSON Lines user-local, duplicate focus, state/error QML và test fake/socket.
- Bổ sung kế hoạch triển khai liên repository và ADR cho ranh giới terminal ngoài
  process, QProcess + Unix socket, protocol versioned và credential isolation.
- Bổ sung Switch Sys Sync từ backend cập nhật: thu thập có giới hạn và parse
  VLAN, interface/trunk, EtherChannel, VTP status; preview xung đột và giữ
  desired-state chưa push. Không thu thập hoặc lưu VTP password.
- Bổ sung **Save configuration** trong menu thiết bị để lưu running-config thành
  startup-config qua session SSH/Telnet hiện hữu, chạy nền và fail-closed nếu
  driver/thiết bị không hỗ trợ.
- Bổ sung tài liệu chức năng app hiện hành và bảng đối chiếu backend–app.
- Bổ sung View & Push Router Interface Cisco IOS qua SSH/Telnet cho IPv4,
  secondary IP, L3 tuning, WAN và Tunnel; tách collector, command renderer,
  worker, state updater và controller thành các file độc lập.
- Bổ sung kết nối/đồng bộ nhiều host đồng thời với task state riêng theo host và
  action **Connect All Waiting** trong menu nhóm Devices.
- Bổ sung fake-connector regression test cho preview, push thành công, lỗi thiết
  bị, xóa interface và redaction mật khẩu PPP.
- Bổ sung quy trình đóng góp, quy tắc lập trình, roadmap theo milestone và quality gate.
- Bổ sung changelog được tuyển chọn từ lịch sử phát triển thay vì sao chép nguyên
  danh sách commit.
- Bổ sung nhận diện default application cho SSH/Telnet/SFTP, SQLite và terminal
  host trên Windows; hỗ trợ XDG default application và Suggested Apps trên Linux.
- Bổ sung SFTP Client vào Applications và Letos vào gợi ý DB Browser.

### Changed

- Đối chiếu lại toàn bộ tài liệu hạng nhất với source/schema ngày 2026-08-16;
  viết lại kiến trúc database/project, schema lifecycle, feature inventory,
  hướng dẫn sử dụng, Syslog, SFTP và code audit.
- Dọn các kế hoạch/progress đã hoàn tất và tài liệu schema backend trùng lặp;
  tài liệu Alacritty upstream được giữ nguyên theo provenance vendor.
- Giảm log khởi động không hữu ích: bỏ qua Cython build tùy chọn khi thiếu
  `Python.h`, giữ lỗi nghiêm ngặt cho lệnh `build`, và lọc riêng diagnostic
  text-input Wayland đã biết của Qt mà không ẩn các category Qt khác.
- Chuyển active CLI composition khỏi widget qtpyTerminal/Netmiko embedded sang
  companion `cams-terminal`; compatibility code cũ tạm giữ nhưng không
  còn được `TerminalHelper` khởi tạo.
- Router Interface dùng session registry của app thay cho inventory/output tạm từ
  backend cũ; chỉ commit pending state sau khi thiết bị chấp nhận lệnh.
- Core package chuyển các facade nặng sang lazy import để feature thuần và unit
  test không tải dependency runtime không liên quan.
- Loại bỏ các bề mặt, worker và schema dành riêng cho QoS, storm control, VRF và
  quản lý YANG model; database runtime cũ được giữ nguyên dữ liệu và app mới
  không còn đọc/ghi các bảng đã ngừng dùng.
- Gộp External Tools và Tool Catalog thành một mục Settings với Feature Bar;
  chuyển giao diện sang loại ứng dụng bên trái và lựa chọn app bên phải; tab
  Suggestion dùng cùng layout và phân nhóm In use/Installed/Not installed.
- Mỗi loại external tool chỉ có một app active; danh sách Terminal trên Windows
  chỉ còn terminal host, không tách PowerShell 7/Windows PowerShell. Category
  hiển thị trực tiếp ứng dụng đang dùng hoặc hỗ trợ tích hợp của CAMS;
  action disclosure/link dùng nút TextIcon.

## [0.1.0] - 2026-07-20

### Added

- Xây dựng ứng dụng desktop PyQt6/QML để quản lý inventory, trạng thái và phiên
  kết nối của router, switch trong môi trường nghiên cứu/lab.
- Bổ sung các nhóm chức năng Routing, DHCP, ACL, NAT, Interfaces, Switching,
  Syslog, SFTP, External Tools và Config Backup.
- Bổ sung luồng lưu cấu hình cục bộ, xem trước và đẩy cấu hình cho nhiều nhóm chức
  năng; hỗ trợ đồng bộ Running Configuration về cơ sở dữ liệu ở các mức khác nhau.
- Xây dựng schema SQLite dạng mô-đun cho dữ liệu cấu hình và dữ liệu thu thập;
  bổ sung builder kiểm tra integrity/foreign key trước khi thay database.
- Bổ sung lịch sử running-config theo thiết bị bằng Dulwich mà không phụ thuộc Git
  CLI ở runtime.
- Xây dựng Syslog listener UDP/TCP, parser, batch writer, truy vấn, retention và
  giao diện quản lý nguồn log.
- Xây dựng SFTP workspace với xác nhận host key, duyệt tệp, hàng đợi truyền,
  progress và cancel.
- Xây dựng hệ thống component QML, theme token, Activity Bar, Panel Side Bar,
  Notification Center, status bar và các biểu mẫu dùng chung.
- Bổ sung unit test, integration test, QML smoke/contract test và structural
  validator cho cây `app/`.
- Bổ sung mã nguồn báo cáo nghiên cứu bằng LaTeX và tài liệu kiến trúc, database,
  UI, hướng dẫn sử dụng, phím tắt và kiểm chứng mã nguồn.

### Changed

- Tái cấu trúc ứng dụng theo luồng phụ thuộc
  `QML → slot → service → repository/worker → infrastructure`.
- Chuyển mã theo chức năng vào `app/features/`; tách adapter database, network và
  system vào `app/infrastructure/`; thu hẹp `app/core/` về contract dùng chung.
- Chuẩn hóa tài nguyên giao diện theo nhóm semantic và giữ thông tin giấy phép của
  icon bên thứ ba.
- Tích hợp nền backend xử lý thiết bị, template Cisco, API, đồng bộ và push cấu
  hình vào cấu trúc repository hiện tại.
- Chuẩn hóa màn hình Routing, DHCP, ACL, NAT, Switching, Syslog và SFTP theo hệ
  component và theme chung.

### Fixed

- Khắc phục EVE-NG/PNETLab chạy trong VMware hoặc VirtualBox bị giữ ở trạng thái
  **Starting** khi web server đã sẵn sàng nhưng trang đăng nhập mới không còn
  HTML fingerprint cũ; IP guest do hypervisor xác nhận nay được probe như hint
  tin cậy, còn host lân cận vẫn phải khớp fingerprint.
- Khắc phục các lỗi database và đường dẫn tài nguyên phát sinh sau khi hợp nhất
  nhánh.
- Khắc phục vòng lặp Notification, lỗi block UI khi kết nối thiết bị và lỗi vòng
  đời QML backend/worker.
- Khắc phục lỗi NAT Route Map, đồng bộ DHCP, ACL/NAT và nhiều lỗi trong luồng push
  Routing, DHCP, NAT, VLAN.
- Khắc phục contract lưu OSPF/EIGRP để dùng bảng canonical và tránh bản ghi trùng.
- Khắc phục các sai lệch giao diện ở Routing, DHCP, ACL, Settings, Logs và status
  bar.

### Security

- Dev mode fail-closed và không được mở kết nối thật khi trạng thái mô phỏng chưa
  được xác minh.
- SFTP yêu cầu người dùng xác minh fingerprint máy chủ trước khi chấp nhận host
  key mới.
- Trường mật khẩu dùng component mask/reveal dùng chung; External Tools không cho
  đưa mật khẩu vào command-line argument.
- Bổ sung giới hạn, batching và retention cho log để tránh tăng dữ liệu không giới
  hạn.

### Known limitations

- API/backend, schema authority, migration database, quản lý secret, xác minh
  transport và một số luồng push/sync chưa đạt mức production.
- Routing, Devices, Interfaces và Switching còn ở trạng thái `partial`; mức kiểm
  chứng trên thiết bị thật chưa đồng đều giữa các feature.
- Các rủi ro và điều kiện hoàn thành được theo dõi trong [ROADMAP.md](ROADMAP.md).
