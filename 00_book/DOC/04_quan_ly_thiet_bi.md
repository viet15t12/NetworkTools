# Quản lý thiết bị

Chương 3 đã giới thiệu đường đi từ Activity Bar tới Devices Sidebar,
Device Tabs, Feature Bar và vùng nội dung. Chương này sử dụng các thành
phần đó để xây dựng danh sách thiết bị, quản lý kết nối, thu thập cấu
hình và thực hiện thao tác trên nhiều host. Các phần cấu hình Interface,
Routing, VLAN và dịch vụ mạng được trình bày ở những chương sau.

## Tổng quan quản lý thiết bị

**Inventory** là danh sách thiết bị trong project đang mở. Mỗi thiết bị
được nhận diện bằng Host; tên hiển thị giúp người dùng phân biệt vai trò
trong hệ thống. Thêm thiết bị là lưu thông tin vào inventory; kết nối là
một bước riêng.

Ví dụ xuyên suốt chương dùng R1 (`192.168.56.11`, Router), R2
(`192.168.56.12`, Router), SW1 (`192.168.56.21`, Switch Layer 2) và SW3
(`192.168.56.23`, Switch Layer 3). Dùng địa chỉ tương ứng với mạng lab
của mình khi thực hành. Kiểm tra đúng project trước khi thay đổi danh
sách.

<figure>
<p><img src="../../figures/gui/chapter-04/01-devices-inventory.png"
style="width:47.0%" /></p>
<figcaption><p>Inventory gồm bốn thiết bị vừa được khai
báo.</p></figcaption>
</figure>

\<fig:ch04-inventory\>

Trong <a href="#fig" class="ref">[fig]</a>:ch04-inventory, cả bốn thiết
bị thuộc nhóm Waiting. Nút thêm một thiết bị và nút thêm nhiều thiết bị
nằm ở phần đầu panel DEVICES. Có thể đưa con trỏ lên từng biểu tượng để
xem tên lệnh trước khi chọn.

## Trạng thái thiết bị

Nhóm trạng thái giúp chọn thao tác phù hợp. Màu xanh, vàng và đỏ lần
lượt hỗ trợ nhận diện Connected, Waiting và Disconnected; hãy đọc cả
nhãn nhóm, không chỉ dựa vào màu.

|              |                                                                                                                                                                      |
|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Trạng thái   | Ý nghĩa và bước tiếp theo                                                                                                                                            |
| Waiting      | Thiết bị đã được lưu, đang chờ kết nối quản lý. Thiết bị mới thêm hoặc import có trạng thái này. Dùng **Connect** khi đã sẵn sàng.                                   |
| Connected    | CAMS đã đánh dấu kết nối thành công. Các lệnh Ping, thu thập cấu hình, Save configuration và Sync được mở theo ngữ cảnh. Vẫn cần đọc kết quả từng tác vụ.            |
| Disconnected | Thiết bị đang được đánh dấu mất/ngắt kết nối; một lần Connect thất bại cũng có thể đưa thiết bị vào nhóm này. Dùng **Reconnect** để đưa về Waiting, rồi **Connect**. |

**Lưu ý:** Trong CAMS hiện tại, **Disconnect connected** đưa host về
**Waiting**. **Reconnect** cũng chỉ đưa host từ Disconnected về Waiting,
chưa mở phiên mới. Lưu chỉnh sửa thiết bị đóng phiên hiện có và đưa
thiết bị về Waiting. Vì vậy không nên suy ra lịch sử kết nối chỉ từ tên
nhóm.

Thiết bị Waiting chưa cho mở vùng cấu hình bằng thao tác chọn đơn. Với
thiết bị khả dụng, chọn dòng trong Sidebar để mở hoặc chuyển tới tab.
Đóng tab chỉ đóng vùng làm việc; việc ngắt phiên và xóa host dùng các
lệnh riêng bên dưới.

## Thêm một thiết bị

### Mở cửa sổ Add New Device

Trong Dashboard, chọn nút thêm một thiết bị ở đầu DEVICES hoặc nhấn
`Ctrl+N`. Cửa sổ **Add New Device** xuất hiện như
<a href="#fig" class="ref">[fig]</a>:ch04-add-device. Đây là cửa sổ
riêng; dùng **Cancel** hoặc nút đóng nếu chưa muốn lưu.

<figure>
<p><img src="../../figures/gui/chapter-04/02-add-device-empty.png"
style="width:75.0%" /></p>
<figcaption><p>Cửa sổ khai báo một thiết bị mới.</p></figcaption>
</figure>

\<fig:ch04-add-device\>

### Khai báo Host và tên thiết bị

