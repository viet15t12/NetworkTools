# Giao diện và QML components của desktop app

Cập nhật: **2026-08-16**.

Tài liệu này chỉ áp dụng cho frontend QML trong `app/`; nó không mô tả toàn backend dự án. QML module là `UI`, khai báo tại `app/UI/qmldir`. Component dùng qua `import UI`; SVG dùng property ngữ nghĩa của singleton `AppAssets` (ví dụ `AppAssets.actionSave`).

## 1. Interface families

| Họ | Pattern | Implementation hiện có |
|---|---|---|
| F1 Observe/Info | Dashboard/read-only | `InformationView`, `info_routing` |
| F2 Entity Workspace | Form trái + saved list phải | DHCP, NAT entity, Interface |
| F3 Policy/Rule | Header/rule editor/table | ACL, NAT ACL, Route Map |
| F4 Process Workspace | Process card + pinned header + section | OSPF, EIGRP |
| F5 Guided Setup | Dialog/form hướng dẫn | New Device, Batch New Device |
| F6 Operations/Inspector | Tool/browser/terminal/log/transfer | Database Browser, External Tools, Device Logs, System Logs và SFTP; Console Serial còn coming-soon/disabled. |
| F7 Settings Catalog | Navigator + setting view | Theme/Status Bar và External Tools (Applications/Suggestion dùng Feature Bar) |

F8 Topology chưa có implementation. Feature mới phải chọn family trước khi tạo layout riêng.

## 2. Component chuẩn

### `components/standard/`

- `StandardButton`: Primary/Secondary/Danger/Ghost/Icon/Text/TextIcon, icon + text, tooltip, accessible metadata và focus ring Accent khi điều hướng bằng Tab. `Text` là action chữ thuần có underline khi hover/focus; `TextIcon` dành cho disclosure/link action có semantic icon và không dùng underline.
- `StandardTextField`: wrapper có label, theme, padding và alias tới `TextField`.
- `StandardPasswordField`: password mặc định được che, eye toggle dùng `AppAssets.actionVisibilityOn`/`actionVisibilityOff`, giữ focus/cursor và có accessible state; đang dùng cho New Device, Batch và PPP.
- `StandardNetworkField`: normalize `/24` thành subnet mask và `-/24` thành wildcard khi editing finished.
- `StandardSpinBox`, `StandardComboBox`, `StandardDropdown`.
- `StandardCheckBox`, `StandardToggleButton`, `StandardBadge`, `StatusIcon`.
- `CopyButton`: nút icon Clipboard dùng chung, có feedback “Copied”, focus/accessibility; chỉ dùng trong Notification History, không hiển thị trên toast nổi.
- `ConfigTextViewer`: viewer cấu hình read-only dùng chung cho Information và Routing Config. Thanh Search/Zoom nằm dưới nội dung; `Ctrl+F` focus ô nhập, Enter/Shift+Enter đi tới kết quả sau/trước. Zoom mặc định 13 px, giới hạn 9–40 px, dùng `Ctrl+wheel` hoặc ba nút `−`, `+`, `Reset`. Gutter và nội dung cùng dùng `TextArea`/font/layout mode để giữ baseline khi zoom. `Copy All` là `StandardButton` cùng hàng action với Reload/title, còn selection hỗ trợ copy bàn phím mặc định. Syntax highlighting theo chunk dùng token màu riêng cho từng ngữ nghĩa; file trên 1.000.000 ký tự fallback về plain text.
- `CommandRegistry`: component phi hiển thị cấp Main, sở hữu shortcut theo context. Lát cắt hiện tại gồm Reload Information và navigation Devices/Database/Settings; command bị chặn khi window lock hoặc input đang focus. Save/View & Push chưa đăng ký vì thiếu dirty/capability contract chung.
- `RoutingProcessComboBox`, `RemoveIconButton`.

Quy ước icon cho action button:

- khai báo rõ `icon.source: AppAssets.<semanticProperty>` ở consumer; không suy action từ text trong `StandardButton` vì label có thể đổi theo trạng thái;
- dùng `actionDatabaseReload` cho reload dữ liệu DB, `actionBackup` cho running-config backup, `actionPush` cho cả View & Push và thao tác Push cuối, `actionSave` cho Save;
- Add/New và button compact tương tự giữ text-only; không gắn `actionAdd` khi label đã có dấu `+` hoặc không đủ không gian. Nút động Add/Save chỉ hiện `actionSave` ở trạng thái Save;
- Mọi action Cancel (`Cancel`, `Cancel Deletes`, `Cancel Changes`, kể cả state động Cancel/Close View) dùng `type: "Text"`, đứng đầu bên trái của action group khi có action xác nhận cùng hàng, không icon/nền/khung; label dùng font weight bình thường và gạch chân khi hover/focus. Không dùng `actionClose` cho rollback/cancel;
- `StandardButton type: "Icon"` dùng icon-only content neo `anchors.centerIn`; không dùng `checked/selected` nếu trạng thái không được phép lấy user accent (ví dụ DND trong Notification Center);
- Không duy trì tỷ lệ “bao nhiêu button có icon” như một quality metric. Icon phải
  hỗ trợ nhận biết action, không trang trí; Security không có Add vì policy chỉ áp
  dụng cho port tồn tại. SFTP dùng asset canonical và 53 icon loại file; không còn
  kho `_unused`. `SftpLogPanel` giới hạn 500 sự kiện. Xem [inventory SVG](resources/SVG_RESOURCES.md)
  và [mapping loại file SFTP](resources/SFTP_FILE_TYPE_ICONS.md).

Lưu ý quan trọng: `StandardNetworkField` **không tự validator IPv4**. Nó chỉ normalize shorthand. Form phải gọi `ValidationUtils.js` khi stage/save và backend vẫn phải validate lại trước khi ghi DB.

### `components/layout/`

- `SplitFormPane`, `StandardSplitHandle`; handle có hit area lớn hơn nét nhìn và hỗ trợ layout ngang/dọc;
- `WorkspaceHeader`, `InlineMessage`, `EmptyState`, `FormSection` cho data workspace/inspector;
- `SavedListPanel`, `SavedListHeader`, `SavedListRow`; ba component kế thừa họ table chung nên header luôn giữ chiều cao và body không chồng lên empty state;
- `FormLayout`, `SectionTitle`;
- `SubBar`, `SegmentTab`;
- `ContextMenuItem`, `ContextMenuDivider`.

### `components/table/`

- `DataTableFrame`: surface/border/clip chuẩn;
- `DataTable`: fixed header + body + empty state theo `count`;
- `DataTableHeader`/`DataTableRow`: chiều cao token 36/40 px, inset cột giống nhau, zebra/hover/selection/divider. Selection dùng nền table trung tính và vạch Accent 2 px; không lấy màu phủ mạnh của Sidebar;
- `DataTableCell`: typography/elide và chế độ header/primary/monospace.

Switch Ports, VLAN, SVI, Port Counters/MAC Table, ACL saved/rules, DHCP Pool/
Excluded/Helper, sáu form NAT, OSPF/EIGRP Networks, Batch New Device, Device Logs,
System Logs, SFTP và Database Browser cùng dùng họ này. Interface/Routing saved list nhận thiết
kế qua `SavedList*`. Chỉ dùng table cho dữ liệu có schema
cột; tree, card, notification và list một cột giữ component đúng ngữ nghĩa.

System Logs giữ cùng cấu trúc với phần còn lại của ứng dụng: `WorkspaceHeader` cho tiêu đề,
`DataTable*` cho message list, `FormSection` cho Settings, `ContextMenuItem` cho thao tác
thiết bị và `PanelSideBar` cho lọc theo host. Workspace được lazy-load ở lần mở đầu tiên rồi
giữ instance để không mất trạng thái UI. Xem [SYSTEM_LOGS.md](SYSTEM_LOGS.md).

Switch có thêm một lớp component chuyên biệt trên primitive bảng chung:

- `SwitchSummaryBar`: bốn chỉ số ngữ cảnh, không dùng card trang trí thừa;
- `SwitchTableToolbar`: title, số lượng/filter và search cùng một hàng;
- `SwitchInspectorPane`: một surface chi tiết duy nhất, có empty state và cuộn độc lập;
- `SwitchInspectorSection`/`SwitchPropertyRow`: progressive disclosure; chế độ đọc dùng key/value, chỉ tạo field nhập khi người dùng chọn Add/Edit;
- `CrudFormActions`: action hierarchy chung; Security đặt `allowCreate: false` để không tạo port từ màn hình policy.

Interfaces, Switching, Security và Monitoring cùng dùng summary → contextual table → inspector. Mỗi context chỉ hiển thị cột/trường có ích cho tác vụ hiện tại; không tái sử dụng cột Mode/VLAN cho Port Security.

`SubBar` chỉ xuất hiện khi có từ hai lựa chọn trở lên. Không hiển thị thanh một
mục chỉ để lấp chỗ; model có thể giữ lựa chọn mặc định để mở rộng sau.

Các form F2 thông thường dùng 320 px preferred/240 px minimum cho pane trái. Interface và ACL cần breakpoint rộng hơn; đây không phải lỗi nếu có lý do nội dung. Nên lưu split size theo feature thay vì ép một ratio cho mọi family.

### External Tools category/application picker

- Panel Side Bar chỉ có một mục External Tools; Feature Bar trong màn chuyển giữa **Applications** và **Suggestion**.
- pane trái chọn loại tác vụ cố định SSH Client/SFTP Client/DB Browser/Terminal; pane phải xếp app theo Current selection, Operating system default, configured và Suggested Apps. Không có combobox đổi Tool type trong editor;
- mỗi loại ở pane trái hiển thị app đang active, trạng thái chưa cấu hình hoặc **Built into CAMS** cho DB Browser/SFTP Client; Suggestion dùng cùng pattern, kèm số app đã cài và app đang dùng;
- dùng `SplitView` ngang từ 920 px, xếp dọc dưới breakpoint đó; nội dung ứng dụng/editor cuộn độc lập;
- detected candidate chỉ là đề xuất: hiển thị source/default association, yêu cầu xác nhận **Use application**, không tự ghi DB hoặc thay default Windows/Linux; mỗi loại chỉ có một app active;
- executable phải đi qua native `FileDialog` và `validateExecutable`; Windows discovery dùng URL `ssh`/`telnet`/`sftp`, file association, Default terminal, App Paths/PATH/Installed Applications/known locations; Linux dùng XDG MIME/default application và PATH, không scan toàn ổ;
- catalog SSH hiện nhận diện PuTTY, Xshell, MobaXterm, Tera Term và SecureCRT; fallback Installed Applications đọc `DisplayName`/`InstallLocation` theo allowlist executable, không duyệt cây filesystem;
- tab Suggestion chia category ở pane trái và ba section In use/Installed apps/Not installed ở pane phải; badge nằm cạnh tên app, còn Official Page nằm cùng dòng metadata và dùng `TextIcon` + icon info;
- Terminal trên Windows chỉ biểu diễn terminal host (Windows Terminal/Command Prompt), không coi PowerShell 7 và Windows PowerShell là hai terminal riêng;
- `{password}` không phải placeholder hợp lệ. Preview phải redact/block và bridge phải chặn cấu hình legacy trước khi tạo process.

### `components/base/`

- `ProcessCard`: base F4 đang được OSPF/EIGRP sử dụng.
- `IconButton`, `CloseButton`, `DialogTitleBar`, `ThemedIcon`.

`BaseCard` và `BaseButton` legacy đã được loại khỏi filesystem và `qmldir` ngày 2026-07-14 sau khi kiểm chứng không có consumer. Không tái tạo alias; process workspace dùng trực tiếp `ProcessCard`, action dùng `StandardButton` hoặc component chuyên biệt.

## 3. Theme và design tokens

`Theme.qml` expose token từ `ColorTokens`, `SizeTokens`, `TypographyTokens`, `MotionTokens`; state light/dark/accent nằm ở `ThemeState`. Tránh hard-code màu/kích thước bên ngoài token files.

