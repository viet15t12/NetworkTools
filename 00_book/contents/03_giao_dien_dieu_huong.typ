#import "../config/commands.typ": report-note
#import "../config/diagrams.typ": flow-diagram
#import "../config/images.typ": insert-image
#import "../config/tables.typ": report-table

= Làm quen với giao diện và điều hướng CAMS

Sau Chương 2, CAMS đã khởi chạy, project `.ntp` đã được tạo hoặc mở và Workspace đã sẵn sàng. Chương này giúp người dùng nhận biết vị trí các thành phần giao diện, chọn thiết bị, chuyển tab và tìm chức năng cần xem. Người dùng chưa cần cấu hình mạng hoặc kết nối tới thiết bị thật.

Các hình sử dụng Workspace minh họa *CAMS Interface Lab*, gồm R1 (`192.0.2.1`, Router), R2 (`192.0.2.2`, Router), SW1 (`192.0.2.11`, Switch Layer 2) và SW3 (`192.0.2.13`, Switch Layer 3). Đây là dữ liệu mẫu dành cho tài liệu. Trạng thái Connected của R1 và SW1 được mô phỏng an toàn, không phải kết quả kết nối tới một hệ thống mạng thật.

== Tổng quan Workspace

Workspace là không gian làm việc chính của CAMS. Trong @fig:ch03-workspace-overview, người dùng đang ở Dashboard, tab R1 đang được chọn và nội dung Information đang hiển thị. Thanh tiêu đề phía trên cho biết tên project đang mở.

#insert-image(
  "figures/gui/chapter-03/01-workspace-overview.png",
  caption: [Các khu vực chính trong Workspace của CAMS.],
  width: 100%,
) <fig:ch03-workspace-overview>

Đọc giao diện từ ngoài vào trong: *Menu Bar* nằm trên cùng; *Activity Bar* là dải biểu tượng sát cạnh trái; *Sidebar* nằm ngay bên phải dải này. Phía trên vùng làm việc thiết bị là *Device Tabs*, bên dưới là *Feature Bar*. *Content Area* chiếm phần lớn diện tích còn lại; *Status Bar* chạy dọc cạnh dưới cửa sổ.

#report-table(
  columns: (1fr, 2.2fr),
  header: ([Khu vực], [Câu hỏi giúp xác định vị trí]),
  rows: (
    ([Menu Bar], [Tôi tìm lệnh chung của ứng dụng ở đâu?]),
    ([Activity Bar], [Tôi đang ở chế độ làm việc nào?]),
    ([Sidebar], [Tôi chọn thiết bị hoặc đối tượng ở đâu?]),
    ([Device Tabs], [Thiết bị nào đang là ngữ cảnh làm việc?]),
    ([Feature Bar], [Tôi đang xem chức năng nào của thiết bị?]),
    ([Content Area], [Nội dung và các thao tác của màn hình nằm ở đâu?]),
    ([Status Bar], [Ứng dụng đang sẵn sàng, bận hay có thông báo?]),
  ),
  caption: [Vai trò các khu vực trong Workspace.],
) <tab:ch03-workspace-regions>

Nếu project chưa có thiết bị hoặc chưa mở tab, Device Tabs và Feature Bar chưa xuất hiện. Đây là trạng thái bình thường; người dùng vẫn có thể dùng menu và Activity Bar để điều hướng.

== Thanh menu

Thanh menu có ba nhóm *File*, *View* và *Help*. Chọn tên menu để mở danh sách lệnh; phím tắt, nếu có, nằm ở bên phải từng lệnh. Lệnh bị làm mờ chưa khả dụng trong ngữ cảnh hiện tại.

*File* tập hợp các lệnh liên quan tới project và phiên làm việc: *New Project…*, *Open Project…*, *Save Workspace*, *Create Snapshot…*, *Snapshot History…*, *Close Workspace* và *Quit*. Quy trình tạo, mở, lưu và snapshot đã được trình bày ở Chương 2.