Nhập `192.168.56.11` vào **Host** và `R1` vào **Device Name**. Host phải
là IPv4 private hoặc domain hợp lệ có dạng phân cấp, chẳng hạn
`r1.lab.example`. Tên ngắn như `R1` dùng cho Device Name, không thay thế
domain trong Host. Nếu để trống Device Name, danh sách dùng Host làm tên
hiển thị.

|                     |                                                                                                                  |
|---------------------|------------------------------------------------------------------------------------------------------------------|
| Trường              | Ý nghĩa                                                                                                          |
| Host                | IPv4 private hoặc domain của thiết bị. Host là giá trị nhận diện và không được trùng với host đã có.             |
| Device Name         | Tên hiển thị trong CAMS, ví dụ R1 hoặc Core-Router.                                                              |
| Protocol            | Giao thức quản lý được khai báo cho thiết bị.                                                                    |
| Port                | Cổng TCP của dịch vụ quản lý, từ 1 đến 65535.                                                                    |
| OS                  | Platform/driver mà CAMS dùng để giao tiếp với thiết bị. Chọn theo hệ điều hành thực tế.                          |
| Role                | Vai trò Router, Switch Layer 2 hoặc Switch Layer 3; quyết định nhóm feature được hiển thị.                       |
| Username / Password | Thông tin xác thực dùng khi mở phiên quản lý. Form cho phép để trống, nhưng dịch vụ của thiết bị có thể yêu cầu. |

**Lưu ý:** Add Device hiện chỉ nhận IPv4 thuộc các dải `10.x.x.x`,
`172.16.x.x` đến `172.31.x.x`, hoặc `192.168.x.x`. IPv4 public và các
dải địa chỉ dành cho ví dụ tài liệu không được form này chấp nhận.

### Chọn giao thức và cổng

Chọn **SSH** cho ví dụ R1. Khi đổi Protocol trong form thêm mới, CAMS tự
điền cổng tương ứng. Nếu dịch vụ dùng cổng khác, sửa Port sau khi chọn
giao thức.

|          |               |
|----------|---------------|
| Protocol | Cổng mặc định |
| SSH      | `22`          |
| TELNET   | `23`          |
| NETCONF  | `830`         |
| RESTCONF | `443`         |

**Giới hạn hiện tại:** Form cho phép khai báo cả bốn giao thức, nhưng
luồng phiên CLI và Get running-config trong chương này hỗ trợ
**SSH/TELNET**. Khai báo NETCONF hoặc RESTCONF không có nghĩa các lệnh
kết nối và cấu hình qua CLI sẽ hoạt động.

### Chọn hệ điều hành và vai trò

Ví dụ R1 dùng **OS: cisco_ios** và **Role: rou**. Các lựa chọn OS hiện
có là `cisco_ios`, `cisco_xe`, `cisco_nxos`, `cisco_asa` và
`mikrotik_routeros`. Việc chọn OS không tự cấu hình dịch vụ quản lý trên
thiết bị.

|         |                |        |
|---------|----------------|--------|
| Mã Role | Vai trò        | Ví dụ  |
| `rou`   | Router         | R1, R2 |
| `sw2`   | Switch Layer 2 | SW1    |
| `sw3`   | Switch Layer 3 | SW3    |

Role mô tả cách CAMS tổ chức chức năng cho thiết bị; nó không chuyển một
switch Layer 2 thành thiết bị Layer 3. Nếu nhóm chức năng không đúng,
kiểm tra Role và tab đang active.

### Khai báo thông tin xác thực

Nhập tài khoản được cấp cho thiết bị vào Username và Password. Username
chỉ nhận chữ cái Latin, chữ số, dấu gạch dưới, dấu chấm và dấu gạch
ngang. Password không được chứa khoảng trắng. Giữ mật khẩu ở chế độ che
khi trình chiếu hoặc chụp ảnh.

<figure>
<p><img src="../../figures/gui/chapter-04/03-add-device-filled.png"
style="width:75.0%" /></p>
<figcaption><p>Thông tin của R1 đã được điền, mật khẩu được
che.</p></figcaption>
</figure>

\<fig:ch04-add-filled\>

### SSH Compatibility cho thiết bị cũ

Nút **SSH Compatibility — Legacy devices only** chỉ khả dụng khi
Protocol là SSH. Đây là thiết lập nâng cao cho từng thiết bị, dành cho
trường hợp đã xác định thiết bị cũ cần thuật toán tương thích riêng.

<figure>
<p><img src="../../figures/gui/chapter-04/05-ssh-compatibility.png"
style="width:66.0%" /></p>
<figcaption><p>Các trường tương thích SSH riêng cho một thiết
bị.</p></figcaption>
</figure>

\<fig:ch04-ssh\>

Các trường **Key exchange algorithms**, **Host key algorithms**,
**Ciphers** và **MAC algorithms** nhận danh sách phân cách bằng dấu
phẩy. **Note** ghi lý do cần ngoại lệ. Chữ màu nhạt trong ô trống là gợi
ý của giao diện, không phải bộ thuật toán đã được bật. Để trống các ô
nếu không cần thay đổi mặc định.

