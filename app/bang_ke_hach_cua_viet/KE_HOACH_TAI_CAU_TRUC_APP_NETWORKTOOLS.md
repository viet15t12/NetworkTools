# Kế hoạch tái cấu trúc thư mục `app/` của CAMS

> Phạm vi đối chiếu: `app/` tại commit `57d6baf621d8ec68aafec4b5a7891f8aa610ec7e`  
> Mục tiêu: tổ chức lại mã nguồn PyQt6/QML theo chức năng, giữ ứng dụng chạy được sau từng giai đoạn và bổ sung hệ thống tài liệu trong từng thư mục.

## 1. Mục tiêu

1. Giảm tình trạng một chức năng nằm rải rác trong `core/`, `backend/` và `network_code/`.
2. Phân biệt rõ:
   - QML/UI;
   - lớp kết nối QML–Python;
   - nghiệp vụ và lưu trữ dữ liệu;
   - kết nối/push cấu hình tới thiết bị;
   - schema và dữ liệu runtime.
3. Giảm kích thước, trách nhiệm và mức phụ thuộc của `core/database.py`.
4. Loại bỏ tên dễ nhầm như `backend.py` và `backend/` khi chúng mang vai trò khác nhau.
5. Đặt code, template, test và tài liệu gần chức năng tương ứng.
6. Có tài liệu ánh xạ đầy đủ từ màn hình QML đến bảng SQLite và lệnh thiết bị.
7. Mỗi thư mục quan trọng phải có `README.md` mô tả trách nhiệm, API và quy tắc phụ thuộc.

## 2. Nguyên tắc bắt buộc

- Không refactor toàn bộ trong một commit.
- Sau mỗi giai đoạn, ứng dụng phải khởi động và test hiện có phải chạy được.
- Không đổi tên QML module `UI` trong đợt đầu.
- Không thay đổi schema và cấu trúc thư mục cùng một commit, trừ khi đường dẫn schema là nội dung chính của commit.
- Không xóa file cũ trước khi mọi import và nơi sử dụng đã chuyển sang file mới.
- Database `.db`, backup, log và cache là dữ liệu runtime, không phải mã nguồn.
- Không để QML chứa câu SQL hoặc logic push cấu hình.
- QML chỉ gọi các QObject/slot được đăng ký bởi Python.
- Repository chỉ xử lý SQLite; worker chỉ xử lý thiết bị; service điều phối hai phía.
- Mỗi chức năng phải có chủ sở hữu rõ ràng trong `FUNCTION_MAP.md`.

## 3. Cấu trúc đích

```text
app/
├── main.py
├── pyproject.toml
├── README.md
├── FUNCTION_MAP.md
├── ARCHITECTURE_RULES.md
│
├── core/
│   ├── README.md
│   ├── app_paths.py
│   ├── settings.py
│   ├── tasks.py
│   ├── sessions.py
│   └── monitoring.py
│
├── features/
│   ├── README.md
│   ├── devices/
│   ├── interfaces/
│   ├── dhcp/
│   ├── routing/
│   │   ├── static/
│   │   ├── ospf/
│   │   └── eigrp/
│   ├── acl/
│   ├── nat/
│   ├── switching/
│   │   ├── switchport/
│   │   ├── vlan/
│   │   ├── vtp/
│   │   ├── stp/
│   │   └── etherchannel/
│   └── syslog/
│
├── infrastructure/
│   ├── README.md
│   ├── database/
│   │   ├── README.md
│   │   ├── connection.py
│   │   ├── paths.py
│   │   ├── migrations/
│   │   └── schemas/
│   │       ├── device_network/
│   │       └── info_collected/
│   └── network/
│       ├── README.md
│       ├── connector.py
│       ├── session_registry.py
│       └── command_runner.py
│
├── UI/
│   ├── README.md
│   ├── qmldir
│   ├── qml/
│   │   ├── app/
│   │   ├── layout/
│   │   ├── panels/
│   │   ├── shared/
│   │   └── features/
│   ├── components/
│   ├── theme/
│   └── resources/
│
├── scripts/
│   ├── README.md
│   ├── build_databases.py
│   └── validate_structure.py
│
├── data/
│   ├── README.md
│   └── .gitkeep
│
├── templates/
│   ├── README.md
│   └── EXdevices.xlsx
│
└── tests/
    ├── README.md
    ├── unit/
    ├── integration/
    ├── qml/
    └── fixtures/
```

## 4. Quy ước cấu trúc một chức năng

