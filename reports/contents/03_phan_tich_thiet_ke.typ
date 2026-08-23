#pagebreak(weak: true)
#import "../config/tables.typ": report-table
#import "../config/commands.typ": report-note

= Phân tích và thiết kế hệ thống

== Tác nhân và ca sử dụng

Hệ thống được thiết kế tối ưu cho môi trường phòng thực hành (lab) và quản trị mạng vừa/nhỏ. Tác nhân chính (Primary Actor) tham gia tương tác trực tiếp với phần mềm là *Người quản trị mạng* (bao gồm giảng viên phụ trách lab, kỹ sư quản trị hoặc sinh viên thực hành). 

Các ca sử dụng cốt lõi (Use Cases) được mô hình hóa bao quát toàn bộ vòng đời quản trị và tự động hóa cấu hình:

/ UC-01 Quản lý danh mục thiết bị (Device Inventory): Khai báo, chỉnh sửa, xóa thông tin định danh, địa chỉ IP và tham số xác thực của Router/Switch; nhập hàng loạt danh sách thiết bị từ tệp JSON/Excel.
/ UC-02 Kiểm tra kết nối và Đồng bộ cơ sở (Ping & Baseline Sync): Kiểm tra khả năng kết nối mạng (Ping ICMP), mở phiên SSH/Telnet, thu thập cấu hình đang chạy (`running-config`) và phân tích (parse) lưu vào cơ sở dữ liệu SQLite làm trạng thái cơ sở.
/ UC-03 Định nghĩa cấu hình mong muốn (Define Desired State): Sử dụng các biểu mẫu đồ họa (Form GUI) để thiết lập thông số mạng cho từng phân hệ (Interface, DHCP, Routing, ACL, NAT, Switching); dữ liệu được kiểm tra tính hợp lệ và ghi vào cơ sở dữ liệu với trạng thái chờ xử lý (`Pending`).
/ UC-04 Xem trước cấu hình (Preview Configuration): Kích hoạt bộ tạo mẫu Jinja2 để kết xuất các bản ghi đang chờ thành tập lệnh CLI Cisco IOS hoàn chỉnh để người quản trị kiểm duyệt trực quan.
/ UC-05 Thực thi cấu hình (Push Configuration): Đẩy tập lệnh đã phê duyệt xuống thiết bị qua phiên kết nối hiện hành, thu thập phản hồi và cập nhật trạng thái đồng bộ thành công vào cơ sở dữ liệu.
/ UC-06 Quản lý lịch sử và phiên bản (Version Control & Backup): Tự động lưu vết các bản cấu hình `running-config` thành các commit Git thông qua Dulwich, hỗ trợ xem lại lịch sử và so sánh sai khác cấu hình (Unified Diff).
/ UC-07 Thao tác dòng lệnh tương tác (Terminal Companion): Mở phiên dòng lệnh nhúng Alacritty để can thiệp cấu hình thủ công khi cần thiết, tự động kích hoạt đồng bộ khi đóng phiên.
/ UC-08 Giám sát nhật ký và truyền tệp (Syslog & SFTP): Khởi chạy máy chủ Syslog lắng nghe bản tin sự kiện thời gian thực và sử dụng máy khách SFTP hai khung nhìn để truyền tệp an toàn tới thiết bị.

== Yêu cầu chức năng

Dựa trên các ca sử dụng, các yêu cầu chức năng (Functional Requirements - FR) được phân định rõ ràng thành nhóm tính năng cốt lõi và nhóm tiện ích mở rộng:

=== Nhóm tính năng cốt lõi

