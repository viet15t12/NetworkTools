# Kiến trúc kỹ thuật CAMS

Ngày đối chiếu: **2026-08-16**.

Tài liệu này mô tả kiến trúc đang chạy của ứng dụng desktop trong `app/` và đặt
các thành phần cũ ở root repository vào đúng ranh giới. Mọi khẳng định về runtime
được đối chiếu từ composition root, import, schema, service và test hiện có.
`backend/` cùng `api_server.py` không nằm trong tiến trình desktop.

## 1. Bối cảnh hệ thống

~~~text
Người dùng
  │
  ├─ CAMS Desktop
  │    ├─ Welcome (tạo/mở project .ntp)
  │    └─ Workspace UI (PyQt6 + QML module UI)
  │          │ QObject, signal/slot
  │          ▼
  │       core facade
  │          │
  │          ▼
  │       feature service
  │          ├─ repository ───────────────→ SQLite trong workspace
  │          ├─ worker → session registry → SSH/Telnet/RESTCONF → thiết bị
  │          ├─ Syslog listener ──────────→ info_collected.db
  │          ├─ SFTP client ──────────────→ SFTP server
  │          └─ terminal manager ─────────→ cams-terminal
  │
  └─ API/backend cũ
       api_server.py → backend/PyCode
       (không được app/main.py khởi tạo hoặc gọi)
~~~

Runtime sản phẩm hiện là ứng dụng desktop chạy trong một tiến trình Python.
Không có HTTP service trung gian giữa QML và nghiệp vụ: QML gọi các QObject do
`app/main.py` đăng ký, còn Python gọi repository hoặc worker trực tiếp.

## 2. Ranh giới repository

| Thành phần | Vai trò hiện tại | Có trong desktop runtime? |
| --- | --- | ---: |
| `app/` | Ứng dụng desktop chuẩn: UI, facade, feature, infrastructure và test. | Có |
| `backend/` | Backend cũ/tham khảo cho dispatcher, sync, topology, security và worker mạng. | Không |
| `api_server.py` | Gateway FastAPI cũ gọi `backend/PyCode`. | Không |
| `mock/` | Payload, cấu hình và fixture thủ công. | Không |
| `reports/` | Tài liệu và artifact báo cáo nghiên cứu, tách khỏi runtime. | Không |
| `docs/` | Contract, audit, hướng dẫn và quyết định kiến trúc. | Không |

`backend/` có thể được nghiên cứu để chuyển khả năng sang app, nhưng không phải
lớp hạ tầng của desktop. Khả năng chỉ tồn tại ở backend cũ không được mô tả là
khả năng của ứng dụng cho tới khi có UI/service an toàn và test trong `app/`.
Bảng đối chiếu nằm tại [BACKEND_APP_PARITY.md](BACKEND_APP_PARITY.md).

## 3. Kiến trúc phân lớp trong `app/`

Luồng phụ thuộc chuẩn:

~~~text
QML → core facade/slot → feature service
                         ├─ repository → infrastructure/database → SQLite
                         └─ worker     → infrastructure/network  → thiết bị
~~~

| Lớp | Trách nhiệm | Không được sở hữu |
| --- | --- | --- |
| `UI/` | Module QML `UI`, cửa sổ, layout, component, theme và resource. | SQL, connector, push trực tiếp |
| `core/` | Contract QObject dùng chung, composition facade, task Qt, settings và lifecycle cấp app. | Nghiệp vụ feature mới |
| `features/` | Use case, validation, model, repository, parser, worker và QML contract theo chức năng. | Cache session riêng, bảng riêng của feature khác |
| `domain/` | Kiểu/trạng thái nghiệp vụ dùng chung, không phụ thuộc Qt. | I/O và UI |
| `infrastructure/` | Adapter SQLite, network, hệ điều hành và package workspace. | Chính sách nghiệp vụ, import QML |
| `scripts/` | Build database và kiểm tra cấu trúc repository. | Runtime state |
| `tests/` | Unit, integration, QML harness và contract test. | Dữ liệu production |

