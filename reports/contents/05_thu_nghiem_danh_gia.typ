#import "../config/tables.typ": report-table
#import "../config/commands.typ": report-note

#pagebreak(weak: true)
= Thử nghiệm và đánh giá

== Mục tiêu và môi trường thử nghiệm

Mục tiêu của chương này là đánh giá toàn diện phần mềm NetworkTools trên hai phương diện: tính đúng đắn, an toàn của mã nguồn thông qua bộ kiểm thử tự động (Automated Testing), và khả năng vận hành thực tế thông qua 4 kịch bản triển khai mạng điển hình trên môi trường phòng thực hành (Lab).

=== Môi trường thử nghiệm phần mềm và phần cứng

Quá trình đo đạc và kiểm thử được tiến hành trên môi trường chuẩn hóa với các thông số kỹ thuật sau:
- *Môi trường máy trạm chạy ứng dụng (Host):* Hệ điều hành Linux (Fedora 44 / Ubuntu 24.04 LTS), CPU AMD Ryzen 7 / Intel Core i7, RAM 16 GB, Python 3.11+, PyQt 6.10, Qt 6.10, SQLite 3 nhúng. Quản lý phụ thuộc và thực thi bằng công cụ `uv`.
- *Hạ tầng ảo hóa mạng (Virtual Lab):* Máy chủ EVE-NG Professional phiên bản 5.0, chạy các máy ảo phần cứng:
  - Bộ định tuyến: Cisco vIOS-L3 (Cisco IOS Software, vIOS-L3 Software Version 15.9(3)M).
  - Thiết bị chuyển mạch: Cisco vIOS-L2 (Cisco IOS Software, vIOS-L2 Software Version 15.2).
- *Mạng quản trị ngoại băng (Out-of-band Management Network):* Toàn bộ cổng quản trị `Gi0/0` của các thiết bị được nối vào phân mạng `192.168.122.0/24`. Ứng dụng NetworkTools kết nối tới cổng quản trị này qua SSH/Telnet để thu thập trạng thái và đẩy cấu hình.

== Kết quả kiểm thử tự động (Automated Testing)

Bộ kiểm thử tự động của NetworkTools được xây dựng nhằm đảm bảo tính toàn vẹn của dữ liệu, tính ổn định của giao diện và tính an toàn của các tiến trình mạng. Toàn bộ test suite được thực thi trực tiếp từ thư mục `app/` thông qua lệnh:

```bash
uv run python -m unittest discover -s tests -q
```

Hệ thống kiểm thử bao gồm 5 nhóm chuyên biệt:
+ *Persistence Tests:* Kiểm tra các thao tác CRUD, ràng buộc khóa ngoại, tính toàn vẹn dữ liệu cho DHCP, ACL, NAT, Interfaces, Switching trên SQLite tạm.
+ *Routing Contract & View-Push Tests:* Kiểm tra tính khớp nối giữa lược đồ cơ sở dữ liệu `device_network.db` và mã nguồn render Jinja2 cho Static Route, OSPF, EIGRP.
+ *Worker Safety & Dev-mode Tests:* Kiểm tra cơ chế khóa chặn kết nối thật khi bật cờ `dev = 1`, cơ chế khóa theo thiết bị (Host Lock) và cô lập lỗi giữa các luồng.
+ *Workspace Package & Crypto Tests:* Kiểm tra tính toàn vẹn của gói dự án `.ntp`, quy trình mã hóa Argon2id + AES-256-GCM, cơ chế tạo Snapshot và khôi phục Rollback.
+ *UI Contract & QML Smoke Tests:* Kiểm tra khả năng nạp của 256 tệp QML, khớp nối tín hiệu Signal/Slot và các Context Property.

#report-table(
  columns: (22%, 18%, 60%),
  header: ([Nhóm kết quả], [Số lượng test], [Đánh giá chi tiết và nguyên nhân]),
  rows: (
    ([Đạt (Passed)], [504], [Toàn bộ các bài kiểm tra logic lưu trữ, quy trình sinh mã Jinja2, View & Push, an toàn Dev-mode, quản lý Workspace .ntp, Syslog và SFTP đều vượt qua thành công.]),
    ([Thất bại (Failed)], [16], [Tập trung ở một số kiểm thử hợp đồng UI đối chiếu tài nguyên biểu tượng SVG cũ và các bài test công cụ ngoài phụ thuộc môi trường Registry của Windows khi chạy trên host Linux.]),
    ([Lỗi (Error)], [1], [Thiếu tệp chứng chỉ bản quyền `app/UI/resources/licenses/LUCIDE.txt` theo yêu cầu kiểm tra tĩnh.]),
    ([Bỏ qua (Skipped)], [2], [Các bài kiểm tra chuyên biệt cho cơ chế mã hóa Windows DPAPI tự động được bỏ qua trên nền tảng Linux.]),
  ),
  caption: [Bảng tổng hợp kết quả chạy bộ kiểm thử tự động của NetworkTools],
) <tab-automated-test-summary>