**Cảnh báo:** Thuật toán SSH legacy có thể làm giảm mức an toàn của kết
nối. Chỉ thêm ngoại lệ cần thiết cho đúng thiết bị và theo chính sách
của hệ thống.

**Close** trở về form; các thiết lập được lưu cùng thao tác Add Device
hoặc Save Changes. **Reset to default** xóa các ngoại lệ; trong Edit,
thao tác reset cập nhật ngay thiết lập đã lưu. **Test SSH** chỉ khả dụng
khi sửa thiết bị đã có, lưu các giá trị đang nhập rồi thực hiện kiểm tra
kết nối SSH. Chỉ dùng khi đã sẵn sàng truy cập thiết bị.

### Lưu thiết bị

Kiểm tra lại Host, Protocol, Port, OS và Role rồi chọn **Add Device**.
Nếu form báo lỗi, sửa trường được chỉ ra rồi thử lại. Host đã có trong
inventory không thể thêm lần nữa; hãy dùng Edit nếu cần đổi thông tin.

Khi lưu thành công, cửa sổ đóng và Devices Panel nạp lại danh sách. R1
xuất hiện trong Waiting như
<a href="#fig" class="ref">[fig]</a>:ch04-added-waiting; thao tác thêm
chưa tự kết nối tới thiết bị.

<figure>
<p><img src="../../figures/gui/chapter-04/04-device-added-waiting.png"
style="width:47.0%" /></p>
<figcaption><p>R1 xuất hiện trong Waiting sau khi được
thêm.</p></figcaption>
</figure>

\<fig:ch04-added-waiting\>

## Thêm nhiều thiết bị

### Add Multiple Devices

Chọn nút thêm nhiều thiết bị ở đầu DEVICES hoặc nhấn `Ctrl+Alt+N`. **Add
Multiple Devices** có phần thiết lập chung, bảng nhập từng host và thanh
nút ở cuối cửa sổ.

<figure>
<p><img src="../../figures/gui/chapter-04/06-add-multiple-devices.png"
style="width:100.0%" /></p>
<figcaption><p>Cửa sổ thêm nhiều thiết bị và các nút nhập danh
sách.</p></figcaption>
</figure>

\<fig:ch04-batch-empty\>

### Shared connection settings

Phần **Shared connection settings** gồm Protocol, Port, OS, Role,
Username và Password. Dòng mới kế thừa các giá trị này. Khi thay đổi
thiết lập chung, các dòng đã có không tự đổi: dùng **Apply to all** để
cập nhật chúng, rồi chỉnh riêng từng dòng nếu cần.

Ví dụ, đặt SSH, 22, cisco_ios, rou và tài khoản dùng chung trước khi tạo
các dòng mới. Sau đó đổi Role của SW1 thành sw2 và SW3 thành sw3. Nếu
nhấn Apply to all sau bước đó, Role riêng của các dòng cũng bị thay bằng
Role chung; cần kiểm tra lại trước khi lưu.

### Thêm và chỉnh sửa các dòng

R1 đã có từ bước trước, vì vậy chỉ thêm R2, SW1 và SW3 vào bảng. Dùng
**Add another row** để thêm dòng; sửa trực tiếp Host, Name và các trường
còn lại. Nút xóa ở cuối dòng bỏ dòng nhập đó; **Clear** đưa bảng về một
dòng trống, không xóa các thiết bị đã lưu trong inventory.

<figure>
<p><img src="../../figures/gui/chapter-04/07-batch-devices-filled.png"
style="width:100.0%" /></p>
<figcaption><p>Ba thiết bị bổ sung với Role riêng trên từng
dòng.</p></figcaption>
</figure>

\<fig:ch04-batch-filled\>

<a href="#fig" class="ref">[fig]</a>:ch04-batch-detail phóng phần Host
và Name để dễ đối chiếu. Mỗi host chỉ xuất hiện một lần trong danh sách
nhập.

<figure>
<p><img src="../../figures/gui/chapter-04/19-batch-table-detail.png"
style="width:85.0%" /></p>
<figcaption><p>Chi tiết Host và Name của ba dòng nhập.</p></figcaption>
</figure>

\<fig:ch04-batch-detail\>

### Xác nhận danh sách thiết bị

Nút **Add 3 devices** thể hiện số dòng đã nhập trong ví dụ. Chọn nút này
để kiểm tra và lưu toàn bộ danh sách; có thể dùng `Ctrl+Enter` khi cửa
sổ đang mở. Nếu một dòng không hợp lệ hoặc cùng host xuất hiện hai lần
trong bảng, CAMS báo dòng lỗi để sửa trước khi thêm.

