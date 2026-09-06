# CHƯƠNG 2. CƠ SỞ LÝ THUYẾT VÀ CÔNG NGHỆ
## 2.1. Quản lý cấu hình và tự động hóa mạng

Trong hệ thống mạng máy tính, router và switch là các thành phần trực tiếp tham gia vào quá trình chuyển tiếp lưu lượng, phân tách miền mạng, định tuyến gói tin và áp dụng các chính sách truy cập. Để mạng hoạt động ổn định, người quản trị phải thực hiện nhiều nhóm công việc như khai báo địa chỉ IP, cấu hình giao diện, thiết lập định tuyến, cấp phát địa chỉ động, kiểm soát truy cập, chuyển đổi địa chỉ mạng, sao lưu cấu hình và theo dõi trạng thái thiết bị. Các nội dung này tạo thành phần nghiệp vụ chính của một hệ thống quản lý cấu hình mạng [Tanenbaum, 2021].

Trong mô hình quản trị truyền thống, kỹ sư mạng thường truy cập từng thiết bị bằng giao diện dòng lệnh CLI. Phương pháp này cho phép kiểm soát chi tiết nhưng phụ thuộc nhiều vào kiến thức câu lệnh và trạng thái của phiên làm việc. Khi số lượng thiết bị tăng, cùng một chuỗi cấu hình có thể phải lặp lại trên nhiều router hoặc switch. Quá trình lặp này làm tăng thời gian triển khai và khả năng xảy ra sai sót như nhập nhầm địa chỉ, thiếu câu lệnh, chọn sai interface hoặc thao tác trên nhầm thiết bị.

Quản lý tập trung hướng đến việc đưa thông tin thiết bị, trạng thái kết nối, dữ liệu cấu hình và lịch sử thao tác về một hệ thống thống nhất. Thay vì xem từng thiết bị như một thực thể hoàn toàn tách biệt, phần mềm xây dựng một lớp quản lý chung để người dùng lựa chọn thiết bị, chỉnh sửa dữ liệu, kiểm tra cấu hình dự kiến và thực hiện triển khai khi cần thiết.

Đối với đề tài CAMS, quản lý thiết bị được xem theo ba nhóm chính: *inventory*, *kết nối* và *cấu hình*. Inventory mô tả thiết bị đang được quản lý; lớp kết nối xác định cách phần mềm giao tiếp với thiết bị; lớp cấu hình quản lý dữ liệu mà người dùng muốn áp dụng. Cách phân chia này giúp tách thông tin quản trị khỏi logic giao tiếp và là nền tảng cho thiết kế module ở các chương sau.

### 2.1.1. Tự Động hóa mạng

Tự động hóa mạng là việc sử dụng phần mềm để hỗ trợ hoặc thực hiện các tác vụ quản trị vốn được tiến hành thủ công. Mục tiêu của tự động hóa không nhất thiết là loại bỏ người quản trị khỏi quy trình. Trong nhiều hệ thống, phần mềm đảm nhiệm các thao tác lặp như kiểm tra dữ liệu, sinh lệnh, kết nối, gửi cấu hình và thu thập kết quả, trong khi quyết định cuối cùng vẫn thuộc về con người.

Một quy trình cấu hình tự động có thể được khái quát như sau:

![Quy trình cấu hình tự động](../contents/diagrams/01_pipeline_automation.svg)
*Quy trình cấu hình tự động*

So với việc nhập lệnh trực tiếp, cách tiếp cận này giúp chuẩn hóa dữ liệu đầu vào, giảm thao tác lặp, tạo khả năng áp dụng cùng một quy tắc cho nhiều thiết bị và lưu lại trạng thái để kiểm tra sau đó. Tuy nhiên, tự động hóa cũng làm tăng yêu cầu về an toàn. Một lỗi trong phần mềm có thể ảnh hưởng đồng thời tới nhiều thiết bị, vì vậy hệ thống cần có validation, cơ chế xem trước, giới hạn xử lý đồng thời và khả năng cô lập lỗi theo từng host.

### 2.1.2. Quản lý cấu hình theo trạng thái

Trong quản lý cấu hình, cần phân biệt trạng thái đang tồn tại trên thiết bị và trạng thái mà người quản trị mong muốn.

*Current state* là trạng thái được quan sát hoặc thu thập từ thiết bị tại một thời điểm. Ví dụ, một interface đang sử dụng địa chỉ 192.168.1.1/24 và ở trạng thái hoạt động.

*Desired state* là trạng thái mà người quản trị mong muốn thiết bị đạt được. Khi người dùng chỉnh địa chỉ interface thành 192.168.10.1/24 trong phần mềm nhưng chưa gửi lệnh xuống router, dữ liệu này mới chỉ phản ánh trạng thái mong muốn.

