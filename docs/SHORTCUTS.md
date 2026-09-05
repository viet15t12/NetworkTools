# Phím tắt CAMS

Danh sách này phản ánh các `Shortcut` đang hoạt động trong QML ngày **2026-08-16**.
Phím tắt toàn cục được điều phối bởi `CommandRegistry.qml`; phím tắt theo ngữ
cảnh chỉ hoạt động khi màn hình tương ứng hiển thị và không có hộp thoại khóa app.

Quy ước tab bám theo Google Chrome: `Ctrl+1` đến `Ctrl+8` chọn tab theo vị trí, `Ctrl+9` chọn tab ngoài cùng bên phải; `Ctrl+T`, `Ctrl+W`, `Ctrl+Shift+T`, `Ctrl+Tab` và `Ctrl+Shift+Tab` giữ hành vi quen thuộc. Settings dùng `Ctrl+,` và toggle sidebar dùng `Ctrl+B` theo VS Code.

## 1. Ứng dụng và Menu Bar

| Phím | Hành vi |
|---|---|
| `Alt+F4` | Thoát CAMS khi cửa sổ chính đang hoạt động. |
| `Ctrl+O` | Mở project. |
| `Ctrl+S` | Lưu workspace hiện tại. |
| `Ctrl+K`, `Ctrl+S` | Mở bảng tham chiếu phím tắt. |
| `Alt+F` / `Alt+V` / `Alt+H` | Mở File / View / Help trên Menu Bar tùy biến. |
| `Ctrl+B` | Ẩn/hiện PanelSideBar. |
| `Ctrl+R` | Reload/refresh view hiện hoạt nếu view hỗ trợ. |

## 2. Activity Bar

| Phím | Hành vi |
|---|---|
| `Ctrl+Alt+D` | Mở Dashboard/Devices. |
| `Ctrl+Alt+F` | Mở SFTP. |
| `Ctrl+Alt+L` | Mở System Logs. |
| `Ctrl+Alt+B` | Mở Database; bị vô hiệu nếu backend không khả dụng. |
| `Ctrl+,` | Mở Settings. |

Các tổ hợp này dùng chữ cái trong tên chức năng và không chiếm dải `Ctrl+1..9` dành cho tab.

## 3. Device panel

| Phím | Hành vi |
|---|---|
| `Ctrl+N` | Mở Add New Device. |
| `Ctrl+Alt+N` | Mở Batch New Device. |
| `F2` | Sửa device đang chọn. |
| Chuột phải → Delete Host… | Xóa vĩnh viễn host sau khi xác nhận; không có phím Delete cho device. |
| `Ctrl+Alt+P` | Ping device đang kết nối. |
| `Ctrl+Alt+C` | Kết nối device đang chờ. |
| `Ctrl+Alt+R` | Đưa device Disconnected về Waiting; sau đó dùng Connect. |
| `Ctrl+Alt+Down` / `Ctrl+Alt+Up` | Đánh dấu device Down/Up trong Dev mode. |
| `Ctrl+Shift+C` | Kết nối các device Waiting đang chọn. |
| `Ctrl+Shift+R` | Lấy running-config của các device Connected đang chọn. |
| `Ctrl+Shift+D` | Ngắt các device Connected đang chọn, đưa về Waiting. |
| `Ctrl+A` | Chọn toàn bộ device đang hiển thị khi ở chế độ multi-select. |
| `Esc` | Xóa selection hiện tại. |
| `Ctrl+\`` | Mở CAMS CLI cho device có tab active. |

## 4. Device tabs

| Phím | Hành vi |
|---|---|
| `Ctrl+T` | Mở Add New Device. |
| `Ctrl+W` / `Ctrl+F4` | Đóng tab hiện tại. |
| `Ctrl+Shift+T` | Khôi phục tab vừa đóng. |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | Chọn tab kế tiếp / trước đó. |
| `Ctrl+1..8` | Chọn tab theo vị trí 1–8. |
| `Ctrl+9` | Chọn tab ngoài cùng bên phải. |
| `Ctrl+K`, `Ctrl+W` | Đóng toàn bộ tab. |
| `Shift+F10` | Mở menu chuột phải của tab hiện tại. |

## 5. SFTP

| Phím | Hành vi |
|---|---|
| `Alt+Left` / `Backspace` | Quay lại lịch sử của pane hiện hoạt. |
| `Alt+Right` | Đi tới lịch sử kế tiếp. |
| `Alt+Up` | Mở thư mục cha. |
| `F5` / `Ctrl+R` | Refresh pane hiện hoạt. |
| `Ctrl+Shift+N` | Tạo thư mục. |
| `F2` | Đổi tên entry đang chọn. |
| `Delete` | Xóa các entry đang chọn. |
| `Enter` | Mở hoặc truyền entry đang chọn. |
| `Ctrl+A` | Chọn mọi entry trong pane hiện hoạt. |
| `Esc` | Xóa selection. |
| `Shift+F10` | Mở menu chuột phải của entry. |

## 6. Interfaces và configuration viewer

Trong danh sách Interfaces, `F2` sửa, `Delete` xóa, `F5` reload và `Shift+F10` mở menu chuột phải. Đây là cùng nhóm ý nghĩa với các màn hình khác và chỉ tồn tại trong context Interfaces.

Trong `ConfigTextViewer`, `Ctrl+F` mở tìm kiếm, `Ctrl+C` sao chép selection, `Ctrl+=`/`Ctrl+-` thay đổi zoom và `Ctrl+0` đưa zoom về 100%. Khi ô tìm kiếm có focus, `Enter`/`Shift+Enter` chuyển tới kết quả tiếp theo/trước đó.

## 7. Dialog

| Ngữ cảnh | Phím | Hành vi |
|---|---|---|
| Add New Device | `Enter` / `Return` | Submit form nếu hợp lệ. |
| Batch New Device | `Ctrl+Enter` / `Ctrl+Alt+N` | Submit batch. |
| Dialog/selection | `Esc` | Cancel, đóng hoặc xóa selection tùy context. |

Các phím theo ngữ cảnh như `F2`, `Delete`, `F5`, `Enter`, `Esc` và `Shift+F10` được phép lặp vì chúng giữ nguyên ý nghĩa thao tác và không bao giờ cùng enabled trên hai workspace. Không có một tổ hợp toàn cục nào điều khiển hai chức năng khác nhau.