Mỗi chức năng trong `features/` sử dụng cấu trúc sau khi thực sự cần; không tạo file rỗng chỉ để đủ mẫu.

```text
features/<feature>/
├── README.md
├── slots.py          # QObject/pyqtSlot công khai cho QML
├── models.py         # Dataclass/model/kiểu dữ liệu
├── repository.py     # CRUD và transaction SQLite
├── service.py        # Validation và điều phối use case
├── worker.py         # Preview/push/sync với thiết bị
├── parser.py         # Parse running-config/show output, nếu có
├── templates/        # Jinja hoặc mẫu lệnh của chức năng
└── tests/            # Chỉ dùng nếu chọn test đồng vị; mặc định để app/tests
```

Luồng phụ thuộc hợp lệ:

```text
QML → slots → service → repository → SQLite
                    └→ worker → infrastructure/network → thiết bị
```

Luồng không hợp lệ:

- QML → SQLite trực tiếp.
- QML → worker trực tiếp.
- Repository → QML.
- Repository → worker.
- `infrastructure/` import QML.
- Feature A sửa trực tiếp bảng riêng của Feature B mà không thông qua contract đã công bố.

## 5. Ánh xạ đường dẫn cũ sang mới

| Đường dẫn hiện tại | Đường dẫn dự kiến | Hành động |
|---|---|---|
| `core/runtime.py` | `core/app_paths.py`, `settings.py`, `tasks.py`, `sessions.py`, `monitoring.py` | Tách theo trách nhiệm |
| `core/database.py` | `features/*/slots.py` và facade tạm | Tách dần, không viết lại một lần |
| `core/dhcp_slots.py` | `features/dhcp/slots.py` | Di chuyển sau khi DHCP service ổn định |
| `core/acl_slots.py` | `features/acl/slots.py` | Di chuyển cùng ACL repository |
| `core/nat_slots.py` | `features/nat/slots.py` | Di chuyển cùng NAT repository |
| `core/database_stubs.py` | Từng `features/*/slots.py` | Đặt stub gần chức năng, ghi rõ trạng thái |
| `core/view_push.py` | `features/<feature>/service.py` | Tách dispatcher theo chức năng |
| `backend/dhcp/` | `features/dhcp/` | Đổi tên module và cập nhật import |
| `backend/route/` | `features/routing/` | Gom static/OSPF/EIGRP |
| `backend/acl/` | `features/acl/` | Gom repository và validation |
| `backend/nat/` | `features/nat/` | Gom repository và validation |
| `backend/syslog_server/` | `features/syslog/` | Gom listener/parser/writer/facade |
| `network_code/login/` | `infrastructure/network/` | Tạo adapter kết nối dùng chung |
| `network_code/routing/` | `features/routing/worker.py`, `templates/` | Chuyển dispatcher/worker/template |
| `network_code/dhcp/` | `features/dhcp/worker.py`, `templates/` | Chuyển dispatcher/worker/template |
| `database/schema/` | `infrastructure/database/schemas/device_network/` | Di chuyển nguồn schema |
| `database/info_collected/` | `infrastructure/database/schemas/info_collected/` | Di chuyển nguồn schema collector |
| `database/build_databases.py` | `scripts/build_databases.py` | Giữ compatibility wrapper tạm thời |
| `template/EXdevices.xlsx` | `templates/EXdevices.xlsx` | Chuẩn hóa tên số nhiều |
| `UI/qml/dhcp/` | `UI/qml/features/dhcp/` | Chuyển sau khi cập nhật `qmldir` |
| `UI/qml/routing/` | `UI/qml/features/routing/` | Di chuyển theo từng subtab |
| `UI/qml/acl/` | `UI/qml/features/acl/` | Di chuyển nguyên cụm |
| `UI/qml/nat/` | `UI/qml/features/nat/` | Di chuyển nguyên cụm |
| `UI/qml/interface/` | `UI/qml/features/interfaces/` | Chuẩn hóa tên số nhiều |
| `UI/qml/syslog/` | `UI/qml/features/syslog/` | Gom cả workspace/settings |

## 6. Kế hoạch thực hiện chi tiết

### Giai đoạn 0 — Lập đường cơ sở

Mục đích: xác định trạng thái chạy được trước khi di chuyển.

Công việc:

- Tạo nhánh `refactor/app-directory-structure`.
- Ghi lại phiên bản Python, PyQt6 và lệnh chạy chuẩn.
- Chạy toàn bộ test hiện có và lưu kết quả.
- Kiểm tra `python main.py` hoặc `uv run python main.py` mở được cửa sổ chính.
- Lập danh sách import Python bằng `rg`.
- Lập danh sách QML import, URL resource, `Loader.source` và component trong `qmldir`.
- Lập danh sách đường dẫn database, backup, template và icon.
- Tạo `FUNCTION_MAP.md` phiên bản đầu từ code đang chạy.

Đầu ra:

- Baseline test report.
- Danh sách dependency/path cần cập nhật.
- `FUNCTION_MAP.md` trạng thái `Current`.

Tiêu chí hoàn thành:

- Có lệnh tái hiện rõ ràng.
- Biết test nào đang pass/fail trước refactor.
- Không có thay đổi hành vi ứng dụng.

### Giai đoạn 1 — Chuẩn hóa tài liệu và dữ liệu runtime

Công việc:

- Tạo toàn bộ README cấp cao được liệt kê ở mục 8.
- Tạo `ARCHITECTURE_RULES.md`.
- Tạo `app/data/` cho database runtime.
- Cập nhật `.gitignore` cho `.db`, journal, WAL, backup, log và cache.
- Chuẩn hóa hàm resolve path; không phụ thuộc working directory.
- Xác nhận các file SQL trong `UI/` là snapshot legacy trước khi xóa/chuyển.

Tiêu chí hoàn thành:

- Clone mới có thể build database từ schema.
- Xóa database runtime rồi chạy app sẽ tái tạo đúng.
- Không còn đường dẫn tuyệt đối theo máy phát triển.

### Giai đoạn 2 — Tách hạ tầng dùng chung

Công việc:

- Tạo `infrastructure/database/connection.py` và `paths.py`.
- Tạo `infrastructure/network/connector.py`.
- Chuyển `DeviceSessionRegistry` vào `infrastructure/network/session_registry.py`.
- Tạo adapter tương thích để import cũ vẫn chạy trong thời gian chuyển đổi.
- Tách `core/runtime.py` thành các module nhỏ.

Tiêu chí hoàn thành:

- Chỉ có một nguồn đường dẫn database.
- Chỉ có một cơ chế tạo/tái sử dụng session thiết bị.
- QML context property và tên slot chưa thay đổi.

### Giai đoạn 3 — Chuyển Devices và Interfaces

Thứ tự:

1. `features/devices/`.
2. `features/interfaces/`.

Công việc:

- Tách CRUD thiết bị khỏi `core/database.py`.
- Tách import/export danh sách thiết bị.
- Đưa interface repository ra khỏi DHCP.
- Thay stub Interface bằng interface contract rõ ràng.
- Bổ sung test CRUD, validation host và transaction rollback.

Tiêu chí hoàn thành:

- Thêm/sửa/xóa/import thiết bị hoạt động.
- Sidebar vẫn reload đúng.
- Interface load/save/edit/cancel hoạt động độc lập với DHCP.

### Giai đoạn 4 — Chuyển DHCP

Công việc:

- Tạo `features/dhcp/{slots,models,repository,service,worker}.py`.
- Chuyển pool, excluded address và helper address.
- Chuyển template/preview/push DHCP.
- Chuyển QML vào `UI/qml/features/dhcp/`.
- Cập nhật `qmldir`, import và Loader.
- Thêm integration test với SQLite tạm và fake connector.

Tiêu chí hoàn thành:

- Load/save/edit/delete hoạt động.
- Preview không cần kết nối thật.
- Dev mode và push thật giữ nguyên contract.

### Giai đoạn 5 — Chuyển Routing

Thực hiện lần lượt:

1. Static/default route.
2. OSPF.
3. EIGRP.
4. Routing Information.

Công việc:

- Mỗi giao thức có repository/service riêng.
- Dùng worker/push contract chung.
- Template đặt cạnh giao thức.
- Chuẩn hóa kết quả preview/push và lỗi trả về QML.
- Di chuyển QML theo từng subtab, không chuyển cả Routing một lần.

Tiêu chí hoàn thành:

- Mỗi giao thức có unit test normalize và CRUD.
- Preview/push có integration test với fake session.
- `FUNCTION_MAP.md` liệt kê đầy đủ bảng và lệnh show/config.

### Giai đoạn 6 — Chuyển ACL và NAT

Công việc:

- Thay stub bằng repository thật hoặc đánh dấu rõ `planned`.
- Tách ACL dùng cho policy và NAT ACL nhưng dùng model chung khi phù hợp.
- Không để NAT sửa trực tiếp dữ liệu ACL mà không qua service.
- Bổ sung transaction cho bản ghi cha–con.
- Di chuyển QML nguyên cụm sau khi backend ổn định.

