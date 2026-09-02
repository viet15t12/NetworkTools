# Bản đồ tài liệu repository

Cập nhật: **2026-08-16**. Đây là điểm bắt đầu để chọn đúng tài liệu và tránh dùng
nhầm kế hoạch lịch sử hoặc tài liệu của mã bên thứ ba.

## Đọc theo nhu cầu

| Nhu cầu | Tài liệu chính |
| --- | --- |
| Cài đặt và chạy nhanh | [`../README.md`](../README.md), [`USAGE_GUIDE.md`](USAGE_GUIDE.md) |
| Biết app đang làm được gì | [`CURRENT_APP_FEATURES.md`](CURRENT_APP_FEATURES.md) |
| Hiểu kiến trúc và thư mục | [`ARCHITECTURE.md`](ARCHITECTURE.md), [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) |
| Làm việc với database | [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md), [`../app/SCHEMA_LOGIC.md`](../app/SCHEMA_LOGIC.md) |
| Phát triển QML/UI | [`UI_COMPONENTS.md`](UI_COMPONENTS.md), [`../app/UI/README.md`](../app/UI/README.md) |
| Viết hoặc review code | [`CODING_STANDARDS.md`](CODING_STANDARDS.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Vận hành Syslog | [`SYSTEM_LOGS.md`](SYSTEM_LOGS.md) |
| Vận hành SFTP | [`SFTP.md`](SFTP.md) |
| Terminal companion | [`decisions/0001-external-cams-terminal.md`](decisions/0001-external-cams-terminal.md), [`../app/features/terminal/README.md`](../app/features/terminal/README.md) |
| Xem rủi ro và mức kiểm chứng | [`CODE_AUDIT.md`](CODE_AUDIT.md), [`BACKEND_APP_PARITY.md`](BACKEND_APP_PARITY.md) |
| Kế hoạch phát triển | [`../ROADMAP.md`](../ROADMAP.md), [`plan/`](plan/) |

## Phân loại tài liệu

### Tài liệu cấp repository

- `README.md` và `README.en.md`: giới thiệu, quick start và giới hạn sản phẩm.
- `CHANGELOG.md`: thay đổi đã tích hợp; không dùng thay roadmap.
- `ROADMAP.md`: mục tiêu tương lai; không mô tả mục chưa hoàn thành như tính năng
  hiện có.
- `CONTRIBUTING.md`, `AUTHORS.md`: quy trình đóng góp và ghi nhận tác giả.

### Tài liệu runtime desktop

- `app/README.md`: entry point, bootstrap, context property và ranh giới package.
- `app/ARCHITECTURE_RULES.md`: quy tắc phụ thuộc bắt buộc.
- `app/SCHEMA_LOGIC.md`: lifecycle trạng thái và quy ước ghi database.
- `app/features/*/README.md`: phạm vi, owner, dữ liệu, luồng và giới hạn của từng
  feature.
- `app/infrastructure/*/README.md`, `app/core/README.md`, `app/UI/README.md`:
  contract theo layer.
- `app/tests/README.md`: cách chạy và cách hiểu kết quả test.

### Tài liệu chuyên đề

- `resources/`: inventory và quy tắc bảo trì SVG/icon.
- `ui-improvement/`: contract UI đã được áp dụng; progress/plan hoàn tất được
  loại bỏ để tránh trở thành nguồn sự thật song song.
- `decisions/`: quyết định kiến trúc đã được chấp nhận.
- `plan/`: chỉ giữ kế hoạch còn mở; phải ghi rõ trạng thái và ngày đối chiếu.

### Mã kế thừa và bên thứ ba

- `backend/README.md`: ranh giới, cách nghiên cứu và cảnh báo của subsystem cũ.
- `app/vendor/README.md`: provenance, build và cập nhật mã vendored.
- Markdown bên trong `app/vendor/alacritty/` thuộc upstream Alacritty. Không dùng
  chúng làm tài liệu CAMS và không viết lại trừ khi cập nhật snapshot
  upstream/fork có chủ đích.
- `app/qtpyTerminal-main/README.md` mô tả adapter tương thích cũ, không phải
  terminal runtime hiện hành.

## Quy tắc duy trì

Khi thay đổi hành vi, cập nhật theo thứ tự: README feature → tài liệu chuyên đề
liên quan → `CURRENT_APP_FEATURES.md`/`ARCHITECTURE.md` nếu claim cấp ứng dụng thay
đổi → `CHANGELOG.md`. Đường dẫn, tên bảng, tên test và trạng thái `implemented` /
`partial` phải được kiểm tra từ source hiện tại; không sao chép từ tài liệu kế
thừa.