`app/app_facade.py` chỉ tập hợp public object phục vụ bootstrap.
`DatabaseManager` trong `core/database/manager.py` là facade tương thích được ghép
từ các slot mixin; đây không phải database server. Nghiệp vụ đang tiếp tục được
tách khỏi facade sang `features/*` theo
[ARCHITECTURE_RULES.md](../app/ARCHITECTURE_RULES.md).

## 4. Khởi động và vòng đời ứng dụng

`app/main.py` là composition root duy nhất của desktop:

1. cấu hình Qt/PyQt6 theo nền tảng và tạo các database mặc định còn thiếu;
2. tạo `QApplication`, `QQmlApplicationEngine` và import path cho module `UI`;
3. khởi tạo service dùng chung, `DeviceSessionRegistry`, facade và controller;
4. đăng ký context property cho QML;
5. tải `UI/Welcome` trước;
6. khi người dùng tạo/mở project, chuyển toàn bộ service sang workspace đó rồi
   mới tải `UI/Main`;
7. khi đóng project, trả service về database mặc định;
8. khi thoát, dừng monitor/task/listener/SFTP, đóng session thiết bị, reset trạng
   thái kết nối và dọn thư mục workspace tạm.

Hai QML root window có vòng đời tách biệt. Main window được lazy-create lần đầu
mở project và được tái sử dụng; chuyển về Welcome chỉ ẩn workspace window. Trước
khi ẩn cửa sổ, composition root giải phóng text-input focus để tránh lỗi lifecycle
trên Wayland.

### Context property chính

| Tên QML | Owner Python | Trách nhiệm |
| --- | --- | --- |
| `dbManager` | `DatabaseManager` | CRUD, feature slot, View & Push và lịch sử config |
| `cli` | `TerminalHelper` | session/batch, running-config, save config và terminal companion |
| `welcomeController` | `WelcomeController` | tạo, mở, đóng project và danh sách gần đây |
| `workspaceSaveController` | `WorkspaceSaveController` | save, Save As, snapshot và rollback nền |
| `networkMonitor` | `NetworkMonitor` | interface/IP/SSID và tài nguyên hệ thống |
| `statusBarSettings` | `StatusBarSettings` | tùy chọn Status Bar |
| `themeSettings` / `systemAppearance` | Settings/system adapter | theme, accent và giao diện hệ điều hành |
| `windowSettings` | `WindowSettings` | geometry/maximized state |
| `menuPresentation` | `MenuPresentationController` | cách trình bày menu theo nền tảng |
| `AppPaths` | `AppPaths` | URL resource độc lập working directory |
| `externalTools` | `ExternalToolsManager` | catalog và khởi chạy công cụ ngoài |
| `sftpController` | `SftpController` | kết nối, duyệt file và transfer SFTP |
| `syslogManager` / `syslogSettings` | Syslog feature | listener, query, cấu hình và retention |

Các cờ Easter Egg cũng được truyền vào QML nhưng không tham gia nghiệp vụ hay
persistence.

## 5. Workspace và dữ liệu

### 5.1 Project `.ntp`

Project là package version 1 do `infrastructure/workspace` sở hữu. Khi mở,
package được kiểm tra giới hạn, path, manifest và SHA-256 rồi giải nén vào thư mục
tạm. Một session chứa tối thiểu:

~~~text
manifest.json
device_network.db
info_collected.db
backup/
snapshots/
~~~

Khi workspace active, composition root đổi đồng bộ path cho `DatabaseManager`,
`DeviceRepository`, `ConfigSyncService`, `ConfigBackupService`,
`ExternalToolsManager` và Syslog. Vì vậy inventory, desired state, dữ liệu thu
thập và lịch sử cấu hình cùng thuộc một project; không được giữ reference tới DB
của workspace sau khi session đóng.

Save tạo staging image ổn định, backup SQLite bằng SQLite API, kiểm tra xung đột
bằng fingerprint và thay package atomically. Snapshot có index/inventory riêng;
rollback tạo một safety snapshot trước khi phục hồi. Project có thể được bảo vệ
bằng Argon2id và AES-256-GCM; mật khẩu không được ghi vào project hoặc danh sách
recent.

### 5.2 Database

Path mặc định được định nghĩa duy nhất tại
`infrastructure/database/paths.py`:

- `data/device_network.db`: inventory và desired/configuration state;
- `data/info_collected.db`: routing, DHCP, ACL, NAT và Syslog đã thu thập;
- `data/app_state.db`: danh sách project gần đây, độc lập với workspace.

Schema hiện hành gồm 73 bảng trong `device_network.db` và 20 bảng trong
`info_collected.db`; số object lớn hơn vì còn index và trigger. Không dùng số
object SQLite để suy ra số bảng.

`CAMS_DATA_DIR` có thể đổi thư mục dữ liệu mặc định. Schema authority là
các file có thứ tự trong:

- `infrastructure/database/schemas/device_network/`;
- `infrastructure/database/schemas/info_collected/`.

`scripts/build_databases.py` build qua file tạm, bật foreign key, chạy
`integrity_check`/`foreign_key_check` rồi thay atomically. Khi khởi động, script
chỉ tạo database thiếu, migrate status số legacy và bổ sung object schema thiếu;
không xóa dữ liệu người dùng để rebuild toàn bộ.

### 5.3 Lịch sử running-config

`features/config_backup` lưu mỗi host ở `backup/<host>/cfg` bằng Git object của
Dulwich, không cần Git CLI. Host được validate trước khi ghép path. Mỗi snapshot
có commit bất biến; service cung cấp HEAD, lịch sử, đọc commit và unified diff.
`features/config_sync` quyết định khi nào snapshot đã commit được đồng bộ vào
SQLite và bảo vệ desired state đang pending khỏi bị ghi đè âm thầm.

## 6. Kết nối thiết bị và đồng thời

`DeviceSessionRegistry` là owner duy nhất của connector automation theo host:

- session được tái sử dụng giữa Connect, Get running-config, View & Push và các
  use case khác;
- `operation_lock` tuần tự hóa mọi thao tác trên cùng CLI channel;
- các host khác nhau có thể chạy song song;
- đóng tab QML không đóng session; Disconnect hoặc shutdown mới đóng;
- `dev = 1` chặn kết nối thật; mô phỏng push hiện chỉ được worker Routing, DHCP,
  ACL và NAT triển khai rõ ràng.

`BatchExecutor` giới hạn mặc định 5 host, cô lập lỗi theo host và chỉ hủy task
chưa bắt đầu tại safe boundary. Blocking operation đi qua `BackgroundTask` /
`AsyncTaskCoordinator` hoặc controller có worker/thread riêng; kết quả quay về
QML bằng Qt signal. Syslog có listener/writer thread riêng, còn SFTP có worker và
transfer queue riêng.

Luồng View & Push:

~~~text
Desired state trong SQLite
  → Preview: validate + render, không mở kết nối
  → Push: worker nền
      → session registry / connector
      → thiết bị
      → cập nhật trạng thái đồng bộ hoặc lỗi theo transaction
~~~

SSH/Telnet là đường automation chính cho các worker Cisco IOS. Routing vẫn có
một số nhánh RESTCONF. Không được suy luận hỗ trợ đầy đủ NETCONF/RESTCONF hoặc đa
vendor chỉ từ dependency trong `pyproject.toml`.

CAMS Terminal là ứng dụng đồng hành tách tiến trình. Feature
`terminal/` quản lý UUID, `QProcess` và IPC NTTP/1; terminal tương tác không
render trong main QML và không dùng chung session Netmiko automation. Source fork
Alacritty nằm trong `vendor/alacritty`; adapter `qtpyTerminal-main` chỉ còn là
compatibility code và không được composition root khởi tạo.

## 7. Các feature runtime

| Feature | Owner | Biên tích hợp chính |
| --- | --- | --- |
| Devices | `features/devices` | inventory, login, batch, running/save config, classification |
| Router Interfaces | `features/interfaces` | repository, validation, preview/push Physical/L3/WAN/Loopback/Tunnel/Subinterface |
| DHCP | `features/dhcp` | pool, excluded, helper, parser và worker |
| Routing | `features/routing` | static/default, OSPF, EIGRP, group đa host |
| FHRP | `features/fhrp` | HSRP, VRRP, GLBP và View & Push đa member |
| ACL | `features/acl` | ACL/rule/binding, collector và worker |
| NAT | `features/nat` | NAT, NAT ACL, route-map, collector và worker |
| Switching | `features/switching` | VLAN, switchport, EtherChannel, STP, VTP, L2 security, SVI và sync một phần |
| Syslog | `features/syslog` | UDP/TCP receiver, parser, batch writer, query, cấu hình và retention |
| SFTP | `features/sftp` | host-key confirmation, browser, upload/download, progress/cancel |
| Config Backup/Sync | `features/config_backup`, `config_sync` | lịch sử Dulwich và policy đồng bộ |
| Terminal | `features/terminal` | companion process và IPC |
| External Tools | `features/external_tools` + core facade | catalog/metadata; discovery/launcher còn trong facade |

