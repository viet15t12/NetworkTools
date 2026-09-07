#import "../config/tables.typ": report-table, table-code
#import "../config/commands.typ": report-note

#pagebreak(weak: true)
= Thử nghiệm và đánh giá

== Mục tiêu và môi trường thử nghiệm

Mục tiêu của chương này là đánh giá toàn diện phần mềm CAMS trên hai phương diện: tính đúng đắn, an toàn của mã nguồn thông qua bộ kiểm thử tự động (Automated Testing), và khả năng vận hành thực tế thông qua 4 kịch bản triển khai mạng điển hình trên môi trường phòng thực hành (Lab).

=== Môi trường thử nghiệm phần mềm và phần cứng

Quá trình đo đạc và kiểm thử được tiến hành trên môi trường chuẩn hóa với các thông số kỹ thuật sau:
- *Môi trường máy trạm chạy ứng dụng (Host):* Hệ điều hành Linux (Fedora 44 / Ubuntu 24.04 LTS), CPU AMD Ryzen 7 / Intel Core i7, RAM 16 GB, Python 3.11+, PyQt 6.10, Qt 6.10, SQLite 3 nhúng. Quản lý phụ thuộc và thực thi bằng công cụ `uv`.
- *Hạ tầng ảo hóa mạng (Virtual Lab):* Máy chủ EVE-NG Professional phiên bản 5.0, chạy các máy ảo phần cứng:
  - Bộ định tuyến: Cisco vIOS-L3 (Cisco IOS Software, vIOS-L3 Software Version 15.9(3)M).
  - Thiết bị chuyển mạch: Cisco vIOS-L2 (Cisco IOS Software, vIOS-L2 Software Version 15.2).
- *Mạng quản trị ngoại băng (Out-of-band Management Network):* Toàn bộ cổng quản trị (thường là Gi0/0 trên router hoặc một cổng VLAN quản trị riêng trên switch, tùy theo model thiết bị) của các thiết bị được nối vào phân mạng 192.168.122.0/24. Ứng dụng CAMS kết nối tới cổng quản trị này qua SSH/Telnet để thu thập trạng thái và đẩy cấu hình.

== Kịch bản kiểm thử thực nghiệm trên phòng Lab

Quá trình thử nghiệm thực nghiệm được thiết kế xoay quanh 4 kịch bản (Test Clusters) có độ phức tạp tăng dần, bao quát toàn bộ các nghiệp vụ mạng từ Lớp 2 đến Lớp 3. Mỗi kịch bản đều tuân thủ quy trình 3 giai đoạn: *Thiết lập & Xem trước trên Giao diện GUI \rightarrow Đẩy cấu hình bất đồng bộ (Push) \rightarrow Xác minh trạng thái qua Terminal nhúng (Verify)*.

=== Kịch bản 1: Cấu hình Hạ tầng Chuyển mạch và Bảo mật Lớp 2 (Switching & L2 Security)

*Mục tiêu kịch bản:* Thiết lập hạ tầng mạng chuyển mạch đa tầng trên môi trường lab, bao gồm khởi tạo phân vùng VLAN, tự động đồng bộ qua VTP, gom kênh liên kết EtherChannel bằng LACP và kích hoạt các cơ chế phòng vệ Lớp 2 (DHCP Snooping, Dynamic ARP Inspection, Port Security).

#figure(
  image("diagrams/LAB_KICH_BAN_1.svg", width: 90%),
  caption: [Sơ đồ Topo Kịch bản 1: Hạ tầng Chuyển mạch và Bảo mật Lớp 2],
) <fig-topo-scenario-1>

*Quy trình thực hiện trên phần mềm CAMS:*

Căn cứ vào sơ đồ Topo Kịch bản 1, toàn bộ 8 thiết bị mạng (2 Router và 6 Switch) trong phòng lab EVE-NG đã được nạp vào không gian làm việc `LAB_KICH_BAN_1` với dải IP quản trị từ `192.168.122.101` đến `192.168.122.108` và hiển thị trạng thái kết nối thành công (*CONNECTED*) tại thanh Sidebar bên trái.

Quá trình cấu hình toàn diện hạ tầng Layer 2 trên phần mềm được thực hiện qua các bước tiêu biểu sau:

*Bước 1: Thiết lập nhóm VTP Group và đồng bộ miền VTP toàn mạng*

Để tối ưu hóa việc quản lý phân vùng trên 6 switch mà không cần khai báo lặp lại thủ công trên từng thiết bị, người dùng truy cập phân hệ *Switching* $arrow$ thẻ *VTP*. Tại đây, tính năng *VTP Group* cho phép cấu hình đồng bộ hàng loạt (Batch capacity 5/5) với tên miền `PTIT_LAB`, phiên bản `VTP Version 2`, áp dụng đồng thời cho 5 thiết bị `SW1` đến `SW5` trong đó `SW1` đóng vai trò VTP Server và các switch còn lại là VTP Client.

#figure(
  image("diagrams/Anh_chuong_5/1_16.png", width: 85%),
  caption: [Giao diện cấu hình nhóm VTP Group quản lý đồng bộ 5 Switch trong miền PTIT_LAB],
) <fig-k1-vtp-group>
*Giải thích @fig-k1-vtp-group:* Giao diện trực quan thể hiện danh sách các switch kết nối (Connected switches: 6), số thiết bị được chọn tham gia miền (Selected: 5) và các miền đã lưu trữ (`Saved domains`). Quản trị viên chỉ cần chọn danh sách switch và nhấn *Save & Push* để thiết lập toàn bộ hạ tầng VTP chỉ trong một thao tác duy nhất.

*Bước 2: Khởi tạo phân vùng VLAN và Kiểm duyệt tập lệnh (View & Push VLAN)*

Tại switch trung tâm `SW1` (VTP Server, IP: `192.168.122.101`), người dùng chuyển sang thẻ *VLAN* để khởi tạo các phân vùng mạng nghiệp vụ: `VLAN 10` (Tên: `IT_VLAN`) và `VLAN 20` (Tên: `HR_VLAN`). Sau khi lưu vào trạng thái mong muốn (`Desired State`), người dùng nhấn nút *View & Push* để mở cửa sổ duyệt trước mã lệnh.

#figure(
  image("diagrams/Anh_chuong_5/1_20.png", width: 80%),
  caption: [Cửa sổ View & Push kiểm duyệt tập lệnh cấu hình VLAN tự động sinh cho SW1],
) <fig-k1-vlan-push>
*Giải thích @fig-k1-vlan-push:* Cửa sổ modal hiển thị chính xác khối lệnh Cisco IOS do Template Engine Jinja2 biên dịch từ dữ liệu đồ họa (`vlan 10`, `name IT_VLAN`, `state active`, `vlan 20`, `name HR_VLAN`). Người dùng có thể đối soát từng dòng lệnh trước khi nhấn nút *Push* để gửi lệnh xuống thiết bị thật qua luồng SSH chạy nền an toàn.