#report-table(
  columns: (15%, 35%, 50%),
  header: ([Mã YC], [Tên yêu cầu chức năng], [Mô tả chi tiết và tiêu chí nghiệm thu]),
  rows: (
    ([FR-01], [Quản lý danh mục thiết bị], [Thêm, sửa, xóa thiết bị; gán vai trò (`rou`, `sw2`, `sw3`); hỗ trợ nhập hàng loạt từ JSON/Excel; lưu trữ thông tin IP, port, credential.]),
    ([FR-02], [Kết nối và Thu thập trạng thái], [Ping kiểm tra kết nối; khởi tạo phiên SSH/Telnet; bóc tách `running-config` và lưu trữ trạng thái Baseline vào SQLite.]),
    ([FR-03], [Cấu hình Giao diện Router], [Quản lý thông số IPv4 cho cổng vật lý L3/WAN; tạo/xóa cổng ảo Loopback, Tunnel GRE và Subinterface 802.1Q (Router-on-a-Stick).]),
    ([FR-04], [Cấu hình Cấp phát IP (DHCP)], [Quản lý DHCP Pool (Network, Gateway, DNS, Lease), dải địa chỉ loại trừ (Excluded IP) và cấu hình Relay Helper Address trên từng interface.]),
    ([FR-05], [Cấu hình Định tuyến mạng], [Quản lý Static & Default Route; cấu hình định tuyến động OSPFv2 (Process, Area, Network, Interface tuning); cấu hình EIGRP (AS, Network, Key Chain).]),
    ([FR-06], [Chính sách kiểm soát truy cập (ACL)], [Quản lý Standard, Extended, Dynamic, Reflexive và MAC ACL; đảm bảo thứ tự ưu tiên (Sequence); gán chính sách vào giao diện theo chiều in/out.]),
    ([FR-07], [Biên dịch địa chỉ mạng (NAT/PAT)], [Quản lý Static NAT (1-1), Dynamic NAT (Pool), PAT (Overload cổng WAN); phân định vai trò `ip nat inside/outside`; kết hợp NAT ACL và Route-map.]),
    ([FR-08], [Chuyển mạch & Bảo mật Lớp 2], [Quản lý VLAN, Switchport Access/Trunk 802.1Q, EtherChannel LACP; cấu hình STP, VTP; kích hoạt Port Security, DHCP Snooping và DAI.]),
  ),
  caption: [Danh mục các yêu cầu chức năng cốt lõi của hệ thống],
) <tab-functional-requirements>

=== Nhóm tính năng mở rộng

- *FR-09 (Máy chủ Syslog):* Tiếp nhận bản tin nhật ký qua UDP/TCP (cổng 514), ghi theo lô vào SQLite, hỗ trợ lọc theo Severity (0–7) và dọn dẹp theo thời gian.
- *FR-10 (Truyền tệp SFTP):* Giao diện hai khung nhìn, xác thực vân tay máy chủ SHA-256, hàng đợi tải tệp nền có thanh tiến trình.
- *FR-11 (Terminal Alacritty nhúng):* Khởi chạy cửa sổ CLI độc lập giao tiếp qua socket IPC nội bộ (NTTP/1), tách biệt khỏi phiên automation.
- *FR-12 (Quản lý Gói dự án .ntp):* Đóng gói toàn bộ cơ sở dữ liệu và cấu hình thành tệp `.ntp` chuẩn Zip, hỗ trợ mã hóa Argon2id + AES-256-GCM và snapshot khôi phục an toàn.

== Yêu cầu phi chức năng

Hệ thống phải đáp ứng các tiêu chuẩn kỹ thuật nghiêm ngặt về hiệu năng, tính ổn định và an toàn (Non-Functional Requirements - NFR):

