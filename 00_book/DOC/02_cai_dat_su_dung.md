# Cài đặt và Bắt đầu sử dụng CAMS

Chương này hướng dẫn người dùng chạy CAMS từ mã nguồn, đi qua cửa sổ
Welcome, tạo hoặc mở một project `.ntp`, rồi xác nhận Workspace đã sẵn
sàng. Chương này chưa yêu cầu thiết bị mạng thật và chưa hướng dẫn cấu
hình router, switch hoặc dịch vụ mạng.

## Yêu cầu trước khi cài đặt

### Thành phần bắt buộc

Để chạy ứng dụng desktop từ mã nguồn, hệ thống cần có:

- Python `3.11` trở lên;

- `uv` để tạo môi trường Python và cài dependency từ `pyproject.toml`
  cùng `uv.lock`;

- Git nếu lấy mã nguồn bằng lệnh `git clone`;

- các thư viện hệ thống cần thiết để Qt/PyQt6 hiển thị giao diện.

Windows là nền tảng phát triển chính. CAMS cũng được chạy và kiểm tra
trên Linux; bản phân phối Linux phải có các thư viện đồ họa, font và thư
viện Qt tương ứng với PyQt6.

**Ghi chú:** Người dùng không cần quyền truy cập router, switch hoặc
thiết bị thật để hoàn thành chương này. Project trống vẫn có thể được
tạo, mở, lưu và quản lý snapshot.

### Thành phần tùy chọn

Các thành phần sau chỉ cần khi sử dụng chức năng liên quan:

- TShark hoặc Wireshark: dùng cho Device Logs và thu thập gói tin trên
  mạng được cấp quyền;

- Rust toolchain (`cargo`): chỉ cần khi phải tự biên dịch CAMS Terminal
  companion;

- CMake và compiler C++: chỉ cần khi phải tự biên dịch Syslog collector
  trên Linux;

- quyền truy cập cùng credential của thiết bị: chỉ cần ở các chương thực
  hành kết nối và cấu hình thiết bị.

**Mẹo:** Nếu mục tiêu trước mắt chỉ là mở ứng dụng và tạo Workspace, hãy
chuẩn bị Python và `uv` trước. Các thành phần tùy chọn có thể bổ sung
sau.

## Lấy mã nguồn CAMS

Kho Git đang được sử dụng bởi project là `viet15t12/CAMS`. Từ Terminal,
PowerShell hoặc Command Prompt, chạy:

``` sh
git clone https://github.com/viet15t12/CAMS.git
cd CAMS
```

Root repository là thư mục làm việc của ứng dụng desktop. Các lệnh trong
phần còn lại của chương được thực hiện tại đây.

Nếu nhận mã nguồn dưới dạng file nén thay vì Git, hãy giải nén toàn bộ
repository, mở Terminal tại thư mục `CAMS`, rồi tiếp tục với bước kiểm
tra môi trường. Bản mã nguồn phải giữ nguyên các thư mục `UI/`, `core/`,
`features/`, `infrastructure/` và file khóa dependency.

## Chuẩn bị Python và uv

### Kiểm tra Python

Chạy một trong các lệnh sau, tùy cách Python được đăng ký trên hệ điều
hành:

``` sh
python --version
```

Trên một số hệ thống Linux, lệnh tương ứng là:

``` sh
python3 --version
```

Kết quả phải là Python `3.11` hoặc mới hơn, ví dụ `Python 3.12.x`.

### Kiểm tra uv

``` sh
uv --version
```

Nếu Terminal hiển thị số phiên bản của `uv`, có thể tiếp tục. Nếu hệ
thống báo không nhận diện lệnh, hãy cài `uv`, mở lại Terminal và kiểm
tra lại trước khi chạy CAMS.

## Khởi chạy CAMS

CAMS có launcher dành cho từng nền tảng và một lệnh chạy trực tiếp.
Launcher phù hợp khi cần đồng bộ dependency, kiểm tra thành phần native
hoặc chuẩn bị môi trường. Lệnh trực tiếp phù hợp khi môi trường đã sẵn
sàng.

### Windows

Từ `CAMS`, chạy:

``` cmd
cams.bat
```

Launcher hiển thị menu. Ở lần chuẩn bị đầu tiên, chọn tác vụ setup hoặc
**Full setup and run**. Khi môi trường đã sẵn sàng, có thể chạy trực
tiếp chế độ run:

``` cmd
cams.bat run
```

### Linux: cài như một ứng dụng desktop

Chạy bộ cài đặt user-local một lần:

``` sh
./install.sh
```

Sau đó mở **CAMS** từ menu ứng dụng hoặc chạy lệnh `cams` ở bất kỳ thư
mục nào. Bộ cài không cần `sudo`, và việc chạy lại bộ cài để cập nhật
không xóa database người dùng.

### Linux: chạy trực tiếp để phát triển

``` sh
./cams.sh
```

Nếu file chưa có quyền thực thi:

``` sh
chmod +x ./cams.sh
```

Launcher Linux cũng hiển thị menu. Có thể yêu cầu chuẩn bị đầy đủ và
chạy bằng:

``` sh
./cams.sh all
```

Khi các binary native đã được chuẩn bị, dùng:

``` sh
./cams.sh run
```

### Chạy trực tiếp

Khi chỉ cần chạy ứng dụng Python trong môi trường dependency đã được
`uv` chuẩn bị, dùng:

``` sh
uv run main.py
```

Lệnh này bỏ qua bước kiểm tra/build terminal companion và Syslog
collector của launcher. Các chức năng native tương ứng có thể chưa sử
dụng được, nhưng cửa sổ Welcome và workflow project vẫn có thể hoạt
động.

## Màn hình Welcome

CAMS luôn nạp cửa sổ Welcome trước Workspace. Ở trạng thái sạch, cửa sổ
hiển thị ba lựa chọn chính:

- **Create New**: tạo project `.ntp` mới;

- **Open**: chọn một project `.ntp` đã có;

- **Settings**: thay đổi thiết lập toàn cục của ứng dụng.

Khi đã có lịch sử làm việc, khu vực giữa cửa sổ hiển thị **Recent
Projects**. Trạng thái khởi động sạch được minh họa tại
<a href="#fig" class="ref">[fig]</a>:ch02-welcome.

<figure>
<p><img src="../../figures/gui/chapter-02/01-welcome-window.png"
style="width:100.0%" /></p>
<figcaption><p>Màn hình Welcome của CAMS khi chưa có project gần
đây.</p></figcaption>
</figure>

\<fig:ch02-welcome\>

Workspace chỉ mở sau khi controller tạo hoặc giải nén thành công một
project hợp lệ. Ứng dụng không tự mở project gần đây ngay khi khởi động.

## Project trong CAMS

Project CAMS là một package có phần mở rộng `.ntp`. Package chứa dữ liệu
Workspace cần thiết, gồm các database, dữ liệu backup và lịch sử
snapshot. Mỗi project là một không gian làm việc độc lập; vì vậy nên
dùng project riêng cho từng bài lab hoặc hệ thống.

Ví dụ tên project:

``` text
Network-Lab.ntp
Branch-Office-Lab.ntp
```

Nên chọn tên mô tả đúng mục đích. Tránh các tên khó phân biệt như
`new.ntp` hoặc `project1.ntp` khi quản lý nhiều môi trường.

## Tạo project mới

Thực hiện theo thứ tự sau:

1.  Khởi chạy CAMS.

2.  Trong cửa sổ Welcome, chọn **Create New**.

3.  Trong hộp thoại **Create New Project**, nhập **Project name**.

4.  Kiểm tra **Project location**. Có thể nhập đường dẫn thư mục hoặc
    chọn **Browse…** để dùng native folder picker.

5.  Nếu muốn dùng thư mục này cho các project sau, bật tùy chọn đặt làm
    vị trí mặc định.

6.  Tùy chọn, bật **Protect project with a password** và nhập mật khẩu
    hai lần.

7.  Chọn **Create Project**.

8.  Chờ hộp thoại đóng và Workspace xuất hiện.

Hộp thoại ban đầu được minh họa tại
<a href="#fig" class="ref">[fig]</a>:ch02-create-dialog. Trường vị trí
trỏ tới một thư mục có thật; CAMS tự tạo tên file `.ntp` an toàn từ tên
project.

<figure>
<p><img src="../../figures/gui/chapter-02/02-create-project.png"
style="width:100.0%" /></p>
<figcaption><p>Hộp thoại tạo một project CAMS mới.</p></figcaption>
</figure>

