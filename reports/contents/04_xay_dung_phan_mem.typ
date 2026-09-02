#pagebreak(weak: true)
#import "../config/tables.typ": report-table, table-code
#import "../config/commands.typ": report-note

= Xây dựng phần mềm

== Môi trường phát triển và tổ chức mã nguồn

=== Môi trường phát triển và các thư viện cốt lõi

Phần mềm CAMS được xây dựng trên nền tảng ngôn ngữ lập trình Python kết hợp với bộ framework giao diện Qt 6 (thông qua PyQt6). Toàn bộ quy trình quản lý phụ thuộc, môi trường ảo và thực thi công cụ được đồng bộ thông qua công cụ quản lý gói `uv`, giúp đảm bảo tính nhất quán tuyệt đối giữa các môi trường phát triển và thử nghiệm.

#report-table(
  columns: (28%, 22%, 50%),
  header: ([Công nghệ / Thư viện], [Phiên bản], [Vai trò chính trong hệ thống]),
  rows: (
    ([Python], [3.11+], [Ngôn ngữ lập trình cốt lõi xây dựng logic nghiệp vụ và điều phối]),
    ([PyQt6 & Qt Quick / QML], [6.10.x], [Xây dựng giao diện đồ họa khai báo và cầu nối Signal/Slot]),
    ([SQLite], [3.x (Embedded)], [Hệ quản trị cơ sở dữ liệu quan hệ nhúng cho Workspace]),
    ([Netmiko / Paramiko], [4.x / 3.x], [Giao tiếp SSH/Telnet, tương tác CLI và điều phối lệnh]),
    ([Dulwich], [0.22.x], [Quản lý lịch sử và phiên bản cấu hình theo chuẩn Git cục bộ]),
    ([Jinja2], [3.1.x], [Template engine kết xuất cấu hình CLI từ dữ liệu Desired State]),
    ([Argon2-cffi & Cryptography], [23.x / 42.x], [Mã hóa gói dự án .ntp bằng Argon2id và AES-256-GCM]),
    ([uv], [0.6.x], [Quản lý phụ thuộc, khóa phiên bản (uv.lock) và kích hoạt runtime]),
  ),
  caption: [Danh mục công nghệ và thư viện nền tảng sử dụng trong dự án],
) <tab-tech-stack>

=== Tổ chức cấu trúc mã nguồn ứng dụng

Toàn bộ mã nguồn ứng dụng desktop nằm tập trung trong thư mục `app/`, được tổ chức theo mô hình kiến trúc phân lớp hướng module (Feature-driven / Clean Architecture). Cách phân chia này đảm bảo sự phân tách trách nhiệm (Separation of Concerns) và tuân thủ nghiêm ngặt quy tắc phụ thuộc một chiều (Dependency Rule): tầng giao diện chỉ gọi các facade của tầng core, tầng core điều phối các feature service, và feature service tương tác với tầng infrastructure (cơ sở dữ liệu, mạng, file system).

```text
app/
├── UI/                          # Lớp Giao diện (Qt Quick / QML)
│   ├── components/              # Các thành phần UI dùng chung (Base, Layout, Standard)
│   ├── qml/                     # Các màn hình chức năng chính (App, Content, Features)
│   └── resources/               # Tài nguyên biểu tượng SVG, phông chữ, bảng màu theme
├── core/                        # Lớp Cầu nối & Điều phối Facade
│   ├── database/                # DatabaseManager facade tổng hợp
│   ├── network_monitor.py       # Giám sát giao diện mạng và tài nguyên máy trạm
│   ├── terminal_helper.py       # Điều phối phiên CLI và Alacritty companion
│   └── settings/                # Quản lý cài đặt giao diện, cửa sổ và thanh trạng thái
├── features/                    # Lớp Nghiệp vụ theo từng tính năng độc lập
│   ├── acl/                     # Quản lý và sinh lệnh ACL (Standard, Extended, Reflexive)
│   ├── config_backup/           # Dịch vụ sao lưu lịch sử cấu hình bằng Git (Dulwich)
│   ├── config_sync/             # Dịch vụ bóc tách cấu hình và đồng bộ vào cơ sở dữ liệu
│   ├── devices/                 # Quản lý danh mục thiết bị (Inventory) và kết nối
│   ├── dhcp/                    # Quản lý Pool, Excluded IP, Helper và đồng bộ DHCP
│   ├── interfaces/              # Quản lý Interface L3, Subinterface, Tunnel, WAN
│   ├── nat/                     # Quản lý Static NAT, Dynamic NAT, PAT, NAT ACL, Route-map
│   ├── routing/                 # Quản lý Static Route, OSPFv2, EIGRP, Routing Group
│   ├── sftp/                    # Máy khách truyền tệp bảo mật hai khung nhìn (Dual-pane)
│   ├── switching/               # Quản lý VLAN, Trunking, EtherChannel, STP, VTP, L2 Security
│   ├── syslog/                  # Máy chủ thu nhận và phân tích nhật ký Syslog UDP/TCP
│   └── terminal/                # Trình điều khiển kết nối Terminal Alacritty qua IPC
├── infrastructure/              # Lớp Hạ tầng kỹ thuật và Adapter
│   ├── database/                # Lược đồ SQLite (schemas/), bộ nạp đường dẫn và migration
│   ├── network/                 # Quản lý phiên (Session Registry), Host Lock, Batch Executor
│   └── workspace/               # Đóng gói dự án (.ntp), quản lý Snapshot và cơ chế mã hóa
├── scripts/                     # Kịch bản khởi tạo cơ sở dữ liệu và kiểm tra cấu trúc
├── tests/                       # Bộ kiểm thử tự động (Unit, Integration, Contract, Smoke)
└── main.py                      # Điểm khởi chạy trung tâm (Composition Root)
```