- *NFR-01 (Hiệu năng giao diện không chặn - Non-blocking UI):* Luồng giao diện chính (UI Thread) phải hoàn toàn độc lập với các tác vụ mạng. Mọi hoạt động kết nối SSH, thu thập cấu hình hoặc đẩy lệnh kéo dài đều phải thực thi trên các luồng nền (Worker Threads / Background Tasks) để giao diện luôn phản hồi mượt mà.
- *NFR-02 (An toàn thực thi Dev-mode - Fail-closed):* Hệ thống cung cấp Chế độ phát triển (Dev-mode). Khi được kích hoạt, hệ thống khóa chặn tuyệt đối việc mở socket kết nối thật xuống thiết bị vật lý, chỉ sinh phản hồi mô phỏng phục vụ kiểm thử logic và giao diện.
- *NFR-03 (Toàn vẹn dữ liệu quan hệ):* Cơ sở dữ liệu SQLite kích hoạt kiểm tra ràng buộc khóa ngoại (`PRAGMA foreign_keys = ON`) và các bộ xác thực nghiệp vụ (Validation) ở backend nhằm ngăn chặn dữ liệu sai lệch (nhập sai IP, Subnet không hợp lệ, hoặc tham chiếu tới đối tượng không tồn tại).
- *NFR-04 (Khóa đồng bộ theo thiết bị - Host Lock):* Áp dụng cơ chế khóa tuần tự hóa (`operation_lock`) trên từng thiết bị. Không cho phép hai tiến trình cùng ghi lệnh vào một kênh CLI tại cùng một thời điểm nhằm loại trừ triệt để hiện tượng xung đột dữ liệu (Race Condition).
- *NFR-05 (Bảo mật thông tin xác thực):* Mật khẩu thiết bị và khóa bí mật không được ghi lại dưới dạng bản rõ (plain-text) trong các tệp nhật ký hệ thống. Mật khẩu kết nối SFTP được bảo vệ qua kho bảo mật Windows DPAPI.

== Kiến trúc phân lớp hệ thống

Kiến trúc phần mềm NetworkTools được thiết kế theo mô hình 4 tầng độc lập, bảo đảm nguyên tắc phân tách trách nhiệm và phân định ranh giới rõ ràng:

#figure(
  image("diagrams/22_architecture_overview.svg", width: 78%),
  caption: [Kiến trúc phân lớp tổng thể của phần mềm NetworkTools],
) <fig-layer-architecture>

/ 1. Lớp Giao diện (Presentation Layer - Qt Quick / QML): Chịu trách nhiệm hiển thị các thành phần trực quan (Cửa sổ, Bảng dữ liệu, Biểu mẫu, Thẻ tiến trình, Hộp thoại View & Push) và tiếp nhận tương tác từ người dùng. Lớp này hoàn toàn không chứa câu lệnh SQL hay mã kết nối mạng trực tiếp.
/ 2. Lớp Cầu nối & Điều phối (Bridge / Facade Layer - PyQt6): Đóng vai trò lớp trung gian chuyển tiếp. Các đối tượng Python kế thừa từ `QObject` (như `DatabaseManager`, `TerminalHelper`, `WorkspaceSaveController`, `SyslogManager`) tiếp nhận yêu cầu từ QML qua `@pyqtSlot` và phát tín hiệu `@pyqtSignal` để cập nhật trạng thái lên giao diện.
/ 3. Lớp Dữ liệu và Nghiệp vụ (Domain & Persistence Layer): Quản lý logic xử lý nghiệp vụ, kiểm tra ràng buộc dữ liệu (Validation) và tương tác với hệ quản trị cơ sở dữ liệu SQLite cục bộ thông qua các Repository chuyên biệt.
/ 4. Lớp Mạng và Thực thi (Network & Worker Layer): Chịu trách nhiệm tương tác trực tiếp với thiết bị mạng. Bao gồm bộ quản lý phiên (`DeviceSessionRegistry`), cơ chế khóa thiết bị (`Host Lock`), bộ điều phối song song (`BatchExecutor`), engine kết xuất mẫu (`Jinja2`) và các thư viện giao tiếp mạng (`Netmiko`, `Paramiko`).

`DatabaseManager` đóng vai trò là Facade trung tâm được nạp vào engine QML. Điểm khởi chạy của toàn bộ ứng dụng desktop là tệp `app/main.py`, vận hành độc lập theo mô hình desktop cục bộ (Local-first Application).