*Pending configuration* là phần cấu hình đã được chỉnh sửa nhưng chưa đồng bộ với thiết bị. *Preview* là bước chuyển desired state thành câu lệnh hoặc biểu diễn cấu hình để người dùng kiểm tra trước. *Push* hoặc *Apply* là quá trình gửi cấu hình xuống thiết bị. Sau đó, *Verify* được sử dụng để xác nhận trạng thái thực tế đã phù hợp với kết quả mong muốn.

![Vòng đời một thay đổi cấu hình theo trạng thái](../contents/diagrams/02_state_flow.svg)
*Vòng đời một thay đổi cấu hình theo trạng thái*

Việc tách các trạng thái giúp thao tác chỉnh sửa trên giao diện không đồng nghĩa với thay đổi ngay thiết bị thật. Đây là nguyên tắc quan trọng đối với CAMS vì hệ thống hướng tới quy trình người dùng chuẩn bị cấu hình, xem trước rồi mới chủ động triển khai. Backup lịch sử cấu hình cũng cần được phân biệt với rollback tự động; có phiên bản cũ để tham khảo chưa đồng nghĩa hệ thống đã có cơ chế khôi phục tự động hoàn chỉnh.

## 2.2. Giao diện dòng lệnh và giao thức quản trị thiết bị

### 2.2.1. Giao diện dòng lệnh CLI

Cisco IOS và nhiều hệ điều hành mạng thiết kế giao diện dòng lệnh (CLI) theo mô hình phân cấp trạng thái (stateful hierarchy). Một số chế độ cơ bản gồm:

![Các chế độ làm việc cơ bản của CLI trên Cisco IOS](../contents/diagrams/03_cli_modes.svg)
*Các chế độ làm việc cơ bản của CLI trên Cisco IOS*

Một câu lệnh chỉ có giá trị thực thi trong một ngữ cảnh (context) nhất định. Chẳng hạn, lệnh `ip address` chỉ hợp lệ tại chế độ cấu hình giao diện (Interface Configuration mode), trong khi lệnh `show ip route` chỉ được chấp nhận tại chế độ EXEC. Do đó, một hệ thống tự động hóa không chỉ đơn thuần gửi chuỗi lệnh mà còn phải duy trì khả năng nhận diện và chuyển đổi linh hoạt giữa các trạng thái để đảm bảo tính hợp lệ của tác vụ.

Đặc thù của phương thức giao tiếp CLI là dữ liệu trả về luôn ở định dạng văn bản thô (raw text). Để thực hiện các tác vụ như thu thập cấu hình đang chạy (running-config) hay truy xuất bảng định tuyến, hệ thống cần tích hợp các bộ phân tích cú pháp (Parser). Thành phần này đóng vai trò trích xuất thông tin từ luồng văn bản của thiết bị và chuyển đổi thành các đối tượng dữ liệu có cấu trúc, từ đó cho phép phân hệ xử lý logic lõi (Core Logic) tiếp nhận và thao tác.

Giao tiếp qua CLI mang lại ưu điểm lớn về khả năng tương thích đa dạng với các nền tảng thiết bị vật lý lẫn môi trường mô phỏng. Dẫu vậy, bản chất duy trì trạng thái (stateful) của CLI đặt ra thách thức lớn về bài toán quản lý phiên làm việc (Session Management). Nếu hệ thống cho phép nhiều tiến trình (worker) gửi lệnh đồng thời qua cùng một kênh kết nối mà thiếu cơ chế khóa đồng bộ (Synchronization Lock), hiện tượng xung đột và đan xen dữ liệu (Race Condition) sẽ xảy ra, dẫn đến sai lệch nghiêm trọng trong quá trình vận hành tự động.

### 2.2.2. SSH và Telnet

Secure Shell (SSH) là giao thức truy cập từ xa có cơ chế bảo vệ kết nối. Kiến trúc SSH được mô tả trong RFC 4251 [RFC 4251]. Trong quản trị mạng, SSH thường được sử dụng để xác thực người dùng, tạo kênh CLI và trao đổi dữ liệu giữa phần mềm quản trị với router hoặc switch.

![Kết nối từ CAMS tới thiết bị qua SSH](../contents/diagrams/04_ssh_connection.svg)
*Kết nối từ CAMS tới thiết bị qua SSH*

SSH được ưu tiên vì thông tin xác thực và nội dung phiên được bảo vệ tốt hơn so với Telnet. Trong Python, các thư viện như Paramiko và Netmiko hỗ trợ xử lý nhiều chi tiết liên quan đến kết nối, xác thực, prompt và gửi lệnh.

Telnet cũng cung cấp khả năng truy cập terminal từ xa nhưng không có cơ chế bảo vệ nội dung phiên tương đương SSH. Vì vậy, Telnet không nên là lựa chọn mặc định trong mạng thực tế. Tuy nhiên, nó vẫn có giá trị trong một số môi trường lab, thiết bị cũ hoặc mô hình mô phỏng.