== Khởi tạo ứng dụng và QML Bridge

=== Điểm khởi chạy trung tâm (Composition Root)

Tệp `app/main.py` đóng vai trò là Composition Root duy nhất của toàn bộ ứng dụng desktop. Khi được kích hoạt, tiến trình khởi tạo diễn ra theo một chuỗi kiểm soát chặt chẽ:

+ *Cấu hình môi trường nền tảng:* Thiết lập các biến môi trường cho thư viện Qt, tắt các cảnh báo không cần thiết trên Wayland (`qt.qpa.wayland.textinput`), và nạp động các tệp nhị phân DLL/SO của PyQt6. Đặc biệt, hệ thống tích hợp cơ chế nạp bù (shim) `Qt6LabsPlatform` để đảm bảo ứng dụng chạy đồng nhất trên cả Windows và Linux.
+ *Khởi tạo Engine và Đăng ký QML Module:* Khởi tạo đối tượng `QApplication` và `QQmlApplicationEngine`, đăng ký đường dẫn chứa module QML `UI` để hỗ trợ cơ chế nạp thành phần theo không gian tên khai báo.
+ *Khởi tạo các dịch vụ nền tảng:* Khởi tạo bộ quản lý phiên thiết bị (`DeviceSessionRegistry`), giám sát mạng máy trạm (`NetworkMonitor`), và các dịch vụ quản lý dự án.
+ *Nạp giao diện khởi động (Welcome Window):* Nạp màn hình `UI/Welcome.qml` để người dùng tạo mới hoặc mở một gói dự án (`.ntp`). Khi một dự án được kích hoạt, ứng dụng định tuyến lại toàn bộ đường dẫn cơ sở dữ liệu vào workspace tạm rồi mới tiến hành nạp giao diện làm việc chính (`UI/Main.qml`).

=== Cơ chế kết nối QML Bridge và Context Properties

Để duy trì kiến trúc tách biệt giữa giao diện đồ họa và logic xử lý Python, CAMS áp dụng cơ chế nạp thuộc tính ngữ cảnh (`setContextProperty`). Thông qua cơ chế này, QML có thể gọi trực tiếp các phương thức Python (thông qua `@pyqtSlot`) và lắng nghe các thay đổi dữ liệu từ backend thông qua tín hiệu (`pyqtSignal`):

