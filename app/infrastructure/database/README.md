# Database infrastructure

Cập nhật: **2026-08-16**. `paths.py` là nguồn path duy nhất. Schema chuẩn ở
`schemas/device_network` (74 bảng) và `schemas/info_collected` (19 bảng); builder
đọc trực tiếp file `.sql` theo thứ tự tên, không tạo aggregate SQL. DB runtime ở
`data/` hoặc `CAMS_DATA_DIR`.

Chạy `uv run python scripts/build_databases.py` chỉ khi muốn build sạch; builder
ghi database tạm, kiểm tra integrity/foreign key rồi thay atomically. Startup dùng
`ensure_runtime_databases()` để tạo file thiếu, migrate trạng thái số legacy và
bổ sung object thiếu mà không xóa dữ liệu. Migration có version trong tương lai
đặt ở `migrations/`. Chi tiết: [`../../../docs/DATABASE_SCHEMA.md`](../../../docs/DATABASE_SCHEMA.md).
