# SFTP trong CAMS

Cập nhật: **2026-08-16**. Tài liệu này mô tả client SFTP tích hợp và cách Activity
Bar chọn giữa client tích hợp với ứng dụng SFTP ngoài.

## 1. Kiến trúc và ownership

```text
SftpView.qml / panels
       ↓ signal/slot
SftpController (QObject, state và điều phối)
       ├─ LocalFileService → filesystem cục bộ
       ├─ SftpService → Paramiko SSH/SFTP
       ├─ FileListModel / TransferModel → QML
       └─ OperationWorker → QThreadPool
```

`app/main.py` tạo một `SftpController`, đăng ký context property
`sftpController` và gọi `shutdown()` khi thoát. Controller serialize thao tác
kết nối/danh sách và quản lý transfer bất đồng bộ; QML không truy cập Paramiko
hoặc filesystem trực tiếp.

## 2. Kết nối và xác minh host key

Kết nối yêu cầu host, port 1–65535, username và password hoặc private key.
`SftpService` nạp system host keys và `~/.ssh/known_hosts`. Với host chưa biết:

1. lần kết nối đầu chỉ lấy key type và fingerprint SHA-256;
2. UI yêu cầu người dùng xác minh fingerprint qua kênh đáng tin cậy;
3. nếu chấp nhận, lần kết nối xác nhận lại fingerprint bằng so sánh constant-time;
4. chỉ khi khớp mới ghi key vào `~/.ssh/known_hosts` và mở SFTP.

Nếu key đổi giữa hai bước, kết nối bị hủy. Không chấp nhận host key tự động và
không bỏ qua kiểm tra chỉ để kết nối được.

## 3. File browser và transfer

Hai panel local/remote hỗ trợ:

- liệt kê thư mục; folder xếp trước file; hiển thị tên, loại, size, thời gian và
  quyền remote;
- Back/Forward/Up/Refresh, path history riêng cho từng panel;
- chọn một, Ctrl-select, Shift-range, Ctrl+A và menu ngữ cảnh;
- upload/download một hoặc nhiều file/thư mục;
- tạo folder, rename và xóa file hoặc **folder rỗng**;
- queue hiển thị progress, trạng thái và cho phép yêu cầu cancel.

Upload thư mục bỏ qua symlink và tạo cây remote; download thư mục tạo cây local.
Xóa không đệ quy: local dùng `rmdir()`, remote dùng `rmdir()`, nên folder còn dữ
liệu sẽ báo lỗi thay vì bị xóa hàng loạt.

Cancel là cooperative: event được kiểm tra trước/sau mỗi lời gọi transfer. Một
lời gọi Paramiko đang blocking không bị ngắt giữa chunk; vì vậy cancel có thể chỉ
có hiệu lực sau khi lời gọi hiện tại trả về. Controller cập nhật queue nhưng
không coi “đã bấm Cancel” là đảm bảo remote/local chưa thay đổi.

## 4. Profile và credential

`QSettings` lưu profile gồm ID, tên, host, port, username, private-key path,
local/remote path gần nhất và cờ `passwordSaved`. JSON profile không chứa mật
khẩu plaintext.

Lưu mật khẩu tắt mặc định và chỉ khả dụng trên Windows khi DPAPI current-user
hoạt động. Secret được mã hóa với entropy ứng dụng và lưu ở key riêng
`SFTP/credentials/<profile-id>`. Linux/macOS hiện không có secure-store adapter,
nên UI phải vô hiệu hóa lựa chọn lưu password. Xóa profile cũng xóa credential.
Ưu tiên private key hoặc SSH agent.

## 5. Client ngoài

Nếu category `SFTP Client` trong External Tools có app active, Activity Bar thử
mở app đó. Placeholder được phép gồm host/IP, port, username và path; `{password}`
bị chặn. Khi executable/argument không hợp lệ hoặc launch thất bại, CAMS
thông báo và mở client tích hợp. Không có profile vẫn có thể mở UI đăng nhập của
client ngoài mà không đưa target hay secret lên command line.

## 6. Phím tắt

- `Alt+Left` / `Alt+Right`: lịch sử của panel đang active;
- mouse Back/Forward: cùng lịch sử;
- `Ctrl+R` hoặc `F5`: refresh panel active;
- `Ctrl+Shift+N`: New Folder trong SFTP;
- `Ctrl+A`: chọn tất cả; `Escape`: bỏ chọn;
- `Shift+F10`: mở menu ngữ cảnh bằng bàn phím.

Shortcut không chiếm phím khi text input đang focus, ngoại trừ mouse navigation
được giữ nếu không có modal lock. Danh sách đầy đủ ở
[`SHORTCUTS.md`](SHORTCUTS.md).

## 7. Giới hạn và kiểm thử

- Chưa có resume transfer, checksum sau truyền, bandwidth limit, chmod/chown,
  recursive delete hoặc secure password store đa nền tảng.
- Một `SftpController` sở hữu một kết nối remote active; profile không tạo nhiều
  session song song.
- Không cam kết atomicity cho upload/download và không rollback file đã truyền
  trước khi task lỗi.

Regression chính: `app/tests/test_sftp_client.py`, `test_external_tools.py`,
`test_ui_contracts.py` và QML smoke. Test dùng fake service/temp directory; không
được kết nối host thật trong test suite mặc định.