== Luồng dữ liệu cốt lõi

=== Luồng 1: Quản lý và đồng bộ trạng thái thiết bị (Sync)

Quy trình kết nối và thu thập trạng thái ban đầu diễn ra theo các bước:

#figure(
  image("diagrams/05_session_lifecycle.svg", width: 85%),
  caption: [Vòng đời phiên kết nối và thu thập dữ liệu thiết bị],
) <fig-session-lifecycle>

+ Người dùng thêm thiết bị vào Inventory và mở phiên làm việc (Tab thiết bị).
+ Hệ thống kích hoạt kiểm tra kết nối mạng (Ping ICMP) và kiểm tra cổng SSH (Port 22/23).
+ `DeviceSessionRegistry` khởi tạo kết nối SSH/Telnet và lưu trữ session handle theo định danh host.
+ Tiến trình nền gửi lệnh `show running-config`, nhận luồng văn bản thô, lưu trữ bản sao Git snapshot qua Dulwich tại `backup/<host>/cfg`.
+ Bộ phân tích cú pháp (Parser) bóc tách thông tin giao diện (Interface IP), bảng định tuyến (OSPF/Static), và lưu vào cơ sở dữ liệu SQLite làm dữ liệu cơ sở (Baseline).

=== Luồng 2: Định nghĩa cấu hình mong muốn (Desired State)

Quá trình ghi nhận cấu hình do người dùng thiết lập diễn ra an toàn và độc lập với thiết bị thật:

+ Người dùng nhập các tham số mạng (ví dụ: tạo DHCP Pool mới, thêm OSPF Network, thiết lập quy tắc Extended ACL) trên biểu mẫu QML.
+ Tầng giao diện và Backend thực hiện kiểm tra tính hợp lệ của dữ liệu (kiểm tra định dạng IPv4, Wildcard Mask, dải cổng hợp lệ).
+ Dữ liệu hợp lệ được ghi vào bảng nghiệp vụ tương ứng trong `device_network.db` kèm theo cờ trạng thái: `success = 0` (Pending Add/Update) hoặc `success = -1` (Pending Delete).
+ Giao diện đồ họa lập tức cập nhật trạng thái hiển thị của bản ghi sang màu vàng/cam để báo hiệu cấu hình đang chờ thực thi (`Pending`).

=== Luồng 3: Xem trước và Thực thi cấu hình (View & Push)

Đây là luồng tác vụ quan trọng nhất để chuyển đổi dữ liệu cấu hình mong muốn thành trạng thái thực tế trên thiết bị:

#figure(
  image("diagrams/02_state_flow.svg", width: 55%),
  caption: [Quy trình chuyển đổi trạng thái cấu hình từ Desired State sang Applied],
) <fig-state-flow>

+ *Quét dữ liệu chờ:* Bộ điều khiển (Controller) truy vấn cơ sở dữ liệu để lọc toàn bộ các bản ghi có `success = 0` hoặc `success = -1` của thiết bị được chọn.
+ *Kết xuất tập lệnh (Rendering):* Dữ liệu được đưa qua engine Jinja2 để sinh ra chuỗi câu lệnh CLI Cisco IOS tương ứng (bao gồm cả các lệnh thêm mới và lệnh phủ định `no ...` đối với tác vụ gỡ bỏ).
+ *Kiểm duyệt trực quan (Preview):* Hộp thoại View & Push hiển thị toàn bộ tập lệnh dự kiến cùng danh sách các mục bị ảnh hưởng để người quản trị kiểm tra cú pháp và logic.
+ *Thực thi bất đồng bộ (Push):* Khi người dùng nhấn nút *Push*, một tiến trình Worker được đưa vào hàng đợi xử lý nền. Worker yêu cầu quyền truy cập phiên kết nối từ `DeviceSessionRegistry`, kích hoạt `Host Lock`, gửi khối lệnh xuống thiết bị và thu thập phản hồi.
+ *Xác minh và Cập nhật (Verify & Update):* Nếu thiết bị thực thi không phát sinh lỗi, hệ thống cập nhật cờ `success = 1` (đối với thêm/sửa) hoặc xóa hẳn bản ghi khỏi bảng (đối với tác vụ xóa). Nếu phát sinh lỗi, trạng thái Pending được giữ nguyên và thông báo lỗi chi tiết được trả về giao diện.

