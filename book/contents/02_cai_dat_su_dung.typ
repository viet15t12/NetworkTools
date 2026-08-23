= Cài đặt và Bắt đầu sử dụng NetworkTools

Chương này hướng dẫn người dùng cách cài đặt phần mềm NetworkTools lần đầu, cũng như các bước cơ bản để bắt đầu sử dụng phần mềm. Sau khi hoàn thành chương, người dùng có thể mở ứng dụng, tạo hoặc mở một Project mới, thêm thiết bị mạng, xác định được vị trí lưu trữ dữ liệu làm việc và thực hiện các thao tác cơ bản để quản lý cấu hình thiết bị mạng.

== Yêu cầu hệ thống
Trước khi cài đặt phần mềm NetworkTools, người dùng cần đảm bảo rằng hệ thống của mình đáp ứng các yêu cầu cần thiết.

=== Yêu cầu cơ bản
NetworkTools yêu cầu:
- Python phiên bản `3.11` trở lên;
- Trình quản lý môi trường và dependency `uv`;
- Quyền truy cập mạng tới các thiết bị mà người dùng được phép quản lý.

Windows và Linux (Fedora 44) là nền tảng phát triển chính của NetworkTools.

| Ghi chú: Các yêu cầu trên áp dụng cho phiên bản NetworkTools đượ chạy trực tiếp từ mã nguồn. Trong các phiên bản tương lai, NetworkTools có thể được phát hành dưới dạng bộ cài đặt độc lập, các yêu cầu, quy trình có thể thay đổi. Người dùng nên tham khảo tài liệu hướng dẫn cài đặt đi kèm với từng phiên bản để biết thông tin chi tiết.

=== Các thành phần tuỳ chọn
Một số chức năng yêu cầu phần mềm bổ sung hoặc các thành phần tuỳ chọn. Người dùng có thể cài đặt các thành phần này nếu muốn sử dụng các tính năng tương ứng.
- TShark hoặc Wireshark: Cần thiết để sử dụng chức năng Device Logs, các tính năng thu thập và phân tích các gói tin mạng, giúp người quản trị theo dõi lưu lượng và phát hiện các vấn đề tiềm ẩn trong môi trường được cấp quyền.
- Rust toolchain: Chỉ cần thết trong trường hợp phải tự biên dịch thành phần Terminal compainion đi kèm với NetworkTools. Người dùng thông thường không cần cài đặt Rust nếu thành phần Terminal đã được chuẩn bị sẵn.

=== Quyền truy cập thiết bị mạng
Để kết nối tới thiết bị thật, người dùng cần có quyền truy cập hợp lệ tới thiết bị mạng. Điều này bao gồm:
- Địa chỉ IP hoặc hostname của thiết bị;
- Phương thức kết nối được hỗ trợ (SSH hoặc Telnet);
- Cổng kết nối (mặc định là 22 cho SSH và 23 cho Telnet);
- Thông tin xác thực hợp lệ (tên người dùng và mật khẩu, hoặc khóa công khai/riêng tư cho SSH);
- Quyền quản trị hoặc quyền truy cập đủ để thực hiện các thay đổi cấu hình trên thiết bị.

NetworkTools chỉ nên được sử dụng để kết nối và cấu hình trên các thiết bị hoặc hệ thống mà người dùng được cấp quyền quản lý.

| Cảnh báo: Việc sử dụng NetworkTools để truy cập hoặc thay đổi cấu hình trên các thiết bị mà người dùng không có quyền hợp pháp là vi phạm pháp luật và chính sách bảo mật. Người dùng phải tuân thủ các quy định và chính sách của tổ chức hoặc nhà cung cấp dịch vụ mạng khi sử dụng phần mềm.

== Mã nguồn NetworkTools
Phiên bản hiện tại có thể được lấy từ kho lưu trữ GitHub chính thức của NetworkTools tại địa chỉ: https://github.com/viet15t12/NetworkTools.git. Người dùng có thể tải xuống mã nguồn, biên dịch và chạy phần mềm trên hệ thống của mình. Hướng dẫn chi tiết về cách lấy mã nguồn, cài đặt các dependency và chạy phần mềm được cung cấp trong tài liệu hướng dẫn đi kèm với kho lưu trữ.

Mở Terminal (Command Prompt) và chạy các lệnh sau để tải xuống mã nguồn và cài đặt các dependency cần thiết:

```sh
$ git clone https://github.com/viet15t12/NetworkTools.git
```

Sau khi quá trình tải xuống hoàn tất, người dùng chuyển tới thư mục chứa mã nguồn và cài đặt các dependency bằng lệnh:

```sh
$ cd NetworkTools/app
```

Thư mục `app/` chứa ứng dụng desktop chính và là thư mục làm việc được sử dụng trong các bước tiếp theo.

== Chuẩn bị tài nguyên cần thiết

=== Kiểm tra Python
Người dùng có thể truy cập trang `https://www.python.org/` để cài đặt Python từ trang chủ chính thức.

Sử dụng lệnh bên dưới để kiểm tra phiên bản. Nếu Python đã được cài đặt đúng, hệ thống sẽ hiển thị phiên bản hiện tại.

```sh
$ python --version # Hoặc python3 --version
```

Kết quả hiển thị ví dụ trên màn hình:

```
Python 3.12.x
```
NetworkTools yêu cầu `Python 3.11` hoặc mới hơn. 

=== Kiểm tra uv
Nhập `uv --version`

Nếu hệ thống nhận diện được lệnh `uv`, có thể tiếp tục quá trình khởi chạy NetworkTools. Nếu lệnh không được nhận diện, cần cài đặt `uv` trước khi tiếp tục.