\<fig:ch02-create-dialog\>

Trong ví dụ tại
<a href="#fig" class="ref">[fig]</a>:ch02-project-details, project có
tên `Network-Lab`, được lưu thành `Network-Lab.ntp` trong thư mục
fixture dành riêng cho tài liệu. Nút **Create Project** chỉ được bật khi
tên và vị trí hợp lệ; nếu bật bảo vệ bằng mật khẩu, hai lần nhập phải
khớp nhau.

<figure>
<p><img src="../../figures/gui/chapter-02/03-project-details.png"
style="width:100.0%" /></p>
<figcaption><p>Thông tin project mới đã sẵn sàng để xác
nhận.</p></figcaption>
</figure>

\<fig:ch02-project-details\>

Sau khi package đầu tiên được tạo thành công, CAMS chuyển sang
Workspace. Tên project xuất hiện trên thanh tiêu đề như trong
<a href="#fig" class="ref">[fig]</a>:ch02-created-workspace. Project mới
chưa có thiết bị; đây là trạng thái đúng ở cuối workflow tạo project.

<figure>
<p><img src="../../figures/gui/chapter-02/04-workspace-opened.png"
style="width:100.0%" /></p>
<figcaption><p>Workspace trống sau khi project Network-Lab được tạo
thành công.</p></figcaption>
</figure>

\<fig:ch02-created-workspace\>

## Bảo vệ project bằng mật khẩu

Tùy chọn **Protect project with a password** bảo vệ toàn bộ package
`.ntp`. Khi mở lại project được bảo vệ, ứng dụng yêu cầu mật khẩu trước
khi giải nén Workspace.

**Quan trọng:** CAMS không lưu mật khẩu project trong Recent Projects và
không có cơ chế khôi phục mật khẩu đã quên. Hãy lưu mật khẩu ở trình
quản lý mật khẩu an toàn; không dùng lại credential của thiết bị mạng.

**Cảnh báo:** Khi project đang mở, dữ liệu phải được giải nén để ứng
dụng làm việc. Mật khẩu bảo vệ file `.ntp` không thay thế việc bảo vệ
tài khoản hệ điều hành, thư mục tạm và bản backup bên ngoài.

Các ảnh của chương này dùng project không có mật khẩu. Không có password
thật hoặc fixture password nào xuất hiện trong PNG.

## Mở project đã có

Để mở một package `.ntp`:

1.  Trở về cửa sổ Welcome. Nếu đang ở Workspace, chọn **File** → **Close
    Workspace** và chờ thao tác lưu/đóng hoàn tất.

2.  Chọn **Open** ở phần đầu cửa sổ như vị trí minh họa tại
    <a href="#fig" class="ref">[fig]</a>:ch02-open-choice.

3.  Trong native file picker của hệ điều hành, chọn file `.ntp`.

4.  Nếu project được bảo vệ, nhập mật khẩu và xác nhận.

5.  Chờ CAMS kiểm tra package, giải nén dữ liệu và mở Workspace.

<figure>
<p><img src="../../figures/gui/chapter-02/05-open-project-choice.png"
style="width:100.0%" /></p>
<figcaption><p>Vị trí lệnh Open để chọn một project đã
có.</p></figcaption>
</figure>

\<fig:ch02-open-choice\>

Nếu package hợp lệ, thanh tiêu đề hiển thị tên project đã mở.
<a href="#fig" class="ref">[fig]</a>:ch02-existing-opened cho thấy
fixture `Branch-Office-Lab.ntp` đã được mở thật qua service project của
ứng dụng; Workspace vẫn sạch và chưa có thiết bị.

<figure>
<p><img src="../../figures/gui/chapter-02/06-open-existing-project.png"
style="width:100.0%" /></p>
<figcaption><p>Workspace sau khi mở project Branch-Office-Lab có
sẵn.</p></figcaption>
</figure>

\<fig:ch02-existing-opened\>

## Recent Projects

Mỗi lần tạo hoặc mở project thành công, CAMS ghi project vào **Recent
Projects**. Danh sách lưu tên, URL file và thời điểm mở gần nhất; mật
khẩu không được lưu. Chọn trực tiếp một dòng để mở lại project bằng cùng
cơ chế kiểm tra package như lệnh **Open**.

