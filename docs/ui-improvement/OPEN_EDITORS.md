# Open Editors and System Logs sidebar contract

Reviewed: **2026-08-16**.

## Nguồn đối chiếu VS Code

- [VS Code User Interface — Explorer](https://code.visualstudio.com/docs/editing/userinterface#_explorer):
  `OPEN EDITORS` phản ánh các editor/tab đang mở và các view trong Explorer có
  thể được sắp xếp lại. Chọn
  một hàng sẽ kích hoạt editor tương ứng; editor active cũng được chọn trong
  danh sách.
- [VS Code `openEditorsView.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/files/browser/views/openEditorsView.ts):
  view cập nhật theo lifecycle open/close/move/active, reveal editor active và
  giới hạn chiều cao theo số editor được cấu hình. Giá trị mặc định của VS Code
  là 9 editor nhìn thấy trước khi danh sách cuộn.

## Contract áp dụng trong CAMS

CAMS hiện chỉ có một nhóm editor là `DeviceTabs`, vì vậy `DeviceTabs`
là nguồn trạng thái duy nhất:

- `openEditorsSnapshot` phản ánh đúng thứ tự tab, tên, UID, loại thiết bị,
  trạng thái và editor active.
- Click một hàng gọi lại `openTabByUid`; không tạo tab hoặc state thứ hai.
- Close của từng hàng gọi `closeTabByUid`; Close All gọi `closeAllTabs`, nên
  session cleanup, history và active fallback giữ nguyên contract của tab.
- Khi active editor đổi, danh sách chọn và reveal hàng tương ứng.
- Section chỉ xuất hiện khi có tab, có thể collapse, và hiển thị tối đa 9 hàng
  trước khi cuộn. Chiều cao mỗi hàng dùng token `Theme.listItemHeight` 28 px
  của ứng dụng thay vì sao chép 22 px từ VS Code.
- Theo thứ tự workspace của CAMS, section nằm sau danh sách device và
  được ghim ở đáy PanelSideBar. Đây là thứ tự sản phẩm đã chọn, không phải sao
  chép vị trí mặc định ở đầu Explorer của VS Code.
- Icon loại thiết bị và màu trạng thái giúp phân biệt editor nhưng tên/UID vẫn
  là tín hiệu chính.

Không mô phỏng editor group, preview/pinned hoặc dirty/save của VS Code vì các
Device workspace hiện chưa có contract chung cho những trạng thái đó. Thêm các
trạng thái giả sẽ làm Open Editors lệch khỏi nguồn dữ liệu thật.

## Contract Header của System Logs

- ActivityBar tiếp tục mang tên feature `System Logs`; PanelSideBar dùng tên
  collection `HOSTS`, tương tự `Dashboard` → `DEVICES` và `Database` →
  `TABLES`.
- Tổng số connected host dùng badge accent thay cho text disabled.
- `Refresh Connected Hosts` là `IconButton` ở góc phải Header, có tooltip và
  disabled khi backend bận; button có chữ ở footer được loại bỏ.
- Timer refresh 5 giây và hành vi search/selection/context menu hiện tại không
  thay đổi.

## Kiểm thử bắt buộc

- QML runtime: snapshot có 3 tab, editor active được chọn/reveal, click đổi tab,
  close một hàng và close all cùng cập nhật `DeviceTabs`.
- Static contract: export QML, wiring Main/PanelSideBar/DevicesPanel, giới hạn
  9 hàng và header System Logs.
- Main module load và full regression phải không có QML warning/failure mới.