== Thiết kế cơ sở dữ liệu

Hệ thống cơ sở dữ liệu SQLite của NetworkTools được phân hoạch thành hai tệp cơ sở dữ liệu độc lập nhằm tách biệt luồng cấu hình mong muốn và luồng dữ liệu quan sát/giám sát:

*Nhóm 1: Cơ sở dữ liệu Cấu hình và Trạng thái (`device_network.db` — 73 bảng)*

Lưu trữ danh mục thiết bị và các tham số mạng do người dùng định nghĩa, đóng vai trò là trạng thái mong muốn (Desired State) cần duy trì:

#[
  #set par(justify: false)
  #report-table(
    columns: (16%, 34%, 50%),
    cell-align: (center + horizon, left + horizon, left + horizon),
    header: ([Tiền tố bảng], [Phân hệ nghiệp vụ], [Mục đích lưu trữ và các bảng tiêu biểu]),
    rows: (
      ([`t01_*`], [Inventory & SSH], [Định danh thiết bị, tham số SSH, cờ dev-mode (`t01_devices`, `t01_ssh_algo`).]),
      ([`t02_*`], [Router Interface], [Thông số IPv4, Subinterface dot1q, Tunnel GRE, WAN (`t02_router_iface_*`).]),
      ([`t03_*`], [Dịch vụ DHCP], [DHCP Pool, dải IP loại trừ, Relay Helper (`t03_dhcp_pool`, `t03_dhcp_excluded_*`).]),
      ([`t04_*`], [Định tuyến L3], [Static Route, quy trình OSPFv2, EIGRP (`t04_static_routing`, `t04_ospf_*`, `t04_eigrp_*`).]),
      ([`t05_*`], [ACL & NAT], [Standard/Extended/Reflexive ACL, Static/Dynamic/PAT NAT, Route-map (`t05_acl_*`, `t05_nat_*`).]),
      ([`t06_*`], [Switching & L2], [VLAN, Switchport Trunk/Access, EtherChannel, STP, Port Security, SVI (`t06_switch_*`).]),
      ([`t08_*`], [Dự phòng FHRP], [Cấu hình nhóm HSRP, VRRP, GLBP và tracking (`t08_fhrp_*`).]),
      ([`t09_*`], [VTP Domain], [Quản lý VTP Domain, chế độ Server/Client/Transparent (`t09_vtp_*`).]),
    ),
    caption: [Phân loại và mục đích của các nhóm bảng cấu hình (Desired State)],
  ) <tab-database-schema-config>
]

*Nhóm 2: Cơ sở dữ liệu Thu thập và Nhật ký (`info_collected.db` — 20 bảng)*

Lưu trữ dữ liệu chỉ đọc (Read-only) được các tiến trình Collector và Listener tự động lấy về từ thiết bị hoặc tiếp nhận qua mạng:

#[
  #set par(justify: false)
  #report-table(
    columns: (20%, 35%, 45%),
    cell-align: (center + horizon, left + horizon, left + horizon),
    header: ([Tiền tố bảng], [Phân hệ dữ liệu thu thập], [Mô tả nội dung dữ liệu quan sát]),
    rows: (
      ([`t08_info_*`], [Bảng định tuyến thực tế], [Lưu các tuyến đường học được thu thập từ lệnh `show ip route`.]),
      ([`t09_info_*`], [Trạng thái cấp phát DHCP], [Bảng IP Binding (`show ip dhcp binding`) và xung đột địa chỉ IP.]),
      ([`t10_info_*`], [Trạng thái ACL hoạt động], [Bộ quy tắc ACL thực tế và thống kê số gói tin khớp luật (Match counters).]),
      ([`t11_info_*`], [Bảng biên dịch NAT], [Các phiên NAT/PAT đang hoạt động (`show ip nat translations`) và thống kê.]),
      ([`t12_syslog_*`], [Nhật ký hệ thống Syslog], [Toàn bộ bản tin Syslog RFC 3164/5424 tiếp nhận qua socket UDP/TCP.]),
    ),
    caption: [Phân loại các nhóm bảng dữ liệu thu thập và giám sát (Observed State)],
  ) <tab-database-schema-info>
]