<a href="#fig" class="ref">[fig]</a>:ch02-recents sử dụng hai package
fixture hợp lệ và đường dẫn tạm an toàn. Nếu một file đã bị di chuyển
hoặc xóa, mục không còn tồn tại sẽ được loại khỏi danh sách khi ứng dụng
nạp lịch sử.

<figure>
<p><img src="../../figures/gui/chapter-02/07-recent-projects.png"
style="width:100.0%" /></p>
<figcaption><p>Danh sách Recent Projects với hai project fixture hợp
lệ.</p></figcaption>
</figure>

\<fig:ch02-recents\>

## Lưu project

Trong Workspace, mở menu **File** và chọn **Save Workspace**, hoặc nhấn
`Ctrl+S`. Lệnh này đóng gói trạng thái hiện tại và thay file `.ntp` theo
cơ chế ghi an toàn. Vị trí lệnh được minh họa tại
<a href="#fig" class="ref">[fig]</a>:ch02-save.

<figure>
<p><img src="../../figures/gui/chapter-02/08-save-project.png"
style="width:100.0%" /></p>
<figcaption><p>Lệnh Save Workspace và các lệnh snapshot trong menu
File.</p></figcaption>
</figure>

\<fig:ch02-save\>

Phiên bản giao diện hiện tại không cung cấp action **Save As**. Vì vậy,
không nên tìm một lệnh **Save As** trong menu hoặc dựa vào mô tả cũ. Nếu
cần một bản sao độc lập, hãy lưu và đóng Workspace trước, rồi sao chép
file `.ntp` bằng công cụ của hệ điều hành; bản sao ngoài ứng dụng là
backup, không phải một thao tác Save As trong CAMS.

**Mẹo:** CAMS có cơ chế auto-save theo chu kỳ, nhưng nên chủ động dùng
`Ctrl+S` trước khi đóng ứng dụng hoặc trước một thay đổi quan trọng.

## Snapshot và khôi phục

Snapshot là điểm lưu trạng thái toàn project. Từ menu **File**:

1.  Chọn **Create Snapshot…** để mở Snapshot History và đặt nhãn tùy
    chọn.

2.  Chọn **Create Snapshot**.

3.  Kiểm tra snapshot mới xuất hiện trong danh sách.

4.  Chỉ dùng **Roll Back** khi đã xác định đúng mốc cần phục hồi.

<a href="#fig" class="ref">[fig]</a>:ch02-snapshot hiển thị một snapshot
thủ công `Before chapter 3` và một mốc automatic được tạo trong workflow
lưu an toàn. Snapshot gồm ảnh nhất quán của database và backup files.
Lịch sử automatic được giới hạn để tránh tăng dung lượng không kiểm
soát.

<figure>
<p><img src="../../figures/gui/chapter-02/09-snapshot-history.png"
style="width:100.0%" /></p>
<figcaption><p>Khu vực Snapshot History với các điểm khôi phục của
project.</p></figcaption>
</figure>

\<fig:ch02-snapshot\>

Khi rollback, implementation hiện tại tạo một safety snapshot được ghim
trước khi phục hồi trạng thái cũ, rồi lưu lại package. Cơ chế này giảm
rủi ro mất trạng thái ngay trước rollback, nhưng snapshot nằm trong
project và không thay thế backup ở thiết bị hoặc vị trí lưu trữ khác.

**Cảnh báo:** Không thử rollback trên project đang dùng cho công việc
thật chỉ để làm quen giao diện. Hãy thực hành trên một bản sao hoặc
project lab.

## Vị trí dữ liệu runtime

Khi chạy từ mã nguồn, dữ liệu runtime toàn cục mặc định nằm trong:

``` text
~/.local/share/cams/data/
```

Đây là vị trí dữ liệu của bản cài Linux. Khi chạy trực tiếp từ mã nguồn,
vị trí mặc định là `CAMS/data/`. Thư mục này chứa database mặc định và
trạng thái ứng dụng như Recent Projects. File project `.ntp` nằm tại vị
trí người dùng chọn trong Create/Open workflow.

Người dùng thông thường không cần đổi thư mục runtime. Trường hợp nâng
cao có thể đặt biến môi trường `CAMS_DATA_DIR` trước khi khởi chạy để
dùng một vị trí khác. Hãy bảo đảm thư mục đích tồn tại trên ổ đĩa tin
cậy và tài khoản hiện tại có quyền đọc/ghi.