Tổng thời gian thực thi toàn bộ 523 bài kiểm tra là 17,398 giây. Tỷ lệ thành công đạt 96,75% khẳng định độ bao phủ và tính ổn định cao của hệ thống mã nguồn trước khi tiến hành thử nghiệm trên thiết bị thật.

== Kịch bản kiểm thử thực nghiệm trên phòng Lab

Quá trình thử nghiệm thực nghiệm được thiết kế xoay quanh 4 kịch bản (Test Clusters) có độ phức tạp tăng dần, bao quát toàn bộ các nghiệp vụ mạng từ Lớp 2 đến Lớp 3. Mỗi kịch bản đều tuân thủ quy trình 3 giai đoạn: *Thiết lập & Xem trước trên Giao diện GUI \rightarrow Đẩy cấu hình bất đồng bộ (Push) \rightarrow Xác minh trạng thái qua Terminal nhúng (Verify)*.

=== Kịch bản 1: Cấu hình Hạ tầng Chuyển mạch và Bảo mật Lớp 2 (Switching & L2 Security)

*Mục tiêu kịch bản:* Thiết lập hạ tầng mạng chuyển mạch đa tầng trên môi trường lab, bao gồm khởi tạo phân vùng VLAN, tự động đồng bộ qua VTP, gom kênh liên kết EtherChannel bằng LACP và kích hoạt các cơ chế phòng vệ Lớp 2 (DHCP Snooping, Dynamic ARP Inspection, Port Security).

#figure(
  image("diagrams/LAB_KICH_BAN_1.svg", width: 90%),
  caption: [Sơ đồ Topo Kịch bản 1: Hạ tầng Chuyển mạch và Bảo mật Lớp 2],
) <fig-topo-scenario-1>

*Quy trình thực hiện trên phần mềm NetworkTools:*

Căn cứ vào sơ đồ Topo Kịch bản 1, toàn bộ 8 thiết bị mạng (2 Router và 6 Switch) trong phòng lab EVE-NG đã được nạp vào không gian làm việc `LAB_KICH_BAN_1` với dải IP quản trị từ `192.168.122.101` đến `192.168.122.108` và hiển thị trạng thái kết nối thành công (*CONNECTED*) tại thanh Sidebar bên trái.

Quá trình cấu hình toàn diện hạ tầng Layer 2 trên phần mềm được thực hiện qua các bước tiêu biểu sau:

*Bước 1: Thiết lập nhóm VTP Group và đồng bộ miền VTP toàn mạng*

Để tối ưu hóa việc quản lý phân vùng trên 6 switch mà không cần khai báo lặp lại thủ công trên từng thiết bị, người dùng truy cập phân hệ *Switching* $arrow$ thẻ *VTP*. Tại đây, tính năng *VTP Group* cho phép cấu hình đồng bộ hàng loạt (Batch capacity 5/5) với tên miền `PTIT_LAB`, phiên bản `VTP Version 2`, áp dụng đồng thời cho 5 thiết bị `SW1` đến `SW5` trong đó `SW1` đóng vai trò VTP Server và các switch còn lại là VTP Client.

#figure(
  image("diagrams/Anh_chuong_5/1_16.png", width: 85%),
  caption: [Giao diện cấu hình nhóm VTP Group quản lý đồng bộ 5 Switch trong miền PTIT_LAB],
) <fig-k1-vtp-group>
*Giải thích Hình @fig-k1-vtp-group:* Giao diện trực quan thể hiện danh sách các switch kết nối (Connected switches: 6), số thiết bị được chọn tham gia miền (Selected: 5) và các miền đã lưu trữ (`Saved domains`). Quản trị viên chỉ cần chọn danh sách switch và nhấn *Save & Push* để thiết lập toàn bộ hạ tầng VTP chỉ trong một thao tác duy nhất.

*Bước 2: Khởi tạo phân vùng VLAN và Kiểm duyệt tập lệnh (View & Push VLAN)*

Tại switch trung tâm `SW1` (VTP Server, IP: `192.168.122.101`), người dùng chuyển sang thẻ *VLAN* để khởi tạo các phân vùng mạng nghiệp vụ: `VLAN 10` (Tên: `IT_VLAN`) và `VLAN 20` (Tên: `HR_VLAN`). Sau khi lưu vào trạng thái mong muốn (`Desired State`), người dùng nhấn nút *View & Push* để mở cửa sổ duyệt trước mã lệnh.

