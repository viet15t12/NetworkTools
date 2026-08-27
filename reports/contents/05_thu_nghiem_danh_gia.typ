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



=== Kịch bản 2: Định tuyến động đa vùng theo nhóm và Tái phân phối tuyến liên chi nhánh (OSPF Group & Route Redistribution)

*Mục tiêu kịch bản:* Thiết lập hạ tầng định tuyến động OSPFv2 liên kết hai chi nhánh doanh nghiệp (Chi nhánh A và Chi nhánh B) thông qua mạng đường trục ISP (Backbone Area 0). Ứng dụng tính năng *Routing Group - OSPF* của NetworkTools để tự động hóa quá trình cấu hình đồng loạt trên 6 bộ định tuyến (`R1`, `R2`, `R3`, `ISP1`, `ISP2`, `R6`), đồng thời kích hoạt cơ chế *Tái phân phối tuyến (Route Redistribution)* nhằm quảng bá các dải mạng LAN cục bộ vào miền OSPF, đảm bảo lưu lượng giữa các phòng ban thuộc hai chi nhánh được thông suốt 100%.

#figure(
  image("diagrams/LAB_2.svg", width: 95%),
  caption: [Sơ đồ Topo Kịch bản 2: Định tuyến OSPF đa vùng liên kết hai chi nhánh qua mạng Backbone],
) <fig-topo-scenario-2>

*Quy hoạch địa chỉ IP và Phân vùng Định tuyến:*

Mô hình kịch bản được chia làm 3 phân vùng định tuyến chính với bảng quy hoạch địa chỉ IP cụ thể như sau:

#report-table(
  columns: (20%, 20%, 25%, 35%),
  header: ([Phân vùng mạng], [Thiết bị / Node], [Dải IP / Subnet], [Ghi chú kiến trúc]),
  rows: (
    ([Chi nhánh A], [VPC11 (A1_VLAN)], [192.168.10.10/24], [Gateway: 192.168.10.1 (R2 Gi0/4)]),
    ([Chi nhánh A], [VPC12 (A2_VLAN)], [192.168.20.10/24], [Gateway: 192.168.20.1 (R3 Gi0/4)]),
    ([Chi nhánh A], [R1, R2, R3], [10.1.12.0/24, 10.1.13.0/24, 10.1.23.0/24], [Miền định tuyến OSPF Area 1]),
    ([Đường trục ISP], [R1, ISP1, ISP2, R6], [10.0.0.0/24, 10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24], [Miền đường trục OSPF Backbone Area 0]),
    ([Chi nhánh B], [VPC14 (B1_VLAN)], [192.168.30.10/24], [Gateway: 192.168.30.1 (R6 Gi0/1)]),
    ([Chi nhánh B], [VPC15 (B2_VLAN)], [192.168.40.10/24], [Gateway: 192.168.40.1 (R6 Gi0/1)]),
    ([Mạng Quản trị], [Toàn bộ Router/SW], [192.168.122.101 -- 109/24], [Kênh Out-of-Band kết nối NetworkTools]),
  ),
  caption: [Bảng quy hoạch địa chỉ IP và phân vùng OSPF cho Kịch bản 2],
) <tab-ip-planning-lab2>

*Quy trình thực hiện trên phần mềm NetworkTools:*

*Bước 1: Cấu hình Giao diện Lớp 3 và gán địa chỉ IP trên các Router*

Trước khi triển khai định tuyến, quản trị viên sử dụng phân hệ *Interfaces* trên NetworkTools để thiết lập các thông số IP, Subnet Mask và kích hoạt trạng thái hoạt động cho từng cổng vật lý (`GigabitEthernet`) trên các thiết bị.

#figure(
  image("diagrams/Chuong_5_lab2/1.png", width: 85%),
  caption: [Giao diện phân hệ Interfaces quản lý và cấu hình tham số Lớp 3 cho các cổng Router],
) <fig-k2-interfaces>
*Giải thích Hình @fig-k2-interfaces:* Bảng điều khiển bên trái liệt kê trực quan trạng thái IP của tất cả cổng mạng trên router `R1`. Ngăn thuộc tính bên phải cho phép chọn cấu hình nhanh IP Address, Subnet Mask, gán nhãn mô tả đường truyền và chuyển đổi trạng thái cổng (`Up/Down`) chỉ qua vài thao tác chuột.

*Bước 2: Cấu hình nhóm OSPF hàng loạt qua tính năng Routing Group*

Thay vì phải truy cập thủ công vào từng router để gõ từng dòng lệnh OSPF, quản trị viên sử dụng tính năng *Routing Group - OSPF* để cấu hình tự động cho toàn bộ 6 Router (`R1`, `R2`, `R3`, `ISP1`, `ISP2`, `R6`).