Tiêu chí hoàn thành:

- Không còn slot giả trả dữ liệu thành công khi chưa ghi DB.
- Save/delete cha–con có rollback khi lỗi.
- Trạng thái `implemented/partial/planned` trong bản đồ đúng với code.

### Giai đoạn 7 — Bổ sung Switching và Syslog

Switching gồm:

- switchport;
- VLAN/VTP;
- STP;
- EtherChannel;
- port security;
- SVI/L3 switch nếu thuộc phạm vi.

Syslog gồm:

- UDP/TCP listener;
- parser/normalizer;
- batch writer;
- truy vấn/lọc/phân trang;
- cấu hình thiết bị gửi log;
- lifecycle start/stop;
- retention và index database.

Tiêu chí hoàn thành:

- Mỗi module có README và hàng tương ứng trong `FUNCTION_MAP.md`.
- Syslog listener không ghi SQLite trên UI thread.
- Không lưu vô hạn log mà thiếu retention policy.

### Giai đoạn 8 — Dọn compatibility và hoàn tất

Công việc:

- Xóa adapter/import compatibility không còn người dùng.
- Xóa `backend.py` cũ hoặc đổi thành facade có tên rõ ràng.
- Xóa `network_code/` sau khi xác nhận không còn import.
- Xóa snapshot SQL legacy đã được kiểm chứng.
- Chạy formatter, lint, unit, integration và QML smoke test.
- Cập nhật toàn bộ README và sơ đồ ánh xạ.
- Kiểm tra clone sạch trên Windows và Fedora.

Tiêu chí hoàn thành:

- `rg "backend\.|network_code" app` không còn import runtime ngoài whitelist.
- Không có database runtime bị Git theo dõi.
- Tài liệu khớp với code và test.

## 7. Chiến lược commit

Mẫu commit:

```text
docs(app): add refactor plan and feature map
refactor(paths): centralize runtime database paths
refactor(network): extract device session infrastructure
refactor(devices): move device repository and slots
refactor(dhcp): move repository service and workers
refactor(qml): move dhcp views into feature namespace
test(routing): add fake-session integration tests
chore(app): remove legacy compatibility modules
```

Mỗi commit phải:

- chỉ giải quyết một mục tiêu;
- không trộn format toàn dự án với di chuyển file;
- ghi rõ file di chuyển bằng `git mv`;
- cập nhật README/`FUNCTION_MAP.md` nếu contract thay đổi;
- có test phù hợp với mức rủi ro.

## 8. Danh sách `README.md` bắt buộc

### 8.1 README cấp ứng dụng

`app/README.md` phải có:

- tổng quan và phạm vi desktop app;
- yêu cầu môi trường;
- lệnh cài, build DB, chạy và test;
- sơ đồ kiến trúc ngắn;
- danh sách context property QML;
- liên kết đến `FUNCTION_MAP.md` và README thư mục con;
- trạng thái chức năng;
- quy tắc dữ liệu runtime và secret.

### 8.2 README cấp lớp

| File | Nội dung bắt buộc |
|---|---|
| `core/README.md` | Dịch vụ dùng chung, điều gì được/không được đặt trong core |
| `features/README.md` | Mẫu module chức năng, dependency direction, naming |
| `infrastructure/README.md` | Adapter DB/network, quy tắc không chứa nghiệp vụ |
| `infrastructure/database/README.md` | DB authority, schema, migration, builder, runtime files |
| `infrastructure/network/README.md` | Connector, session lifecycle, timeout, lỗi, bảo mật |
| `UI/README.md` | QML module, `qmldir`, component, Loader, theme, resource |
| `scripts/README.md` | Mục đích, cách chạy và tính an toàn/idempotent của script |
| `data/README.md` | File runtime, cách tái tạo, backup/retention, không commit |
| `templates/README.md` | Template import và template cấu hình, format/version |
| `tests/README.md` | Test layout, fixture, fake connector, cách chạy |

### 8.3 README cho từng chức năng

Tối thiểu tạo:

```text
features/devices/README.md
features/interfaces/README.md
features/dhcp/README.md
features/routing/README.md
features/routing/static/README.md
features/routing/ospf/README.md
features/routing/eigrp/README.md
features/acl/README.md
features/nat/README.md
features/switching/README.md
features/syslog/README.md
```

Mỗi README chức năng phải trả lời:

