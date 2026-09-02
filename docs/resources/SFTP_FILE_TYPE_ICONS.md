# Icon loại file của SFTP

Cập nhật: **2026-08-16**. Runtime hiện có **53 SVG loại file** trong
`app/UI/resources/files/types/`, cộng `file.svg`, `folder.svg` và hai icon hướng
transfer. Không còn thư mục `_unused`.

## Nguồn và giấy phép

Các icon loại file được tuyển chọn từ Material Icon Theme. Notice được giữ tại
`licenses/material-icons.txt`; icon không được đổi giấy phép chỉ vì đã được chép
vào resource CAMS. `licenses/lucide-icon.txt` và các notice khác áp dụng
cho asset tương ứng ngoài bộ loại file.

## Runtime mapping

`AppAssets.fileTypeIcon(fileName)` là nguồn ánh xạ duy nhất. Thứ tự:

1. normalize basename/extension không phân biệt hoa thường;
2. kiểm tra tên đặc biệt như Dockerfile, license, environment và project file;
3. kiểm tra extension theo nhóm;
4. trả chuỗi rỗng để consumer dùng `fileGeneric` nếu chưa biết;
5. directory luôn dùng `folder` và không đi qua mapping extension.

Nhóm hiện có bao phủ archive, audio/video/image, binary/hex, certificate/key,
database, document/spreadsheet/presentation/PDF, config/log/markup và các ngôn
ngữ phổ biến (C/C++, Go, Java, JavaScript/TypeScript, Kotlin, Lua, PHP, Python,
Ruby, Rust, Swift, shell, PowerShell, Vue/Svelte/React). Packet capture dùng
binary/hex fallback; định dạng VM dùng icon virtual.

`SftpFilePanel.qml` chỉ hỏi `AppAssets` và render icon bằng `Image` để giữ màu
gốc. Consumer không viết literal path và không ColorOverlay icon nhiều màu.

## Thêm hoặc đổi mapping

1. Xác minh nguồn/license và chỉ thêm icon có consumer thực tế.
2. Đặt file trong `files/types/` với tên ổn định.
3. Thêm property semantic và rule trong `AppAssets.qml`.
4. Cập nhật notice nếu nguồn mới khác nguồn đang có.
5. Cập nhật tài liệu này và test `test_ui_contracts.py`/QML mapping.

Không giữ icon “có thể dùng sau” trong resource runtime; Git history là nơi phục
hồi asset đã xóa.
