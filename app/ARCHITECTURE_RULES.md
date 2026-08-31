# Quy tắc kiến trúc CAMS

Cập nhật: **2026-08-16**.

Luồng phụ thuộc chuẩn là `QML → slots → service → repository/worker`. Repository chỉ làm việc với SQLite; worker chỉ làm việc với thiết bị qua `infrastructure/network`; service điều phối và validation.

- `core` chỉ chứa dịch vụ dùng chung, không chứa nghiệp vụ feature mới.
- `features` sở hữu QML contract, nghiệp vụ, persistence và worker của từng chức năng.
- `infrastructure` không import QML hoặc chứa chính sách nghiệp vụ.
- QML không chứa SQL và không gọi worker trực tiếp.
- Mọi path runtime lấy từ `infrastructure.database.paths`, không phụ thuộc working directory.
- DB, WAL, journal, backup, log, cache và secret không được commit.
- Thay đổi contract phải cập nhật README feature và tài liệu cấp ứng dụng liên
  quan trong `docs/`; xem bản đồ tại `docs/README.md`.

Adapter legacy chỉ được tồn tại khi có consumer, phải được đánh dấu và xóa sau khi consumer cuối cùng chuyển đổi.