*Bước 3: Cấu hình gom kênh liên kết EtherChannel (LACP)*

Nhằm tăng băng thông và đảm bảo tính dự phòng cho đường truyền Trunk giữa `SW1` và `SW3`, người dùng truy cập thẻ *EtherChannel* trên tab `SW1`. Tại đây, người dùng gom 2 cổng vật lý `GigabitEthernet1/0` và `GigabitEthernet1/1` vào nhóm logic `Port-channel1` với giao thức LACP (`mode active`) và gán nhãn mô tả `Link_To_SW3`.

#figure(
  image("diagrams/Anh_chuong_5/1_3.png", width: 80%),
  caption: [Cửa sổ View & Push cấu hình gom kênh EtherChannel LACP cho liên kết SW1 -- SW3],
) <fig-k1-etherchannel-push>
*Giải thích @fig-k1-etherchannel-push:* Hệ thống tự động tách và sinh mã cấu hình chuẩn cho từng giao diện thành phần (`interface GigabitEthernet1/1`, `channel-group 1 mode active`) và giao diện logic tổng hợp (`interface Port-channel1`, `description Link_To_SW3`), loại bỏ nguy cơ cấu hình lệch mode gây nghẽn vòng lặp Spanning Tree.

*Bước 4: Thiết lập cơ chế phòng vệ DHCP Snooping và Dynamic ARP Inspection (DAI)*

Để ngăn chặn các cuộc tấn công mạng Lớp 2 (DHCP Rogue Server, Man-in-the-Middle và ARP Spoofing), người dùng chuyển sang phân hệ *Security* $arrow$ thẻ *L2 Security*.

#figure(
  image("diagrams/Anh_chuong_5/1_21.png", width: 85%),
  caption: [Giao diện quản trị an ninh Layer 2: Thiết lập DHCP Snooping và Dynamic ARP Inspection],
) <fig-k1-l2-security>
*Giải thích @fig-k1-l2-security:* Bảng điều khiển cho phép bật/tắt chính sách bảo vệ VLAN Protection theo từng phân vùng (VLAN 1, 10, 20, 99). Tại ngăn thuộc tính bên phải, quản trị viên kích hoạt tính năng *Enable DHCP Snooping* và *Enable DAI* chỉ bằng một nút gạt chuyển trạng thái; đồng thời chỉ định các đường gom Trunk là *Trusted Uplinks* để cho phép lưu lượng DHCP/ARP hợp lệ đi qua.

*Bước 5: Cấu hình giới hạn truy cập Port Security trên Switch truy cập SW5*

Trên switch truy cập `SW5` (IP: `192.168.122.105`), người dùng chuyển sang thẻ *Port Security* để bảo vệ các cổng kết nối đến người dùng cuối. Với cổng `GigabitEthernet0/2`, người dùng thiết lập số lượng địa chỉ MAC tối đa là `4`, kích hoạt học địa chỉ tự động (`mac-address sticky`), thời gian lưu vết `5 phút` và cơ chế xử lý vi phạm là ngắt cổng tức thì (`violation shutdown`).

#figure(
  image("diagrams/Anh_chuong_5/1_25.png", width: 80%),
  caption: [Cửa sổ View & Push áp dụng chính sách Port Security bảo vệ cổng truy cập trên SW5],
) <fig-k1-port-security-push>
#block[
  #set par(justify: false)
  *Giải thích @fig-k1-port-security-push:* Hệ thống sinh đầy đủ khối lệnh Port Security chuẩn để quản trị viên kiểm tra trước khi đẩy xuống thiết bị:
]

```text
switchport mode access
switchport port-security
switchport port-security maximum 4
switchport port-security violation shutdown
switchport port-security mac-address sticky
switchport port-security aging time 5
```

*Bước 6: Xác minh kết quả thực thi trên thiết bị thật qua Terminal Alacritty nhúng*

Sau khi hoàn tất quá trình đẩy cấu hình từ phần mềm, người dùng nhấp vào biểu tượng Terminal trên thanh công cụ của CAMS để mở cửa sổ điều khiển trực tiếp tới thiết bị và thực hiện các câu lệnh kiểm tra trạng thái thực tế.

#figure(
  image("diagrams/Anh_chuong_5/1_30.png", width: 85%),
  caption: [Kiểm tra trạng thái VLAN và VTP trên Switch Client SW3 thông qua Terminal tích hợp],
) <fig-k1-terminal-verify>
*Giải thích @fig-k1-terminal-verify:* Kết quả lệnh `show vlan` trên `SW3` chứng minh toàn bộ các VLAN (`10 IT_VLAN`, `20 HR_VLAN`, `99 VLAN0099`) đã được đồng bộ tự động từ `SW1`. Lệnh `show vtp status` xác nhận `SW3` đang hoạt động ở chế độ `Client`, thuộc VTP Domain `PTIT_LAB`, chạy phiên bản 2, có chỉ số `Configuration Revision: 12` và chuỗi `MD5 digest` trùng khớp hoàn toàn với thông tin cấu hình từ server `192.168.122.101`.

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

*Mục tiêu kịch bản:* Thiết lập hạ tầng định tuyến động OSPFv2 liên kết hai chi nhánh doanh nghiệp (Chi nhánh A và Chi nhánh B) thông qua mạng đường trục ISP (Backbone Area 0). Ứng dụng tính năng *Routing Group - OSPF* của CAMS để tự động hóa quá trình cấu hình đồng loạt trên 6 bộ định tuyến (`R1`, `R2`, `R3`, `ISP1`, `ISP2`, `R6`), đồng thời kích hoạt cơ chế *Tái phân phối tuyến (Route Redistribution)* nhằm quảng bá các dải mạng LAN cục bộ vào miền OSPF, đảm bảo lưu lượng giữa các phòng ban thuộc hai chi nhánh được thông suốt 100%.