## Kiểm tra ứng dụng sau khi khởi chạy

Sau khi project được tạo hoặc mở, kiểm tra nhanh:

- cửa sổ Welcome đã đóng hoặc được ẩn;

- tên project đúng trên thanh tiêu đề;

- thanh menu, Activity Bar, Devices sidebar và vùng nội dung đã hiển
  thị;

- thanh trạng thái không có thông báo lỗi;

- không có hộp thoại loading hoặc password còn mở;

- Workspace có thể ở trạng thái trống nếu chưa thêm thiết bị.

Trạng thái sẵn sàng được minh họa tại
<a href="#fig" class="ref">[fig]</a>:ch02-ready. Không cần tạo thiết bị
hoặc kết nối mạng để hoàn thành bước kiểm tra này.

<figure>
<p><img src="../../figures/gui/chapter-02/10-ready-workspace.png"
style="width:100.0%" /></p>
<figcaption><p>Workspace sạch và sẵn sàng cho chương tiếp
theo.</p></figcaption>
</figure>

\<fig:ch02-ready\>

Sau khi project được tạo hoặc mở thành công, CAMS chuyển sang Workspace.
Người dùng có thể tiếp tục làm quen với giao diện và các khu vực chức
năng ở chương tiếp theo.

## Một số lỗi khởi chạy thường gặp

### Python không được nhận diện

Kiểm tra lại `python --version` hoặc `python3 --version`. Bảo đảm phiên
bản từ `3.11` trở lên và executable đã có trong `PATH`.

### uv không được nhận diện

Chạy lại `uv --version` trong một Terminal mới. Nếu lệnh vẫn không tồn
tại, cài `uv` và kiểm tra cấu hình `PATH` của tài khoản hiện tại.

### QML hoặc Qt không tải trên Linux

Kiểm tra thư viện hệ thống đồ họa, font, plugin platform và QML
libraries tương ứng với wheel PyQt6. Chạy ứng dụng từ Terminal để đọc
thông báo thiếu thư viện đầu tiên; không sao chép ngẫu nhiên plugin Qt
giữa các phiên bản.

### Không tạo được database hoặc thư mục runtime

Kiểm tra quyền ghi đối với thư mục dữ liệu ở trên hoặc thư mục do
`CAMS_DATA_DIR` chỉ định. Không chạy nhiều instance cùng ghi một
Workspace. Không xóa file `-wal`, `-shm` hoặc journal khi ứng dụng còn
chạy.

### Terminal companion hoặc Syslog collector còn thiếu

Launcher đầy đủ có thể yêu cầu Rust/Cargo, CMake hoặc compiler để build
thành phần native. Nếu chỉ cần hoàn thành chương này, có thể thử
`uv run main.py`; Terminal và Syslog native có thể chưa hoạt động. Chuẩn
bị các binary đó trước khi dùng chức năng tương ứng.

## Lưu ý về an toàn dữ liệu

**Quan trọng:** Không commit hoặc chia sẻ công khai project `.ntp`,
database, file `-wal`/`-shm`/journal, running-config, backup, Syslog,
pcap, credential, password hoặc private key. Các file này có thể chứa
topology, địa chỉ, cấu hình và thông tin xác thực của hệ thống thật.

Ngoài snapshot trong project, hãy duy trì ít nhất một bản sao `.ntp` ở
vị trí độc lập trước khi thực hiện thay đổi lớn. Chỉ đóng, sao chép hoặc
di chuyển project sau khi thao tác lưu đã hoàn tất. Không chỉnh trực
tiếp database hoặc nội dung package `.ntp` bằng công cụ ngoài khi
Workspace đang mở.

## Tóm tắt chương

Chương này đã hoàn thành workflow từ môi trường chưa chạy ứng dụng đến
một Workspace hợp lệ:

- Chuẩn bị môi trường

<!-- -->

- Lấy CAMS

<!-- -->

- Kiểm tra Python và uv

<!-- -->

- Khởi chạy ứng dụng

<!-- -->

- Welcome

<!-- -->

- Create/Open project

<!-- -->

- Workspace sẵn sàng

Ở thời điểm này, người dùng đã có thể tạo, mở, lưu và nhận biết snapshot
của project. Việc thêm thiết bị và cấu hình router/switch được chuyển
sang các chương sau.
