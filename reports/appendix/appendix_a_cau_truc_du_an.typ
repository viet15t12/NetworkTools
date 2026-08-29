#import "../config/commands.typ": appendix-heading, appendix-section
#import "../config/tables.typ": report-table, table-code

#appendix-heading[PHỤ LỤC A. CẤU TRÚC DỰ ÁN VÀ ÁNH XẠ MÃ NGUỒN]

#appendix-section[A.1.][Cây cấu trúc thư mục mã nguồn runtime ứng dụng desktop]

Toàn bộ mã nguồn ứng dụng desktop NetworkTools được tổ chức tại thư mục `app/` theo kiến trúc Clean Architecture:

```text
app/
├── UI/                                  # Lớp Giao diện người dùng (Qt Quick / QML)
│   ├── components/                      # Các khối thành phần UI tái sử dụng
│   │   ├── base/                        # Nút bấm, biểu tượng, hộp thoại cơ sở
│   │   ├── form/                        # Các trường nhập liệu, nhãn, nhóm form
│   │   ├── layout/                      # Khung chia đôi SplitForm, thanh Sidebar
│   │   └── standard/                    # ComboBox, CheckBox, TableView chuẩn hóa
│   ├── qml/                             # Các màn hình phân hệ chức năng
│   │   ├── app/                         # Main.qml, Welcome.qml, MenuBar.qml
│   │   ├── content/                     # DatabaseBrowser, Settings, SFTP, Syslog
│   │   ├── devices/                     # DeviceTabs, DeviceContextMenu
│   │   ├── feature/                     # FeatureBar, FeatureDropdown
│   │   └── features/                    # ACL, DHCP, Interfaces, NAT, Routing, Switching
│   └── resources/                       # Biểu tượng SVG, Brand Logo, Font chữ
├── core/                                # Lớp Cầu nối & Điều phối Facade (PyQt6)
│   ├── database/                        # DatabaseManager facade kết nối QML
│   ├── network_monitor.py               # Giám sát giao diện mạng và CPU/RAM máy trạm
│   ├── terminal_helper.py               # Điều phối CLI session và Alacritty companion
│   └── settings/                        # Quản lý cài đặt giao diện, Theme, cửa sổ
├── domain/                              # Mô hình nghiệp vụ độc lập (Pure Python)
├── features/                            # Lớp Nghiệp vụ theo từng tính năng
│   ├── acl/                             # Model, Repository, Worker và Template ACL
│   ├── config_backup/                   # Quản lý lịch sử sao lưu Git bằng Dulwich
│   ├── config_sync/                     # Thu thập và đồng bộ Running Configuration
│   ├── devices/                         # Repository, Batch Executor quản lý thiết bị
│   ├── dhcp/                            # Model, Repository, Worker, Template DHCP
│   ├── external_tools/                  # Tích hợp công cụ ngoài (PuTTY, Wireshark)
│   ├── fhrp/                            # Quản lý cấu hình HSRP, VRRP, GLBP
│   ├── interfaces/                      # Quản lý Interface L3, Subinterface, Tunnel
│   ├── nat/                             # Model, Repository, Worker, Template NAT/PAT
│   ├── routing/                         # Model, Repository, Worker Static, OSPF, EIGRP
│   ├── sftp/                            # Client truyền tệp hai khung nhìn bất đồng bộ
│   ├── switching/                       # Quản lý VLAN, Trunk, EtherChannel, STP, VTP
│   ├── syslog/                          # Syslog Server UDP/TCP, Parser, Retention
│   └── terminal/                        # Giao tiếp IPC với Alacritty qua NTTP/1
├── infrastructure/                      # Lớp Hạ tầng và Adapter kỹ thuật
│   ├── database/                        # Lược đồ SQLite (schemas/), Adapter kết nối
│   ├── network/                         # DeviceSessionRegistry, Host Lock, Netmiko Adapter
│   └── workspace/                       # Đóng gói .ntp, quản lý Snapshot và Mã hóa
├── scripts/                             # build_databases.py, validate_structure.py
├── tests/                               # 523 bài kiểm thử tự động đa tầng
└── main.py                              # Composition Root khởi tạo toàn bộ ứng dụng
```

