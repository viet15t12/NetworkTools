# Cấu trúc dự án CAMS

Cập nhật: **2026-09-04**. Runtime desktop nằm trực tiếp ở root; mã kế thừa nằm
trong `archive/`, dữ liệu mẫu trong `examples/`, còn `vendor/` là mã bên thứ ba/fork.

## 1. Cây repository

```text
CAMS-main/
├── README.md / README.en.md
├── main.py / app_facade.py       # Composition root và public bootstrap exports
├── pyproject.toml / uv.lock      # Python dependency lock
├── core/ / domain/ / features/   # Contract và nghiệp vụ ứng dụng
├── infrastructure/               # SQLite/network/system/workspace adapters
├── UI/                           # QML module, component, theme và resource
├── scripts/ / tests/             # Build, validation và test suite
├── templates/ / data/            # Template và runtime data mặc định
├── vendor/alacritty/             # Fork terminal companion bằng Rust
├── install.sh / uninstall.sh     # Cài/gỡ ứng dụng user-local trên Linux
├── packaging/                    # Launcher/tài nguyên đóng gói
├── archive/                      # FastAPI và worker/SQL kế thừa
├── docs/                         # Tài liệu chuẩn, ADR, plan và resource inventory
│   └── research/                 # Báo cáo và sách Typst
├── examples/mock/                # Payload/config thủ công, không phải authority
├── licenses/                     # Notice/license tài nguyên và dependency
└── qtpyTerminal-main/            # Compatibility adapter không active
```

## 2. Runtime ở root theo layer

| Đường dẫn | Owner | Ví dụ |
| --- | --- | --- |
| `UI/` | Presentation | `Welcome`, `Main`, feature views, standard controls |
| `core/` | QML bridge và lifecycle cấp app | `DatabaseManager`, `TerminalHelper`, settings, tasks |
| `features/` | Use case/validation/repository/worker | devices, routing, FHRP, SFTP, Syslog, terminal |
| `domain/` | Kiểu dùng chung | `ConnectionStatus`, `SyncStatus` |
| `infrastructure/database/` | DB path, connection, health và schema | 73 + 20 bảng canonical |
| `infrastructure/network/` | Transport/session/concurrency | Netmiko connector, registry, runner, batch |
| `infrastructure/system/` | Probe hệ điều hành | desktop environment, network, VM/lab, RAM |
| `infrastructure/workspace/` | Project package | crypto, package, save, staging, snapshot |

Dependency chuẩn là `QML → core slot → feature → infrastructure`. Không đặt SQL
hoặc lệnh thiết bị trong QML; không tạo session cache riêng trong feature.

## 3. Feature map

```text
features/
├── devices/          inventory, login, batch, running/save config, sync
├── interfaces/       Router Interface desired state và View & Push
├── routing/          static/default, OSPF, EIGRP và Routing Group
├── fhrp/             HSRP, VRRP, GLBP đa member
├── dhcp/ acl/ nat/   dịch vụ mạng và security
├── switching/        VLAN, port, STP, VTP, security, SVI, pull/push
├── config_backup/    Dulwich running-config history
├── config_sync/      policy role/change/conflict
├── syslog/           listener, parser, repository và device configurator
├── sftp/             client hai panel và transfer queue
├── terminal/         companion lifecycle và NTTP/1
└── external_tools/   catalog feature marker; QObject chính còn ở core
```

Mỗi feature README ghi trạng thái, owner, DB/transport và giới hạn. Danh sách
capability cấp người dùng nằm tại
[`CURRENT_APP_FEATURES.md`](CURRENT_APP_FEATURES.md).

## 4. QML module

`UI/qmldir` là manifest component công khai. Cấu trúc:

```text
UI/
├── qml/app/          Welcome/Main, menu và window state
├── qml/content/      router nội dung, settings, information, DB browser
├── qml/features/     ACL, DHCP, FHRP, Interface, NAT, Routing, Switching, Syslog
├── qml/sftp/         workspace/client SFTP
├── qml/devices/      device tabs
├── qml/layout/       ActivityBar và StatusBar
├── qml/panels/       Devices/Settings/DB/SFTP/Syslog sidebar
├── qml/sidebar/      item, context menu và form thiết bị
├── qml/shared/       command registry, dialog, notification, View & Push
├── components/       base/layout/standard/table primitives
├── theme/            state và design tokens
└── resources/        icon/logo với path tập trung ở AppAssets
```

View nặng được lazy-load và giữ instance khi phù hợp. QML test harness nằm trong
`tests/qml/`; test Python khóa qmldir, object contract và null-backend load.

## 5. Source of truth

| Câu hỏi | Nguồn ưu tiên |
| --- | --- |
| App khởi tạo gì? | `main.py`, `app_facade.py` |
| QML được phép gọi gì? | `UI/qmldir`, context properties và slot/signal Python |
| Nghiệp vụ làm gì? | `features/<feature>/` và test liên quan |
| Bảng/constraint nào tồn tại? | `infrastructure/database/schemas/` |
| Path/network/session do ai sở hữu? | `infrastructure/` |
| Tính năng người dùng hiện có? | `docs/CURRENT_APP_FEATURES.md` |
| Tài liệu nào dùng cho việc gì? | `docs/README.md` |

Mã trong `archive/backend/` hoặc `examples/mock/` không được dùng để nâng claim
desktop nếu chưa có composition, UI/service và test trong runtime ở root.

## 6. Artifact không commit

`.venv`, `data/*.db*`, backup/running-config, project `.ntp`, log, cache, compiled
Cython extension, `vendor/alacritty/target`, credential và private key là runtime
hoặc build artifact. Không thêm chúng bằng force. Xem `.gitignore` và chạy
`scripts/validate_structure.py` trước khi commit.
