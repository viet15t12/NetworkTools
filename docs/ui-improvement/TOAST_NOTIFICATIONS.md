# Toast and actionable notification contract

Reviewed: **2026-08-16**. Đây là contract regression, không phải báo cáo test
release hiện tại.

## Mục tiêu

Toast không chỉ báo lỗi mà phải giúp người dùng xử lý lỗi ngay tại ngữ cảnh.
Hạng mục đầu tiên là đưa người dùng tới `Settings > External Tools` khi SSH,
SFTP hoặc Database Browser ngoài bị thiếu hay cấu hình không hợp lệ.

## Nghiên cứu VS Code

- [VS Code notification UX guideline](https://code.visualstudio.com/api/ux-guidelines/notifications):
  notification phải tôn trọng sự chú ý, tránh lặp và chỉ có action khi action
  thực sự giải quyết được vấn đề.
- [VS Code `notificationsToasts.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/browser/parts/notifications/notificationsToasts.ts):
  tối đa ba toast cùng lúc; timeout Info/Warning/Error lần lượt là
  10/12/15 giây; toast không tự đóng khi đang hover, có focus hoặc là sticky;
  Notification Center đang mở thì không hiện toast.
- [VS Code `notificationsViewer.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/browser/parts/notifications/notificationsViewer.ts):
  primary action xuất hiện dưới message và mặc định đóng notification sau khi
  chạy; từng notification có close action riêng.
- [VS Code notification model](https://github.com/microsoft/vscode/blob/main/src/vs/platform/notification/common/notification.ts):
  model tách primary/secondary action; error có primary action và progress
  notification là các trường hợp sticky.

## Contract của CAMS

### Model

Mỗi notification có thể mang:

- `msgText`, `msgType`, `timestamp`;
- `sourceText`;
- `actionLabel`, `actionId`, `actionData`.

Model chỉ lưu ID/data dạng chuỗi, không giữ JavaScript callback. `Main.qml` là
router duy nhất thực thi action, tránh callback hết lifetime hoặc feature tự
điều hướng không đồng bộ.

### Toast

- Tối đa ba toast đồng thời; lịch sử vẫn nằm trong Notification Center.
- Info/Success tự đóng sau 10 giây, Warning sau 12 giây, Error sau 15 giây.
- Error có primary action và progress toast là sticky.
- Timer dừng khi hover hoặc focus nằm trên action/dismiss.
- Escape đóng toast đang focus.
- Action có label, source và accessible description; chạy action sẽ đóng cả
  toast lẫn entry lịch sử tương ứng.
- Duplicate suppression hiện tại tiếp tục áp dụng trong cửa sổ ba giây.

### Notification Center

- Hiển thị lại source và primary action từ lịch sử.
- Primary action chạy qua cùng router và đóng entry.
- Có dismiss cho từng entry, ngoài Clear All và Do Not Disturb hiện có.
- Khi Center mở, notification mới chỉ vào lịch sử và không che workspace bằng
  toast.

### External Tools

- Backend trả `settingsKey: "external_tools"` cho lỗi thiếu SSH Client, đường
  dẫn executable không còn tồn tại, arguments không an toàn hoặc launcher
  ngoài thất bại.
- CLI từ FeatureBar/shortcut, Device context menu, external SFTP và Database
  Browser đều chuyển metadata này thành action `Open External Tools`.
- Action gọi `open-settings` với data `external_tools`; ActivityBar, sidebar
  selection và Settings content cùng chuyển trạng thái qua một router.
- Built-in SFTP/Database fallback hợp lệ không bị biến thành lỗi cấu hình và
  không tạo notification quảng bá lặp lại.

## Kiểm thử

- Runtime: tạo actionable error, kích hoạt action và xác nhận app chuyển tới
  Settings/External Tools, toast và history entry được đóng.
- Runtime: năm toast liên tiếp chỉ giữ ba toast.
- Runtime: action và dismiss trong Notification Center cập nhật model.
- Backend: lỗi thiếu/không an toàn trả đúng `settingsKey`.
- Static contract: khóa timeout, stack limit, source/action roles và mọi entry
  point External Tools.

## Kết quả nghiệm thu

- Actionable error mở đúng ActivityBar `Settings`, chọn card `External Tools`
  và hiển thị đúng content tương ứng.
- Action từ Toast và Notification Center đều đóng entry sau khi chạy; dismiss
  từng entry không ảnh hưởng các notification còn lại.
- Năm toast liên tiếp chỉ giữ ba toast hiển thị.
- DND, duplicate suppression và quy tắc Center mở thì không hiện toast tiếp
  tục pass regression.
- Runtime/QML contract test phải kiểm tra các hành vi trên. Kết quả của một lần
  chạy lịch sử không được giữ ở đây; baseline hiện tại nằm trong
  [`../CODE_AUDIT.md`](../CODE_AUDIT.md).