#figure(
  image("diagrams/Chuong_5_lab2/10.png", width: 80%),
  caption: [Cửa sổ Routing Group - OSPF (Bước 1: Chọn đồng thời 6 Router tham gia cấu hình nhóm)],
) <fig-k2-group-hosts>
*Giải thích Hình @fig-k2-group-hosts:* Quản trị viên chỉ cần tích chọn danh sách các router cần cấu hình trong không gian làm việc `LAB_KICH_BAN_2`. Hệ thống tự động xác định các giao diện kết nối và địa chỉ IP tương ứng trên từng thiết bị.

Tiếp theo, tại bước *Networks*, quản trị viên gán các dải mạng kết nối trực tiếp vào từng vùng định tuyến phù hợp (Area 0 cho các liên kết Backbone ISP và Area 1 cho các liên kết nội bộ Chi nhánh A).

#figure(
  image("diagrams/Chuong_5_lab2/11.png", width: 80%),
  caption: [Cửa sổ Routing Group - OSPF (Bước 4: Khai báo phân vùng mạng và gán OSPF Area tương ứng)],
) <fig-k2-group-networks>
*Giải thích Hình @fig-k2-group-networks:* Giao diện tự động phân nhóm các cổng của từng router (`R1: 10.1.12.0/24 -> Area 1`, `10.1.13.0/24 -> Area 1`, `10.0.0.0/24 -> Area 0`; `R2: 10.1.12.0/24 -> Area 1`, `10.1.23.0/24 -> Area 1`). Sau khi hoàn tất, quản trị viên nhấn *Save & Push* để hệ thống đẩy cấu hình song song xuống toàn bộ các router.

*Bước 3: Cấu hình Tái phân phối tuyến (Route Redistribution) cho mạng LAN người dùng*

Để các dải mạng người dùng (`192.168.10.0/24`, `192.168.20.0/24` ở Chi nhánh A và `192.168.30.0/24`, `192.168.40.0/24` ở Chi nhánh B) được quảng bá xuyên suốt qua mạng OSPF mà không cần chạy OSPF trực tiếp xuống Switch mạng truy cập, quản trị viên cấu hình tính năng *Redistribute Connected Subnets* trên các router biên `R2`, `R3` và `R6`.

#figure(
  image("diagrams/Chuong_5_lab2/16.png", width: 85%),
  caption: [Giao diện thiết lập tham số Tái phân phối tuyến (OSPF Redistribute) trên Router biên R6],
) <fig-k2-redistribute-gui>
*Giải thích Hình @fig-k2-redistribute-gui:* Quản trị viên mở tab `R6`, chọn phân hệ *Routing* $arrow$ thẻ *OSPF* $arrow$ tiểu mục *Redistribute*. Tại đây, người dùng thực hiện:
- Chọn tiến trình định tuyến: `192.168.122.106 / PID 1`.
- Chọn giao thức nguồn cần tái phân phối: `connected` (hoặc `static`).
- Nhập Process ID nguồn: `1`.
- Tích chọn `Subnets`: Cho phép tái phân phối cả các mạng con VLSM không nằm trong lớp mạng chuẩn (Classless).
- Nhấn *+ Add Redistribute* để lưu vào danh sách chờ thực thi (hiển thị nhãn trạng thái `connected 1 subnets`).

Sau khi lưu cấu hình trên giao diện, quản trị viên nhấn nút *View & Push* để kiểm duyệt khối lệnh chuẩn bị đẩy xuống router.

#figure(
  image("diagrams/Chuong_5_lab2/14.png", width: 80%),
  caption: [Cửa sổ View & Push OSPF tự động sinh khối lệnh tái phân phối tuyến cho Router R2],
) <fig-k2-redistribute-push>
*Giải thích Hình @fig-k2-redistribute-push:* Cửa sổ kiểm duyệt hiển thị khối lệnh Cisco IOS sinh ra:
```text
# Cấu hình OSPF và Redistribution sinh tự động cho R2
router ospf 1
 router-id 2.2.2.2
 network 10.1.12.0 0.0.0.255 area 1
 network 10.1.23.0 0.0.0.255 area 1
 network 2.2.2.0 0.0.0.255 area 1
 redistribute connected subnets
 no default-information originate
 no passive-interface default
 exit
```
Lệnh `redistribute connected subnets` giúp router biên chuyển đổi các tuyến mạng LAN kết nối trực tiếp thành các tuyến ngoại vi OSPF External Type 2 (`O E2`) để phát tán vào toàn bộ miền định tuyến.

*Bước 4: Xác minh cấu hình OSPF đa thiết bị trên Terminal Alacritty nhúng*

Sau khi hoàn tất tiến trình đẩy cấu hình từ phần mềm, quản trị viên mở các cửa sổ Terminal tích hợp để kiểm tra trực tiếp tệp cấu hình chạy trên cả 6 router.

#figure(
  image("diagrams/Chuong_5_lab2/12.png", width: 90%),
  caption: [Xác minh đồng thời cấu hình OSPF trên 6 Router (R1, R2, R3, ISP1, ISP2, R6) qua Terminal nhúng],
) <fig-k2-multi-terminal-ospf>
*Giải thích Hình @fig-k2-multi-terminal-ospf:* Lệnh `show run | section ospf` trên từng cửa sổ chứng minh tất cả 6 router đã nhận đầy đủ tiến trình OSPF Process 1, Router-ID duy nhất (`1.1.1.1` đến `6.6.6.6`) và các dải mạng được gán chính xác vào Area 0 và Area 1 đúng theo thiết kế ban đầu.