| Tiêu chí | SSH | Telnet |
| :--- | :--- | :--- |
| Bảo vệ nội dung phiên | Có (Mã hóa toàn bộ phiên) | Không (Bản rõ plain-text) |
| Cổng TCP mặc định | 22 | 23 |
| Khuyến nghị trong mạng thực tế | Ưu tiên bắt buộc | Hạn chế tối đa |
| Sử dụng trong môi trường lab | Có (Ưu tiên) | Có (Dự phòng cho thiết bị cũ) |

*Bảng: So sánh các đặc tính giữa giao thức SSH và Telnet*

### 2.2.3. Vòng đời phiên quản trị

Một phiên quản trị thường trải qua các bước kết nối, xác thực, mở CLI channel, thực thi lệnh, đọc kết quả và đóng hoặc tái sử dụng phiên.

![Vòng đời một phiên quản trị thiết bị](../contents/diagrams/05_session_lifecycle.svg)
*Vòng đời một phiên quản trị thiết bị*

Mở một kết nối mới cho từng câu lệnh làm tăng số lần xác thực và độ trễ. Ngược lại, tái sử dụng session giúp giảm chi phí nhưng yêu cầu phần mềm biết session nào thuộc host nào, còn hợp lệ hay không và có worker nào đang sử dụng. Đây là cơ sở cho thiết kế Session Registry và khóa CLI theo host trong Chương 3.

## 2.3. Nghiệp vụ mạng thuộc phạm vi đề tài

### 2.3.1. Interface và địa chỉ IPv4

Interface là điểm kết nối vật lý hoặc logic của thiết bị với mạng. Đối với router, một interface Layer 3 thường có các thuộc tính như tên, địa chỉ IPv4, subnet mask, trạng thái administrative và description.

```text
interface GigabitEthernet0/0
description LAN
ip address 192.168.1.1 255.255.255.0
no shutdown
```

Địa chỉ IPv4 và subnet mask phải được kiểm tra trước khi tạo lệnh. Ngoài interface vật lý, hệ điều hành mạng còn hỗ trợ các interface ảo như Loopback, Tunnel, Subinterface và SVI. Sự khác biệt này có ý nghĩa đối với phần mềm quản lý: interface vật lý gắn với phần cứng và không thể tùy ý tạo hoặc xóa, trong khi Loopback hoặc Tunnel có thể được sinh ra bằng cấu hình.

### 2.3.2. DHCP

Dynamic Host Configuration Protocol (DHCP) cho phép client nhận tự động các tham số mạng. DHCP được mô tả trong RFC 2131 [RFC 2131]. Quá trình cấp phát thường được tóm tắt bằng chuỗi DORA:

![Chuỗi trao đổi DORA giữa client và DHCP server](../contents/diagrams/dhcp_dora.png)
*Chuỗi trao đổi DORA giữa client và DHCP server*

Một DHCP pool có thể gồm network, default gateway, DNS server và lease. Một số địa chỉ được loại khỏi vùng cấp phát bằng excluded address. Khi DHCP client và server khác broadcast domain, router có thể sử dụng cơ chế relay như `ip helper-address` để chuyển yêu cầu tới DHCP server.

Từ góc nhìn phần mềm, DHCP là dữ liệu có quan hệ: một thiết bị có thể có nhiều pool, mỗi pool có nhiều tùy chọn và các helper address liên quan tới interface. Do đó, backend cần lưu cấu trúc rõ ràng thay vì chỉ lưu một chuỗi lệnh tổng hợp.

### 2.3.3. Định tuyến tĩnh

Router sử dụng routing table để lựa chọn đường đi tới mạng đích. Static route được cấu hình thủ công bằng mạng đích và next-hop hoặc exit interface.

```text
ip route 10.10.0.0 255.255.0.0 192.168.1.2
```

Default route được dùng khi không có route cụ thể hơn:

```text
ip route 0.0.0.0 0.0.0.0 192.168.1.1
```

Định tuyến tĩnh đơn giản và dễ kiểm soát nhưng không tự thích nghi khi topology thay đổi. Trong hệ thống quản lý cấu hình, static route phù hợp với mô hình desired state: người dùng nhập destination và next-hop dưới dạng dữ liệu, backend kiểm tra, sinh lệnh, preview và push.

### 2.3.4. OSPF

Open Shortest Path First (OSPF) là giao thức định tuyến động thuộc nhóm link-state. OSPFv2 cho IPv4 được mô tả trong RFC 2328 [RFC 2328]. Các khái niệm quan trọng trong phạm vi đề tài gồm process, router ID, area, network, interface participation, passive-interface và cost.

![Ba router cùng thuộc Area 0 trong OSPF](../contents/diagrams/07_ospf_area.png)
*Ba router cùng thuộc Area 0 trong OSPF*

So với static route, dữ liệu OSPF có quan hệ phức tạp hơn. Một process có thể có nhiều network, area và thiết lập interface. Vì vậy, phần mềm cần mô hình hóa quan hệ parent-child và sinh câu lệnh theo thứ tự phù hợp.

### 2.3.5. EIGRP

Enhanced Interior Gateway Routing Protocol (EIGRP) được mô tả trong RFC 7868 [RFC 7868]. Trong cấu hình cơ bản, các thành phần thường gặp gồm autonomous system, network statement, passive interface và một số tham số liên quan tới metric hoặc neighbor.