Nếu host đã tồn tại trong inventory, backend bỏ qua host đó và thông báo
số lượng được thêm/bỏ qua. Kiểm tra kết quả thay vì chỉ đếm số dòng
trước khi submit. Các host mới được lưu ở Waiting. Nếu toàn bộ danh sách
đều đã tồn tại, không có thiết bị mới được thêm và cửa sổ giữ thông báo
lỗi.

### Import từ Excel hoặc JSON

Dùng **Import file** ở cuối cửa sổ để chọn tệp `.xlsx` hoặc `.json`.
Excel dùng hàng đầu làm tiêu đề cột và dữ liệu ở worksheet đầu. JSON có
thể là danh sách đối tượng, hoặc một đối tượng chứa danh sách dưới khóa
`devices`, `rows` hay `items`.

Các cột thường dùng gồm `host`, `name`, `protocol`, `port`, `os`,
`role`, `username` và `password`. Các tên thay thế như `ip`,
`device_name`, `user` và `pass` cũng được nhận. Ví dụ JSON tối thiểu,
không chứa mật khẩu:

``` json
[
  {"host": "192.168.56.99", "name": "TEMP-SW",
   "protocol": "SSH", "port": 22,
   "os": "cisco_ios", "role": "sw2"}
]
```

**Lưu ý:** Import ghi thiết bị trực tiếp vào inventory. Khi có thiết bị
được thêm, cửa sổ đóng; không có bước nạp các dòng để duyệt lại trong
bảng Batch. Kiểm tra tệp trước khi chọn, nhất là Host, cổng, vai trò và
thông tin xác thực. Luồng import hiện không áp dụng đầy đủ các kiểm tra
của form nhập tay.

Host trùng hoặc dòng thiếu Host được bỏ qua; thông báo cho biết số lượng
Imported và Skipped. Import không cập nhật thông tin của host đã tồn
tại. <a href="#fig" class="ref">[fig]</a>:ch04-import minh họa TEMP-SW
được thêm vào Waiting trong một inventory đang có các trạng thái khác
nhau.

<figure>
<p><img src="../../figures/gui/chapter-04/18-import-result.png"
style="width:47.0%" /></p>
<figcaption><p>TEMP-SW xuất hiện trong inventory sau
import.</p></figcaption>
</figure>

\<fig:ch04-import\>

### Sample import file

Nút **Download template** mở hộp chọn nơi lưu với tên gợi ý
**Template_CAMS-MultipleDevices.xlsx**. Ở phiên bản được khảo sát, chức
năng này có thể báo **Sample file not found** do đường dẫn mẫu chưa khớp
tệp được đóng gói. Nếu gặp lỗi, dùng tệp `templates/EXdevices.xlsx` đi
kèm bản source, hoặc tạo JSON theo ví dụ trên. Không đổi tên phần mở
rộng của một tệp văn bản thành `.xlsx`.

## Tìm kiếm và lọc thiết bị

Ô **Search devices…** tìm theo tên hoặc địa chỉ IP; tìm tên không phân
biệt chữ hoa/thường. Nhập `SW` để chỉ giữ SW1 và SW3 như
<a href="#fig" class="ref">[fig]</a>:ch04-search. Xóa từ khóa để trở lại
danh sách đầy đủ.

<figure>
<p><img src="../../figures/gui/chapter-04/08-search-filter.png"
style="width:47.0%" /></p>
<figcaption><p>Tìm SW để giữ lại các switch phù hợp.</p></figcaption>
</figure>

\<fig:ch04-search\>

Nút **Filter** mở các nhóm STATUS và DEVICE TYPE. Có thể chọn Connected,
Waiting hoặc Disconnected trong STATUS; khi không chọn trạng thái nào,
CAMS hiển thị mọi trạng thái. Từ khóa và bộ lọc được áp dụng đồng thời.
Nhấn mũi tên của nhóm để mở rộng nếu nhóm đang thu gọn.

**Giới hạn hiện tại:** Các lựa chọn DEVICE TYPE chưa khớp mã phân loại
thiết bị trong inventory, nên chọn Router hoặc Switch có thể làm danh
sách trống dù có thiết bị tương ứng. Bỏ chọn lọc loại và dùng Search
theo tên/IP kết hợp STATUS.

## Chọn nhiều thiết bị

Chuột phải lên một host rồi chọn **Select multiple** để bắt đầu. Có thể
giữ `Ctrl` và nhấn từng dòng để chọn/bỏ chọn; giữ `Shift` và nhấn để
chọn một khoảng trong danh sách đang hiển thị. Khi đã bật chọn nhiều,
nhấn một dòng sẽ đổi trạng thái chọn, không chuyển tab như chế độ chọn
đơn.

<figure>
<p><img src="../../figures/gui/chapter-04/13-multi-select.png"
style="width:47.0%" /></p>
<figcaption><p>Bốn host được chọn với trạng thái hỗn
hợp.</p></figcaption>
</figure>