#figure(
  image("diagrams/LAB_2-report.png", width: 95%),
  caption: [Sơ đồ Topo Kịch bản 2: Định tuyến OSPF đa vùng giữa hai chi nhánh],
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
    (
      [Đường trục ISP],
      [R1, ISP1, ISP2, R6],
      [10.0.0.0/24, 10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24],
      [Miền đường trục OSPF Backbone Area 0],
    ),
    ([Chi nhánh B], [VPC14 (B1_VLAN)], [192.168.30.10/24], [Gateway: 192.168.30.1 (R6 Gi0/1)]),
    ([Chi nhánh B], [VPC15 (B2_VLAN)], [192.168.40.10/24], [Gateway: 192.168.40.1 (R6 Gi0/1)]),
    ([Mạng Quản trị], [Toàn bộ Router/SW], [192.168.122.101 -- 109/24], [Kênh Out-of-Band kết nối CAMS]),
  ),
  caption: [Bảng quy hoạch địa chỉ IP và phân vùng OSPF cho Kịch bản 2],
) <tab-ip-planning-lab2>

*Quy trình thực hiện trên phần mềm CAMS:*

*Bước 1: Cấu hình Giao diện Lớp 3 và gán địa chỉ IP trên các Router*

Trước khi triển khai định tuyến, quản trị viên sử dụng phân hệ *Interfaces* trên CAMS để thiết lập các thông số IP, Subnet Mask và kích hoạt trạng thái hoạt động cho từng cổng vật lý (`GigabitEthernet`) trên các thiết bị.

#figure(
  image("diagrams/Chuong_5_lab2/1.png", width: 85%),
  caption: [Giao diện phân hệ Interfaces quản lý và cấu hình tham số Lớp 3 cho các cổng Router],
) <fig-k2-interfaces>
*Giải thích @fig-k2-interfaces:* Bảng điều khiển bên trái liệt kê trực quan trạng thái IP của tất cả cổng mạng trên router `R1`. Ngăn thuộc tính bên phải cho phép chọn cấu hình nhanh IP Address, Subnet Mask, gán nhãn mô tả đường truyền và chuyển đổi trạng thái cổng (`Up/Down`) chỉ qua vài thao tác chuột.

*Bước 2: Cấu hình nhóm OSPF hàng loạt qua tính năng Routing Group*

Thay vì phải truy cập thủ công vào từng router để gõ từng dòng lệnh OSPF, quản trị viên sử dụng tính năng *Routing Group - OSPF* để cấu hình tự động cho toàn bộ 6 Router (`R1`, `R2`, `R3`, `ISP1`, `ISP2`, `R6`).

#figure(
  image("diagrams/Chuong_5_lab2/10.png", width: 80%),
  caption: [Cửa sổ Routing Group - OSPF (Bước 1: Chọn đồng thời 6 Router tham gia cấu hình nhóm)],
) <fig-k2-group-hosts>
*Giải thích @fig-k2-group-hosts:* Quản trị viên chỉ cần tích chọn danh sách các router cần cấu hình trong không gian làm việc `LAB_KICH_BAN_2`. Hệ thống tự động xác định các giao diện kết nối và địa chỉ IP tương ứng trên từng thiết bị.

Tiếp theo, tại bước *Networks*, quản trị viên gán các dải mạng kết nối trực tiếp vào từng vùng định tuyến phù hợp (Area 0 cho các liên kết Backbone ISP và Area 1 cho các liên kết nội bộ Chi nhánh A).

#figure(
  image("diagrams/Chuong_5_lab2/11.png", width: 80%),
  caption: [Cửa sổ Routing Group - OSPF (Bước 4: Khai báo phân vùng mạng và gán OSPF Area tương ứng)],
) <fig-k2-group-networks>
#block[
  #set par(justify: false)
  *Giải thích @fig-k2-group-networks:* Giao diện tự động phân nhóm các cổng theo từng router và gán mỗi dải mạng vào vùng OSPF tương ứng:
]