#report-table(
  columns: (23%, 25%, 52%),
  text-size: 9.5pt,
  cell-inset: (x: 4pt, y: 4.5pt),
  header: ([Context Property], [Lớp Python sở hữu], [Trách nhiệm phục vụ trên giao diện]),
  rows: (
    ([#table-code("dbManager")], [#table-code("DatabaseManager")], [Cung cấp các API CRUD dữ liệu cấu hình, kích hoạt View & Push]),
    ([#table-code("cli")], [#table-code("TerminalHelper")], [Điều khiển kết nối CLI, gửi lệnh đồng bộ, lưu cấu hình running-config]),
    ([#table-code("welcomeController")], [#table-code("WelcomeController")], [Quản lý tạo mới, mở, đóng và danh sách dự án gần đây]),
    ([#table-code("workspaceSaveController")], [#table-code("WorkspaceSaveController")], [Thực hiện lưu, đóng gói .ntp, tạo snapshot và phục hồi dự án]),
    ([#table-code("networkMonitor")], [#table-code("NetworkMonitor")], [Cung cấp thông số IP, card mạng, mức sử dụng CPU/RAM của máy trạm]),
    ([#table-code("syslogManager")], [#table-code("SyslogManager")], [Điều khiển máy chủ Syslog, lọc bản tin và cấu hình logging thiết bị]),
    ([#table-code("sftpController")], [#table-code("SftpController")], [Quản lý phiên kết nối, duyệt cây thư mục và hàng đợi tải tệp]),
    ([#table-code("externalTools")], [#table-code("ExternalToolsManager")], [Quản lý danh mục và kích hoạt các công cụ bên ngoài (PuTTY, Wireshark...)]),
    ([#table-code("themeSettings")], [#table-code("ThemeSettings")], [Quản lý chế độ sáng/tối (Dark/Light) và màu sắc chủ đạo (Accent Color)]),
  ),
  caption: [Các đối tượng Context Property cốt lõi được nạp vào QML Engine],
) <tab-context-properties>

== Quản lý thiết bị, kết nối và đồng bộ trạng thái

=== Quản lý danh mục thiết bị (Inventory)

Phân hệ thiết bị cung cấp khả năng quản lý danh sách tập trung các router và switch trong phòng lab. Thông tin của mỗi thiết bị được lưu trữ trong bảng `t01_devices`, bao gồm: định danh (`device_id`), địa chỉ IP/Hostname (`host`), cổng dịch vụ (`port`), giao thức (`protocol`: SSH hoặc Telnet), tài khoản đăng nhập (`username`, `password`), mật khẩu đặc quyền (`secret_key`), hệ điều hành (`device_os`: Cisco IOS) và vai trò (`device_role`: `rou` cho Router, `sw2` cho Layer 2 Switch, `sw3` cho Multilayer Switch).

Để phục vụ triển khai nhanh trong các bài thực hành lớn, hệ thống hỗ trợ tính năng nhập hàng loạt (Batch Import) thông qua tệp định dạng JSON hoặc bảng tính Microsoft Excel (XLSX). Dữ liệu nhập vào được kiểm tra cấu trúc nghiêm ngặt trước khi ghi vào cơ sở dữ liệu.

=== Quản lý phiên kết nối và Cơ chế khóa theo Host (Host Lock)

Toàn bộ các phiên kết nối mạng được quản lý độc quyền bởi đối tượng `DeviceSessionRegistry` nằm tại lớp hạ tầng:

- *Duy trì phiên làm việc (Session Keep-alive):* Khi người dùng mở một tab thiết bị trên giao diện, phiên kết nối SSH/Telnet được khởi tạo và duy trì. Các tác vụ cấu hình tiếp theo sẽ tái sử dụng phiên này, giúp giảm thiểu tối đa độ trễ do phải xác thực nhiều lần.
- *Cơ chế khóa theo Host (Host Lock):* Mỗi thiết bị được gắn một đối tượng khóa tuần tự hóa (`operation_lock`). Khi một tiến trình (như lấy cấu hình running-config hoặc đẩy cấu hình OSPF) đang gửi lệnh qua kênh CLI, khóa này ngăn chặn tuyệt đối các tác vụ khác chen ngang, loại trừ hoàn toàn hiện tượng xung đột dữ liệu (Race Condition) trên luồng terminal.
- *Xử lý song song đa thiết bị (BatchExecutor):* Hệ thống cho phép thực hiện đồng thời các tác vụ trên nhiều thiết bị khác nhau (tối đa mặc định 5 thiết bị đồng thời), với cơ chế cô lập lỗi độc lập: sự cố mất kết nối trên một thiết bị không làm gián đoạn tiến trình đang chạy trên các thiết bị còn lại.

=== Sao lưu và kiểm soát phiên bản cấu hình bằng Git (Dulwich)

Mỗi khi người dùng thực hiện thao tác đồng bộ hoặc lấy cấu hình (`Get Running Config`), hệ thống sẽ kích hoạt phân hệ `config_backup`:

+ Cấu hình thô dạng văn bản được thu thập từ lệnh `show running-config`.
+ Phân hệ sử dụng thư viện Dulwich để khởi tạo và quản lý một kho Git cục bộ tại đường dẫn `backup/<host>/cfg`. Mỗi bản cấu hình mới được lưu lại dưới dạng một Commit Git độc lập kèm thời gian và mô tả.
+ Giao diện cung cấp bảng lịch sử phiên bản (tối đa 100 bản ghi gần nhất), cho phép kỹ sư xem lại nội dung tại bất kỳ thời điểm nào trong quá khứ hoặc thực hiện so sánh sai biệt cấu hình (Unified Diff) trực quan giữa hai phiên bản bất kỳ.

=== Trình duyệt cơ sở dữ liệu nhúng (Database Browser)

Nhằm phục vụ công tác kiểm tra, đối soát và gỡ lỗi dữ liệu trong quá trình nghiên cứu, ứng dụng tích hợp màn hình `DatabaseBrowserView`. Trình duyệt này cho phép người quản trị:
- Xem danh sách toàn bộ các bảng trong hai tệp cơ sở dữ liệu `device_network.db` và `info_collected.db`.
- Thực hiện lọc dữ liệu theo thiết bị (`host`), tìm kiếm bản ghi theo từ khóa và phân trang tự động.
- Kiểm tra trực tiếp các cờ trạng thái cấu hình (`success`, `sync_status`) để xác minh tính toàn vẹn của dữ liệu trước và sau khi thực hiện đẩy lệnh.

== Phân hệ Giao diện Router (Router Interfaces)

Phân hệ Giao diện Router chịu trách nhiệm định nghĩa và quản lý các tham số tầng vật lý và tầng mạng (L3) cho các cổng giao tiếp trên thiết bị định tuyến:

=== Các loại giao diện hỗ trợ

- *Giao diện vật lý (Physical L3 / WAN):* Quản lý các cổng Ethernet (FastEthernet, GigabitEthernet) và Serial. Hỗ trợ cấu hình địa chỉ IPv4, Subnet mask, địa chỉ phụ (Secondary IP), mô tả giao diện (Description), tốc độ truyền (Bandwidth) và trạng thái đóng/mở (`shutdown` / `no shutdown`).
- *Giao diện ảo Loopback:* Giao diện logic độc lập phục vụ định danh Router ID cho OSPF/BGP và kiểm thử khả năng kết nối.
- *Giao diện đường hầm (Tunnel):* Hỗ trợ cấu hình giao diện Tunnel đóng gói GRE hoặc IPsec, quản lý địa chỉ nguồn (`tunnel source`), địa chỉ đích (`tunnel destination`) và chế độ đường hầm (`tunnel mode`).
- *Giao diện con 802.1Q (Subinterface):* Hỗ trợ mô hình định tuyến liên VLAN (Router-on-a-Stick), cho phép cấu hình mã nhận diện VLAN (`encapsulation dot1Q <vlan_id>`) và gán địa chỉ IP tương ứng.

=== Ràng buộc toàn vẹn và Luồng cấu hình View & Push

Để ngăn chặn các sai sót phá hủy cấu hình phần cứng, phân hệ áp dụng các ràng buộc chặt chẽ:
- Các giao diện vật lý chỉ được phép chỉnh sửa các thông số cấu hình sau khi đã được đồng bộ từ thiết bị thực tế; hệ thống cấm thao tác tạo mới hoặc xóa bỏ cổng vật lý trên cơ sở dữ liệu.
- Người dùng chỉ được phép tạo mới hoặc xóa bỏ các giao diện logic (Loopback, Tunnel, Subinterface).
- Khi đẩy cấu hình (Push), hệ thống sử dụng mẫu Jinja2 để kết xuất tập lệnh IOS chuẩn xác. Đối với các giao diện WAN sử dụng giao thức PPP/HDLC có thiết lập mật khẩu xác thực (PAP/CHAP), giao diện xem trước (Preview) tự động che giấu chuỗi mật khẩu nhằm đảm bảo an toàn thông tin.

== Phân hệ Dịch vụ cấp phát IP động (DHCP)

Phân hệ DHCP cho phép người quản trị xây dựng và triển khai dịch vụ máy chủ cấp phát địa chỉ IP tự động cho toàn bộ các phân vùng mạng trong hệ thống.

=== Mô hình dữ liệu và tham số cấu hình

Phân hệ quản lý ba nhóm dữ liệu chính:
+ *DHCP Pools (`t03_dhcp_pool`):* Quản lý tên phân vùng (Pool Name), dải mạng cấp phát (Network/Subnet Mask), cổng mặc định (Default Router), máy chủ phân giải tên miền (DNS Server), tên miền nội bộ (Domain Name) và thời gian cho thuê địa chỉ (Lease Time).
+ *Dải địa chỉ loại trừ (`t03_dhcp_excluded_address`):* Định nghĩa dải địa chỉ IP tĩnh không được cấp phát tự động (dành cho Gateway, Server, Printer), bao gồm địa chỉ bắt đầu (`start_ip`) và địa chỉ kết thúc (`end_ip`).
+ *Địa chỉ chuyển tiếp DHCP Relay (`t03_router_iface_helper`):* Cấu hình lệnh `ip helper-address` trên các giao diện mạng để chuyển tiếp yêu cầu DHCP broadcast sang máy chủ DHCP tập trung khi client và server nằm khác miền broadcast.

=== Cơ chế lưu trữ theo trạng thái (Staged Save) và View & Push

Quy trình triển khai DHCP áp dụng triệt để mô hình quản lý cấu hình theo trạng thái:
- Khi người dùng tạo mới hoặc cập nhật một Pool, bản ghi được lưu vào cơ sở dữ liệu với cờ `success = 0` (Pending Add/Update). Nếu người dùng chọn xóa một Pool, bản ghi được đánh dấu `success = -1` (Pending Delete).
- Hộp thoại *View & Push* thu thập toàn bộ các bản ghi đang ở trạng thái Pending, đưa qua engine Jinja2 để kết xuất thành tập lệnh CLI:

```text
! Mã lệnh sinh ra từ View & Push cho DHCP
ip dhcp excluded-address 192.168.10.1 192.168.10.10
!
ip dhcp pool POOL_LAN_IT
 network 192.168.10.0 255.255.255.0
 default-router 192.168.10.1
 dns-server 8.8.8.8 1.1.1.1
 domain-name lab.ptit.edu.vn
 lease 0 12 0
```

- Worker nền tiếp nhận tập lệnh, thực thi tuần tự qua phiên SSH, kiểm tra phản hồi từ thiết bị và cập nhật trạng thái bản ghi thành `success = 1` sau khi hoàn tất.
- Đồng thời, tiến trình thu thập (Collector) tự động đọc bảng cấp phát thực tế (`show ip dhcp binding`) và lưu vào bảng `t09_info_dhcp_binding` để người quản trị theo dõi trực tiếp trên giao diện.

== Phân hệ Định tuyến mạng (Routing)

Phân hệ Định tuyến hỗ trợ thiết lập cả hai giải pháp định tuyến tĩnh và định tuyến động phổ biến trên hạ tầng mạng doanh nghiệp và phòng lab:

=== Định tuyến tĩnh và Tuyến mặc định (Static & Default Route)

Hệ thống cho phép cấu hình bảng định tuyến tĩnh (`t04_static_routing`) với các trường thông tin: mạng đích (`prefix`), mặt nạ mạng (`mask`), địa chỉ chặng kế tiếp (`next_hop`) hoặc giao diện xuất gói (`exit_interface`), và chỉ số khoảng cách quản trị (Administrative Distance) phục vụ thiết lập đường truyền dự phòng (Floating Static Route). Đối với tuyến mặc định, hệ thống tự động gán tham số mạng đích về `0.0.0.0/0`.

=== Định tuyến động OSPFv2

Phân hệ OSPF được thiết kế hoàn chỉnh theo mô hình phân cấp của giao thức OSPFv2:
- *Quy trình OSPF (`t04_ospf_process`):* Quản lý Process ID, Router ID, và khoảng cách quản trị (Distance).
- *Vùng OSPF (`t04_ospf_area`):* Quản lý các loại Area (Standard, Stub, Totally Stubby, NSSA) và cấu hình tóm tắt tuyến (Area Range Summarization).
- *Mạng tham gia OSPF (`t04_ospf_network`):* Cấu hình các dải mạng quảng bá kèm Wildcard Mask và Area ID tương ứng.
- *Tham số Giao diện OSPF (`t04_ospf_interface`):* Cấu hình chi phí đường truyền (`ip ospf cost`), độ ưu tiên bầu cử DR/BDR (`ip ospf priority`), khoảng thời gian gửi gói tin chào hỏi (`hello-interval`, `dead-interval`), chế độ mạng (`network point-to-point`) và giao diện thụ động (`passive-interface`).
- *Tái phân phối tuyến (`t04_ospf_redistribute`):* Hỗ trợ tái phân phối tuyến từ Static, Connected hoặc EIGRP vào OSPF kèm chỉ số Metric và Metric Type.

=== Định tuyến động EIGRP

Phân hệ EIGRP hỗ trợ cấu hình giao thức định tuyến khoảng cách vector nâng cao của Cisco:
- *Quy trình EIGRP (`t04_eigrp_process`):* Quản lý số hiệu Autonomous System (AS Number), Router ID, và cơ chế tự động tóm tắt tuyến (`auto-summary` / `no auto-summary`).
- *Mạng quảng bá (`t04_eigrp_network`):* Khai báo các mạng nội bộ tham gia trao đổi bảng định tuyến.
- *Thiết lập nâng cao:* Quản lý Passive Interface, Tái phân phối tuyến (Redistribution kèm metric 5 thành phần: Bandwidth, Delay, Reliability, Load, MTU), Distribute List lọc tuyến và xác thực láng giềng qua Key Chain (MD5).

=== Tiện ích Routing Group và Tách biệt mẫu cấu hình

Đối với các hệ thống lab gồm nhiều router kết nối, CAMS cung cấp tính năng *Routing Group*. Tính năng này cho phép tự động quét danh sách các mạng đang kết nối trực tiếp (Connected Networks) trên các router được chọn, sau đó tự động nhân bản chính sách định tuyến và đẩy cấu hình hàng loạt theo cơ chế đa tiến trình, giúp tiết kiệm đáng kể thời gian thiết lập hạ tầng định tuyến ban đầu.

== Phân hệ Danh sách điều khiển truy cập (ACL)

Phân hệ ACL cung cấp công cụ trực quan để thiết lập các chính sách lọc gói tin và an ninh mạng từ Lớp 2 đến Lớp 4:

=== Phân loại các chủng loại ACL hỗ trợ

#report-table(
  columns: (25%, 35%, 40%),
  header: ([Chủng loại ACL], [Tiêu chuẩn nhận diện], [Đặc tính nghiệp vụ]),
  rows: (
    ([Standard ACL], [Số hiệu 1–99, 1300–1999 hoặc Named], [Lọc lưu lượng dựa trên địa chỉ IPv4 nguồn]),
    ([Extended ACL], [Số hiệu 100–199, 2000–2699 hoặc Named], [Lọc chi tiết theo Protocol (TCP/UDP/ICMP/IP), IP nguồn/đích, Cổng dịch vụ (Port) và cờ TCP established]),
    ([Dynamic ACL], [Lock-and-Key ACL], [Cấp quyền truy cập mạng tạm thời cho người dùng sau khi hoàn thành xác thực phiên Telnet/SSH]),
    ([Reflexive ACL], [Session-based Filtering], [Tự động theo dõi phiên kết nối khởi tạo từ bên trong (`reflect`) và mở cổng cho lưu lượng phản hồi (`evaluate`)]),
    ([MAC ACL], [Layer 2 Named ACL], [Lọc khung tin tại Lớp 2 dựa trên địa chỉ MAC nguồn và MAC đích]),
  ),
  caption: [Các loại danh sách kiểm soát truy cập (ACL) được hỗ trợ trong hệ thống],
) <tab-acl-types>

=== Bảo toàn thứ tự quy tắc (Sequence Number) và Gán giao diện

- *Bảo toàn thứ tự Sequence:* Do nguyên lý của ACL là đối chiếu gói tin tuần tự từ trên xuống dưới và kết thúc bằng luật ngầm định chặn tất cả (`implicit deny all`), phân hệ lưu trữ chính xác chỉ số thứ tự (`sequence_num`) trong bảng `t05_acl_rules`. Khi chỉnh sửa hoặc thêm quy tắc xen kẽ, hệ thống tự động tái đánh số và sinh lệnh CLI đúng vị trí mong muốn.
- *Gán giao diện (Interface Binding):* Bảng `t05_acl_interface_apply` cho phép liên kết một danh sách ACL với nhiều cổng giao tiếp khác nhau, chỉ định rõ hướng lọc gói tin (`in` cho chiều đi vào hoặc `out` cho chiều đi ra khỏi giao diện).

== Phân hệ Biên dịch địa chỉ mạng (NAT / PAT)

Phân hệ NAT/PAT giải quyết bài toán ánh xạ địa chỉ IP nội bộ (Private IP) sang địa chỉ công cộng (Public IP) phục vụ truy cập mạng diện rộng:

=== Các chế độ biên dịch địa chỉ

- *Static NAT (`t05_nat_static`):* Ánh xạ cố định 1-1 giữa một địa chỉ IP nội bộ (`inside local`) và một địa chỉ IP công cộng (`inside global`), thường dùng cho các máy chủ công khai (Web, Mail Server).
- *Dynamic NAT (`t05_nat_dynamic`):* Ánh xạ động nhiều địa chỉ nội bộ tới một tập hợp địa chỉ IP công cộng thông qua dải địa chỉ Pool (`t05_nat_pool`).
- *PAT / NAT Overload (`t05_nat_overload_interface`):* Cho phép toàn bộ mạng nội bộ dùng chung một địa chỉ IP duy nhất của cổng WAN ra ngoài Internet thông qua việc theo dõi và phân biệt chỉ số cổng (Port Multiplexing).
- *Phân định vai trò giao diện (`t05_nat_interface_role`):* Thiết lập cờ `ip nat inside` trên các cổng kết nối mạng LAN và `ip nat outside` trên cổng kết nối mạng WAN/ISP.
- *Chính sách nâng cao (NAT ACL & Route-map):* Kết hợp danh sách ACL hoặc cấu trúc Route-map để thiết lập chính sách biên dịch có điều kiện phức tạp (Policy-based NAT).

=== Giám sát bảng chuyển đổi địa chỉ (NAT Translations)

Sau khi đẩy cấu hình thành công, tiến trình giám sát tự động đọc dữ liệu từ thiết bị qua lệnh `show ip nat translations` và `show ip nat statistics`, bóc tách các trường thông tin (Giao thức, Inside Global/Local, Outside Global/Local) và cập nhật vào bảng `t11_info_nat_translations` để người dùng theo dõi trực tiếp các phiên chuyển đổi địa chỉ đang hoạt động trong thời gian thực.

== Phân hệ Chuyển mạch và Bảo mật Lớp 2 (Switching & Layer 2 Security)

Phân hệ Chuyển mạch cung cấp giải pháp toàn diện cho việc cấu hình và quản trị hạ tầng mạng cục bộ trên các thiết bị Switch Cisco (vIOS-L2):

=== Quản lý VLAN, Trunking và EtherChannel

- *VLAN Management (`t06_switch_vlan`):* Khởi tạo, chỉnh sửa tên và xóa các VLAN trong dải ID hợp lệ từ 1 đến 4094.
- *Cấu hình Switchport (`t06_switch_interface`):* Phân loại cổng truy cập (`mode access`) gán vào một VLAN cụ thể, hoặc cổng trung kế (`mode trunk`) sử dụng chuẩn đóng gói 802.1Q mang lưu lượng của nhiều VLAN.
- *Gom kênh EtherChannel (`t06_switch_etherchannel`):* Gom nhóm từ 2 đến 8 cổng vật lý thành một cổng logic (`Port-channel`) nhằm tăng cường băng thông và cung cấp dự phòng đường truyền. Hệ thống hỗ trợ cả hai giao thức chuẩn công nghiệp LACP (`active`/`passive`) và giao thức độc quyền Cisco PAgP (`desirable`/`auto`).

=== Spanning Tree (STP) và VLAN Trunking Protocol (VTP)

- *Spanning Tree Protocol (`t06_switch_stp`):* Cấu hình các chế độ chống vòng lặp Lớp 2: PVST+, Rapid-PVST (RSTP) và Multiple Spanning Tree (MST). Cho phép điều chỉnh độ ưu tiên Bridge Priority (0–61440) để xác định Root Bridge, kích hoạt tính năng PortFast trên cổng nối máy trạm và BPDU Guard ngăn chặn thiết bị lạ can thiệp vào cấu trúc cây Spanning Tree.
- *VLAN Trunking Protocol (`t09_vtp_domain`):* Thiết lập tên miền VTP Domain, phiên bản VTP (Version 1, 2, 3) và chế độ hoạt động (Server, Client, Transparent, Off). Nhằm tuân thủ tiêu chuẩn an toàn thông tin, hệ thống tuyệt đối không thu thập hoặc lưu trữ mật khẩu VTP quan sát từ thiết bị dưới dạng văn bản rõ.

=== Bảo mật Lớp 2 (Layer 2 Security)

- *Port Security (`t06_switch_port_security`):* Giới hạn số lượng địa chỉ MAC tối đa được phép kết nối vào một cổng, kích hoạt cơ chế tự động học địa chỉ MAC (`sticky MAC`), và chỉ định hành động xử lý khi phát hiện vi phạm bảo mật (`shutdown`, `restrict`, `protect`).
- *DHCP Snooping & Dynamic ARP Inspection (DAI):* Cấu hình phân loại cổng tin cậy (`Trusted`) và không tin cậy (`Untrusted`), kích hoạt kiểm tra luồng cấp phát IP và gói tin ARP trên từng VLAN cụ thể nhằm ngăn chặn triệt để các hình thức tấn công DHCP Spoofing và Man-in-the-Middle qua ARP Poisoning.
- *Giao diện định tuyến SVI (`t06_switch_svi`):* Khởi tạo giao diện ảo Lớp 3 (`interface Vlan <id>`) trên Switch Multilayer, thiết lập địa chỉ IP định tuyến liên VLAN và kích hoạt dịch vụ `ip routing`.

== Phân hệ Tiện ích hệ thống và Giám sát

Bên cạnh các nghiệp vụ cấu hình mạng cốt lõi, CAMS được trang bị hệ thống tiện ích mở rộng phục vụ công tác vận hành và giám sát chuyên nghiệp:

=== Máy chủ nhật ký hệ thống (System Logs / Syslog Server)

Phân hệ `features/syslog` hoạt động như một Syslog Server độc lập:
- *Thu nhận đa giao thức:* Khởi chạy một tiến trình lắng nghe (Listener Thread) trên socket UDP hoặc TCP (mặc định cổng 514), hỗ trợ bóc tách các bản tin nhật ký theo chuẩn RFC 3164 và RFC 5424.
- *Lưu trữ hàng loạt (Batch Writer):* Các bản tin đến được đưa vào hàng đợi (`Queue`) và ghi xuống bảng `t12_syslog_messages` theo từng lô (Batch Insert), giúp hạn chế tối đa hiện tượng nghẽn I/O trên cơ sở dữ liệu SQLite khi có bão log.
- *Giao diện lọc và Chính sách dọn dẹp:* Cung cấp bộ lọc theo địa chỉ IP nguồn, mức độ nghiêm trọng (Severity từ 0 - Emergency đến 7 - Debug), tìm kiếm chuỗi thông điệp và hỗ trợ cơ chế tự động xóa bản tin cũ theo ngưỡng thời gian (Retention Policy).
- *Tự động cấu hình thiết bị:* Hỗ trợ đẩy tập lệnh `logging host <server_ip>` trực tiếp xuống router/switch qua phiên SSH đang kết nối.

=== Máy khách truyền tệp an toàn (SFTP Client)

Phân hệ `features/sftp` tích hợp trình duyệt và truyền tệp bảo mật hai khung nhìn (Dual-pane SFTP Client):
- Kết nối tới máy chủ SSH/SFTP với cơ chế xác thực vân tay máy chủ (Host-key SHA-256 Fingerprint Confirmation).
- Cung cấp hàng đợi truyền tệp nền (Transfer Queue) cho phép tải lên/tải xuống tệp và thư mục bất đồng bộ kèm thanh tiến trình và nút hủy tác vụ an toàn.
- Bảo mật thông tin xác thực thông qua cơ chế mã hóa Windows DPAPI trên hệ điều hành Windows.

=== Trình dòng lệnh nhúng đồng hành (Terminal Companion)

Để phục vụ nhu cầu can thiệp dòng lệnh thủ công của kỹ sư, CAMS tích hợp phân hệ `cams-terminal` (dựa trên bản fork mã nguồn mở Alacritty):
- Ứng dụng desktop giao tiếp với cửa sổ Terminal thông qua socket IPC cục bộ bằng giao thức nội bộ NTTP/1 (CAMS Terminal Protocol Version 1).
- Thông tin đăng nhập không bị lộ qua tham số dòng lệnh (`argv`) hay biến môi trường. Đối với thiết bị Cisco IOS legacy, hệ thống sử dụng tiến trình con Paramiko PTY độc lập.
- Phiên Terminal tương tác được tách biệt hoàn toàn khỏi phiên tự động hóa Netmiko, bảo đảm không gây tranh chấp luồng lệnh.

=== Đóng gói dự án và Quản lý Workspace (.ntp)

Hệ thống cung cấp giải pháp lưu trữ toàn bộ không gian làm việc thành một gói tệp duy nhất với phần mở rộng `.ntp` (CAMS Package):
- *Cấu trúc gói nén:* Sử dụng định dạng nén Zip chuẩn hóa Version 1, chứa tệp kê khai `manifest.json`, mã băm kiểm tra toàn vẹn SHA-256, hai tệp cơ sở dữ liệu SQLite (`device_network.db`, `info_collected.db`) và thư mục sao lưu Git `backup/`.
- *Mã hóa bảo vệ:* Người dùng có thể tùy chọn mã hóa toàn bộ gói dự án bằng thuật toán sinh khóa Argon2id kết hợp với thuật toán mã hóa đối xứng AES-256-GCM.
- *Cơ chế Snapshot & Rollback:* Cho phép tạo các điểm khôi phục nhanh (Safety Snapshot) trong quá trình làm việc và hỗ trợ hoàn tác dữ liệu khi có sự cố.

== Minh bạch kỹ thuật và các thành phần chưa tích hợp

Nhằm đảm bảo tính trung thực và minh bạch trong báo cáo nghiên cứu khoa học, nhóm tác giả nêu rõ ranh giới giữa các chức năng đã hoàn thiện trong ứng dụng desktop và các thành phần mã nguồn thử nghiệm/kế thừa:

+ *Máy chủ API cũ (`api_server.py`) và thư mục gốc `backend/`:* Đây là các module nguyên mẫu ban đầu được xây dựng để thử nghiệm giao tiếp mạng độc lập. Thành phần này không được nạp trong tiến trình của ứng dụng desktop (`app/main.py`), chưa tích hợp cơ chế xác thực phân quyền chuẩn và không được tính vào kết quả sản phẩm desktop hiện tại.
+ *Các mẫu cấu hình chưa có giao diện hoàn chỉnh:* Các mẫu Jinja2 cho giao thức BGP, công nghệ VRF, và bộ định tuyến đa hãng (Multi-vendor: MikroTik, VyOS) hiện mới tồn tại ở tầng template hoặc schema dự phòng (`t07_*`), chưa được tích hợp luồng View & Push hoàn chỉnh trên giao diện.
+ *Module bắt gói tin Telnet thô:* Mã nguồn thử nghiệm lắng nghe thông tin xác thực Telnet trong thư mục backend cũ đã được chủ động loại bỏ khỏi ứng dụng chính nhằm loại trừ triệt để các rủi ro về an toàn thông tin và thu thập dữ liệu trái phép.

== Tổng kết chương

Chương 4 đã trình bày chi tiết quá trình xây dựng và hiện thực hóa phần mềm CAMS. Ứng dụng được tổ chức theo kiến trúc phân lớp hướng module rõ ràng, tận dụng sức mạnh của Python 3.11+, PyQt6/QML và hệ quản trị SQLite cục bộ. Các phân hệ nghiệp vụ cốt lõi từ quản lý thiết bị, cấu hình Lớp 3 (Interface, DHCP, Static Routing, OSPF, EIGRP), chính sách an ninh (ACL, NAT/PAT), chuyển mạch Lớp 2 (VLAN, EtherChannel, STP, VTP, L2 Security) cho đến các tiện ích vận hành (Syslog, SFTP, Terminal Alacritty, Workspace .ntp) đều được cài đặt bài bản, tuân thủ nguyên tắc an toàn dữ liệu và tối ưu trải nghiệm người dùng.

Nội dung của chương này là nền tảng thực nghiệm quan trọng để tiến hành các quy trình kiểm thử tự động, thử nghiệm kịch bản phòng lab và đánh giá hiệu năng được trình bày chi tiết trong Chương 5.