```text
router eigrp 100
network 10.0.0.0
passive-interface GigabitEthernet0/1
```

Đối với phần mềm, EIGRP cũng có mô hình process chứa nhiều network và thiết lập interface. Điều quan trọng là duy trì sự nhất quán giữa dữ liệu được lưu, cấu hình preview và trạng thái thật sau khi push.

### 2.3.6. Access Control List

Access Control List (ACL) là tập hợp các luật cho phép hoặc từ chối lưu lượng theo các điều kiện xác định. Rule thường được xét theo thứ tự từ trên xuống, do đó *sequence* có ý nghĩa nghiệp vụ.

![Gói tin được đối chiếu tuần tự qua các rule trong ACL](../contents/diagrams/08_acl_packet_flow.jpg)
*Gói tin được đối chiếu tuần tự qua các rule trong ACL*

Standard ACL chủ yếu phân loại lưu lượng dựa trên địa chỉ IPv4 nguồn; trong khi Extended ACL cung cấp khả năng kiểm soát chi tiết hơn dựa trên giao thức, địa chỉ nguồn/đích và cổng dịch vụ (Port). Để đáp ứng các kịch bản an ninh mạng nâng cao, Cisco IOS còn hỗ trợ:
- *Dynamic ACL (Lock-and-Key):* Cho phép mở cổng truy cập tạm thời cho người dùng sau khi họ vượt qua bước xác thực qua Telnet/SSH.
- *Reflexive ACL:* Cung cấp khả năng lọc gói tin theo phiên (session-filtering), tự động cho phép lưu lượng phản hồi từ bên ngoài vào mạng nội bộ dựa trên các kết nối được khởi tạo từ bên trong.
- *MAC ACL:* Hoạt động tại Lớp 2 (Data Link Layer), kiểm soát lưu lượng dựa trên địa chỉ MAC thay vì địa chỉ IP.

Dưới góc độ thiết kế cơ sở dữ liệu, cấu trúc của ACL được ánh xạ theo mối quan hệ một-nhiều (One-to-Many relationship): một danh sách định danh ACL sẽ quản lý nhiều quy tắc (rule) chi tiết bên trong. Đặc biệt, do thứ tự ưu tiên của các quy tắc (sequence) mang tính quyết định đến kết quả đối chiếu và lọc gói tin, hệ thống bắt buộc phải lưu trữ chính xác tham số sequence này. Điều này nhằm đảm bảo tính toàn vẹn của dữ liệu từ khi thiết lập trên giao diện cho đến khi được biên dịch thành tập lệnh CLI đẩy xuống thiết bị.

### 2.3.7. NAT và PAT

Network Address Translation (NAT) chuyển đổi địa chỉ IP giữa các không gian địa chỉ. Traditional NAT được mô tả trong RFC 3022 [RFC 3022]. Các hình thức cơ bản gồm Static NAT, Dynamic NAT và Port Address Translation (PAT).

Static NAT ánh xạ cố định giữa địa chỉ inside local và inside global. Dynamic NAT lựa chọn địa chỉ từ một pool. PAT cho phép nhiều host nội bộ chia sẻ một địa chỉ global bằng cách phân biệt port:

![Nhiều host nội bộ chia sẻ một địa chỉ global qua PAT](../contents/diagrams/09_nat_pat.svg)
*Nhiều host nội bộ chia sẻ một địa chỉ global qua PAT*

Cấu hình NAT còn liên quan tới vai trò inside/outside của interface, ACL và route-map. Do đó backend không chỉ kiểm tra từng trường riêng lẻ mà còn phải kiểm tra các tham chiếu giữa nhiều đối tượng trước khi sinh cấu hình.

### 2.3.8. First Hop Redundancy Protocol (FHRP)

First Hop Redundancy Protocol (FHRP) là nhóm cơ chế cung cấp dự phòng default gateway (cổng mặc định) cho các thiết bị đầu cuối. Các giao thức dự phòng thường gặp trong hệ thống Cisco gồm HSRP, VRRP và GLBP. Thông qua FHRP, nhiều router có thể phối hợp hoạt động để cung cấp một địa chỉ virtual gateway chung, nhờ đó các host trong mạng LAN không bị mất kết nối khi có một thiết bị định tuyến vật lý gặp sự cố.

![Hai router cùng cung cấp một virtual gateway theo FHRP](../contents/diagrams/10_fhrp_gateway.svg)
*Hai router cùng cung cấp một virtual gateway theo FHRP*

### 2.3.9. Chuyển mạch Lớp 2 (Layer 2 Switching)

Trong kiến trúc chuyển mạch, VLAN (Virtual Local Area Network) được sử dụng để phân chia hạ tầng mạng vật lý thành các miền broadcast logic độc lập. Cổng truy cập (Access port) thường được gán vào một VLAN duy nhất phục vụ thiết bị đầu cuối, trong khi đường truyền trung kế (Trunk port) có khả năng mang lưu lượng của nhiều VLAN thông qua cơ chế gắn thẻ (tagging) chuẩn 802.1Q. 