*Quản lý vòng đời trạng thái dữ liệu (State Management):*

Trong các bảng cấu hình nghiệp vụ, tính nhất quán giữa dữ liệu trên phần mềm và trạng thái trên thiết bị được kiểm soát chặt chẽ thông qua trường `success`:
- `success = 0`: Bản ghi ở trạng thái chờ thêm mới hoặc cập nhật (`Pending Add/Update`).
- `success = 1`: Bản ghi đã được đẩy và đồng bộ thành công trên thiết bị (`Applied / Synchronized`).
- `success = -1`: Bản ghi ở trạng thái chờ gỡ bỏ khỏi thiết bị (`Pending Delete / Soft Delete`).

== Thiết kế giao diện người dùng

Giao diện người dùng của NetworkTools được thiết kế hiện đại trên nền tảng Qt Quick/QML, hướng tới sự tối giản, tối ưu không gian làm việc và hỗ trợ thao tác nhanh cho kỹ sư mạng:

=== Khung ứng dụng chính (Application Shell)

Giao diện ứng dụng bao gồm 4 khu vực chức năng chính:
- *Thanh tiêu đề và Menu hệ thống (Header & Menu Bar):* Hiển thị thông tin dự án `.ntp` đang mở, chế độ hiển thị menu (Auto/Global/Custom), nút chuyển đổi Theme sáng/tối (Dark/Light Mode), và nút kích hoạt nhanh các công cụ ngoài.
- *Thanh điều hướng tính năng (Feature Bar):* Thanh bên trái nhóm các phân hệ nghiệp vụ theo danh mục logic: Quản lý thiết bị (Devices), Định tuyến (Routing), Chuyển mạch (Switching), Dịch vụ mạng (Services), An ninh (Security), Giám sát (Syslog / SFTP) và Cài đặt (Settings).
- *Thanh quản lý tab thiết bị (Device Tab Bar):* Mỗi thiết bị đang kết nối được biểu diễn bằng một Tab làm việc độc lập. Người dùng có thể chuyển đổi linh hoạt giữa các router/switch mà không làm mất trạng thái biểu mẫu đang nhập dở.
- *Thanh trạng thái (Status Bar):* Nằm ở cạnh dưới cửa sổ, hiển thị trạng thái kết nối mạng của máy trạm, địa chỉ IP cục bộ, mức sử dụng CPU/RAM và tiến trình của các tác vụ nền đang chạy.

=== Cơ chế nạp thành phần lười (Lazy Loading & Performance Optimization)

Để tối ưu hóa thời gian khởi động ứng dụng và tiết kiệm tài nguyên bộ nhớ khi quản lý hàng chục thiết bị cùng lúc, toàn bộ các màn hình cấu hình phức tạp (như OSPF Editor, ACL Rules Builder, Switching View) được nhúng trong các thành phần `Loader` của QML. Một màn hình chỉ thực sự được nạp (instantiate) vào bộ nhớ khi người dùng nhấp chọn tính năng tương ứng trên Feature Bar, giúp ứng dụng duy trì tốc độ phản hồi 60 FPS mượt mà.

=== Các mẫu thiết kế giao diện chuẩn (UI Patterns)