*View* là điểm truy cập các lệnh điều hướng: *Reload UI* nạp lại nội dung giao diện hiện tại; *Toggle Sidebar* ẩn hoặc hiện Sidebar; các lệnh *Dashboard*, *SFTP*, *System Logs*, *Database* và *Settings* đưa người dùng tới khu vực tương ứng. @fig:ch03-menu-bar minh họa menu View đang mở.

#insert-image(
  "figures/gui/chapter-03/02-menu-bar.png",
  caption: [Các lệnh điều hướng trong menu View.],
  width: 60%,
) <fig:ch03-menu-bar>

*Help* cung cấp *Keyboard Shortcuts* để xem bảng phím tắt trong ứng dụng và *About CAMS* để xem thông tin phần mềm. Các hình trong chương dùng kiểu menu tùy biến của CAMS; vị trí menu có thể khác khi chọn cách hiển thị menu do hệ điều hành quản lý.

== Activity Bar

Activity Bar nằm sát cạnh trái của Workspace và dùng để chuyển giữa các chế độ làm việc chính. Biểu tượng đang được chọn có dấu nhấn màu; đưa con trỏ lên biểu tượng để đọc tên và phím tắt. Phần trên của thanh được minh họa tại @fig:ch03-activity-bar.

#insert-image(
  "figures/gui/chapter-03/03-activity-bar.png",
  caption: [Nhóm điều hướng phía trên với Dashboard đang được chọn.],
  width: 56%,
) <fig:ch03-activity-bar>

Theo thứ tự từ trên xuống, nhóm phía trên gồm *Dashboard* để làm việc với thiết bị, *SFTP* để mở khu vực truyền tệp và *System Logs* để xem khu vực nhật ký hệ thống. Nhóm sát đáy gồm *Database* và *Settings*. Khi chuyển chế độ, Sidebar cũng đổi nội dung: danh sách thiết bị, kết nối SFTP, đối tượng log, bảng dữ liệu hoặc nhóm thiết lập.

Database có thể mở trình duyệt dữ liệu trong CAMS hoặc công cụ ngoài tùy thiết lập. Khi thành phần hỗ trợ chưa có, biểu tượng có thể bị vô hiệu hóa; nếu công cụ ngoài chưa sẵn sàng, ứng dụng có thể đưa ra thông báo hướng dẫn. Tương tự, SFTP có thể mở ứng dụng ngoài nếu người dùng đã chọn dùng SFTP client ngoài.

Nhấn lại *Dashboard* hoặc *Settings* đang active sẽ ẩn/hiện Sidebar. Với SFTP tích hợp và Database ở chế độ mặc định, thao tác nhấn lại cũng có thể thực hiện việc này. Riêng *System Logs* hiện luôn kích hoạt màn hình log và hiện Sidebar. Chọn *View → Dashboard* hoặc dùng phím tắt Dashboard sẽ trở về chế độ thiết bị và hiện Sidebar, không thực hiện thao tác nhấn lại để ẩn.

== Devices Sidebar

Trong Dashboard, Sidebar hiển thị panel *DEVICES*. Ô *Search devices…* tìm theo tên hoặc địa chỉ IP; nút *Filter* ở phần đầu panel lọc theo trạng thái và loại thiết bị. Nếu không thấy thiết bị cần tìm, hãy kiểm tra từ khóa, bộ lọc và các nhóm đang thu gọn trước.

#insert-image(
  "figures/gui/chapter-03/04-devices-sidebar.png",
  caption: [Devices Sidebar với các nhóm trạng thái và thiết bị mẫu.],
  width: 45%,
) <fig:ch03-devices-sidebar>

Các thiết bị được chia vào ba nhóm *Connected*, *Waiting* và *Disconnected*, kèm số lượng đang hiển thị. Biểu tượng xanh, vàng và đỏ hỗ trợ phân biệt các trạng thái này. Chọn mũi tên ở đầu nhóm để mở rộng hoặc thu gọn danh sách. Trong hình, nhóm Disconnected đã được mở rộng để thấy SW3.