#report-table(
  columns: (18%, 52%, 30%),
  header: ([Router], [Dải mạng], [Vùng OSPF]),
  rows: (
    (table.cell(rowspan: 3)[*R1*], [#table-code("10.1.12.0/24")], [Area 1]),
    ([#table-code("10.1.13.0/24")], [Area 1]),
    ([#table-code("10.0.0.0/24")], [Area 0 (Backbone)]),
    (table.cell(rowspan: 2)[*R2*], [#table-code("10.1.12.0/24")], [Area 1]),
    ([#table-code("10.1.23.0/24")], [Area 1]),
  ),
  cell-align: (center + horizon, left + horizon, center + horizon),
  width: 88%,
  text-size: 10.5pt,
  cell-inset: (x: 7pt, y: 6pt),
)

#block[
  #set par(justify: false)
  Sau khi kiểm tra các ánh xạ, quản trị viên nhấn *Save & Push*. Hệ thống sau đó đẩy cấu hình song song xuống toàn bộ router đã chọn.
]

*Bước 3: Cấu hình Tái phân phối tuyến (Route Redistribution) cho mạng LAN người dùng*

Để các dải mạng người dùng (`192.168.10.0/24`, `192.168.20.0/24` ở Chi nhánh A và `192.168.30.0/24`, `192.168.40.0/24` ở Chi nhánh B) được quảng bá xuyên suốt qua mạng OSPF mà không cần chạy OSPF trực tiếp xuống Switch mạng truy cập, quản trị viên cấu hình tính năng *Redistribute Connected Subnets* trên các router biên `R2`, `R3` và `R6`.

#figure(
  image("diagrams/Chuong_5_lab2/16.png", width: 85%),
  caption: [Giao diện thiết lập tham số Tái phân phối tuyến (OSPF Redistribute) trên Router biên R6],
) <fig-k2-redistribute-gui>
*Giải thích @fig-k2-redistribute-gui:* Quản trị viên mở tab `R6`, chọn phân hệ *Routing* $arrow$ thẻ *OSPF* $arrow$ tiểu mục *Redistribute*. Tại đây, người dùng thực hiện:
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
*Giải thích @fig-k2-redistribute-push:* Cửa sổ kiểm duyệt hiển thị khối lệnh Cisco IOS sinh ra:
```text
# Cấu hình OSPF và Redistribution sinh tự động cho R2
router ospf 1
 router-id 2.2.2.2
 network 10.1.12.0 0.0.0.255 area 1
 network 10.1.23.0 0.0.0.255 area 1
 network 2.2.2.0 0.0.0.255 area 1
 redistribute connected subnets
 exit
```
Lệnh `redistribute connected subnets` giúp router biên chuyển đổi các tuyến mạng LAN kết nối trực tiếp thành các tuyến ngoại vi OSPF External Type 2 (`O E2`) để phát tán vào toàn bộ miền định tuyến.

*Bước 4: Xác minh cấu hình OSPF đa thiết bị trên Terminal Alacritty nhúng*

Sau khi hoàn tất tiến trình đẩy cấu hình từ phần mềm, quản trị viên mở các cửa sổ Terminal tích hợp để kiểm tra trực tiếp tệp cấu hình chạy trên cả 6 router.

#figure(
  image("diagrams/Chuong_5_lab2/12.png", width: 90%),
  caption: [Xác minh đồng thời cấu hình OSPF trên 6 Router (R1, R2, R3, ISP1, ISP2, R6) qua Terminal nhúng],
) <fig-k2-multi-terminal-ospf>
*Giải thích @fig-k2-multi-terminal-ospf:* Lệnh `show run | section ospf` trên từng cửa sổ chứng minh tất cả 6 router đã nhận đầy đủ tiến trình OSPF Process 1, Router-ID duy nhất (`1.1.1.1` đến `6.6.6.6`) và các dải mạng được gán chính xác vào Area 0 và Area 1 đúng theo thiết kế ban đầu.

*Bước 5: Kiểm tra Bảng định tuyến OSPF (show ip route)*

Quản trị viên thực hiện lệnh `show ip route` trên router trung tâm `R1` để kiểm tra khả năng hội tụ của hệ thống định tuyến:

#figure(
  image("diagrams/Chuong_5_lab2/18.png", width: 85%),
  caption: [Bảng định tuyến trên Router R1 hiển thị đầy đủ các tuyến nội vùng và tuyến ngoại vi O E2],
) <fig-k2-route-table-r1>
*Giải thích @fig-k2-route-table-r1:* Bảng định tuyến của `R1` ghi nhận đầy đủ:
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
*Giải thích @fig-k2-ping-vpc11-vpc14:* Từ máy trạm `VPC11` (`192.168.10.10` thuộc phân vùng `A1_VLAN` tại Chi nhánh A), lệnh `ping 192.168.30.10` (máy trạm `VPC14` thuộc phân vùng `B1_VLAN` tại Chi nhánh B) đạt tỷ lệ phản hồi 5/5 gói tin thành công, thời gian trễ trung bình cực thấp (~6.9 ms), gói tin đi qua 5 hop định tuyến (`ttl=59`).

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

*Đánh giá kết quả Kịch bản 2:* Giải pháp cấu hình định tuyến động theo nhóm *Routing Group - OSPF* kết hợp cùng cơ chế *Route Redistribution* trên phần mềm CAMS đã hoàn thành xuất sắc bài toán kết nối mạng liên chi nhánh đa vùng. Toàn bộ các router tự động thiết lập quan hệ láng giềng, học đầy đủ bảng định tuyến và truyền thông dữ liệu hai chiều giữa tất cả các máy trạm đạt độ ổn định và tin cậy 100%.



=== Kịch bản 3: Tích hợp Cổng dự phòng GLBP, Cấp phát DHCP và Chuyển đổi địa chỉ NAT/PAT

*Mục tiêu kịch bản:* Xây dựng mô hình mạng LAN có khả năng cấp phát địa chỉ IP tự động, sử dụng cổng mặc định dự phòng và cân bằng tải bằng giao thức GLBP, đồng thời cho phép các máy trạm trong mạng nội bộ truy cập ra mạng ngoài thông qua cơ chế NAT/PAT. Kịch bản tập trung kiểm thử khả năng phối hợp nhiều chức năng Lớp 3 trên CAMS theo cùng một quy trình *Thiết lập trên GUI $arrow$ View & Push $arrow$ Xác minh trực tiếp trên thiết bị*.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/fhrp-nat-dhcp-report.png", width: 95%),
  caption: [Sơ đồ Topo Kịch bản 3: Tích hợp GLBP, DHCP và NAT/PAT cho mạng LAN],
) <fig-topo-scenario-3>

*Quy hoạch địa chỉ và vai trò thiết bị:*

#report-table(
  columns: (14%, 28%, 18%, 40%),
  text-size: 9.5pt,
  cell-inset: (x: 4pt, y: 4.5pt),
  header: ([Thiết bị], [Giao diện / Địa chỉ], [Vai trò], [Ghi chú]),
  rows: (
    ([R1], [#table-code("Gi0/0 - 192.168.4.2/24")], [Gateway member], [Tham gia GLBP Group 113, Priority 101]),
    ([R2], [#table-code("Gi0/0 - 192.168.4.3/24")], [Gateway member], [Tham gia GLBP Group 113, Priority 100]),
    ([GLBP Virtual IP], [#table-code("192.168.4.1")], [Default Gateway], [Địa chỉ gateway cấp cho các máy trạm qua DHCP]),
    ([NAT], [#table-code("Gi0/1 - 192.168.1.2/24")], [NAT Inside], [Kết nối hướng về R1]),
    ([NAT], [#table-code("Gi0/3 - 192.168.2.2/24")], [NAT Inside], [Kết nối hướng về R2]),
    ([NAT], [#table-code("Gi0/2 - 10.0.10.2/24")], [NAT Outside], [Kết nối tới mạng ISP / upstream]),
    ([PC1], [DHCP], [Máy trạm kiểm thử], [Nhận IP động và sử dụng gateway `192.168.4.1`]),
  ),
  caption: [Bảng quy hoạch địa chỉ và vai trò thiết bị trong Kịch bản 3],
) <tab-ip-planning-lab3>

*Quy trình thực hiện trên phần mềm CAMS:*

*Bước 1: Khai báo vai trò NAT Inside/Outside cho các giao diện trên Router NAT*

Trên thiết bị `NAT` có địa chỉ quản trị `192.168.122.103`, quản trị viên truy cập phân hệ *NAT* $arrow$ thẻ *Interfaces* để xác định hướng lưu lượng cho từng cổng. Hai giao diện `GigabitEthernet0/1` và `GigabitEthernet0/3` được đánh dấu là *Inside*, trong khi `GigabitEthernet0/2` được đánh dấu là *Outside*.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/01-nat-interfaces.png", width: 90%),
  caption: [Giao diện khai báo vai trò NAT Inside/Outside trên Router NAT],
) <fig-k3-nat-interfaces>

*Giải thích @fig-k3-nat-interfaces:* Bảng *NAT Interfaces* bên phải thể hiện rõ ba giao diện đã được lưu ở trạng thái mong muốn: `Gi0/1` và `Gi0/3` mang vai trò `Inside`, còn `Gi0/2` mang vai trò `Outside`. Cách biểu diễn này giúp người dùng kiểm tra nhanh hướng NAT trước khi sinh lệnh cấu hình.

*Bước 2: Tạo Access Control List xác định dải địa chỉ nội bộ được phép NAT*

Tại thẻ *ACL* của phân hệ NAT, quản trị viên tạo ACL chuẩn có tên `NAT_demo`, hành động `permit`, áp dụng cho mạng nguồn `192.168.0.0` với wildcard mask `0.0.7.255`. Dải này bao phủ các mạng nội bộ được sử dụng trong mô hình thử nghiệm.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/02-nat-acl.png", width: 90%),
  caption: [Khai báo ACL NAT_demo xác định các mạng nội bộ được phép chuyển đổi địa chỉ],
) <fig-k3-nat-acl>

Sau khi lưu các tham số giao diện và ACL, người dùng mở cửa sổ *View & Push* để kiểm duyệt tập lệnh trước khi gửi xuống thiết bị.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/03-nat-config-preview.png", width: 78%),
  caption: [Cửa sổ View & Push sinh cấu hình NAT Interface và ACL cho Router NAT],
) <fig-k3-nat-preview>

*Giải thích @fig-k3-nat-preview:* CAMS tự động sinh đúng các lệnh `ip nat inside`, `ip nat outside` trên từng giao diện và khối ACL:
```text
ip access-list standard NAT_demo
 10 permit 192.168.0.0 0.0.7.255
```
Người dùng có thể đối soát toàn bộ lệnh trước khi nhấn *Push*, giữ nguyên nguyên tắc Staged Save đã sử dụng ở các kịch bản trước.

*Bước 3: Cấu hình PAT Overload sử dụng địa chỉ của giao diện Outside*

Sau khi xác định vùng Inside/Outside và ACL, quản trị viên chuyển sang thẻ *PAT*. Tại đây, ACL `NAT_demo` được chọn làm nguồn cần chuyển đổi, `Source Type` được đặt là *Outside Interface* và giao diện `GigabitEthernet0/2` được sử dụng làm địa chỉ đại diện phía ngoài.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/04-nat-pat.png", width: 90%),
  caption: [Giao diện cấu hình PAT Overload sử dụng cổng Outside GigabitEthernet0/2],
) <fig-k3-pat-gui>

Cửa sổ *View & Push* cho thấy lệnh PAT được sinh tự động:

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/05-nat-pat-preview.png", width: 78%),
  caption: [Cửa sổ View & Push kiểm duyệt lệnh PAT Overload trước khi đẩy xuống Router NAT],
) <fig-k3-pat-preview>

```text
ip nat inside source list NAT_demo interface GigabitEthernet0/2 overload
```

Lệnh trên cho phép nhiều địa chỉ IPv4 trong mạng nội bộ dùng chung địa chỉ IP của giao diện `Gi0/2`, phân biệt các phiên kết nối thông qua số hiệu cổng lớp vận chuyển.

*Bước 4: Xác minh cấu hình NAT/PAT trực tiếp trên thiết bị*

Sau khi Push, quản trị viên mở Terminal tích hợp và kiểm tra cấu hình thực tế trên Router NAT. Kết quả xác nhận `Gi0/1` và `Gi0/3` đã nhận `ip nat inside`, trong khi `Gi0/2` đã nhận `ip nat outside`.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/06-nat-interface-verify.png", width: 72%),
  caption: [Xác minh vai trò NAT trên ba giao diện của Router NAT bằng lệnh show running-config],
) <fig-k3-nat-interface-verify>

Tiếp tục kiểm tra cấu hình tổng thể cho thấy lệnh PAT, ACL `NAT_demo` và tuyến mặc định tới `10.0.10.1` đã tồn tại trong running-config.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/07-nat-config-verify.png", width: 82%),
  caption: [Xác minh ACL, PAT Overload và Default Route trên Router NAT],
) <fig-k3-nat-config-verify>

*Bước 5: Thiết lập GLBP làm Default Gateway dự phòng cho mạng LAN*

Để tránh phụ thuộc vào một router gateway duy nhất, quản trị viên sử dụng phân hệ *FHRP* $arrow$ *GLBP*. Hai router `R1` (`192.168.122.101`) và `R2` (`192.168.122.102`) được chọn làm thành viên của nhóm `113`, sử dụng địa chỉ gateway ảo `192.168.4.1` trên mạng LAN `192.168.4.0/24`.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/08-glbp-setup.png", width: 86%),
  caption: [Giao diện tạo GLBP Group 113 với Virtual IP 192.168.4.1 trên R1 và R2],
) <fig-k3-glbp-setup>

Tại phần *Member policy*, CAMS tự động ghép các giao diện cùng subnet với địa chỉ Virtual IP. `R1 Gi0/0 - 192.168.4.2/24` được đặt Priority `101`, `R2 Gi0/0 - 192.168.4.3/24` có Priority `100`; cả hai cho phép `Preempt`, sử dụng `Maximum Weighting 100` và cấu hình `Forwarder Preempt Delay` là `30` giây.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/09-glbp-member-policy.png", width: 86%),
  caption: [Thiết lập chính sách thành viên GLBP cho R1 và R2],
) <fig-k3-glbp-member-policy>

Trước khi áp dụng, cửa sổ *View & Push FHRP* tổng hợp lệnh cho cả hai thiết bị trong cùng một phiên kiểm duyệt.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/10-glbp-config-preview.png", width: 80%),
  caption: [Cửa sổ View & Push FHRP sinh đồng thời cấu hình GLBP cho R1 và R2],
) <fig-k3-glbp-preview>

*Giải thích @fig-k3-glbp-preview:* Trên cả hai router, hệ thống sinh các lệnh `glbp 113 ip 192.168.4.1`, `glbp 113 preempt`, `glbp 113 load-balancing round-robin`, `glbp 113 weighting 100` và `glbp 113 forwarder preempt delay minimum 30`. Riêng R1 được đặt `priority 101`, cao hơn R2 là `100`, phù hợp với chính sách ưu tiên đã khai báo trên GUI.

*Bước 6: Tạo DHCP Pool và cấp GLBP Virtual IP làm Default Gateway cho máy trạm*

Sau khi gateway ảo đã được thiết lập, quản trị viên chuyển sang thiết bị `R1`, mở phân hệ *DHCP* và tạo pool `LAN_R1` cho mạng `192.168.4.0/24`. Trường *Default Router* được đặt là `192.168.4.1`, chính là Virtual IP của GLBP thay vì địa chỉ vật lý của riêng R1 hoặc R2.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/11-dhcp-pool.png", width: 88%),
  caption: [Giao diện tạo DHCP Pool LAN_R1 với Default Gateway là GLBP Virtual IP 192.168.4.1],
) <fig-k3-dhcp-pool>

Cửa sổ kiểm duyệt cho thấy cấu hình DHCP được sinh tương ứng:

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/13-dhcp-config-preview.png", width: 78%),
  caption: [Cửa sổ View & Push DHCP sinh cấu hình pool LAN_R1 trên R1],
) <fig-k3-dhcp-preview>

```text
ip dhcp pool LAN_R1
 network 192.168.4.0 255.255.255.0
 default-router 192.168.4.1
 exit
```

Cách cấu hình này giúp máy trạm không phụ thuộc trực tiếp vào địa chỉ vật lý `192.168.4.2` hoặc `192.168.4.3`, mà luôn sử dụng gateway logic `192.168.4.1` do GLBP quản lý.

*Bước 7: Xác minh DHCP và GLBP trên R1, R2*

Trên `R1`, lệnh `show ip dhcp pool` xác nhận pool `LAN_R1` đã được tạo cho mạng `192.168.4.0/24`. Đồng thời, `show running-config interface g0/0` xác nhận giao diện LAN `192.168.4.2/24` đang tham gia GLBP Group `113`, có Virtual IP `192.168.4.1`, Priority `101` và bật `preempt`.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/14-dhcp&glbp-r1-verify.png", width: 88%),
  caption: [Xác minh DHCP Pool và cấu hình GLBP trên Router R1],
) <fig-k3-r1-verify>

Trên `R2`, giao diện `Gi0/0` mang địa chỉ `192.168.4.3/24` và tham gia cùng GLBP Group `113` với Virtual IP `192.168.4.1`, đảm bảo hai router cùng cung cấp dịch vụ gateway cho một mạng LAN.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/15-glbp-r2-verify.png", width: 82%),
  caption: [Xác minh cấu hình GLBP Group 113 trên Router R2],
) <fig-k3-r2-verify>

*Bước 8: Kiểm tra cấp phát DHCP và đường đi lưu lượng từ máy trạm*

Cuối cùng, trên máy trạm `PC1`, lệnh `ip dhcp` được sử dụng để yêu cầu cấp phát địa chỉ. Máy trạm nhận thành công địa chỉ `192.168.4.4/24` cùng default gateway `192.168.4.1`.

#figure(
  image("diagrams/fhrp_nat_dhcp_lap/16-client-connectivity-test.png", width: 82%),
  caption: [Kiểm tra PC1 nhận DHCP và truy vết đường đi qua GLBP Gateway tới Router NAT và mạng upstream],
) <fig-k3-client-test>

