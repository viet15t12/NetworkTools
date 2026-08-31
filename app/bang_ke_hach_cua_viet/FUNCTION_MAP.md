# Bản đồ chức năng CAMS

Trạng thái được đối chiếu ngày 2026-08-11. `partial` nghĩa là luồng chính có code nhưng còn nằm trong facade/adapter legacy hoặc thiếu test độc lập.

## Tổng quan

| Feature | Role | Trạng thái | QML entry | Python API hiện tại | Persistence/worker | DB |
|---|---|---|---|---|---|---|
| Devices | all | partial | `UI/qml/sidebar/new_device`, `panels/DevicesPanel.qml` | `core.database.DatabaseManager`, `features.devices`, `TerminalHelper` | login/status/Get/Save config đã có service; CRUD/import còn trong manager | device_network |
| Router Interfaces | rou/sw3 | implemented | `InterfaceView.qml` + `InterfaceSubBar.qml` | `core/interface_slots.py`, `InterfaceService` | `features/interfaces` repository + View/Push | device_network |
| DHCP | rou/sw3 | implemented | `UI/qml/features/dhcp/DhcpView.qml` | `core/dhcp_slots.py` | `features/dhcp`, `features/dhcp/worker.py` | device_network |
| Routing | rou/sw3 | partial | `UI/qml/features/routing/RoutingView.qml` | `DatabaseManager` | `features/routing`, `features/routing/worker.py` | device_network |
| FHRP | rou/sw3 | implemented | `UI/qml/features/fhrp/FhrpView.qml` | `core/fhrp_slots.py` | `features/fhrp` + Cisco IOS template/worker | device_network |
| ACL | rou/sw2/sw3 | implemented | `UI/qml/features/acl/AclView.qml` | `core/acl_slots.py` | `features/acl` | device_network |
| NAT | rou | implemented | `UI/qml/features/nat/NatView.qml` | `core/nat_slots.py` | `features/nat`, `features/nat/worker.py` | device_network |
| Switching | sw2/sw3 | partial | `UI/qml/features/switching/SwitchWorkspace.qml` | `core/switch_slots.py`, Manual Sync | desired state, View/Push và VLAN/interface/EtherChannel/VTP pull-sync | device_network |
| Syslog | all | implemented | `UI/qml/features/syslog/SyslogWorkspace.qml` | `SyslogManager` | `features/syslog` | info_collected |
| Config Backup | all | implemented | `UI/qml/content/InformationView.qml` | `DatabaseManager` delegate, `TerminalHelper` | `features/config_backup`, Dulwich repository | filesystem |
| Save Config | all | implemented | Device context menu | `TerminalHelper.saveDeviceConfigAsync` | `features/devices/save_config_service.py`, active SSH/Telnet session | device startup-config |
| CAMS Terminal | all | partial | Feature Bar, device context menu, `Ctrl+\`` | `openDeviceTerminal`, `focusDeviceTerminal`, `closeDeviceTerminal`, `restartDeviceTerminal`, state/error signals | `features/terminal`: QProcess + NTTP/1; companion Alacritty fork pending | none |

## UI → Python

| QML | Context object | Contract | Async? |
|---|---|---|---:|
| device/sidebar views | `dbManager` | device CRUD, tab lifecycle | no |
| feature workspaces | `dbManager` | load/save/delete/view/push slots | push: yes |
| terminal actions | `cli` | external managed process, NTTP/1 state/focus/close/restart | event-driven |
| syslog workspace | `syslogManager`, `syslogSettings` | lifecycle/query/settings | yes |
| SFTP workspace | `sftpController` | connect/list/transfer | yes |
| Information view | `dbManager` | HEAD/history/read commit/unified Diff range | local read |

## Python → database

| Feature | Authority | Tables | Transaction |
|---|---|---|---:|
| Devices | DeviceRepository cho login/status; DatabaseManager cho CRUD còn lại | `t01_devices` | yes |
| Router Interfaces | `features/interfaces/repository.py` | `t02_interface_name`, `t02_router_iface_*` | yes |
| DHCP | DHCP repositories | `t03_*`, `t08_*` | yes |
| Routing | route repositories | `t04_*` | yes |
| FHRP | `FhrpRepository` | `t08_fhrp_*` | yes |
| ACL/NAT | ACL/NAT repositories | `t05_*` | yes |
| Switching | switching repositories | `t06_*` | yes |
| Syslog | SyslogRepository | syslog event/settings tables | batched |

