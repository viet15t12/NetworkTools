<!-- markdownlint-disable MD033 MD041 -->
[English](README.en.md) | [Tiếng Việt](README.md)
<div align="center">
  <img src="UI/resources/brand/logo_readme.svg" alt="CAMS logo" width="144">

  <img src="UI/resources/brand/name.svg" alt="CAMS name">

  <p><strong>Nền tảng desktop quản lý, cấu hình và giám sát thiết bị mạng tập trung.</strong></p>

  <p><a href="https://github.com/viet15t12/CAMS.git">Kho mã nguồn chính thức</a></p>

  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-%E2%89%A53.11-3776AB?logo=python&logoColor=white">
    <img alt="PyQt6" src="https://img.shields.io/badge/UI-PyQt6%20%2B%20QML-41CD52?logo=qt&logoColor=white">
    <img alt="SQLCipher" src="https://img.shields.io/badge/Database-SQLCipher-003B57?logo=sqlite&logoColor=white">
    <img alt="Status" src="https://img.shields.io/badge/Status-Development-F59E0B">
  </p>
</div>

<img src="UI/resources/brand/stats-dark.svg" alt="stats-dark">

## Tổng quan

CAMS cung cấp một giao diện thống nhất để quản lý inventory, theo dõi trạng thái và xây dựng cấu hình cho router, switch cùng các dịch vụ mạng. Ứng dụng kết hợp giao diện Qt Quick/QML với backend Python, lưu dữ liệu cục bộ bằng SQLCipher và giao tiếp với thiết bị qua SSH/Telnet.

Dự án được phát triển trong khuôn khổ nghiên cứu:

> Nghiên cứu và xây dựng hệ thống quản lý tập trung, tự động hóa cấu hình và giám sát an ninh mạng.

## Tính năng chính

| Nhóm tính năng | Khả năng |
| --- | --- |
| Quản lý thiết bị | Thêm, sửa, xóa, nhập hàng loạt, ping, kết nối/đồng bộ đồng thời nhiều host |
| Cấu hình mạng | DHCP, ACL, NAT, Router Interface View & Push, static route, OSPF và EIGRP |
| Switching | Quản lý switchport, VLAN, SVI/L3, View & Push và pull-sync VLAN/interface/EtherChannel/VTP Cisco IOS |
| Terminal & phiên kết nối | Mở CLI, quản lý vòng đời session, chạy lệnh và lưu running-config thành startup-config |
| Sao lưu cấu hình | Lưu lịch sử running-config theo thiết bị bằng Dulwich |
| System Logs | Nhận, lọc và lưu Syslog qua UDP/TCP |
| Device Logs | Bắt và phân tích lưu lượng với TShark trong môi trường được cấp quyền |
| SFTP | Duyệt file, upload/download và theo dõi hàng đợi truyền file |
| Công cụ ngoài | Tích hợp SSH client, terminal và trình duyệt SQLite trên máy người dùng |
| Project/workspace | Package `.ntp`, mã hóa tùy chọn, snapshot và rollback |

> Một số luồng cấu hình phụ thuộc vendor, protocol và thiết bị lab. Luôn xem trước lệnh và thử nghiệm trong dev-mode trước khi đẩy cấu hình lên thiết bị thật.

## Yêu cầu hệ thống