Ở chế độ chọn đơn, nhấn một dòng thiết bị khả dụng để mở hoặc chuyển tới tab của thiết bị đó. Thiết bị Waiting có dòng hiển thị mờ và chưa cho mở vùng cấu hình; trạng thái này không có nghĩa thiết bị đã bị xóa khỏi project.

Để chọn nhiều dòng, giữ `Ctrl` rồi nhấn từng thiết bị; giữ `Shift` rồi nhấn để chọn một khoảng trong danh sách đang hiển thị. Khi chế độ chọn nhiều đang bật, nhấn một dòng sẽ thay đổi lựa chọn của nhóm thay vì chuyển tab. Thanh thao tác nhóm cho biết số thiết bị đã chọn; nhấn `Esc` khi không nhập trong ô tìm kiếm để thoát lựa chọn nhóm.

Các lệnh quản lý thiết bị sẽ được trình bày ở Chương 4. Trong chương này, chỉ cần phân biệt *chọn một thiết bị để xem* với *chọn nhiều thiết bị để thao tác theo nhóm*.

== Device Tabs

Device Tabs nằm trên Feature Bar. Mỗi tab đại diện cho ngữ cảnh của một thiết bị, nhận diện bằng tên và biểu tượng loại thiết bị. Tab đang active có vạch nhấn ở cạnh trên. @fig:ch03-device-tabs cho thấy R1 và SW1 đã được mở, trong đó R1 đang active.

#insert-image(
  "figures/gui/chapter-03/05-device-tabs.png",
  caption: [Hai tab thiết bị với R1 đang là tab hoạt động.],
  width: 100%,
) <fig:ch03-device-tabs>

Chọn tab SW1 để chuyển ngữ cảnh làm việc sang SW1; chọn lại tab R1 để quay về Router. Mở lại cùng một host từ Sidebar sẽ đưa tab đã có lên phía trước, không tạo thêm tab trùng. Mỗi tab ghi nhớ feature đang xem: chẳng hạn R1 đang ở Routing, còn SW1 vẫn ở Information khi chuyển qua lại.

Chọn nút đóng trên tab để đóng vùng làm việc đó. Nếu đóng tab active, CAMS ưu tiên tab còn mở vừa dùng gần nhất trong lịch sử; nếu không có lịch sử phù hợp, ứng dụng chọn tab cuối còn lại. Khi đóng hết tab, vùng làm việc trở về trạng thái chưa chọn thiết bị. Menu chuột phải trên tab cũng có các lệnh đóng tab, đóng các tab khác và mở lại tab vừa đóng.

#report-note[*Ghi chú:* Đóng tab chỉ đóng vùng làm việc của thiết bị; nó không xóa thiết bị khỏi project. *Close* trên tab và *Delete Device* là hai thao tác khác nhau.]

== Feature Bar

Feature Bar nằm ngay dưới Device Tabs. Thanh này xác định chức năng đang xem của host active và gồm hai nhóm: các biểu tượng chức năng chính ở bên trái và các tên chức năng theo loại thiết bị ở bên phải.

=== Các chức năng chính

Ba biểu tượng chính lần lượt là *Information*, *CAMS Terminal* và *Interface*. Information mở màn hình thông tin cấu hình đã lưu của host; Interface mở khu vực giao diện mạng tương ứng với loại thiết bị. Đưa con trỏ lên biểu tượng để đọc tên trước khi chọn.

#report-note[*Ghi chú:* Biểu tượng Terminal mở hoặc đưa cửa sổ *CAMS Terminal* riêng lên phía trước, thay vì đổi Content Area như Information hoặc Interface. Phần sử dụng phiên CLI trong Terminal sẽ được trình bày ở chương sau.]

=== Các chức năng theo loại thiết bị

@fig:ch03-feature-router và @fig:ch03-feature-switch cùng giữ Information đang được chọn, nhưng phần tên chức năng khác nhau vì tab active đã đổi từ R1 sang SW1.