*Giải thích @fig-k3-client-test:* Kết quả `trace 1.1.1.1` ghi nhận hop đầu tiên là `192.168.4.2` (R1), tiếp theo là `192.168.1.2` (Router NAT) và sau đó tới `10.0.10.1` ở phía upstream. Kết quả này chứng minh máy trạm đã nhận đúng cấu hình DHCP, sử dụng được GLBP Virtual Gateway và lưu lượng đã đi qua đúng chuỗi thiết bị theo thiết kế. Tại hop `10.0.10.1`, thiết bị upstream trả về ICMP `Destination port unreachable`; vì vậy phép thử này được sử dụng để xác minh đường đi tới mạng ngoài của mô hình lab, không được xem là bằng chứng kết nối Internet hoàn chỉnh tới địa chỉ `1.1.1.1`.

*Đánh giá kết quả Kịch bản 3:* CAMS đã cấu hình thành công chuỗi chức năng liên hoàn *DHCP $arrow$ GLBP $arrow$ NAT/PAT*. Máy trạm nhận địa chỉ động `192.168.4.4/24`, sử dụng gateway ảo `192.168.4.1`; hai router R1/R2 cùng tham gia GLBP Group 113; Router NAT nhận đúng vai trò Inside/Outside, ACL và PAT Overload. Kết quả truy vết xác nhận lưu lượng từ LAN đi đúng qua R1 tới Router NAT và tới gateway upstream `10.0.10.1`. Qua đó, kịch bản chứng minh phần mềm có khả năng phối hợp nhiều nghiệp vụ Lớp 3 trên nhiều thiết bị trong cùng một quy trình cấu hình và kiểm chứng thống nhất.