- *Khung biểu mẫu chia đôi (Split Form Pane):* Nửa bên trái hiển thị biểu mẫu nhập liệu (Form Section, Input Field, ComboBox), nửa bên phải là bảng danh sách các mục đã lưu (Saved List Panel). Kỹ sư có thể vừa xem lại các cấu hình hiện có vừa tạo mới nhanh chóng.
- *Thẻ quy trình (Process Card):* Dành riêng cho các giao thức định tuyến phức tạp (OSPF, EIGRP), gom nhóm các tham số cấu hình liên quan (Process ID, Router ID, Area, Network Statements) vào một thẻ trực quan, giúp dễ dàng theo dõi toàn cục.
- *Hộp thoại View & Push (View & Push Dialog):* Cửa sổ kiểm duyệt trung tâm, hiển thị mã lệnh CLI dạng tô màu cú pháp (Syntax Highlighting), cho phép sao chép nhanh (`CopyButton`), hiển thị danh sách thiết bị nhận lệnh và nút kích hoạt đẩy lệnh bất đồng bộ.

== Thiết kế an toàn và xử lý lỗi

Đặc thù của tự động hóa mạng là một sai sót nhỏ có thể làm sập toàn bộ đường truyền. Do đó, NetworkTools được tích hợp các cơ chế phòng vệ đa tầng:

- *Cô lập môi trường phát triển (Dev-mode Fail-Closed):* Hệ thống cung cấp cờ `dev = 1` cho thiết bị. Khi được bật, mọi luồng giao tiếp SSH/Telnet hướng tới cổng vật lý bị ngắt hoàn toàn theo nguyên tắc "fail-closed". Mọi thao tác View & Push trong chế độ này đều chạy qua hàm mô phỏng (Mock Worker), cho phép kỹ sư kiểm tra tính đúng đắn của logic mà không gây rủi ro cho mạng thật.
- *Khóa theo thiết bị (Host Lock):* Mỗi thiết bị được quản lý bởi một khóa tuần tự hóa (`operation_lock`). Khi một tác vụ SSH đang chạy, mọi yêu cầu can thiệp khác vào cùng thiết bị sẽ được xếp vào hàng đợi hoặc từ chối an toàn, ngăn ngừa xung đột trạng thái CLI.
- *Ngắt thời gian chờ (Timeout) và Hủy tác vụ an toàn (Cooperative Cancellation):* Toàn bộ các kết nối mạng đều được thiết lập ngưỡng timeout (mặc định 10–30 giây). Khi người dùng nhấn nút Hủy (Cancel) trên giao diện, tiến trình nền sẽ kiểm tra cờ hủy tại các ranh giới an toàn (Safe Boundary) và giải phóng tài nguyên mà không để lại phiên treo trên thiết bị.
- *Bảo vệ dữ liệu nhạy cảm:* Mật khẩu thiết bị và mật khẩu đường truyền PPP/VTP được che giấu trên giao diện Preview và không ghi vào file log vận hành. Toàn bộ gói dự án `.ntp` có thể được mã hóa bằng thuật toán Argon2id và AES-256-GCM để bảo vệ toàn diện dữ liệu khi lưu trữ hoặc chia sẻ.

== Tổng kết chương

Chương 3 đã hoàn thiện bức tranh phân tích và thiết kế toàn diện cho phần mềm NetworkTools. Từ việc mô hình hóa các ca sử dụng, phân rã yêu cầu chức năng/phi chức năng, xác lập kiến trúc 4 tầng chuẩn mực, đến việc thiết kế luồng dữ liệu 3 bước (Sync \rightarrow Desired State \rightarrow View & Push), chuẩn hóa lược đồ cơ sở dữ liệu 93 bảng và xây dựng trải nghiệm người dùng tối ưu. Toàn bộ các nguyên tắc an toàn, cô lập lỗi và bảo vệ dữ liệu đã được lồng ghép chặt chẽ vào thiết kế, làm tiền đề vững chắc cho việc hiện thực hóa mã nguồn trong Chương 4.