## Thiết bị

| Feature | Show/collect | Config | Parser/worker |
|---|---|---|---|
| DHCP | show DHCP bindings/pools | IOS DHCP pool/helper commands | `features/dhcp/worker.py` |
| Routing | show ip route/protocol | static, OSPF, EIGRP templates | `features/routing/worker.py` |
| FHRP | — | HSRP, VRRP, GLBP Cisco IOS | `features/fhrp/worker.py` |
| Running config | prompt-buffered `do show running-config` | `do terminal length 0` | `infrastructure/network/running_config_collector.py` |
| NAT | show ip nat | IOS NAT commands | `features/nat/worker.py` |
| Router Interfaces | desired state `t02_*` | Physical/L3/WAN, Loopback, Tunnel, 802.1Q Subinterface | `features/interfaces/worker.py` |
| Syslog | UDP/TCP messages | IOS logging commands | syslog receiver/parser/configurator |

## Ma trận UI

| Feature | Load | Save | Edit | Cancel | Delete | View | Push | Sync |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Devices | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | — | — | — |
| Router Interfaces | ✅ | ✅ | ✅ | ✅ | ✅ virtual / 🔒 physical | ✅ | ✅ | 🟡 |
| DHCP | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Routing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Routing Group | ✅ | ✅ | — | ✅ | — | ✅ | ✅ | — |
| FHRP | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ | — |
| ACL | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | 🟡 | 📌 |
| NAT | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Switching | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 📌 | 🟡 |
| Syslog | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Ownership và dependency

| Module | Được import | Không được import | Owner | Test chính |
|---|---|---|---|---|
| `features/*` | core contracts, infrastructure | feature khác không qua contract | feature tương ứng | unit/integration feature |
| `infrastructure/database` | stdlib | QML, feature | platform | database bootstrap |
| `infrastructure/network` | transport libraries | QML, repository | platform | fake connector |
| `UI` | module `UI`, context objects | SQLite/worker | UI | QML smoke |

## Known gaps

| ID | Feature | Thiếu sót | Ảnh hưởng | Kế hoạch | Trạng thái |
|---|---|---|---|---|---|
| GAP-001 | Devices | CRUD/import/YANG còn trong `core/database/manager.py` | coupling | chuyển sang service/repository và slot delegate | in-progress |
| GAP-002 | Network | worker đã chuyển nhưng integration test cần dependency tùy chọn | chưa xác minh full suite tại sandbox | chạy fake-session/full suite trong môi trường đã sync | blocked-environment |
| GAP-003 | Runtime | shim tương thích còn tồn tại đến 2026-10-20 | consumer cũ còn phụ thuộc import | xóa sau thời hạn khi external consumer đã chuyển | compatibility |
| GAP-005 | External Tools | facade đã rời runtime nhưng còn trộn SQL/discovery/launcher | khó kiểm thử riêng | tách sang `features/external_tools` và adapter system | open |
| GAP-006 | Database facade | các slot đã tách file nhưng một số mixin vẫn trực tiếp gọi SQL | ranh giới file đạt, ranh giới feature/repository chưa hoàn tất | chuyển SQL mixin sang feature service/repository | in-progress |
| GAP-004 | CI | môi trường hiện tại thiếu PyQt6/Jinja2/Paramiko | chưa chạy full suite | chạy `uv sync` nơi có network/cache | blocked-environment |
| GAP-007 | Router Interfaces | chưa có catalog device-model để tự populate physical interface; IPv6/verify/rollback chưa có | physical phụ thuộc dữ liệu discovery hiện hữu và push cần kiểm tra lab | bổ sung Device Profile rồi mở rộng ConfigPlan/verify | open |
| GAP-008 | CAMS Terminal | companion Alacritty fork chưa có trong workspace; chưa build/package/lab-test Fedora Wayland và EVE-NG | Python manager có fake/socket test nhưng chưa có end-to-end terminal | hoàn tất Phase B-E trong `docs/plan/networktools-terminal-alacritty.md` ở repository riêng | external-dependency |