#insert-image(
  "figures/gui/chapter-03/06-feature-bar-router.png",
  caption: [Feature Bar khi làm việc với Router R1.],
  width: 100%,
) <fig:ch03-feature-router>

#insert-image(
  "figures/gui/chapter-03/07-feature-bar-switch.png",
  caption: [Feature Bar khi làm việc với Switch Layer 2 SW1.],
  width: 100%,
) <fig:ch03-feature-switch>

#report-table(
  columns: (1fr, 2.25fr),
  header: ([Loại thiết bị], [Nhóm chức năng hiển thị và có thể chọn]),
  rows: (
    ([Router], [Routing, DHCP, ACL, NAT, FHRP, Syslog Server]),
    ([Switch Layer 2 (`sw2`)], [Switching, Security, Monitoring, Syslog Server]),
    ([Switch Layer 3 (`sw3`)], [Routing, Switching, Services, Security, Monitoring, FHRP, Syslog Server]),
  ),
  caption: [Các nhóm chức năng theo loại thiết bị trong giao diện hiện tại.],
) <tab:ch03-features-by-role>

Bảng liệt kê các nhóm đang khả dụng theo thứ tự hiển thị; nó không khẳng định mọi thao tác bên trong mỗi nhóm đã hoàn thiện. Khi chiều ngang không đủ, chọn mũi tên ở cuối Feature Bar để tìm thêm các mục trong danh sách. Chưa cần đi vào nội dung cấu hình của những nhóm này.

#report-note[*Ghi chú:* Các feature hiển thị thay đổi theo role/loại thiết bị. Một feature không xuất hiện không nhất thiết là lỗi ứng dụng; hãy kiểm tra tab active và loại thiết bị trước.]

== Content Area

Content Area là vùng nội dung chính bên dưới Feature Bar. Nội dung thay đổi theo host active, feature, loại thiết bị và chế độ ứng dụng. Trong Settings, khu vực này hiển thị thiết lập; trong Dashboard, nó hiển thị nội dung của thiết bị đang chọn. Tên màn hình và địa chỉ host ở đầu vùng giúp kiểm tra mình đang xem đúng nơi.

#insert-image(
  "figures/gui/chapter-03/08-content-area.png",
  caption: [Phần nội dung Information của R1 khi chưa có dữ liệu cấu hình.],
  width: 100%,
) <fig:ch03-content-area>

Trong @fig:ch03-content-area, *No backup history* và *No running-config data is available* là thông báo chưa có dữ liệu, không phải ứng dụng đang tải vô thời hạn. Mục Snapshot tại đây thuộc nội dung cấu hình thiết bị; không nhầm với snapshot toàn project trong menu File. Chương này chỉ yêu cầu nhận diện vùng nội dung, chưa cần thu thập hay so sánh cấu hình.

Một số màn hình chỉ được nạp khi mở lần đầu nên có thể xuất hiện trạng thái tải ngắn. Sau khi chuyển tab hoặc feature, hãy chờ nội dung ổn định và kiểm tra tên host trước khi tiếp tục.

== Status Bar

Status Bar nằm ở cạnh dưới Workspace. Phần trái hiển thị trạng thái Python/runtime và kiểm tra database, ví dụ *SYSTEM READY* khi môi trường sẵn sàng. Khi ứng dụng có tác vụ nền, thanh này có thể hiển thị thông báo, tiến độ hoặc kết quả tác vụ.

#insert-image(
  "figures/gui/chapter-03/09-status-bar.png",
  caption: [Vị trí các nhóm thông tin trên Status Bar.],
  width: 100%,
) <fig:ch03-status-bar>

Phần phải có thông tin kết nối mạng, Virtual Lab nếu được phát hiện, RAM, ngày/giờ và chuông thông báo. Trạng thái mạng của máy chạy CAMS không thay thế trạng thái kết nối từng thiết bị trong Sidebar. Chọn chuông để mở khu vực thông báo; đây cũng là nơi kiểm tra lại kết quả hoặc vấn đề ứng dụng vừa báo.

