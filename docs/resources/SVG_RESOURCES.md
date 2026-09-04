# Kiểm kê và tổ chức SVG

Cập nhật: **2026-08-16**. `UI/resources/` hiện có **124 SVG** active:

| Nhóm | Số file | Vai trò |
| --- | ---: | --- |
| `actions/` | 22 | add/save/delete/copy/connect/transfer/monitor... |
| `brand/` | 5 | logo, name, project icon và README graphic |
| `devices/` | 8 | router/switch/network/virtual-lab/VPN status |
| `files/` | 57 | generic/folder/transfer và 53 loại file |
| `navigation/` | 21 | Activity Bar, arrow/chevron và destination |
| `status/` | 8 | info/success/warning/error/notification/DND |
| `window-control-icons-svg/` | 3 | close/minimize/restore |

Không còn `_unused`: asset không có consumer được xóa thay vì giữ một kho song
song trong runtime.

## Path ownership

QML dùng property ngữ nghĩa trong `UI/qml/shared/AppAssets.qml`, ví dụ:

```qml
icon.source: AppAssets.actionSave
iconSource: AppAssets.navigationSyslog
```

Không viết literal `resources/...svg` tại consumer và không gọi helper path tùy
ý. Ngoại lệ có chủ đích: `main.py` dùng `brand/logo.ico` làm window icon;
README có thể dùng brand SVG trực tiếp vì không phải QML runtime.

`AppAssets.fileTypeIcon()` quản lý mapping SFTP; xem
[`SFTP_FILE_TYPE_ICONS.md`](SFTP_FILE_TYPE_ICONS.md). `ThemedIcon` phù hợp icon
monochrome theo theme; icon loại file nhiều màu dùng `Image`.

## License

Notice cấp repository nằm trong `licenses/`. `UI/resources/licenses/` giữ
notice được đóng gói cùng resource khi cần. Không xóa/đổi tên notice nếu asset
tương ứng còn tồn tại. Mọi asset mới phải ghi nguồn, giấy phép và consumer trong
PR.

## Quy trình bảo trì

1. Tìm mọi consumer QML/Python và kiểm tra `qmldir`/`AppAssets`.
2. Thêm/đổi file theo nhóm ý nghĩa, không theo tên màn hình.
3. Sửa một property semantic; consumer không phụ thuộc path vật lý.
4. Xóa asset không dùng sau khi kiểm tra license còn consumer khác hay không.
5. Chạy `test_ui_contracts.py`, QML smoke và kiểm tra case-sensitive path trên
   Linux.

Số lượng trong tài liệu là snapshot kiểm kê, không phải mục tiêu thiết kế; nếu
asset hợp lệ thay đổi, cập nhật bảng cùng code/test.
