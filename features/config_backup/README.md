# Config backup

Trạng thái: **implemented**. Đối chiếu: **2026-08-16**.

Feature lưu lịch sử `running-config` bằng Dulwich, không gọi Git CLI và không ghi lịch sử vào SQLite. Mỗi host có repository riêng tại `backup/<host>/cfg`; object/ref nằm trong `.cams-git`, file `running-config.txt` là bản mới nhất và mỗi lần thu thập thành công luôn tạo một commit, kể cả nội dung không đổi.

## Luồng và API

`TerminalHelper` yêu cầu `DeviceConnector.collect_running_config()` rồi chuyển nội dung cho `ConfigBackupService`. Kết quả commit có cờ `changed`, được tính bằng cách so sánh blob mới với `HEAD`; `ConfigSyncService` dùng cờ này và role inventory để chỉ đồng bộ router `rou` khi cấu hình thay đổi. Adapter `save_running_config()` cũ vẫn được giữ cho interactive CLI; code mới không dùng adapter này để quyết định nơi lưu.

Trước khi chuyển snapshot sang `ConfigBackupService`, collector xử lý nội dung tại
máy chạy ứng dụng và bỏ mọi prompt bị lặp ở cuối như `R2(config)#^@`. Các dòng cấu
hình `!` và `end` vẫn được giữ nguyên. Lệnh gửi tới thiết bị vẫn là
`show running-config` không kèm pipe/filter.

Facade QML ổn định `dbManager` ủy quyền bốn slot sang feature này:

- `getLatestRunningConfig(host)` đọc `HEAD`.
- `getRunningConfigHistory(host)` trả tối đa 100 commit, mới nhất trước (service hỗ trợ giới hạn tối đa 500).
- `getRunningConfigAtCommit(host, commitId)` chỉ đọc blob từ commit reachable, không checkout và không thay đổi thiết bị.
- `getRunningConfigDiff(host, baseCommitId, targetCommitId)` trả unified Diff giữa hai commit reachable. Hai endpoint không liền kề biểu diễn thay đổi tích lũy qua toàn bộ khoảng phiên bản, kèm số dòng thêm/xóa và `versionSpan`.

`InformationView` có hai chế độ Snapshot/Compare. Compare mặc định dùng commit mới nhất và commit ngay trước đó, đồng thời cho phép chọn hai endpoint bất kỳ trong 100 phiên bản đã tải. Diff chỉ đọc Git object, không checkout working tree.

Repository chuẩn hóa host, chặn traversal/ký tự điều khiển, ghi file tạm rồi `os.replace()`, và dùng lock riêng cho từng host trong tiến trình. Commit dùng author `CAMS <cams@localhost>`, thời gian local dạng `dd/MM/yyyy HH:mm:ss`, cùng timezone trong metadata.

## Migration

Khi chưa có commit nhưng tồn tại `<host>_running-config.txt`, service import file thành commit `Import legacy backup - ...`, sau đó đổi tên file nguồn thành `.migrated`. Migration chạy lặp lại không tạo commit import trùng và không xóa bản cũ.

Repository tạo bởi phiên bản cũ với control directory `.git` được đổi nguyên tử
sang `.cams-git` khi truy cập. Bộ lưu workspace cũng chuẩn hóa bản staging,
kể cả backup nằm trong snapshot, nên `.ntp` vẫn cấm đường dẫn `.git` mà không làm
mất lịch sử commit.

Không commit `backup/`, `.git` lồng bên trong, credential hoặc cấu hình thiết bị vào repository mã nguồn.