\<fig:ch04-multi-select\>

Thanh chọn nhiều hiển thị số lượng host đã chọn. **Select all visible
hosts** hoặc `Ctrl+A` trong chế độ này chọn các host của danh sách đang
được lọc, kể cả host trong nhóm đang thu gọn. **Clear selection and
exit**, nút xóa lựa chọn hoặc `Esc` thoát chế độ chọn nhiều. Khi con trỏ
đang nhập trong Search, phím theo ngữ cảnh có thể chưa tác động tới danh
sách.

Chuột phải lên host đã chọn giữ nguyên nhóm lựa chọn. Chuột phải lên một
host chưa chọn sẽ trở lại ngữ cảnh riêng của host đó. Trước khi chạy
lệnh, luôn đọc số host ở đầu menu.

**Ghi chú:** Chọn nhiều chỉ chọn các bản ghi trong inventory, chưa thực
hiện thao tác mạng. Chỉ khi kích hoạt Connect, Get configs hoặc
Disconnect thì tác vụ tương ứng mới bắt đầu.

## Menu ngữ cảnh của thiết bị

Chuột phải lên dòng host để mở menu. **Select multiple**, **Edit**,
**CAMS Terminal** và **Delete Host…** có trong menu chọn đơn. Những mục
còn lại phụ thuộc trạng thái như
<a href="#tab" class="ref">[tab]</a>:ch04-context.

|              |                                                     |
|--------------|-----------------------------------------------------|
| Trạng thái   | Lệnh theo trạng thái trong menu chọn đơn            |
| Waiting      | Connect; Ping vẫn hiện nhưng bị làm mờ.             |
| Connected    | Ping; Get running-config; Save configuration; Sync. |
| Disconnected | Reconnect; Ping vẫn hiện nhưng bị làm mờ.           |

Trong lúc tác vụ liên quan đang chạy, một số lệnh tạm bị vô hiệu hóa.
Menu hiện không có Disconnect riêng cho một host; dùng chế độ chọn nhiều
ngay cả khi chỉ muốn ngắt một thiết bị.

<figure>
<p><img src="../../figures/gui/chapter-04/09-device-context-waiting.png"
style="width:66.0%" /></p>
<figcaption><p>Menu của thiết bị Waiting với lệnh
Connect.</p></figcaption>
</figure>

\<fig:ch04-context-waiting\>

<figure>
<p><img src="../../figures/gui/chapter-04/11-device-context-connected.png"
style="width:66.0%" /></p>
<figcaption><p>Menu của thiết bị Connected.</p></figcaption>
</figure>

\<fig:ch04-context-connected\>

## Kết nối thiết bị

### Connect

Với R1 đang Waiting, chuột phải lên R1 và chọn **Connect**. CAMS dùng
thông tin đã lưu để mở phiên quản lý, thu thập running-config, lưu bản
sao và đồng bộ dữ liệu cấu hình được hỗ trợ vào Workspace. Chờ tác vụ
kết thúc, theo dõi Status Bar/thông báo và kiểm tra R1 chuyển sang
Connected.

<figure>
<p><img src="../../figures/gui/chapter-04/10-device-connected.png"
style="width:47.0%" /></p>
<figcaption><p>R1 chuyển sang Connected sau thao tác
Connect.</p></figcaption>
</figure>

\<fig:ch04-connected\>

Nếu Connect thất bại, kiểm tra Host, cổng, giao thức, tài khoản và khả
năng truy cập dịch vụ quản lý từ máy chạy CAMS. Sửa thông tin bằng Edit
khi cần. Với cảnh báo khóa host SSH, kiểm tra thông tin nhận diện trước
khi chấp nhận kết nối.

Trạng thái Connected không bảo đảm mọi bước thu thập, backup hoặc đồng
bộ đã thành công: CAMS có thể giữ kết nối và báo cảnh báo cho một bước
tiếp theo. Đọc thông báo chi tiết; không bấm Connect lặp lại khi tác vụ
cũ còn chạy.

### Reconnect

Với host Disconnected, mở menu như
<a href="#fig" class="ref">[fig]</a>:ch04-context-disconnected và chọn
**Reconnect**. Thiết bị chuyển về Waiting. Sau đó chuột phải lần nữa,
chọn **Connect** để thực sự mở lại phiên. Phím `Ctrl+Alt+R` thực hiện
cùng bước đưa về Waiting.

<figure>
<p><img src="../../figures/gui/chapter-04/12-device-context-disconnected.png"
style="width:66.0%" /></p>
<figcaption><p>Lệnh Reconnect của thiết bị
Disconnected.</p></figcaption>
</figure>

\<fig:ch04-context-disconnected\>

### Disconnect