![Mô hình phân chia miền Broadcast bằng VLAN](../contents/diagrams/vlan.png)
*Mô hình phân chia miền Broadcast bằng VLAN*

Đối với các thiết bị chuyển mạch đa tầng (Multilayer Switch), tính năng SVI (Switch Virtual Interface) được sử dụng để cung cấp giao diện định tuyến Lớp 3 liên kết giữa các VLAN. Để tối ưu băng thông và cung cấp khả năng dự phòng đường truyền giữa các switch, kỹ thuật EtherChannel (sử dụng giao thức LACP hoặc PAgP) cho phép gom nhóm nhiều cổng vật lý thành một cổng logic duy nhất.

![Liên kết EtherChannel gom nhóm nhiều cổng vật lý](../contents/diagrams/Etherchannel.jpg)
*Liên kết EtherChannel gom nhóm nhiều cổng vật lý*

Bên cạnh đó, để quản trị hạ tầng chuyển mạch quy mô lớn, Spanning Tree Protocol (STP) được triển khai nhằm ngăn chặn triệt để hiện tượng vòng lặp (loop) ở Lớp 2 bằng cách khóa các đường truyền dự phòng chưa cần thiết.

![Nguyên lý hoạt động của Spanning Tree Protocol (STP)](../contents/diagrams/STP.jpg)
*Nguyên lý hoạt động của Spanning Tree Protocol (STP)*

Đồng thời, VLAN Trunking Protocol (VTP) cho phép đồng bộ hóa thông tin cơ sở dữ liệu VLAN xuyên suốt một miền quản trị (`VTP Domain`) từ một thiết bị đóng vai trò VTP Server trung tâm, giúp giảm thiểu rủi ro sai sót do cấu hình thủ công phân tán trên từng switch.

![Cơ chế đồng bộ cơ sở dữ liệu VLAN qua VTP Domain](../contents/diagrams/VTP.jpg)
*Cơ chế đồng bộ cơ sở dữ liệu VLAN qua VTP Domain*

### 2.3.10. Bảo mật Lớp 2 (Layer 2 Security)

Hạ tầng chuyển mạch thường đối mặt với các rủi ro tấn công nội bộ nguy hiểm như giả mạo máy chủ cấp phát IP (`DHCP Spoofing`) hay đầu độc bộ nhớ cache ARP (`ARP Poisoning`). Để bảo vệ tính toàn vẹn của luồng dữ liệu, hệ thống quản trị cần tích hợp cấu hình các cơ chế phòng vệ chuyên sâu:

- *DHCP Snooping:* Hoạt động như một bức tường lửa kiểm soát luồng cấp phát IP tại tầng truy cập. Hệ thống phân loại cổng mạng thành "Tin cậy" (`Trusted` - kết nối với DHCP Server hợp pháp) và "Không tin cậy" (`Untrusted`), đồng thời tự động xây dựng bảng ràng buộc (`Binding Database`) ánh xạ chính xác giữa địa chỉ IP, địa chỉ MAC và cổng vật lý để loại bỏ các gói tin phản hồi từ DHCP Server giả mạo.

![Cơ chế kiểm soát luồng cấp phát IP của DHCP Snooping](../contents/diagrams/dhcp-snooping.jpg)
*Cơ chế kiểm soát luồng cấp phát IP của DHCP Snooping*

- *Dynamic ARP Inspection (DAI):* Kế thừa trực tiếp dữ liệu từ bảng ràng buộc của DHCP Snooping để đối chiếu tính hợp lệ của mọi gói tin ARP lưu chuyển qua switch. Bất kỳ gói tin ARP nào có sự sai lệch thông tin giữa IP và MAC đều bị hệ thống tự động hủy bỏ, qua đó ngăn chặn triệt để các kỹ thuật tấn công trung gian (Man-in-the-Middle) dựa trên ARP Spoofing.

## 2.4. Cơ sở dữ liệu và SQLite

### 2.4.1. Vai trò của cơ sở dữ liệu

Một hệ thống quản lý cấu hình cần lưu dữ liệu lâu hơn vòng đời của một phiên SSH. Các nhóm dữ liệu tiêu biểu gồm inventory, interface, routing, DHCP, ACL, NAT, FHRP, switching, desired state, trạng thái đồng bộ, dữ liệu thu thập và lịch sử cấu hình.

Mô hình dữ liệu quan hệ tổ chức thông tin thành bảng. Primary key định danh record, foreign key biểu diễn quan hệ giữa các bảng. Ví dụ:

![Quan hệ một-nhiều giữa Device và các bảng nghiệp vụ](../contents/diagrams/11_db_schema.svg)
*Quan hệ một-nhiều giữa Device và các bảng nghiệp vụ*