`Theme.selectionBackground`/`selectionForeground` là contract chung cho text selection. Background theo accent ở light/dark và dùng cặp đen/trắng cố định ở high-contrast; foreground được chọn bằng WCAG relative-luminance để đạt contrast tối thiểu 4.5:1 kể cả custom accent. Hai token đã được áp dụng cho `StandardTextField`, `StandardPasswordField`, `StandardSpinBox`, Information/Route Info, View & Push và editor Database Browser. Consumer mới không dùng trực tiếp `accentColor`/`accentEmphasis` cho text selection.

## 4. Validation contract

```text
Input component
  → ký tự/normalize nhẹ
Form validateBeforeStage/Save
  → message theo field
Python slot/repository validate lại
  → transaction hoặc structured error
```

Không dùng RegExp duy nhất để khẳng định IPv4/mask hợp lệ. Regex có thể hạn chế ký tự, còn semantic validation phải kiểm tra octet, mask liên tục, prefix, quan hệ start/end và network/gateway.

Các khoảng trống hiện có:

- DHCP/NAT/Interface phần lớn chỉ kiểm tra field khác rỗng;
- backend thường trim/convert rồi ghi DB;
- credential input mới phải dùng `StandardPasswordField`; không khai báo `echoMode` rời rạc hoặc để password ở chế độ text thường.

## 5. Lifecycle và reload

`ContentArea`, `SwitchWorkspace` và các container Routing/DHCP/NAT/ACL lazy-load bất đồng bộ rồi cache view đã Ready. Incubation không còn active bị hủy để tránh tranh CPU; host switch được coalesce 16 ms và chỉ truyền host cuối xuống outer view/subtab active, nên view cache đang ẩn không query lại. Switch giữ cache riêng cho Ports/Routed Ports/SVI/VLAN/Port Security/Port Counters/MAC Table, vì vậy đổi Feature không hủy draft/selection hoặc query lại ngay. `activeViewLoading` truyền qua Main tới Device Tabs: icon device của tab active được thay bằng `LoadingSpinner` màu Accent trong lúc outer/subtab loader, Information command/highlighter hoặc session đang mở. Component feature nên expose API nhất quán:

```qml
function reloadData(reason) { ... }
function canLeaveWithDirtyState() { ... }
```

Router gọi `reloadData("activated")` khi người dùng quay lại feature, nhưng phải tránh ghi đè form đang dirty. Có thể reload ngay khi clean, còn khi dirty hiển thị banner “dữ liệu nguồn đã đổi”.

## 6. Accessibility và thẩm mỹ

- Giữ hit target tối thiểu, focus indicator và tooltip cho icon-only button.
- Mọi `StandardButton` dùng `Qt.StrongFocus`; focus ring `Theme.accentColor` chỉ hiện qua `visualFocus` khi điều hướng bàn phím/Tab.
- Không chỉ dùng màu để biểu đạt success/error/pending.
- `ConfigTextViewer` đã thống nhất font monospace 13 px mặc định, toolbar dưới nội dung, search Enter/Shift+Enter, gutter `TextArea` đồng bộ baseline, ba nút zoom tới 40 px, Copy All ở header và syntax highlighting cho hai bề mặt cấu hình. 13 token màu riêng được export qua `ColorTokens`/`Theme`; runtime test khóa palette light/dark, rich-text selection, fallback file lớn và benchmark 10.000 dòng. `InformationView.reloadData(reason, force)` được ContentArea gọi khi activation và coalesce request trùng/command đang chạy.
- Text UI hiện chủ yếu là tiếng Anh; comment/tài liệu có thể tiếng Việt. Không trộn ngôn ngữ trong cùng workflow.
- Với `pragma ComponentBehavior: Bound`, delegate phải khai báo `required property`.

Các contract UI chuyên đề còn hiệu lực nằm tại
[`ui-improvement/README.md`](ui-improvement/README.md); capability/gap cấp ứng
dụng nằm tại [`CURRENT_APP_FEATURES.md`](CURRENT_APP_FEATURES.md).