Chọn **Select multiple**, giữ lại host Connected cần ngắt, rồi dùng
**Disconnect connected (N)** hoặc `Ctrl+Shift+D`. Có thể chỉ chọn một
host. CAMS đóng phiên quản lý của những host Connected đủ điều kiện và
đưa chúng về Waiting; inventory, cấu hình đã lưu và lịch sử backup vẫn
được giữ.

Muốn kết nối lại sau thao tác này, dùng Connect từ Waiting. Không cần
chọn Reconnect. Đóng Device Tab cũng không thay cho lệnh ngắt phiên.

## Kiểm tra kết nối bằng Ping

Khi host Connected, chuột phải rồi chọn **Ping** hoặc dùng `Ctrl+Alt+P`
trong ngữ cảnh thiết bị. CAMS yêu cầu kiểm tra khả năng phản hồi của
host và đưa kết quả tới thông báo/Status Bar. Nếu cần xem lại, mở khu
vực thông báo.

Ping bị làm mờ trong menu Waiting và Disconnected. Kết quả Ping không
thay thế kiểm tra đăng nhập hay kết quả đồng bộ cấu hình. Khi không có
phản hồi, kiểm tra đường đi mạng và chính sách ICMP của hệ thống trước
khi kết luận dịch vụ quản lý không hoạt động.

## Thu thập running-config

**Get running-config** đọc cấu hình đang hoạt động trên thiết bị. Với R1
Connected, chuột phải chọn lệnh này và chờ kết quả. Luồng hiện tại thu
thập qua SSH/TELNET, lưu vào lịch sử backup của host, đồng thời áp dụng
chính sách đồng bộ tự động cho các dữ liệu cấu hình được hỗ trợ.

Mở tab R1, chọn **Information**, rồi xem phần **Snapshot** và
**Version**. Chọn phiên bản cần đọc trong danh sách.
<a href="#fig" class="ref">[fig]</a>:ch04-running-config minh họa phần
nội dung đã thu thập; cấu hình ngắn giúp nhận diện đúng hostname và địa
chỉ, chưa phải bài cấu hình Interface.

<figure>
<p><img src="../../figures/gui/chapter-04/17-running-config-result.png"
style="width:100.0%" /></p>
<figcaption><p>Một phiên bản running-config trong
Information.</p></figcaption>
</figure>

\<fig:ch04-running-config\>

Mỗi lần thu thập thành công tạo một mốc lịch sử, kể cả khi nội dung chưa
đổi. **Compare** dùng để đối chiếu phiên bản. Nếu chưa có dữ liệu hoặc
tác vụ thất bại, kiểm tra thông báo và thử lại khi phiên quản lý sẵn
sàng. Mốc backup này thuộc riêng thiết bị; snapshot toàn project trong
menu File được trình bày ở Chương 2.

## Lưu cấu hình và đồng bộ

**Save configuration** lưu cấu hình đang chạy thành cấu hình khởi động
trên thiết bị qua driver của phiên quản lý hiện có. Thiết bị/driver phải
hỗ trợ thao tác lưu; đọc kết quả để biết thành công hay bị từ chối. Đây
là thao tác lên thiết bị và khác với **Save Workspace**, vốn lưu project
CAMS.

**Sync** thu thập running-config mới để đối chiếu và cập nhật dữ liệu
cấu hình được hỗ trợ trong Workspace. Sync không đẩy toàn bộ dữ liệu
Workspace lên thiết bị. Nếu không có xung đột, CAMS áp dụng chế độ an
toàn. Khi có thay đổi cục bộ đang chờ, hộp **Manual Sync conflict** cho
chọn:

- **Keep pending changes**: bỏ qua các nhóm dữ liệu đang có thay đổi
  chờ, giữ phần chỉnh sửa cục bộ đó.

- **Use device state**: bỏ thay đổi cục bộ đang chờ và thay bằng trạng
  thái mới từ thiết bị.

- **Cancel**: hủy quyết định đồng bộ lần này.

**Lưu ý:** Chỉ chọn **Use device state** khi đã kiểm tra và chấp nhận bỏ
phần chỉnh sửa cục bộ liên quan. Kết quả backup thành công và kết quả
đồng bộ là hai bước riêng; đọc cảnh báo nếu một bước chưa hoàn tất.

## Thao tác hàng loạt

Sau khi chọn nhiều host, chuột phải lên một dòng đã chọn để mở menu
nhóm. Ví dụ <a href="#fig" class="ref">[fig]</a>:ch04-batch-actions gồm
R1 và SW1 Connected, R2 Waiting, SW3 Disconnected. Do đó menu có đúng
một host đủ điều kiện Connect và hai host đủ điều kiện Get configs hoặc
Disconnect.