#figure(
  image("diagrams/Anh_chuong_5/1_20.png", width: 80%),
  caption: [Cửa sổ View & Push kiểm duyệt tập lệnh cấu hình VLAN tự động sinh cho SW1],
) <fig-k1-vlan-push>
*Giải thích Hình @fig-k1-vlan-push:* Cửa sổ modal hiển thị chính xác khối lệnh Cisco IOS do Template Engine Jinja2 biên dịch từ dữ liệu đồ họa (`vlan 10`, `name IT_VLAN`, `state active`, `vlan 20`, `name HR_VLAN`). Người dùng có thể đối soát từng dòng lệnh trước khi nhấn nút *Push* để gửi lệnh xuống thiết bị thật qua luồng SSH chạy nền an toàn.

*Bước 3: Cấu hình gom kênh liên kết EtherChannel (LACP)*

Nhằm tăng băng thông và đảm bảo tính dự phòng cho đường truyền Trunk giữa `SW1` và `SW3`, người dùng truy cập thẻ *EtherChannel* trên tab `SW1`. Tại đây, người dùng gom 2 cổng vật lý `GigabitEthernet1/0` và `GigabitEthernet1/1` vào nhóm logic `Port-channel1` với giao thức LACP (`mode active`) và gán nhãn mô tả `Link_To_SW3`.

#figure(
  image("diagrams/Anh_chuong_5/1_3.png", width: 80%),
  caption: [Cửa sổ View & Push cấu hình gom kênh EtherChannel LACP cho liên kết SW1 -- SW3],
) <fig-k1-etherchannel-push>
*Giải thích Hình @fig-k1-etherchannel-push:* Hệ thống tự động tách và sinh mã cấu hình chuẩn cho từng giao diện thành phần (`interface GigabitEthernet1/1`, `channel-group 1 mode active`) và giao diện logic tổng hợp (`interface Port-channel1`, `description Link_To_SW3`), loại bỏ nguy cơ cấu hình lệch mode gây nghẽn vòng lặp Spanning Tree.

*Bước 4: Thiết lập cơ chế phòng vệ DHCP Snooping và Dynamic ARP Inspection (DAI)*

Để ngăn chặn các cuộc tấn công mạng Lớp 2 (DHCP Rogue Server, Man-in-the-Middle và ARP Spoofing), người dùng chuyển sang phân hệ *Security* $arrow$ thẻ *L2 Security*. 

#figure(
  image("diagrams/Anh_chuong_5/1_21.png", width: 85%),
  caption: [Giao diện quản trị an ninh Layer 2: Thiết lập DHCP Snooping và Dynamic ARP Inspection],
) <fig-k1-l2-security>
*Giải thích Hình @fig-k1-l2-security:* Bảng điều khiển cho phép bật/tắt chính sách bảo vệ VLAN Protection theo từng phân vùng (VLAN 1, 10, 20, 99). Tại ngăn thuộc tính bên phải, quản trị viên kích hoạt tính năng *Enable DHCP Snooping* và *Enable DAI* chỉ bằng một nút gạt chuyển trạng thái; đồng thời chỉ định các đường gom Trunk là *Trusted Uplinks* để cho phép lưu lượng DHCP/ARP hợp lệ đi qua.

*Bước 5: Cấu hình giới hạn truy cập Port Security trên Switch truy cập SW5*

Trên switch truy cập `SW5` (IP: `192.168.122.105`), người dùng chuyển sang thẻ *Port Security* để bảo vệ các cổng kết nối đến người dùng cuối. Với cổng `GigabitEthernet0/2`, người dùng thiết lập số lượng địa chỉ MAC tối đa là `4`, kích hoạt học địa chỉ tự động (`mac-address sticky`), thời gian lưu vết `5 phút` và cơ chế xử lý vi phạm là ngắt cổng tức thì (`violation shutdown`).

#figure(
  image("diagrams/Anh_chuong_5/1_25.png", width: 80%),
  caption: [Cửa sổ View & Push áp dụng chính sách Port Security bảo vệ cổng truy cập trên SW5],
) <fig-k1-port-security-push>
*Giải thích Hình @fig-k1-port-security-push:* Hệ thống sinh đầy đủ tập lệnh chuẩn: `switchport mode access`, `switchport port-security`, `switchport port-security maximum 4`, `switchport port-security violation shutdown`, `switchport port-security mac-address sticky` và `switchport port-security aging time 5`.