- Python **3.11 trở lên**;
- [`uv`](https://docs.astral.sh/uv/) để quản lý môi trường và dependency;
- Windows là nền tảng phát triển chính; Linux cần có đầy đủ thư viện Qt tương ứng;
- TShark/Wireshark nếu sử dụng tính năng Device Logs;
- quyền truy cập hợp lệ tới thiết bị mạng khi sử dụng kết nối thật.

## Cài đặt, cập nhật và gỡ CAMS trên Linux

### Cài đặt lần đầu

```bash
git clone https://github.com/viet15t12/CAMS.git
cd CAMS
./install.sh
```

Sau lần cài đầu tiên, mở **CAMS** từ menu ứng dụng hoặc chạy `cams` ở terminal;
không cần vào lại repository hay gọi `cams.sh run`. Bộ cài đặt user-local không
cần `sudo`, lưu chương trình tại `~/.local/share/cams/app`, tạo launcher trong
`~/.local/bin` và giữ database người dùng riêng tại `~/.local/share/cams/data`.

### Cập nhật

Trong CAMS, mở **Settings → Cập nhật phần mềm** rồi chọn **Kiểm tra và cập
nhật**. Khi hoàn tất, khởi động lại ứng dụng để dùng phiên bản mới.

Hoặc cập nhật từ terminal bằng một lệnh:

```bash
~/.local/share/cams/app/update.sh --update
```

Với repository dùng để phát triển, vẫn có thể cập nhật thủ công:

Mở terminal tại repository đã clone, tải mã mới rồi chạy lại bộ cài:

```bash
cd /duong/dan/toi/CAMS
git pull --ff-only
./install.sh
```

Bộ cài chỉ thay thế file chương trình và giữ nguyên database, workspace cùng
thiết lập người dùng trong `~/.local/share/cams/data`. Sau khi cập nhật, tiếp tục
mở CAMS từ menu ứng dụng hoặc bằng lệnh `cams`.

### Gỡ cài đặt

Từ repository CAMS, chạy:

```bash
./uninstall.sh
```

Lệnh trên gỡ chương trình, launcher và icon nhưng giữ dữ liệu người dùng. Muốn
xóa luôn database và thiết lập cục bộ, chạy:

```bash
./uninstall.sh --purge-data
```

Không thể khôi phục dữ liệu đã xóa bằng tùy chọn `--purge-data` nếu không có bản
sao lưu.

### Chạy trực tiếp để phát triển

```bash
./cams.sh setup
./cams.sh run
```

Các lệnh phát triển chạy ngay từ root. `uv` tạo môi trường từ `pyproject.toml`
và `uv.lock`; có thể đặt `CAMS_DATA_DIR` để dùng vị trí dữ liệu khác.

## Hướng dẫn sử dụng

### Thêm và kết nối thiết bị

1. Mở khu vực **Devices** và chọn **Add Device** hoặc nhấn `Ctrl+N`.
2. Nhập địa chỉ host, protocol, port, tài khoản đăng nhập, hệ điều hành và vai trò thiết bị.
3. Lưu thiết bị; trạng thái ban đầu là `Waiting`/`Pending`.
4. Mở menu ngữ cảnh của thiết bị để **Ping**, **Connect**, **Reconnect**, lấy
   **Running Config**, **Save configuration** vào startup-config hoặc mở **CLI**.
   Có thể chọn **Connect All Waiting** từ menu nhóm để chạy các kết nối host độc
   lập và đồng thời.
5. Chỉ lưu credential dùng cho môi trường lab và không commit database runtime lên Git.

### Thử nghiệm bằng dev-mode

1. Thêm một thiết bị giả với thông tin lab.
2. Khi thiết bị ở trạng thái `Waiting`, chọn **Up (Dev)**.
3. Tạo hoặc chỉnh sửa cấu hình cục bộ.
4. Dùng **View & Push** để xem trước kết quả trước khi thực hiện trên thiết bị thật.

Dev-mode mô phỏng push cho Routing, DHCP, ACL và NAT. Interface, FHRP,
Switching, Syslog device configuration, SFTP và terminal không tự động kế thừa
cơ chế này; không nên xem dev-mode là lớp bảo vệ duy nhất.

### Tạo và triển khai cấu hình

1. Chọn thiết bị đang hoạt động.
2. Mở feature cần cấu hình: Routing, DHCP, ACL, NAT, Interface hoặc Switching.
3. Nhập dữ liệu và lưu cấu hình cục bộ.
4. Kiểm tra phần preview, host đích, vendor và protocol.
5. Sao lưu running-config trước khi chọn **Push**.
6. Theo dõi trạng thái tác vụ và kiểm tra lại cấu hình trên thiết bị sau khi hoàn tất.

Switch Layer 2 dùng cùng luồng View & Push cho VLAN, switch port/EtherChannel,
STP, VTP và L2 Security qua SSH/Telnet. App chỉ đánh dấu từng module đã đồng bộ
sau khi thiết bị chấp nhận lệnh. Xem giới hạn an toàn tại
[`features/switching/INTEGRATION_LIMITATIONS.md`](features/switching/INTEGRATION_LIMITATIONS.md).

Router Interface View & Push hỗ trợ Cisco IOS qua SSH/Telnet cho Physical/L3/WAN,
Loopback, Tunnel và 802.1Q Subinterface. Physical chỉ được chỉnh sửa khi đã có từ
dữ liệu thiết bị; backend chỉ cho tạo/xóa interface ảo. Preview che mật khẩu PPP và app chỉ
đánh dấu row đã áp dụng sau khi thiết bị chấp nhận batch lệnh. RESTCONF/NETCONF,
IPv6, verify và rollback tự động chưa được tích hợp; xem chi tiết tại
[`features/interfaces/README.md`](features/interfaces/README.md).

Config Backup lưu lịch sử Git nội bộ bằng Dulwich trong thư mục
`.cams-git`. Khi lưu workspace, layout `.git` cũ được migrate trong staging
để `.ntp` tiếp tục cấm metadata Git chuẩn nhưng vẫn bảo toàn toàn bộ lịch sử.

### Syslog, Device Logs và SFTP

- **System Logs:** cấu hình listener trong **Settings → System Logs**, xác thực bind address/port rồi khởi động listener từ Activity Bar.
- **Device Logs:** chọn capture interface và filter trước khi bắt gói; chỉ sử dụng trên mạng mà bạn được phép giám sát.
- **SFTP:** xác minh fingerprint SHA-256 của máy chủ trước khi chấp nhận kết nối
  và truyền file; xem [tài liệu SFTP](docs/SFTP.md).

Hướng dẫn chi tiết cho từng màn hình nằm trong [docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md). Danh sách phím tắt nằm tại [docs/SHORTCUTS.md](docs/SHORTCUTS.md).

## Kiến trúc

```text
QML / Qt Quick
      │
      ▼
Core facade & context properties
      │
      ▼
Feature services / repositories / workers
      │
      ├── SQLite
      └── Network adapters ──► Thiết bị
```

| Đường dẫn | Vai trò |
| --- | --- |
| `UI/`, `core/`, `features/` | Giao diện, facade và nghiệp vụ của ứng dụng |
| `infrastructure/` | Adapter cơ sở dữ liệu, hệ thống và kết nối mạng |
| `scripts/`, `tests/` | Công cụ build/kiểm tra và test suite |
| `archive/backend/` | Mã thử nghiệm/kế thừa, không được composition root desktop nạp |
| `docs/` | Tài liệu sử dụng, kiến trúc và quy ước kỹ thuật |
| `docs/research/` | Báo cáo và sách Typst, tách khỏi runtime |
| `packaging/` | Launcher và tài nguyên đóng gói ứng dụng |

Đọc thêm tại [Kiến trúc hệ thống](docs/ARCHITECTURE.md) và [Cấu trúc dự án](docs/PROJECT_STRUCTURE.md).

## Kiểm thử và kiểm tra chất lượng

Chạy các lệnh sau từ root repository:

```bash
uv run python scripts/validate_structure.py
uv run python -m compileall .
uv run python -m unittest discover -s tests -v
```

Database runtime, log, cache, credential, private key và backup cục bộ không được đưa vào commit.

CAMS sử dụng SQLCipher Community Edition để mã hóa database. SQLCipher là
Copyright (c) 2008-2026, ZETETIC, LLC và được phân phối theo giấy phép BSD;
toàn văn giấy phép có trong `UI/resources/licenses/SQLCIPHER.txt` và màn hình
About của ứng dụng.

## Tài liệu

- [Bản đồ và mục đích tài liệu](docs/README.md)
- [Hướng dẫn sử dụng](docs/USAGE_GUIDE.md)
- [Kiến trúc kỹ thuật](docs/ARCHITECTURE.md)
- [Cấu trúc thư mục](docs/PROJECT_STRUCTURE.md)
- [Cơ sở dữ liệu](docs/DATABASE_SCHEMA.md)
- [Thành phần giao diện](docs/UI_COMPONENTS.md)
- [System Logs](docs/SYSTEM_LOGS.md)
- [SFTP](docs/SFTP.md)
- [Phím tắt](docs/SHORTCUTS.md)
- [Báo cáo kiểm tra mã nguồn](docs/CODE_AUDIT.md)
- [Chức năng app hiện có](docs/CURRENT_APP_FEATURES.md)
- [Đối chiếu backend và app](docs/BACKEND_APP_PARITY.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [Hướng dẫn đóng góp](CONTRIBUTING.md)
- [Quy tắc lập trình](docs/CODING_STANDARDS.md)
- [Tác giả và thành viên nghiên cứu](AUTHORS.md)

## An toàn vận hành

- Chỉ kết nối, bắt gói và thay đổi cấu hình trên hệ thống mà bạn được cấp quyền.
- Không đặt mật khẩu trong command-line argument, log, ảnh chụp hoặc commit.
- Luôn sao lưu cấu hình và database trước khi rebuild hoặc push.
- Xác minh thiết bị đích, nội dung preview và trạng thái dev-mode trước mọi thao tác triển khai.
- Không mở API, Syslog listener hoặc database ra mạng công cộng khi chưa có lớp xác thực và kiểm soát truy cập phù hợp.

## Trạng thái dự án

CAMS đang trong giai đoạn phát triển và kiểm chứng trong môi trường nghiên cứu/lab. API, một số worker backend và một số luồng View & Push vẫn đang được hoàn thiện; không nên sử dụng như một hệ thống production khi chưa có kiểm thử tích hợp trên hạ tầng mục tiêu.