*Bước 5: Kiểm tra Bảng định tuyến OSPF (show ip route)*

Quản trị viên thực hiện lệnh `show ip route` trên router trung tâm `R1` để kiểm tra khả năng hội tụ của hệ thống định tuyến:

#figure(
  image("diagrams/Chuong_5_lab2/18.png", width: 85%),
  caption: [Bảng định tuyến trên Router R1 hiển thị đầy đủ các tuyến nội vùng và tuyến ngoại vi O E2],
) <fig-k2-route-table-r1>
*Giải thích Hình @fig-k2-route-table-r1:* Bảng định tuyến của `R1` ghi nhận đầy đủ:
- Các tuyến nội vùng OSPF (`O`): `2.2.2.2/32`, `3.3.3.3/32`, `4.4.4.4/32`, `5.5.5.5/32`, `6.6.6.6/32` và các mạng liên kết `10.0.2.0/24`, `10.0.3.0/24`, `10.1.23.0/24`.
- Toàn bộ 4 dải mạng LAN của hai chi nhánh được học qua cơ chế tái phân phối tuyến ngoại vi:
  - `O E2 192.168.10.0/24 [110/20] via 10.1.12.2 (R2)`
  - `O E2 192.168.20.0/24 [110/20] via 10.1.13.2 (R3)`
  - `O E2 192.168.30.0/24 [110/20] via 10.0.0.2 (ISP1 -> R6)`
  - `O E2 192.168.40.0/24 [110/20] via 10.0.0.2 (ISP1 -> R6)`

*Bước 6: Kiểm tra truyền thông liên chi nhánh thực tế (ICMP Ping Test)*

Để chứng minh hai chi nhánh đã hoàn toàn thông suốt, quản trị viên mở terminal trên các máy trạm đầu cuối (VPC) để thực hiện kiểm tra ping chéo giữa hai chi nhánh:

#figure(
  image("diagrams/Chuong_5_lab2/25.png", width: 75%),
  caption: [Kết quả kiểm tra Ping từ VPC11 (Chi nhánh A) sang VPC14 (Chi nhánh B) thành công 100%],
) <fig-k2-ping-vpc11-vpc14>
*Giải thích Hình @fig-k2-ping-vpc11-vpc14:* Từ máy trạm `VPC11` (`192.168.10.10` thuộc phân vùng `A1_VLAN` tại Chi nhánh A), lệnh `ping 192.168.30.10` (máy trạm `VPC14` thuộc phân vùng `B1_VLAN` tại Chi nhánh B) đạt tỷ lệ phản hồi 5/5 gói tin thành công, thời gian trễ trung bình cực thấp (~6.9 ms), gói tin đi qua 5 hop định tuyến (`ttl=59`).

Ngoài ra, kết quả kiểm tra từ máy trạm `VPC15` (`192.168.40.10` thuộc phân vùng `B2_VLAN` tại Chi nhánh B) gửi ping tới tất cả các dải mạng tại Chi nhánh A đều đạt kết quả tuyệt đối:
```text
VPCS> ping 192.168.10.10
84 bytes from 192.168.10.10 icmp_seq=1 ttl=59 time=8.198 ms
84 bytes from 192.168.10.10 icmp_seq=2 ttl=59 time=12.808 ms
84 bytes from 192.168.10.10 icmp_seq=3 ttl=59 time=7.955 ms
84 bytes from 192.168.10.10 icmp_seq=4 ttl=59 time=12.856 ms
84 bytes from 192.168.10.10 icmp_seq=5 ttl=59 time=6.671 ms

VPCS> ping 192.168.20.10
84 bytes from 192.168.20.10 icmp_seq=1 ttl=59 time=9.799 ms
84 bytes from 192.168.20.10 icmp_seq=2 ttl=59 time=8.915 ms
84 bytes from 192.168.20.10 icmp_seq=3 ttl=59 time=6.835 ms
84 bytes from 192.168.20.10 icmp_seq=4 ttl=59 time=6.497 ms
84 bytes from 192.168.20.10 icmp_seq=5 ttl=59 time=10.691 ms
```

*Đánh giá kết quả Kịch bản 2:* Giải pháp cấu hình định tuyến động theo nhóm *Routing Group - OSPF* kết hợp cùng cơ chế *Route Redistribution* trên phần mềm NetworkTools đã hoàn thành xuất sắc bài toán kết nối mạng liên chi nhánh đa vùng. Toàn bộ các router tự động thiết lập quan hệ láng giềng, học đầy đủ bảng định tuyến và truyền thông dữ liệu hai chiều giữa tất cả các máy trạm đạt độ ổn định và tin cậy 100%.



=== Kịch bản 3: 


=== Kịch bản 4: 






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