1. Chức năng giải quyết vấn đề gì?
2. Trạng thái: `implemented`, `partial`, `stub`, hay `planned`?
3. QML entry và component liên quan là gì?
4. Public slot/signal nào được QML sử dụng?
5. Service/use case nào tồn tại?
6. Repository đọc/ghi bảng nào?
7. Worker chạy lệnh hoặc giao thức nào?
8. Model và quy tắc validation là gì?
9. Luồng Load/Save/Edit/Cancel/View/Push hoạt động ra sao?
10. Test nào bảo vệ module?
11. Hạn chế, rủi ro và backlog còn lại là gì?

## 9. Mẫu `README.md` cho thư mục chức năng

```markdown
# <Tên chức năng>

## Phạm vi

Mô tả ngắn chức năng và những nội dung không thuộc phạm vi.

## Trạng thái

- Mức độ: implemented | partial | stub | planned
- Người/phần phụ trách:
- Cập nhật gần nhất:

## Cấu trúc

| File/thư mục | Vai trò |
|---|---|
| `slots.py` | API QObject cho QML |
| `service.py` | Điều phối use case |
| `repository.py` | CRUD SQLite |
| `worker.py` | Preview/push/sync thiết bị |

## Luồng dữ liệu

QML → slot → service → repository/worker.

## Public API cho QML

| Slot/signal | Input | Output | Lỗi |
|---|---|---|---|

## Database

| Bảng | Đọc | Ghi | Khóa/quan hệ |
|---|---:|---:|---|

## Thiết bị mạng

| Nghiệp vụ | Lệnh show | Lệnh cấu hình | Giao thức |
|---|---|---|---|

## Validation

- Các quy tắc dữ liệu.
- Transaction và rollback.

## Kiểm thử

- Unit test.
- Integration test.
- QML smoke test.

## Hạn chế và backlog

- Các phần chưa triển khai hoặc rủi ro đã biết.
```

## 10. Đặc tả `FUNCTION_MAP.md`

Tạo file `app/FUNCTION_MAP.md` làm nguồn tra cứu trung tâm. File không thay thế README chức năng; nó cung cấp ánh xạ ngang toàn ứng dụng.

### 10.1 Bảng tổng quan chức năng

| Feature | Device role | Trạng thái | QML entry | Python slot | Service | Repository | Worker | DB |
|---|---|---|---|---|---|---|---|---|
| Devices | all | implemented | `...` | `...` | `...` | `...` | `...` | `device_network` |
| Interfaces | rou/sw2/sw3 | partial | `...` | `...` | `...` | `...` | planned | `device_network` |
| DHCP | rou/sw3 | implemented | `...` | `...` | `...` | `...` | `...` | `device_network` |

### 10.2 Ánh xạ UI → Python

| QML file/component | Action | Context object | Slot/signal | Python implementation | Async? |
|---|---|---|---|---|---:|

### 10.3 Ánh xạ Python → database

| Feature | Repository method | Database | Tables | Operation | Transaction |
|---|---|---|---|---|---:|

### 10.4 Ánh xạ cấu hình thiết bị

| Feature | Vendor/OS | Collect/show command | Config template/command | Parser | Worker |
|---|---|---|---|---|---|

### 10.5 Ánh xạ theo vai trò thiết bị

| Feature | Router | Switch L2 | Switch L3 | Điều kiện hiển thị |
|---|---:|---:|---:|---|

### 10.6 Ma trận thao tác giao diện

| Feature | Load | Save | Edit | Cancel | Delete | View | Push | Sync |
|---|---:|---:|---:|---:|---:|---:|---:|---:|

Quy ước giá trị:

- `✅`: đã triển khai và có test;
- `🟡`: triển khai một phần hoặc thiếu test;
- `⚪`: đang dùng stub;
- `—`: không áp dụng;
- `📌`: đã có kế hoạch nhưng chưa code.

### 10.7 Dependency và ownership

| Module | Được phép import | Không được import | Owner | Test chính |
|---|---|---|---|---|

### 10.8 Known gaps

Mỗi mục phải có:

- mã định danh;
- feature;
- mô tả thiếu sót;
- mức độ ảnh hưởng;
- file liên quan;
- kế hoạch xử lý;
- trạng thái.

## 11. Quy tắc cập nhật tài liệu