Quan hệ một-nhiều phù hợp với thực tế một thiết bị có nhiều interface hoặc nhiều cấu hình nghiệp vụ. Việc chuẩn hóa giúp giảm lặp dữ liệu và hạn chế bất nhất.

### 2.4.2. SQLite

SQLite là hệ quản trị cơ sở dữ liệu quan hệ nhúng. Dữ liệu thường được lưu trong file và ứng dụng truy cập trực tiếp thông qua thư viện, không cần triển khai database server riêng. Đặc điểm này phù hợp với ứng dụng desktop local-first như CAMS.

SQLite hỗ trợ SQL, transaction, index, constraint và foreign key. Tuy nhiên, khả năng ghi đồng thời khác với các hệ quản trị cơ sở dữ liệu server chuyên dụng. Khi nhiều worker cập nhật gần như cùng lúc, backend cần giữ transaction ngắn và hạn chế giữ write lock không cần thiết.

### 2.4.3. Transaction và tính toàn vẹn

Transaction nhóm nhiều thao tác thành một đơn vị logic. Các tính chất ACID gồm Atomicity, Consistency, Isolation và Durability. Trong bài toán cấu hình mạng, một thao tác có thể đồng thời cập nhật object nghiệp vụ và trạng thái đồng bộ. Nếu lỗi xảy ra giữa quá trình, transaction giúp tránh trạng thái chỉ được lưu một phần.

Constraint như `NOT NULL`, `UNIQUE`, `CHECK` và foreign key hỗ trợ bảo vệ dữ liệu ở tầng persistence. Tuy vậy, constraint không thay thế validation nghiệp vụ. Một chuỗi có thể đúng kiểu dữ liệu nhưng vẫn không phải địa chỉ IP hoặc prefix phù hợp. Vì vậy, hệ thống cần kết hợp kiểm tra ở service và ràng buộc ở database.

## 2.5. Python, Qt Quick và PyQt6

### 2.5.1. Python trong tự động hóa mạng

Python có hệ sinh thái thư viện mạnh cho SSH, template, database và automation. Trong CAMS, Python có thể đảm nhiệm xử lý nghiệp vụ, truy cập SQLite, sinh cấu hình, điều phối worker và cung cấp object cho giao diện Qt.

Việc sử dụng Python không tự động tạo ra kiến trúc tốt. Nếu UI trực tiếp truy cập SQL hoặc gửi SSH, code vẫn khó bảo trì. Vì vậy, Python cần được tổ chức theo các lớp có trách nhiệm rõ ràng như service, repository, worker và infrastructure.

### 2.5.2. Qt Quick và QML

Qt là framework đa nền tảng; Qt Quick cung cấp mô hình xây dựng giao diện khai báo bằng QML. Thay vì tạo giao diện hoàn toàn bằng lệnh thủ tục, QML mô tả component, property, binding, signal và trạng thái.

![Cây component chính trong giao diện Qt Quick](../contents/diagrams/13_qtquick_tree.svg)
*Cây component chính trong giao diện Qt Quick*

Component hóa giúp tái sử dụng button, dialog, panel và form control. Property binding giúp UI tự phản ánh giá trị mới, trong khi signal được dùng để thông báo sự kiện giữa các component.

### 2.5.3. PyQt6 và cơ chế signal/slot

PyQt6 cho phép Python sử dụng Qt 6. `QObject` đóng vai trò cầu nối giữa backend và QML.

![QObject làm cầu nối giữa QML và tầng Service/Backend](../contents/diagrams/14_qml_signal_slot.svg)
*QObject làm cầu nối giữa QML và tầng Service/Backend*

Ở chiều ngược lại, backend có thể phát signal hoặc thay đổi property để giao diện cập nhật. `pyqtSlot`, `pyqtSignal` và property vì vậy tạo thành contract giữa QML và Python.

Contract này cần được duy trì nhất quán. Nếu QML gọi một slot đã bị đổi tên hoặc thay đổi tham số, lỗi có thể xuất hiện trong runtime. Do đó, QML smoke test và contract test có giá trị khi ứng dụng được refactor.

## 2.6. Các thư viện phục vụ tự động hóa

### 2.6.1. Netmiko và Paramiko

Paramiko cung cấp implementation SSH cho Python. Netmiko xây dựng lớp hỗ trợ ở mức thiết bị mạng cao hơn, giúp xử lý prompt, device type, show command và configuration mode.

![Netmiko và Paramiko trong chuỗi kết nối tới Cisco IOS](../contents/diagrams/12_netmiko_stack.svg)
*Netmiko và Paramiko trong chuỗi kết nối tới Cisco IOS*

Trong kiến trúc phần mềm, các thư viện này nên được đặt sau một connector hoặc adapter. Service nghiệp vụ chỉ yêu cầu thực thi tác vụ, còn infrastructure chịu trách nhiệm kết nối, gửi lệnh và trả kết quả. Cách tách này cũng cho phép thay connector thật bằng fake connector trong kiểm thử.

### 2.6.2. Jinja2