Phạm vi đã kiểm chứng chi tiết nằm tại
[CURRENT_APP_FEATURES.md](CURRENT_APP_FEATURES.md). Topology graph/discovery,
Console Serial, SNMP và plugin/provider API chưa có trong composition root của
repository này.

## 8. Backend và FastAPI cũ

`api_server.py` khai báo các endpoint gọi dispatcher trong `backend/PyCode` cho
DHCP, sync, interface, routing, ACL/NAT, switching và info collection. Đây là
một subsystem cũ, không phải API của desktop:

- `app/main.py` không import hoặc khởi chạy FastAPI;
- backend dùng config/path/global output riêng và còn trộn hai kiểu import
  `backend.PyCode...` với `PyCode...`;
- backend yêu cầu `.env` và database riêng theo contract của nó;
- API chưa có authentication/authorization, request model typed, task ID,
  status/cancel hoặc error propagation end-to-end;
- phản hồi “success” chỉ xác nhận dispatcher được gọi/xếp nền, không xác nhận
  thiết bị đã áp dụng cấu hình.

Nếu API được phục hồi, nó phải có package/dependency/entry point độc lập và
integration test riêng. Không cho API cùng ghi trực tiếp vào workspace đang mở
trước khi có schema version, locking và ownership contract rõ ràng.

## 9. Ranh giới bảo mật và độ tin cậy

- `t01_devices` hiện lưu username/password dạng text trong SQLite; mã hóa project
  bảo vệ package khi nghỉ nhưng không thay thế secret store khi workspace đã mở.
- Một số RESTCONF request còn `verify=False`; không coi TLS peer verification là
  đã hoàn tất.
- SFTP xác nhận host key. Lưu password tự động chỉ khả dụng qua Windows DPAPI;
  nền tảng không có secure store sẽ lưu profile mà không lưu password.
- External Tools chặn placeholder `{password}` để không đưa credential lên argv.
- Preview Router Interface che PPP password, nhưng desired state vẫn có thể chứa
  secret và phải được bảo vệ như dữ liệu nhạy cảm.
- Running-config, backup, Syslog, private key, database/WAL/journal và project đã
  giải nén không được commit hoặc ghi log.
- Task mạng cần timeout/cancel có giới hạn. Không chạy worker blocking trên Qt
  main thread và không tạo connector/session cache ngoài registry.

## 10. Contract, kiểm thử và thay đổi kiến trúc

Nguồn sự thật theo thứ tự:

1. `app/main.py` và public QML contract trong `UI/qmldir`;
2. code/service/repository/worker của feature;
3. schema modular trong `infrastructure/database/schemas`;
4. test trong `app/tests`;
5. README feature và tài liệu cấp `docs/`.

Kiểm tra thay đổi kiến trúc bằng:

~~~bash
cd app
uv run python scripts/validate_structure.py
uv run python -m unittest discover -s tests
~~~

Test suite gồm unit test, SQLite/fake-connector integration, concurrency/session,
workspace package/snapshot và QML smoke/contract harness. Test giả không chứng
minh tương thích với mọi model/firmware; claim thiết bị thật cần bằng chứng lab.

Mọi feature mới phải giữ luồng `QML → slot → service → repository/worker`, dùng
path canonical, dùng registry chung và cập nhật README feature cùng các tài liệu
cấp ứng dụng chịu ảnh hưởng. Bản đồ mục đích tài liệu nằm tại
[`README.md`](README.md); quy tắc review nằm tại
[`CODING_STANDARDS.md`](CODING_STANDARDS.md).