#insert-image(
  "figures/gui/chapter-03/09-status-details.png",
  caption: [Chi tiết kết nối mẫu, RAM và biểu tượng thông báo.],
  width: 100%,
) <fig:ch03-status-details>

Trong các hình, *DOC FIXTURE* đánh dấu phiên minh họa, *Documentation Link* là tên kết nối mẫu và RAM được cố định ở 42%. Ngày/giờ được ẩn để ảnh không thay đổi theo thời điểm chụp. Khi dùng CAMS bình thường, các giá trị phản ánh môi trường đang chạy; người dùng có thể bật/tắt những nhóm thông tin trong *Settings → Theme → Status Bar*.

== Điều chỉnh không gian làm việc

Đưa con trỏ tới đường phân cách giữa Sidebar và vùng nội dung rồi kéo sang trái hoặc phải để đổi độ rộng. Khi kéo đủ hẹp về phía trái, Sidebar sẽ thu gọn. CAMS giữ độ rộng hợp lệ trước đó để khôi phục khi hiện lại.

Có ba cách thuận tiện để ẩn/hiện Sidebar: nhấn `Ctrl+B`, chọn *View → Toggle Sidebar*, hoặc nhấn lại biểu tượng *Dashboard* đang active. Nhấn lại lần nữa để hiện Sidebar. Cách dùng Activity Bar ở các chế độ khác đã được lưu ý ở phần trước.

#insert-image(
  "figures/gui/chapter-03/10-sidebar-collapsed.png",
  caption: [Workspace khi Sidebar được thu gọn.],
  width: 100%,
) <fig:ch03-sidebar-collapsed>

So sánh @fig:ch03-sidebar-collapsed với @fig:ch03-workspace-overview: Content Area rộng hơn, còn tab R1, tab SW1 và Information vẫn được giữ. Ẩn Sidebar không đóng tab, không đổi host active và không xóa lựa chọn thiết bị.

== Các phím tắt điều hướng

Các phím tắt sau tương ứng với các lệnh trong menu hiện tại. Với tổ hợp có dấu phẩy như `Ctrl+K, Ctrl+S`, nhấn tổ hợp đầu, thả ra rồi nhấn tổ hợp sau.

#report-table(
  columns: (1.25fr, 1.15fr, 1.7fr),
  header: ([Phím tắt], [Lệnh], [Tác dụng]),
  rows: (
    ([`Ctrl+O`], [Open Project], [Yêu cầu chuyển sang mở project.]),
    ([`Ctrl+S`], [Save Workspace], [Lưu Workspace hiện tại.]),
    ([`Ctrl+R`], [Reload UI], [Nạp lại nội dung giao diện đang xem.]),
    ([`Ctrl+B`], [Toggle Sidebar], [Ẩn hoặc hiện Sidebar.]),
    ([`Ctrl+Alt+D`], [Dashboard], [Trở về chế độ làm việc với thiết bị.]),
    ([`Ctrl+Alt+F`], [SFTP], [Mở khu vực SFTP hoặc client đã chọn.]),
    ([`Ctrl+Alt+L`], [System Logs], [Mở khu vực nhật ký hệ thống.]),
    ([`Ctrl+Alt+B`], [Database], [Mở trình duyệt dữ liệu/công cụ đã chọn khi khả dụng.]),
    ([`Ctrl+,`], [Settings], [Mở thiết lập ứng dụng.]),
    ([`Ctrl+K, Ctrl+S`], [Keyboard Shortcuts], [Mở bảng tham khảo phím tắt.]),
  ),
  caption: [Phím tắt menu và điều hướng Workspace.],
) <tab:ch03-shortcuts>