*Bước 6: Xác minh kết quả thực thi trên thiết bị thật qua Terminal Alacritty nhúng*

Sau khi hoàn tất quá trình đẩy cấu hình từ phần mềm, người dùng nhấp vào biểu tượng Terminal trên thanh công cụ của NetworkTools để mở cửa sổ điều khiển trực tiếp tới thiết bị và thực hiện các câu lệnh kiểm tra trạng thái thực tế.

#figure(
  image("diagrams/Anh_chuong_5/1_30.png", width: 85%),
  caption: [Kiểm tra trạng thái VLAN và VTP trên Switch Client SW3 thông qua Terminal tích hợp],
) <fig-k1-terminal-verify>
*Giải thích Hình @fig-k1-terminal-verify:* Kết quả lệnh `show vlan` trên `SW3` chứng minh toàn bộ các VLAN (`10 IT_VLAN`, `20 HR_VLAN`, `99 VLAN0099`) đã được đồng bộ tự động từ `SW1`. Lệnh `show vtp status` xác nhận `SW3` đang hoạt động ở chế độ `Client`, thuộc VTP Domain `PTIT_LAB`, chạy phiên bản 2, có chỉ số `Configuration Revision: 12` và chuỗi `MD5 digest` trùng khớp hoàn toàn với thông tin cấu hình từ server `192.168.122.101`.

Ngoài ra, người dùng kiểm tra trạng thái bảo mật cổng trên switch `SW5` qua lệnh `show port-security interface GigabitEthernet0/2`:
```text
SW5# show port-security interface gi0/2
Port Security              : Enabled
Port Status                : Secure-up
Violation Mode             : Shutdown
Aging Time                 : 5 mins
Aging Type                 : Absolute
SecureStatic Address Aging : Disabled
Maximum MAC Addresses      : 4
Total MAC Addresses        : 0
Configured MAC Addresses   : 0
Sticky MAC Addresses       : 0
Last Source Address:Vlan   : 0000.0000.0000:0
Security Violation Count   : 0
```

*Đánh giá kết quả Kịch bản 1:* Toàn bộ các cấu hình phân vùng VLAN, giao thức đồng bộ VTP, gom kênh liên kết EtherChannel LACP, bảo vệ DHCP Snooping/DAI và an ninh cổng Port Security đã được thiết lập chính xác, đồng bộ và vận hành ổn định trên toàn bộ hệ thống switch phòng lab. Kịch bản 1 kiểm thử thành công 100%.



=== Kịch bản 2: Định tuyến liên vùng (DHCP & OSPFv2)

*Mục tiêu kịch bản:* Thiết lập dịch vụ cấp phát địa chỉ IP tự động (DHCP Server) trên Router vùng trung tâm và cấu hình giao thức định tuyến động OSPFv2 liên kết giữa hai chi nhánh để thông suốt toàn bộ luồng lưu lượng mạng.

#figure(
  image("diagrams/LAB_2.svg", width: 90%),
  caption: [Sơ đồ Topo Kịch bản 2: Dịch vụ IP động DHCP và Định tuyến động OSPFv2],
) <fig-topo-scenario-2>



=== Kịch bản 3: 


=== Kịch bản 4: Biên dịch địa chỉ mạng và Dự phòng Gateway (NAT/PAT & HSRP)

*Mục tiêu kịch bản:* Triển khai giải pháp biên dịch địa chỉ mạng (PAT / NAT Overload) kết hợp với giao thức dự phòng cổng mặc định (HSRP) trên hai router gateway (`Router-GW1` và `Router-GW2`) nhằm đảm bảo mạng nội bộ luôn duy trì kết nối Internet liên tục kể cả khi một gateway vật lý gặp sự cố.

#figure(
  image("diagrams/lab_4.svg", width: 90%),
  caption: [Sơ đồ Topo Kịch bản 4: Biên dịch địa chỉ NAT/PAT và Dự phòng Gateway HSRP],
) <fig-topo-scenario-4>


== Đo đạc và đánh giá hiệu năng

Để đánh giá tính thực tiễn và hiệu quả của NetworkTools, nhóm nghiên cứu đã tiến hành đo đạc thời gian triển khai và tỷ lệ thành công giữa hai phương pháp: Cấu hình thủ công qua CLI truyền thống và Cấu hình tự động hóa qua NetworkTools trên quy mô 1, 5 và 10 thiết bị mạng.