<figure>
<p><img src="../../figures/gui/chapter-04/14-multi-select-actions.png"
style="width:95.0%" /></p>
<figcaption><p>Thao tác hàng loạt với bốn thiết bị được
chọn.</p></figcaption>
</figure>

\<fig:ch04-batch-actions\>

|                                |                         |
|--------------------------------|-------------------------|
| Lệnh trong ví dụ               | Host thực sự được xử lý |
| Connect waiting (1)            | R2                      |
| Get configs from connected (2) | R1 và SW1               |
| Disconnect connected (2)       | R1 và SW1               |

SW3 vẫn nằm trong số bốn host đã chọn nhưng không thuộc mục tiêu của ba
lệnh trên. Muốn kết nối SW3, trước hết dùng Reconnect để đưa host về
Waiting. Lệnh có số lượng bằng không bị vô hiệu hóa.

Theo dõi tiến độ và kết quả từng host; lỗi của một host không có nghĩa
toàn bộ nhóm đều thất bại. Khi batch hoàn tất, CAMS thông báo số thành
công/thất bại, nạp lại danh sách và thoát chế độ chọn nhiều. Chọn lại
nhóm nếu muốn chạy tác vụ tiếp theo.

## Chỉnh sửa thiết bị

Chuột phải lên R1, chọn **Edit**, đổi **Device Name** thành
`Core-Router` rồi chọn **Save Changes**. Các trường kết nối và phân loại
có thể được chỉnh trong cùng cửa sổ.
<a href="#fig" class="ref">[fig]</a>:ch04-edit minh họa trạng thái ngay
trước khi lưu.

<figure>
<p><img src="../../figures/gui/chapter-04/15-edit-device.png"
style="width:75.0%" /></p>
<figcaption><p>Đổi tên R1 thành Core-Router trong Edit
Device.</p></figcaption>
</figure>

\<fig:ch04-edit\>

**Host** chỉ đọc trong Edit; không sửa IP trực tiếp tại đây. Nếu cần một
host mới, thêm bản ghi mới và kiểm tra trước khi quyết định xóa bản ghi
cũ. Xóa rồi thêm lại không bảo toàn lịch sử gắn với host cũ.

Lưu chỉnh sửa đóng phiên quản lý hiện có và đưa thiết bị về Waiting. Sau
khi kiểm tra thông tin mới, dùng Connect để mở lại phiên. Đừng hiểu
trạng thái Waiting sau Edit là mất bản ghi.

## Xóa thiết bị

Dùng một thiết bị tạm, chẳng hạn TEMP-SW (`192.168.56.99`), để kiểm tra
quy trình. Chuột phải lên đúng host, chọn **Delete Host…**. CAMS mở hộp
**Permanently delete host?** như
<a href="#fig" class="ref">[fig]</a>:ch04-delete.

<div>

**Cảnh báo xóa vĩnh viễn:** Delete Host xóa thiết bị cùng cấu hình liên
quan, dữ liệu đã thu thập, dữ liệu Syslog và lịch sử backup của host
trong Workspace. Thao tác này không có Undo. Nếu cần giữ dữ liệu, lưu
bản project hoặc snapshot phù hợp trước khi xóa; kiểm tra kỹ địa chỉ
trong hộp xác nhận.

</div>

<figure>
<p><img src="../../figures/gui/chapter-04/16-delete-device-confirmation.png"
style="width:100.0%" /></p>
<figcaption><p>Xác nhận trước khi xóa vĩnh viễn thiết bị
tạm.</p></figcaption>
</figure>

\<fig:ch04-delete\>

Để xác nhận, đánh dấu ô đã hiểu hậu quả và nhập chính xác chuỗi mà hộp
thoại yêu cầu, ví dụ `DELETE 192.168.56.99`. Chỉ khi cả hai điều kiện
đúng, nút **Permanently Delete** mới khả dụng. Chọn **Cancel** để giữ
nguyên dữ liệu.

Khi xác nhận, CAMS đóng phiên quản lý của host rồi thực hiện xóa. Kiểm
tra thông báo kết quả và danh sách sau đó. Lệnh này xóa dữ liệu quản lý
trong project, không phải lệnh xóa cấu hình trên thiết bị mạng. CAMS
hiện không có phím Delete để xóa device đang chọn; phải đi qua menu
chuột phải và hộp xác nhận.

## Phím tắt quản lý thiết bị

Các phím trong <a href="#tab" class="ref">[tab]</a>:ch04-shortcuts hoạt
động theo ngữ cảnh. Đưa focus ra khỏi Search và đóng hộp thoại đang giữ
thao tác trước khi dùng phím của Devices Panel. Các lệnh Ping, Connect
và Reconnect yêu cầu trạng thái phù hợp, giống lệnh menu.