=== Kịch bản 4: Thu thập, giám sát và phân tích nhật ký tập trung bằng Syslog Server

*Mục tiêu kịch bản:* Kiểm thử khả năng cấu hình đồng loạt dịch vụ Syslog trên nhiều thiết bị Cisco và khả năng tiếp nhận, phân tích, hiển thị nhật ký thời gian thực ngay trong CAMS. Kịch bản sử dụng 4 thiết bị gồm ba router `R1`, `R2`, `R3` và switch `SW1`; tất cả gửi log về Syslog Server tại địa chỉ `192.168.122.1`, sử dụng cổng `5514/UDP`. Ngoài việc kiểm tra cấu hình trên từng thiết bị, kịch bản còn xác minh khả năng phân loại thông điệp theo Host, Source IP, Facility/Severity, Mnemonic và nội dung Raw Message.

#figure(
  image("diagrams/syslog lab/syslog-lab-topology-report.png", width: 92%),
  caption: [Sơ đồ Topo Kịch bản 4: Thu thập Syslog tập trung],
) <fig-topo-scenario-4>

*Quy hoạch thiết bị và chính sách Syslog:*

#report-table(
  columns: (11%, 24%, 27%, 38%),
  text-size: 9.5pt,
  cell-inset: (x: 4pt, y: 4.5pt),
  header: ([Thiết bị], [IP quản trị], [Source Interface], [Chính sách gửi Syslog]),
  rows: (
    ([R1], [#table-code("192.168.122.101")], [#table-code("GigabitEthernet0/0")], [#table-code("192.168.122.1:5514/UDP"), mức #table-code("notifications")]),
    ([R2], [#table-code("192.168.122.102")], [#table-code("GigabitEthernet0/0")], [#table-code("192.168.122.1:5514/UDP"), mức #table-code("notifications")]),
    ([R3], [#table-code("192.168.122.103")], [#table-code("GigabitEthernet0/0")], [#table-code("192.168.122.1:5514/UDP"), mức #table-code("notifications")]),
    ([SW1], [#table-code("192.168.122.104")], [#table-code("Vlan1")], [#table-code("192.168.122.1:5514/UDP"), mức #table-code("notifications")]),
  ),
  caption: [Bảng quy hoạch nguồn gửi Syslog trong Kịch bản 4],
) <tab-syslog-planning-lab4>

*Quy trình thực hiện trên phần mềm CAMS:*

*Bước 1: Mở phân hệ Syslog Server và chuẩn bị cấu hình đích nhận log*

Từ thiết bị đang được quản lý, quản trị viên mở thẻ *Syslog Server*. Tại thời điểm ban đầu chưa có đích Syslog nào được cấu hình, các chỉ số `Destinations`, `Applied`, `Pending apply` và `Pending removal` đều bằng `0`. Người dùng sử dụng chức năng *Syslog Group* để tạo một chính sách chung và áp dụng đồng thời cho nhiều thiết bị thay vì khai báo lặp lại từng router/switch.

#figure(
  image("diagrams/syslog lab/01-syslog-configuration.png", width: 92%),
  caption: [Giao diện quản lý Syslog Server trước khi tạo chính sách gửi log],
) <fig-k4-syslog-config>

*Giải thích @fig-k4-syslog-config:* Giao diện thể hiện mô hình quản lý trạng thái tương tự các phân hệ cấu hình khác của CAMS. Người dùng có thể tạo mới đích Syslog, kiểm duyệt lệnh bằng *View & Push* hoặc cấu hình theo nhóm bằng *Syslog Group*.

*Bước 2: Chọn đồng thời các thiết bị tham gia Syslog Group*

Tại bước *Hosts*, quản trị viên chọn cả bốn thiết bị đang kết nối gồm `R1`, `R2`, `R3` và `SW1`. Hệ thống hiển thị số lượng giao diện phát hiện được trên từng thiết bị để làm dữ liệu đầu vào cho bước lựa chọn Source Interface.

#figure(
  image("diagrams/syslog lab/02-syslog-select-hosts.png", width: 78%),
  caption: [Bước Hosts của Syslog Group: chọn 4 thiết bị cùng tham gia chính sách gửi log],
) <fig-k4-syslog-hosts>

*Giải thích @fig-k4-syslog-hosts:* Việc nhóm nhiều host vào cùng một workflow giúp giảm thao tác lặp lại và đảm bảo các thiết bị sử dụng thống nhất địa chỉ máy chủ, giao thức vận chuyển và mức severity.

*Bước 3: Chọn Source Interface cho từng thiết bị*

Tại bước *Interfaces*, CAMS cho phép chọn riêng giao diện nguồn trên từng host. Ba router sử dụng `GigabitEthernet0/0`, tương ứng với mạng quản trị `192.168.122.0/24`; switch `SW1` sử dụng giao diện logic `Vlan1`.

#figure(
  image("diagrams/syslog lab/03-syslog-source-interfaces.png", width: 78%),
  caption: [Lựa chọn Source Interface cho từng Router và Switch trong Syslog Group],
) <fig-k4-syslog-source>

Cấu hình `logging source-interface` giúp các bản tin Syslog phát ra với địa chỉ nguồn ổn định, nhờ đó CAMS có thể ánh xạ chính xác bản tin về đúng thiết bị trong danh sách quản lý.

*Bước 4: Khai báo chính sách Syslog dùng chung cho toàn nhóm*

Tại bước *Policy*, quản trị viên nhập địa chỉ máy chủ `192.168.122.1`, chọn giao thức `UDP`, cổng `5514` và mức *Trap severity* là `5 - Notifications`. Hai tùy chọn bổ sung *Include millisecond log timestamps* và *Include sequence numbers* được bật để tăng độ chính xác khi sắp xếp, đối chiếu sự kiện.

#figure(
  image("diagrams/syslog lab/04-syslog-policy.png", width: 78%),
  caption: [Thiết lập đích Syslog 192.168.122.1:5514/UDP và mức severity Notifications],
) <fig-k4-syslog-policy>

Với mức `notifications`, thiết bị gửi các thông điệp từ severity 0 đến severity 5 tới máy chủ Syslog. Đây là mức phù hợp cho bài thử vì có thể thu nhận các sự kiện thay đổi trạng thái interface, thông báo cấu hình và các bản tin kiểm thử do người quản trị chủ động tạo ra.

*Bước 5: Kiểm duyệt tập lệnh Syslog trước khi Push hàng loạt*

Sau khi hoàn tất ba bước của wizard, CAMS mở cửa sổ *View & Push Syslog Group* để tổng hợp cấu hình cho cả bốn thiết bị. Quản trị viên có thể xem toàn bộ lệnh trước khi nhấn *Push*.

#figure(
  image("diagrams/syslog lab/05-syslog-config-preview.png", width: 82%),
  caption: [Cửa sổ View & Push Syslog Group tổng hợp lệnh cho 4 thiết bị trước khi thực thi],
) <fig-k4-syslog-preview>

*Giải thích @fig-k4-syslog-preview:* Với router, hệ thống sinh các lệnh tiêu biểu:
```text
logging host 192.168.122.1 transport udp port 5514
logging trap notifications
service timestamps log datetime msec
service sequence-numbers
logging source-interface GigabitEthernet0/0
```
Riêng `SW1`, lệnh cuối được thay bằng `logging source-interface Vlan1`. Cách sinh lệnh theo từng host cho phép dùng chung một Policy nhưng vẫn giữ đúng đặc điểm giao diện của từng thiết bị.

*Bước 6: Xác minh cấu hình Syslog trên R1, R2, R3 và SW1*

Sau khi Push thành công, quản trị viên mở Terminal tích hợp và thực hiện lệnh `show running-config | section logging` trên từng thiết bị. Kết quả trên `R1`, `R2` và `R3` đều ghi nhận máy chủ `192.168.122.1`, giao thức UDP cổng `5514`, mức `notifications` và Source Interface `GigabitEthernet0/0`.

#figure(
  image("diagrams/syslog lab/06-syslog-r1-verify.png", width: 88%),
  caption: [Xác minh cấu hình Syslog trên Router R1],
) <fig-k4-r1-verify>

#figure(
  image("diagrams/syslog lab/07-syslog-r2-verify.png", width: 88%),
  caption: [Xác minh cấu hình Syslog trên Router R2],
) <fig-k4-r2-verify>