#pagebreak(weak: true)
#appendix-section[A.2.][Bảng ánh xạ luồng thành phần toàn hệ thống]

Bảng dưới đây mô tả chi tiết chuỗi liên kết từ thành phần giao diện đồ họa (QML UI), qua lớp cầu nối (PyQt6 Bridge / Facade), đến tầng lưu trữ cơ sở dữ liệu (SQLite Table) và các mẫu cấu hình / tiến trình thực thi mạng (Worker / Jinja2 Template):

#report-table(
  columns: (18%, 17%, 21%, 18%, 26%),
  text-size: 8.5pt,
  cell-inset: (x: 3pt, y: 4pt),
  header: ([Thành phần QML], [Bridge / Facade], [Dịch vụ & Repo], [Bảng SQLite], [Worker / Template]),
  rows: (
    ([#table-code("DeviceTabs.qml")], [#table-code("cli / dbManager")], [#table-code("DeviceRepository")], [#table-code("t01_devices")], [#table-code("DeviceSessionRegistry")]),
    ([#table-code("InterfacesView.qml")], [#table-code("dbManager")], [#table-code("InterfaceRepository")], [#table-code("t02_router_iface_*")], [#table-code("router_interface.j2")]),
    ([#table-code("DhcpView.qml")], [#table-code("dbManager")], [#table-code("DhcpRepository")], [#table-code("t03_dhcp_*")], [#table-code("dhcp_worker.py / dhcp.j2")]),
    ([#table-code("StaticRouting.qml")], [#table-code("dbManager")], [#table-code("RoutingRepository")], [#table-code("t04_static_routing")], [#table-code("routing_worker.py / static_route.j2")]),
    ([#table-code("OspfEditor.qml")], [#table-code("dbManager")], [#table-code("RoutingRepository")], [#table-code("t04_ospf_*")], [#table-code("routing_worker.py / ospf.j2")]),
    ([#table-code("EigrpEditor.qml")], [#table-code("dbManager")], [#table-code("RoutingRepository")], [#table-code("t04_eigrp_*")], [#table-code("routing_worker.py / eigrp.j2")]),
    ([#table-code("AclEditor.qml")], [#table-code("dbManager")], [#table-code("AclRepository")], [#table-code("t05_acl_*")], [#table-code("acl_worker.py / acl.j2")]),
    ([#table-code("NatEditor.qml")], [#table-code("dbManager")], [#table-code("NatRepository")], [#table-code("t05_nat_*")], [#table-code("nat_worker.py / nat.j2")]),
    ([#table-code("SwitchingView.qml")], [#table-code("dbManager")], [#table-code("SwitchingRepository")], [#table-code("t06_switch_*")], [#table-code("switching_worker.py / switching.j2")]),
    ([#table-code("FhrpEditor.qml")], [#table-code("dbManager")], [#table-code("FhrpRepository")], [#table-code("t08_fhrp_*")], [#table-code("fhrp.j2")]),
    ([#table-code("VtpEditor.qml")], [#table-code("dbManager")], [#table-code("SwitchingRepository")], [#table-code("t09_vtp_*")], [#table-code("vtp.j2")]),
    ([#table-code("SyslogView.qml")], [#table-code("syslogManager")], [#table-code("SyslogRepository")], [#table-code("t12_syslog_*")], [#table-code("SyslogListener (UDP/TCP)")]),
    ([#table-code("SftpView.qml")], [#table-code("sftpController")], [#table-code("SftpClientService")], [Hàng đợi bộ nhớ], [#table-code("ParamikoSFTPWorker")]),
    ([#table-code("TerminalHost.qml")], [#table-code("cli")], [#table-code("TerminalManager")], [Socket IPC NTTP/1], [#table-code("networktools-terminal")]),
    ([#table-code("DatabaseBrowser.qml")], [#table-code("dbManager")], [#table-code("DatabaseBrowserService")], [Tất cả 93 bảng], [#table-code("sqlite3 query engine")]),
  ),
  caption: [Bảng ánh xạ luồng thành phần từ Giao diện QML đến Cơ sở dữ liệu và Worker],
) <tab-system-component-mapping>
