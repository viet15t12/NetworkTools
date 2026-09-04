# Devices

## Phạm vi và trạng thái

Quản lý inventory, credential metadata, vai trò, import/export, Connect/Get/Save
running-config và batch nhiều thiết bị. **partial**: CRUD/import QML còn trong
facade/mixin `core/database/`. Đối chiếu: **2026-08-18**.

## Contract và dữ liệu

- QML: `qml/sidebar/new_device`, `qml/panels/DevicesPanel.qml`, `qml/devices`.
- API: add/update/delete/list/import/export và signal reload của `DatabaseManager`; terminal nhận `DeviceLoginService`/`DeviceService` qua composition root. `DeviceRepository.get_role()` là contract đọc role cho policy đồng bộ running-config.

`role` là nguồn phân loại duy nhất (`rou`, `sw2`, `sw3`). `device_type` được
giữ như cột tương thích và luôn suy ra từ role (`rou → router`); startup chuẩn
hóa an toàn các bản ghi legacy đã nhận dạng được.
- Database: đọc/ghi `t01_devices`; host phải không rỗng/duy nhất, port hợp lệ; thao tác batch phải transaction/rollback.
- `connection_service.py`: mở/reuse session, lấy snapshot, backup/sync và giữ
  đăng nhập sau Connect.
- `running_config_service.py`: thu thập snapshot qua registry dùng chung, không
  tự tạo connector tạm.
- `sync/`: phân loại riêng Physical/L3, Tunnel, WAN và Subinterface; snapshot
  quan sát không biến child profile đã biến mất thành tác vụ push ngược lại
  thiết bị.
- `save_config_service.py`: lưu running-config thành startup-config qua capability
  `save_config` của session SSH/Telnet đang mở; không tự kết nối và không fallback
  sang shell/command tùy ý.
- `post_push_service.py`: sau một Push có thay đổi và thành công, chạy đúng lệnh
  `copy running-config startup-config`, thu thập một snapshot mới, backup rồi
  force-sync DB. Toàn bộ chuỗi Push/copy/collect giữ cùng khóa session theo host;
  lỗi hậu-push được trả theo stage và không làm giao diện chờ trên main thread.
- `batch_service.py`: chuẩn hóa/deduplicate host, quản lý batch ID/cancel và tổng
  hợp partial failure. Concurrency thực thi bởi
  `infrastructure.network.batch_executor.BatchExecutor`.
- Slot một host cũ vẫn được giữ trong `TerminalHelper`; API mới nhận danh sách
  host và phát `batchStarted`, `hostOperationChanged`, `batchProgress`,
  `batchFinished`. Batch Get cũng phát `runningConfigFinished` cho từng host để
  tab Information tự reload sau khi snapshot đã commit.

## Luồng, test và backlog

QML lưu active/selection theo host (chuột phải chọn `Select multiple`, sau đó
click trái để thêm/bỏ host và thao tác từ context menu) → facade slot → batch
service → service một
host → session registry → connector. Lỗi một host được ghi vào result của host
đó và không dừng batch. Save/Edit reload sidebar nhưng vẫn giữ active/selection
theo host. Backlog: chuyển toàn bộ inventory/import sang service hiện có và
thêm import service với rollback/validation độc lập.