#figure(
  image("diagrams/syslog lab/08-syslog-r3-verify.png", width: 88%),
  caption: [Xác minh cấu hình Syslog trên Router R3],
) <fig-k4-r3-verify>

Trên switch `SW1`, cấu hình tương tự nhưng sử dụng `Vlan1` làm Source Interface.

#figure(
  image("diagrams/syslog lab/09-syslog-sw1-verify.png", width: 88%),
  caption: [Xác minh cấu hình Syslog trên Switch SW1 với Source Interface Vlan1],
) <fig-k4-sw1-verify>

Các kết quả xác minh cho thấy cấu hình thực tế trên thiết bị khớp với nội dung đã xem trước trên GUI, qua đó xác nhận quy trình *Syslog Group $arrow$ View & Push $arrow$ Verify* hoạt động đúng trên cả Router và Switch.

*Bước 7: Khởi động Syslog Listener tích hợp trong CAMS*

Tiếp theo, quản trị viên chuyển sang màn hình *System Logs*. Trước khi khởi động, trạng thái hiển thị *Listener stopped*, số bản tin nhận được bằng `0` và bảng log chưa có dữ liệu.

#figure(
  image("diagrams/syslog lab/10-syslog-listener-before-start.png", width: 94%),
  caption: [Màn hình System Logs trước khi khởi động Syslog Listener],
) <fig-k4-listener-before>