== Khởi chạy NetworkTools
NetworkTools cung cấp trình khởi chạy để chuẩn bị môi trường và khởi động ứng dụng. Trình khởi chạy thực hiện các bước chuẩn bị cần thiết trước khi mở ứng dụng. 

=== Khởi chạy trên Windows
Từ thư mục `NetworkTools/app`, chạy:

```cmd
> .\networktools.bat
```

=== Khởi chạy trên Linux
Từ thư mục `NetworkTools/app`, chạy:

```sh
$ ./networktools.sh
```

Trường hợp file chưa có quyền thực thi, có thể cần cấp quyền thực thi trước khi chạy:

```sh
chmod +x ./networktools/sh
```

=== Khởi chạy trực tiếp
Nếu môi trường đã được chuẩn bị sẵn, NetworkTools có thể được chạy trực tiếp bằng:

```sh
$ uv run main.py
```

`uv` sử dụng thông tin dependency của project để chuẩn bị môi trường Python cần thiết cho ứng dụng.

== Lần khởi chạy đầu tiên
Khi NetworkTools được khởi động thành công, ứng dụng hiển thị Welcome Windows.
Đây là điểm bắt đầu của mỗi phiên làm việc. Từ màn hình Welcome, người dùng có thể: 
- tạo một project mới;
- mở một project đã có;
- tự động mở lại một project gần đây;
- truy cập các project NetworkTools đã được lưu trước đó.

Không gian làm việc chính của NetworkTools chỉ được mở sau khi một project hợp lệ được tạo hoặc mở.

#figure(
  image("../figures/gui/welcome.png", width: 95%),
  caption: [Màn hình Welcome của NetworkTools],
)

== Project trong NetworkTools
NetworkTools tổ chức dữ liệu làm việc theo Project.

Mỗi project đại diện cho một không gian làm việc độc lập, trong đó có thể chứ thông tin thiết bị, cấu hình, dữ liệu sao lưu và các thông tinn liên quan đến môi trường mạng đang được quản lý.

Project NetworkTools sử dụng phần mềm mở rộng `.ntp`, ví dụ:

```
Core-Lab.ntp
```

Việc sử dụng project cho phép tách dữ liệu của nhiều hệ thống hoặc bài thực hành khác nhau thay vì lưu tất cả thông tin vào cùng một cơ sở dữ liệu.

=== Tạo project mới
Từ màn hình Welcome:
1. Chọn *Create New*.
```
TODO: Tạo lại Welcome Screen trên ứng dụng, sau đó viết lại hướng dẫn này do có một số thao tác chưa hợp lý.
```

==== Nguyên tắc đặt tên cho project
Nên sử dụng tên giúp xác định rõ mục đích của project, ví dụ: `CCNA_Lab.ntp`, `Router_Test.ntp`, `DoAn_Mang.ntp`

Hạn chế sử dụng những tên chung chung, gây nhiễu khi quản lý nhiều project, ví dụ: `new.ntp`, `project1.ntp`

==== Bảo vệ project bằng mật khẩu
Khi tạo project, người dùng có thể lựa chọn bảo vệ project bằng mật khẩu. Project được bảo vệ sẽ yêu cầu người dùng nhập mật khẩu khi mở.

NetworkTools Project không lưu mật khẩu của project trong danh sách Recent Project. Do đó, người dùng cần tự ghi nhớ và quản lý mật khẩu đã sử dụng, không thể khôi phục mật khẩu khi đã quên.

| *Quan trọng:* Không nên sử dụng cùng mật khẩu của project với mật khẩu đăng nhập của thiết bị mạng.

| *Quan trọng:* Cần lưu mật khẩu project ở vị trí an toàn. Không nên đưa mật khẩu vào ảnh chụp màn hình, log, tài liệu công khai hoặc repository Git.

=== Mở project đã có
Để mở một project NetworkTools
1. Khởi chạy NetworkTools
2. Tại Welcome Windows, chọn Open Project.
3. Chọn file có phần mở rộng `.ntp`.
4. Chọn Open.
5. Nhập mật khẩu nếu project được bảo vệ.

Nếu project hợp lệ, NetworkTools sẽ tải dữ liệu và mở workspace.

=== Recent Projects
NetworkTools lưu danh sách các project được mở gần đây. Người dùng có thể chọn một project tại *Recent Projects* để mở nhanh mà không cần duyệt lại tới vị trí của file.

Đối với prroject được bảo vệ, mật khẩu vẫn phải được nhập lại khi mở.

=== Lưu project
Trong quá trình làm việc, người dùng có thể sử dụng:
- *Save* để lưu project hiện tại;
- *Save As* để lưu project thành một file khác.

Quá trình lưu có thể bao gồm dữ liệu của cơ sở dữ liệu dữ liệu backup và các thành phần cần thiết của workspace.

Nên lưu project trước và sau những thay đổi cấu hình quan trọng.

| *Khuyến nghị:* Ngoài file project đang sử dụng, nên duy trì ít nhất một bản sao lưu ở vị trí độc lập trước khi thực hiện những thay đổi lớn đối với thiết bị hoặc workspace.

=== Snapshot và khôi phục trạng thái project
NetworkTools hỗ trợ snapshot cho các project.

Snapshot có thể được sử dụng để ghi lại trạng thái project tại một thời điểm nhất định trước khi thực hiện những thay đổi lớn. Người dùng có thể truy cập *Snapshot History* để:
- tạo snapshot;
- xem các snapshot đã lưu;
- lựa chọn trạng thái trước đó;
- thực hiện rollback khi cần thiết.

Trước khi rollback, NetworkTools tạo safety snapshot để giảm nguy cơ mất trạng thái hiện tại. Tuy nhiên, snapshot trong ứng dụng không nên được xem là phương án sao lưu duy nhất.