- Thêm feature mới: cập nhật `features/<feature>/README.md` và `FUNCTION_MAP.md` trong cùng PR.
- Thêm/xóa/đổi tên slot: cập nhật bảng Public API.
- Thay đổi bảng hoặc cột: cập nhật README database, feature README và function map.
- Thay đổi lệnh show/config: cập nhật ánh xạ thiết bị và test worker/parser.
- Di chuyển QML: cập nhật `UI/README.md`, `qmldir` và UI → Python map.
- Chuyển trạng thái từ stub sang thật: cập nhật trạng thái và ma trận thao tác.
- README không được khẳng định chức năng đã hoàn thành nếu chưa có code/test chứng minh.

## 12. Kiểm tra tự động tài liệu và cấu trúc

Tạo `scripts/validate_structure.py` để kiểm tra tối thiểu:

- mỗi thư mục feature có `README.md`;
- mọi QML public component có khai báo phù hợp trong `qmldir`;
- đường dẫn trong `FUNCTION_MAP.md` tồn tại;
- không commit `.db`, `.db-wal`, `.db-shm`;
- không có import từ thư mục legacy sau khi đã đóng giai đoạn;
- không có absolute path Windows/Linux trong runtime code;
- feature status hợp lệ: `implemented|partial|stub|planned`.

Có thể chạy trong CI:

```bash
uv run python scripts/validate_structure.py
uv run python -m unittest discover -s tests
```

## 13. Kiểm thử sau mỗi lần di chuyển

Checklist tối thiểu:

- [ ] Import toàn bộ module Python thành công.
- [ ] `main.py` load được module QML `UI/Main`.
- [ ] Không có lỗi `module ... is not installed` hoặc component unavailable.
- [ ] Icon/resource được resolve đúng trên Windows và Fedora.
- [ ] Database được tạo từ schema ở vị trí mới.
- [ ] CRUD feature đang chuyển hoạt động với database tạm.
- [ ] Session thiết bị được đóng khi đóng tab.
- [ ] Dev mode không mở kết nối thật.
- [ ] Preview không ghi sai trạng thái DB.
- [ ] Push chạy nền, không khóa UI thread.
- [ ] README và `FUNCTION_MAP.md` đã cập nhật.

## 14. Rủi ro và biện pháp giảm thiểu

| Rủi ro | Ảnh hưởng | Biện pháp |
|---|---|---|
| Hỏng Python import | App không khởi động | Adapter compatibility, chuyển từng feature |
| Hỏng `qmldir`/QML import | UI không load | Di chuyển từng cụm và chạy QML smoke test |
| Sai path database | Tạo DB ở nhầm nơi | Một module `paths.py`, test từ working directory khác |
| Mất dữ liệu runtime | Mất cấu hình người dùng | Backup DB trước migration, không xóa tự động |
| Trộn refactor với sửa nghiệp vụ | Khó review/rollback | Commit nhỏ, không đổi hành vi trong move commit |
| README nhanh lỗi thời | Tài liệu gây hiểu nhầm | Validate đường dẫn trong CI, cập nhật cùng PR |
| Trùng trách nhiệm feature | Coupling quay trở lại | Quy tắc dependency và owner trong function map |

## 15. Definition of Done toàn bộ kế hoạch

- [ ] Cấu trúc đích đã được áp dụng hoặc mọi ngoại lệ đều được ghi rõ.
- [ ] Không còn code runtime phụ thuộc `network_code/` legacy.
- [ ] `core/database.py` không còn là nơi chứa toàn bộ nghiệp vụ.
- [ ] Mỗi feature có README đầy đủ.
- [ ] `FUNCTION_MAP.md` ánh xạ UI, Python, DB và thiết bị.
- [ ] Có unit test cho repository/service quan trọng.
- [ ] Có integration test cho DB và fake connector.
- [ ] Có QML smoke test cho màn hình chính và feature view.
- [ ] Build database chạy được trên clone sạch.
- [ ] Ứng dụng chạy được trên Windows và Fedora.
- [ ] Không commit secret, database runtime, backup hoặc log.
- [ ] Tất cả compatibility wrapper đã xóa hoặc có ngày loại bỏ.

## 16. Thứ tự ưu tiên đề xuất

```text
Documentation/Baseline
→ Runtime paths
→ Network infrastructure
→ Devices
→ Interfaces
→ DHCP
→ Static Routing
→ OSPF
→ EIGRP
→ ACL
→ NAT
→ Switching
→ Syslog
→ Legacy cleanup
```

Thứ tự này ưu tiên các nền tảng được nhiều chức năng dùng chung, đồng thời để ACL/NAT và các phần đang stub sau các module đã có backend thực nhằm giảm rủi ro khi vừa di chuyển vừa hoàn thiện nghiệp vụ.