Sau khi nhấn *Start Listener*, dịch vụ chuyển sang trạng thái *Listener active* và lắng nghe trên `0.0.0.0:5514/UDP+TCP`. Khi các thiết bị phát sinh sự kiện, các bản tin được đưa trực tiếp vào bảng System Logs theo thời gian thực.

#figure(
  image("diagrams/syslog lab/11-syslog-listener-receiving.png", width: 94%),
  caption: [Syslog Listener đang hoạt động và tiếp nhận bản tin từ các thiết bị mạng],
) <fig-k4-listener-active>

*Giải thích @fig-k4-listener-active:* Tại thời điểm chụp, hệ thống đã tiếp nhận `245` bản tin. Mỗi dòng được phân tách thành các trường `Time`, `Host`, `Source IP`, `Facility/Severity`, `Mnemonic` và `Message`. Các sự kiện như `LINK`, `LINEPROTO`, `SYS` được hiển thị rõ ràng, cho phép quản trị viên nhanh chóng xác định thiết bị và loại sự kiện phát sinh.

*Bước 8: Kiểm tra khả năng phân tích chi tiết một bản tin Syslog*

Khi chọn một dòng log, CAMS mở cửa sổ *System Log Message* để hiển thị cả dữ liệu đã phân tích và bản tin nguyên gốc. Trong mẫu thử từ `192.168.122.101`, hệ thống nhận dạng thành công giao thức `UDP`, Cisco facility `LINEPROTO`, severity `5`, mnemonic `UPDOWN`, sequence number `104` và trạng thái parser là `parsed`.

#figure(
  image("diagrams/syslog lab/12-syslog-message-detail.png", width: 68%),
  caption: [Cửa sổ chi tiết một bản tin Syslog sau khi được parser phân tích],
) <fig-k4-message-detail>

Phần *Raw message* vẫn được giữ nguyên để phục vụ đối chiếu khi cần:
```text
<189>104: *Aug 29 20:25:44.323: %LINEPROTO-5-UPDOWN:
Line protocol on Interface Loopback99, changed state to down
```
Việc đồng thời lưu trường đã chuẩn hóa và Raw Message giúp giao diện thuận tiện cho giám sát thông thường nhưng vẫn bảo toàn dữ liệu gốc để kiểm tra chuyên sâu.

*Bước 9: Tạo sự kiện kiểm thử trên từng thiết bị và đối chiếu với Syslog Server*

Để tạo lượng log đủ lớn và có tính lặp lại, trên các router CAMS thực hiện chu kỳ thay đổi trạng thái `Loopback99`; trên switch, giao diện `GigabitEthernet1/3` được chuyển trạng thái Up/Down. Các thiết bị đồng thời phát sinh các bản tin `USERLOG_WARNING`, `USERLOG_NOTICE`, `LINK`, `LINEPROTO` và `CONFIG_I`.

#figure(
  image("diagrams/syslog lab/13-syslog-r1-device-logs.png", width: 94%),
  caption: [Nhật ký sự kiện kiểm thử phát sinh trực tiếp trên Router R1],
) <fig-k4-r1-device-logs>

#figure(
  image("diagrams/syslog lab/14-syslog-r2-device-logs.png", width: 94%),
  caption: [Nhật ký sự kiện kiểm thử phát sinh trực tiếp trên Router R2],
) <fig-k4-r2-device-logs>

#figure(
  image("diagrams/syslog lab/15-syslog-r3-device-logs.png", width: 94%),
  caption: [Nhật ký sự kiện kiểm thử phát sinh trực tiếp trên Router R3],
) <fig-k4-r3-device-logs>

#figure(
  image("diagrams/syslog lab/16-syslog-sw1-device-logs.png", width: 94%),
  caption: [Nhật ký sự kiện kiểm thử phát sinh trực tiếp trên Switch SW1],
) <fig-k4-sw1-device-logs>

*Giải thích các Hình @fig-k4-r1-device-logs -- @fig-k4-sw1-device-logs:* Các terminal cho thấy chuỗi sự kiện được tạo liên tục trên cả bốn thiết bị. Khi giao diện bị `shutdown` hoặc `no shutdown`, IOS phát sinh các thông điệp trạng thái liên kết và line protocol; đồng thời các bản tin `USERLOG_*` được dùng để đánh dấu từng chu kỳ thử nghiệm. Những sự kiện tương ứng xuất hiện trên màn hình System Logs, chứng minh luồng truyền bản tin từ thiết bị tới CAMS hoạt động liên tục và đúng nguồn.

*Đánh giá kết quả Kịch bản 4:* CAMS đã cấu hình thành công Syslog theo nhóm cho 4 thiết bị, trong đó ba router sử dụng `GigabitEthernet0/0` và switch sử dụng `Vlan1` làm Source Interface. Syslog Listener tích hợp nhận được đồng thời bản tin từ các nguồn `192.168.122.101` đến `192.168.122.104`, phân tích được các trường Cisco Facility/Severity/Mnemonic và vẫn bảo toàn Raw Message. Các sự kiện thực nghiệm về thay đổi trạng thái interface và thông báo cấu hình xuất hiện nhất quán giữa Terminal thiết bị và bảng System Logs. Kịch bản vì vậy xác nhận chức năng Syslog của CAMS hoạt động đúng từ khâu cấu hình nguồn gửi, tiếp nhận tập trung đến phân tích và quan sát nhật ký thời gian thực.


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

Chương 5 đã chứng minh tính khả thi, độ tin cậy và hiệu năng vượt trội của phần mềm CAMS thông qua kết quả kiểm thử tự động đạt 96,75% và 4 kịch bản thực nghiệm toàn diện trên phòng lab EVE-NG. Các kết quả đo đạc định lượng cho thấy công cụ giúp giảm trên 90% thời gian triển khai cấu hình và loại bỏ các sai sót cú pháp so với phương pháp thủ công, đáp ứng xuất sắc các mục tiêu nghiên cứu đã đề ra.
