# Runtime data

Trạng thái: **implemented**. Thư mục này là vị trí mặc định cho database runtime
`device_network.db`, `info_collected.db` và `app_state.db`. Có thể đổi vị trí
bằng biến `CAMS_DATA_DIR`.

Chỉ file README được theo dõi. Không commit database, `-wal`, `-shm`, journal,
workspace đã giải nén, credential hoặc dữ liệu thiết bị. Database được tạo và
bổ sung schema không phá hủy khi app khởi động; dùng
`scripts/build_databases.py` chỉ khi chủ động tạo lại database từ schema sạch.