Jinja2 là template engine có thể sử dụng để tách dữ liệu cấu hình khỏi cú pháp CLI. Ví dụ:

```jinja2
interface {{ interface }}
ip address {{ address }} {{ mask }}
no shutdown
```

Với dữ liệu `GigabitEthernet0/0`, `192.168.1.1` và `255.255.255.0`, template tạo ra tập lệnh IOS tương ứng. Ưu điểm của cách này là syntax được tập trung trong template, trong khi validation và nghiệp vụ được xử lý ở service.

Template không tự xác nhận dữ liệu hợp lệ. Vì vậy pipeline đúng phải kiểm tra dữ liệu trước khi render, sau đó mới tạo preview và triển khai.

### 2.6.3. Nornir và thực thi nhiều host

Nornir là framework automation Python hỗ trợ khái niệm inventory, host và task. Đối với bài toán nhiều thiết bị, ý tưởng quan trọng là cho phép thực hiện các tác vụ độc lập song song nhưng giới hạn số worker đang chạy.

Một batch executor cần giữ kết quả riêng theo host, không để lỗi của một host làm mất toàn bộ batch và giới hạn concurrency để tránh tạo quá nhiều kết nối cùng lúc. Đây là nền tảng của cơ chế xử lý đa thiết bị được trình bày trong Chương 3.

### 2.6.4. Dulwich

Dulwich là implementation Git bằng Python và có thể sử dụng để lưu lịch sử running-config dưới dạng các phiên bản text. Lịch sử cấu hình giúp theo dõi thay đổi theo thời gian và hỗ trợ so sánh. Tuy nhiên, version history cần được phân biệt với rollback tự động.

## 2.7. Xử lý đồng thời và tác vụ nền

### 2.7.1. Tách tác vụ mạng khỏi UI thread

Tác vụ SSH có thể mất nhiều thời gian hơn thao tác giao diện thông thường. Nếu kết nối và gửi lệnh được thực hiện trực tiếp trên UI thread, event loop không thể xử lý repaint và tương tác trong thời gian chờ, khiến cửa sổ có biểu hiện không phản hồi.

Giải pháp là đưa tác vụ dài sang worker hoặc executor:

![UI thread giao việc dài cho các worker riêng biệt](../contents/diagrams/15_ui_thread_workers.svg)
*UI thread giao việc dài cho các worker riêng biệt*

UI chỉ khởi tạo yêu cầu và nhận kết quả thông qua signal hoặc cơ chế đồng bộ phù hợp. Cách này giúp giao diện duy trì khả năng phản hồi.

### 2.7.2. Parallel giữa host và tuần tự trên cùng host

Các thiết bị độc lập có thể được xử lý song song. Tuy nhiên, nhiều worker không nên đồng thời ghi vào một CLI session của cùng host.

![Nhiều worker cùng tranh chấp một CLI session của một host](../contents/diagrams/16_host_lock.svg)
*Nhiều worker cùng tranh chấp một CLI session của một host*

Nếu lệnh xen kẽ, trạng thái CLI có thể bị thay đổi ngoài dự kiến và output có thể bị đọc nhầm. Cơ chế lock theo host bảo đảm chỉ một chuỗi thao tác được sử dụng CLI channel tại một thời điểm, trong khi các host khác vẫn có thể chạy song song.

![Serialize trên cùng host, parallel giữa các host](../contents/diagrams/17_serialize_parallel.svg)
*Serialize trên cùng host, parallel giữa các host*

Nguyên tắc có thể tóm tắt là *serialize trên cùng host, parallel giữa các host*. Bên cạnh đó, batch executor cần cô lập lỗi, duy trì trạng thái riêng cho từng thiết bị và có cơ chế xử lý yêu cầu hủy ở điểm an toàn.

## 2.8. Syslog, SFTP và các chức năng hỗ trợ

Syslog là cơ chế phổ biến để thiết bị gửi thông điệp sự kiện tới hệ thống thu thập log. Một pipeline cơ bản gồm thiết bị gửi message, receiver tiếp nhận, parser chuẩn hóa, writer lưu dữ liệu và giao diện thực hiện truy vấn. Với lượng log lớn, ghi theo batch giúp giảm số transaction và hạn chế contention trên SQLite.

![Pipeline thu thập log Syslog cơ bản](../contents/diagrams/18_syslog_pipeline.svg)
*Pipeline thu thập log Syslog cơ bản*

SFTP cung cấp khả năng truyền file trên kênh bảo mật dựa trên SSH. Trong ứng dụng desktop, thao tác truyền file có thể kéo dài nên cần được thực hiện dưới dạng tác vụ nền và báo tiến độ về giao diện.

Hai chức năng này mở rộng CAMS từ công cụ cấu hình sang hướng quản lý tập trung hơn. Tuy nhiên, chúng đóng vai trò hỗ trợ cho các nghiệp vụ cấu hình cốt lõi như interface, routing, DHCP, ACL và NAT.

## 2.9. Nguyên tắc kiểm thử phần mềm

### 2.9.1. Unit test và integration test

