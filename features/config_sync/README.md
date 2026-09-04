# Config sync

Trạng thái: **implemented cho router `rou` và switch `sw2`/`sw3`** trong phạm vi
parser nêu dưới đây. Đối chiếu: **2026-08-16**.

Feature tích hợp pipeline đọc `running-config`. Manual Sync dùng lại pipeline có
guard nhưng cho phép đồng bộ snapshot commit không đổi khi người dùng chủ động
yêu cầu.

1. `TerminalHelper` thu thập cấu hình từ thiết bị.
2. `ConfigBackupService` ghi snapshot và so sánh blob mới với `HEAD` bằng Dulwich.
3. `ConfigSyncService` chọn pipeline theo role trong `t01_devices`.

Router chỉ đồng bộ khi running-config thay đổi hoặc người dùng gọi Manual Sync.
Switch có thể đồng bộ operational state ngay cả khi running-config không đổi:
VLAN, interface status/trunk, EtherChannel và VTP status. Manual Sync preview trả
về module xung đột; chế độ `safe` giữ desired-state chưa push, còn
`force_device_state` áp dụng trạng thái thiết bị. VTP password không được thu thập.
Parser/writer switch nằm ở `features/switching/sync.py`; service này vẫn chỉ sở
hữu policy role/change, không sở hữu kết nối thiết bị, Git repository hoặc QML.