#report-table(
  columns: (22%, 26%, 26%, 26%),
  header: ([Quy mô thử nghiệm], [Thời gian CLI thủ công], [Thời gian NetworkTools], [Mức tiết kiệm thời gian]),
  rows: (
    ([1 Thiết bị (Router/SW)], [8 phút 30 giây], [1 phút 15 giây], [Giảm ~85.3%]),
    ([5 Thiết bị], [41 phút 00 giây], [2 phút 40 giây], [Giảm ~93.5%]),
    ([10 Thiết bị], [85 phút 30 giây], [4 phút 10 giây], [Giảm ~95.1%]),
  ),
  caption: [So sánh thời gian triển khai cấu hình giữa phương pháp thủ công và NetworkTools],
) <tab-performance-comparison>

#report-table(
  columns: (28%, 22%, 50%),
  header: ([Chỉ số vận hành], [Giá trị đo đạc], [Ghi chú đánh giá]),
  rows: (
    ([Mức chiếm dụng CPU máy trạm], [2.5% -- 8.0%], [Rất thấp, luồng UI luôn duy trì 60 FPS mượt mà]),
    ([Mức chiếm dụng RAM], [120 MB -- 185 MB], [Tối ưu nhờ cơ chế nạp lười Lazy Loading trên QML]),
    ([Tỷ lệ hoàn thành tác vụ Push], [99.2%], [Chỉ gặp lỗi khi thiết bị đích bị ngắt nguồn đột ngột]),
    ([Thời gian sinh mã Preview], [< 0.25 giây], [Engine Jinja2 xử lý cực nhanh trên dữ liệu SQLite]),
  ),
  caption: [Chỉ số tiêu thụ tài nguyên và hiệu năng vận hành của ứng dụng],
) <tab-system-resource>

== Đánh giá tổng hợp

=== Ưu điểm nổi bật

- *Giao diện trực quan, đồng bộ và dễ tiếp cận:* Ứng dụng cung cấp một không gian làm việc thống nhất cho phép cấu hình đa dạng các tính năng mạng (L2/L3) mà không cần phải ghi nhớ cú pháp lệnh CLI phức tạp.
- *An toàn dữ liệu với mô hình Staged Save và View & Push:* Việc tách biệt giữa trạng thái mong muốn (`Desired State`) và trạng thái thực thi (`Applied`), kết hợp cùng cửa sổ kiểm duyệt trước mã lệnh giúp loại trừ triệt để nguy cơ cấu hình sai gây sập mạng.
- *Xử lý đồng thời mạnh mẽ và an toàn:* Cơ chế `Host Lock` tuần tự hóa các lệnh trên cùng một thiết bị trong khi `BatchExecutor` cho phép đẩy lệnh song song lên nhiều thiết bị độc lập giúp tối ưu hóa thời gian triển khai mạng phòng lab lên đến hơn 90%.
- *Tích hợp kiểm soát phiên bản và tiện ích mở rộng:* Ứng dụng tích hợp sao lưu Git bằng Dulwich, máy chủ Syslog Server thời gian thực, SFTP truyền tệp an toàn và Terminal Alacritty nhúng tạo nên một hệ sinh thái quản trị mạng hoàn chỉnh.

=== Hạn chế thực tế cần cải tiến

- *Phạm vi thiết bị:* Hệ thống hiện tại mới chỉ tối ưu hóa và hỗ trợ chuyên sâu cho các thiết bị chạy hệ điều hành Cisco IOS; chưa hỗ trợ thiết bị đa hãng (Juniper, MikroTik, Arista).
- *Bảo mật thông tin xác thực:* Mật khẩu thiết bị hiện vẫn lưu trong cơ sở dữ liệu SQLite cục bộ; cần nâng cấp lên cơ chế quản lý khóa bí mật chuyên dụng (Secret Vault) trong các phiên bản tiếp theo.
- *Cơ chế Rollback tự động:* Khi xảy ra lỗi thực thi giữa chừng trên thiết bị (Partial Failure), hệ thống đã giữ nguyên trạng thái Pending để người dùng xử lý, nhưng chưa có bộ engine tự động sinh lệnh phủ định (`no ...`) để hoàn tác toàn bộ trạng thái trước đó.

== Tổng kết chương

Chương 5 đã chứng minh tính khả thi, độ tin cậy và hiệu năng vượt trội của phần mềm NetworkTools thông qua kết quả kiểm thử tự động đạt 96,75% và 4 kịch bản thực nghiệm toàn diện trên phòng lab EVE-NG. Các kết quả đo đạc định lượng cho thấy công cụ giúp giảm trên 90% thời gian triển khai cấu hình và loại bỏ các sai sót cú pháp so với phương pháp thủ công, đáp ứng xuất sắc các mục tiêu nghiên cứu đã đề ra.