Unit test kiểm tra các đơn vị logic nhỏ như validation, parser, model hoặc hàm xử lý trạng thái. Mục tiêu là phát hiện lỗi sớm mà không cần mở toàn bộ ứng dụng hoặc kết nối router thật.

Integration test kiểm tra nhiều thành phần làm việc cùng nhau, ví dụ:

![Integration test qua Repository với SQLite tạm](../contents/diagrams/19_testing_flow_a.svg)
*Integration test qua Repository với SQLite tạm*

hoặc:

![Integration test qua Worker với Fake Connector](../contents/diagrams/20_testing_flow_b.svg)
*Integration test qua Worker với Fake Connector*

Database tạm cho phép kiểm tra schema, transaction và foreign key mà không ảnh hưởng dữ liệu thật. Fake connector giúp kiểm tra logic worker mà không phụ thuộc vào tính sẵn sàng của thiết bị.

### 2.9.2. Contract test và QML smoke test

Contract test xác minh hai module có cùng kỳ vọng về API. Với QML/Python, contract gồm tên context property, slot, tham số và signal. Contract cũng tồn tại giữa repository và database schema; repository truy vấn một bảng đã đổi tên là lỗi tích hợp dù từng module riêng lẻ vẫn import thành công.

QML smoke test kiểm tra component có thể load mà không gặp các lỗi cơ bản như thiếu import, property không tồn tại, sai context object hoặc syntax error. Smoke test không thay thế kiểm thử trải nghiệm người dùng nhưng rất hữu ích trong quá trình refactor.

### 2.9.3. Dev mode và thử nghiệm lab

Một công cụ automation cần bảo đảm môi trường phát triển không vô tình gửi cấu hình tới thiết bị thật. Dev mode hoặc fake connector cho phép mô phỏng một số luồng mà không mở kết nối thật. Safety test cần xác nhận rằng thiết bị được đánh dấu dev không tạo session SSH/Telnet ngoài ý muốn.

Sau kiểm thử logic, hệ thống mạng vẫn cần thử nghiệm end-to-end trên thiết bị hoặc môi trường mô phỏng như EVE-NG/GNS3:

![Quy trình thử nghiệm end-to-end trên môi trường lab](../contents/diagrams/21_lab_test_flow.svg)
*Quy trình thử nghiệm end-to-end trên môi trường lab*

Chương 2 chỉ trình bày nguyên tắc của môi trường kiểm thử. Topology cụ thể, số lần thử, thời gian thực thi, tỷ lệ thành công và các kết quả đo cần được trình bày tại chương thử nghiệm và đánh giá để tránh nhầm lẫn giữa cơ sở lý thuyết và kết quả nghiên cứu.

## 2.10. Mối liên hệ giữa các công nghệ

Các thành phần được trình bày trong chương tạo thành một chuỗi xử lý thống nhất. QML đảm nhiệm presentation; PyQt6 tạo cầu nối tới Python; service thực hiện validation và nghiệp vụ; repository làm việc với SQLite; worker và connector giao tiếp với thiết bị; Jinja2 hỗ trợ sinh cấu hình; executor điều phối tác vụ nền; Netmiko/Paramiko cung cấp kết nối CLI; Dulwich hỗ trợ lưu lịch sử running-config.

![Chuỗi xử lý tổng quan từ người dùng tới thiết bị](../contents/diagrams/22_architecture_overview.svg)
*Chuỗi xử lý tổng quan từ người dùng tới thiết bị*

Hai nguyên tắc quan trọng được rút ra. Thứ nhất, presentation không nên phụ thuộc trực tiếp vào công nghệ kết nối. Người dùng thực hiện thao tác trên QML nhưng QML không cần biết Netmiko được gọi ra sao. Thứ hai, nghiệp vụ cần tách khỏi persistence và network adapter để có thể kiểm thử và mở rộng độc lập. Đây là cơ sở lý thuyết trực tiếp cho kiến trúc `QML → slot/service → repository/worker → infrastructure` được áp dụng trong thiết kế CAMS.

## 2.11. Tổng kết chương

Chương này đã trình bày các cơ sở lý thuyết và công nghệ phục vụ xây dựng CAMS. Các nội dung chính gồm quản lý cấu hình theo trạng thái, CLI, SSH/Telnet, interface, DHCP, định tuyến, ACL, NAT, FHRP, switching, cơ sở dữ liệu SQLite, Python, Qt Quick/QML, PyQt6 và các thư viện tự động hóa. Bên cạnh đó, chương đã làm rõ nhu cầu xử lý tác vụ nền, giới hạn concurrency, khóa theo host và các cấp kiểm thử phần mềm.

Những nội dung trên là cơ sở để Chương 3 chuyển từ "công nghệ có thể sử dụng" sang "hệ thống được phân tích và thiết kế như thế nào", bao gồm yêu cầu chức năng, kiến trúc phân lớp, mô hình dữ liệu, cơ chế View & Push, quản lý session và thực thi đa thiết bị.