Khi con trỏ đang nhập trong ô văn bản, một số lệnh theo ngữ cảnh như Reload UI, Dashboard, SFTP, System Logs và Database tạm không được kích hoạt. Nếu phím tắt không có tác dụng, kết thúc việc nhập, chọn một vùng không phải ô văn bản và kiểm tra lệnh có đang bị vô hiệu hóa trong menu hay không. Hộp thoại đang mở cũng có thể giữ quyền thao tác.

Với Device Tabs đang hiển thị, dùng `Ctrl+Tab` để sang tab tiếp theo, `Ctrl+Shift+Tab` để về tab trước, `Ctrl+W` để đóng tab active và `Ctrl+Shift+T` để mở lại tab vừa đóng. Các phím này giúp di chuyển nhanh mà vẫn giữ nguyên danh sách thiết bị trong project.

== Thực hành điều hướng cơ bản

Bài tập sử dụng bản sao project mẫu `CAMS-Interface-Lab.ntp`, nằm trong thư mục `book/fixtures/chapter-03/` của bộ tài liệu. Mở project mẫu theo cách đã biết ở Chương 2, rồi bắt đầu từ Workspace đã sẵn sàng. Nếu chỉ có project trống, người dùng vẫn có thể luyện menu, Settings và ẩn/hiện Sidebar trước.

Trong project thực hành, R1, SW1 và SW3 thuộc nhóm *Disconnected*; mở rộng nhóm này để thấy các dòng thiết bị. Trạng thái này khác ảnh minh họa Connected, nhưng vẫn cho mở tab và xem các feature mà không tự mở session mạng. R2 giữ trạng thái Waiting. Không dùng lệnh Connect, Terminal hoặc lệnh cấu hình để hoàn thành bài tập.

1. Chọn *View → Dashboard* và xác định Devices Sidebar, vùng nội dung cùng Status Bar.
2. Trong nhóm Disconnected của Workspace mẫu, chọn *R1*. Kiểm tra tab R1 xuất hiện và có dấu nhấn active như @fig:ch03-device-tabs.
3. Chọn biểu tượng *Information*. Đọc tên màn hình và địa chỉ `192.0.2.1` ở đầu Content Area.
4. Chọn biểu tượng *Interface*, sau đó chọn *Routing*. Chỉ quan sát sự thay đổi màn hình, không nhập hoặc lưu cấu hình.
5. Chọn *SW1* ở Sidebar. Đối chiếu Feature Bar với @fig:ch03-feature-switch và nhận ra các nhóm Switching, Security, Monitoring.
6. Chuyển về tab *R1*. Kiểm tra tab nhớ Routing; chọn lại Information. Chọn R1 thêm lần nữa từ Sidebar và kiểm tra không có tab R1 trùng.
7. Nhấn `Ctrl+B` để ẩn Sidebar, rồi nhấn lại để hiện. Kiểm tra host và feature đang xem không thay đổi.
8. Chọn *View → Settings*. Quan sát Sidebar chuyển sang danh mục thiết lập, sau đó trở về *View → Dashboard*.
9. Mở *Help → Keyboard Shortcuts*, tìm phím tắt Toggle Sidebar rồi đóng hộp thoại. Chỉ ra vị trí Status Bar và biểu tượng thông báo.

Bài tập hoàn tất khi người dùng xác định được chế độ, host, feature đang xem và biết cách hiện lại Sidebar.

== Tóm tắt chương

Ghi nhớ luồng điều hướng thiết bị dưới đây. Menu Bar cung cấp các lệnh chung.

#flow-diagram(
  [Activity Bar\ Chọn chế độ],
  [Sidebar\ Chọn đối tượng],
  [Device Tab\ Xác định host],
  [Feature Bar\ Chọn chức năng],
  [Content Area\ Xem nội dung],
  [Status Bar\ Đọc trạng thái],
  max-per-row: 3,
  node-width: 44mm,
  max-node-width: 44mm,
  node-height: 20mm,
  max-node-height: 20mm,
)

Chương 4 sẽ tiếp tục với *Quản lý thiết bị*.