|                |                                                      |
|----------------|------------------------------------------------------|
| Phím tắt       | Tác dụng                                             |
| `Ctrl+N`       | Mở Add New Device.                                   |
| `Ctrl+Alt+N`   | Mở Add Multiple Devices.                             |
| `F2`           | Edit thiết bị đang active trong Sidebar.             |
| `Ctrl+Alt+P`   | Ping thiết bị Connected.                             |
| `Ctrl+Alt+C`   | Connect thiết bị Waiting.                            |
| `Ctrl+Alt+R`   | Đưa thiết bị Disconnected về Waiting.                |
| `Ctrl+Shift+C` | Connect các host Waiting đang chọn.                  |
| `Ctrl+Shift+R` | Get running-config các host Connected đang chọn.     |
| `Ctrl+Shift+D` | Ngắt các host Connected đang chọn; đưa về Waiting.   |
| `Ctrl+A`       | Chọn toàn bộ danh sách đang hiển thị khi chọn nhiều. |
| `Esc`          | Xóa lựa chọn và thoát chọn nhiều.                    |
| `` Ctrl+` ``   | Mở CAMS Terminal cho thiết bị của tab active.        |

Trong Add New Device, `Enter` gửi form khi không có hộp phụ đang mở.
Trong Batch, `Ctrl+Enter` gửi danh sách. Với Device Tabs, `Ctrl+T` cũng
yêu cầu mở form thêm thiết bị khi ngữ cảnh tab khả dụng. Không dùng phím
tắt để bỏ qua kiểm tra thông tin trước khi lưu.

## Thực hành quản lý một inventory nhỏ

**Mục tiêu:** tạo inventory bốn thiết bị và thực hiện trọn vòng quản lý
trên một project lab. Chuẩn bị các thiết bị được phép truy cập, dịch vụ
SSH và thông tin xác thực phù hợp; dùng địa chỉ lab của mình nếu khác ví
dụ.

1.  Mở project lab, dùng Add Device thêm R1 tại `192.168.56.11`, OS
    cisco_ios, Role rou.

2.  Dùng Add Multiple Devices thêm R2, SW1 và SW3; kiểm tra Role lần
    lượt rou, sw2, sw3. Không thêm lại R1.

3.  Tìm `SW1` trong Search, kiểm tra địa chỉ; xóa từ khóa khi đã xác
    định đúng thiết bị.

4.  Quan sát bốn host Waiting và kiểm tra tên/IP trước khi kết nối.

5.  Chuột phải R1 → Connect. Chờ kết quả và xác nhận R1 Connected. Kết
    nối SW1 để có thêm một host Connected nếu cần thử batch.

6.  Bật Select multiple và chọn cả bốn host. Đọc số lượng trên thanh
    chọn.

7.  Mở menu nhóm, xác định host đủ điều kiện cho từng lệnh. Chỉ chạy Get
    configs trên những host Connected đã chuẩn bị.

8.  Thoát chọn nhiều; Edit SW1 và đổi tên thành `Access-SW1`. Kiểm tra
    host vẫn giữ nguyên và trở về Waiting sau khi lưu.

9.  Mở tab R1 → Information → Snapshot. Nếu chưa có cấu hình, chạy Get
    running-config và đọc kết quả trước khi xem lại.

10. Thêm TEMP-SW với một Host tạm chưa tồn tại; mở Delete Host, kiểm tra
    cảnh báo và xác nhận xóa khi không cần giữ dữ liệu đó. Kiểm tra bốn
    host chính vẫn còn.

Hoàn tất khi tìm được từng thiết bị, giải thích được trạng thái hiện
tại, biết host nào được xử lý bởi batch và phân biệt được Save
Workspace, Save configuration cùng Get running-config.

## Tóm tắt chương

Thêm hoặc import tạo bản ghi trong inventory ở Waiting. Connect mở phiên
và thực hiện thu thập/đồng bộ; các lệnh quản lý tiếp theo cần trạng thái
và giao thức phù hợp. Sơ đồ dưới đây tóm tắt đường đi thông thường,
trong đó nhóm lệnh ở nút cuối là các lựa chọn theo nhu cầu.

- Add / Import

<!-- -->

- Inventory  
  Waiting

<!-- -->

- Connect

<!-- -->

- Connected

<!-- -->

- Ping / Running-config / Sync

Hai đường quay lại trạng thái chờ cần nhớ:

- Connected

<!-- -->

- Disconnect

<!-- -->

- Waiting

<!-- -->

- Connect

<!-- -->

- Connected

<!-- -->

- Disconnected

<!-- -->

- Reconnect

<!-- -->

- Waiting

<!-- -->

- Connect

<!-- -->

- Connected

Edit cập nhật thông tin nhưng đóng phiên hiện có; Delete Host xóa vĩnh
viễn bản ghi và dữ liệu liên quan. Khi đã quản lý được inventory và
phiên thiết bị, người dùng có thể chuyển sang các chương cấu hình chuyên
môn.
