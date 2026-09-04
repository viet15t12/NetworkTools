# ĐỀ CƯƠNG BÁO CÁO NGHIÊN CỨU KHOA HỌC SINH VIÊN

## Xây dựng phần mềm quản lý tập trung và tự động hóa cấu hình thiết bị mạng

> **Tên sản phẩm:** CAMS  
> **Loại đề tài:** Nghiên cứu khoa học sinh viên  
> **Lĩnh vực:** Mạng máy tính, tự động hóa mạng, phần mềm desktop  
> **Phạm vi sản phẩm hiện tại:** Ứng dụng desktop PyQt6/QML, cơ sở dữ liệu SQLite và các worker Python phục vụ thiết bị Cisco IOS

---

## 1. Nguyên tắc sử dụng đề cương

Đề cương này được đối chiếu với mã nguồn trong runtime ở root tại thời điểm cập nhật. Khi viết báo cáo chính thức phải phân biệt ba mức:

- **Đã triển khai:** Có luồng giao diện và backend thực, hoặc có test tự động tương ứng.
- **Đã có nền tảng:** Có giao diện, schema, template hoặc mã thử nghiệm nhưng chưa có luồng end-to-end được xác nhận.
- **Dự kiến phát triển:** Chưa thuộc kết quả hiện tại; chỉ trình bày ở phần hướng phát triển.

Không xem `archive/backend/` và `archive/api_server.py` là runtime chính của ứng dụng desktop. Đây là hệ thống độc lập; chỉ mô tả là đã tích hợp khi có contract và kiểm thử phù hợp.

Số liệu, ảnh giao diện, kết quả EVE-NG/GNS3 và hiệu năng chỉ được đưa vào mục “kết quả” sau khi đo thực tế. Không biến mục tiêu hoặc schema chưa có luồng chạy thành kết quả đã hoàn thành.

---

## 2. Hiện trạng sản phẩm làm cơ sở cho báo cáo

### 2.1. Kiến trúc runtime

```text
QML/Qt Quick UI
       │ signal/slot và context property
       ▼
PyQt6 bridge: DatabaseManager, TerminalHelper, settings, monitor
       │
       ├── SQLite: cấu hình mong muốn, thiết bị, trạng thái đồng bộ
       ├── features/: chuẩn hóa và lưu dữ liệu nghiệp vụ
       └── infrastructure/network/: kết nối, preview và push
                                │
                                ▼
                     Thiết bị Cisco IOS hoặc dev-mode
```

Entry point là `main.py`, nạp QML module `UI`. Runtime chính không phải kiến trúc web client/server.

### 2.2. Ma trận chức năng thực tế

| Nhóm chức năng | Trạng thái | Phạm vi đã có | Giới hạn cần nêu |
|---|---|---|---|
| Khung ứng dụng desktop | Đã triển khai | Cửa sổ nhiều tab thiết bị, sidebar, feature bar, theme, status bar, settings | Chưa đánh giá khả dụng với người dùng thật |
| Quản lý thiết bị | Đã triển khai | Thêm/sửa/xóa, tìm kiếm, nhập JSON/XLSX, dev-mode, tạo thư mục backup | Thông tin đăng nhập còn lưu trong SQLite |
| Kết nối và đồng bộ | Đã triển khai một phần | Ping, SSH/Telnet theo connector, giữ session theo tab, backup running-config, parser interface/OSPF | Chưa chứng minh đầy đủ cho mọi IOS và mọi phương thức quản trị |
| Information/Database Browser | Đã triển khai | Xem backup, thông tin định tuyến, duyệt/chỉnh bảng SQLite, mở công cụ ngoài | Chỉnh DB trực tiếp cần kiểm soát rủi ro |
| Interface Router | Đã có UI và persistence | CRUD L3/WAN/Tunnel/QoS trong SQLite | Chưa có controller View & Push trong runtime chính |
| DHCP | Đã triển khai | Pool, excluded address, helper; preview/push; SSH/RESTCONF và dev-mode trong worker | Cần thử nghiệm lab end-to-end |
| Static Routing | Đã triển khai | Route/default route, preview/push, trạng thái pending | Chưa có static route đa router dựa trên topology |
| OSPF | Đã triển khai nhưng còn lỗi tích hợp schema | UI process/area/network/interface/tuning, lưu DB, preview/push | Hai test hợp đồng routing hiện lỗi do tên bảng interface settings không khớp schema |
| EIGRP | Đã triển khai nhưng còn lỗi tích hợp schema | UI process/network/interface và các tùy chọn, lưu DB, preview/push | Hai test hợp đồng routing hiện lỗi tương tự OSPF |
| ACL | Đã có UI và persistence | Standard, Extended, Dynamic, Reflexive, MAC ACL; rule và binding interface | Chưa có View & Push controller trong runtime ở root |
| NAT/PAT | Đã triển khai | Static, Dynamic, PAT, interface role, NAT ACL, route-map; preview/push | Cần bổ sung test worker/end-to-end trên lab |
| VLAN, STP, switching | Mới có schema/mã di sản | Schema L2 và worker thử nghiệm tồn tại | Feature bar vẫn đánh dấu chưa triển khai |
| BGP | Mới có template | Một số Jinja2 template Cisco/MikroTik | Chưa có UI, bridge và luồng persistence hoàn chỉnh |
| VRF | Mới có schema | Các bảng VRF đã được thiết kế | Chưa có màn hình và backend runtime |
| Topology và static route đa router | Dự kiến phát triển | Có mã khám phá topology trong vùng di sản | Chưa tích hợp vào app, chưa có test |
| SFTP, Syslog, Serial, Firewall | Dự kiến phát triển | Chưa phải chức năng sản phẩm | Chỉ trình bày ở Chương 6 |

### 2.3. Bằng chứng kiểm thử tại thời điểm rà soát

Lệnh kiểm thử:

```powershell
$env:UV_CACHE_DIR = ".uv-cache"
uv run python -m unittest discover -s tests -v
```

Kết quả rà soát hiện tại: 30 test được phát hiện; 28 test chức năng vượt qua, 2 test hợp đồng OSPF/EIGRP thất bại do code truy cập các bảng `t04_ospf_interface_settings` và `t04_eigrp_interface_settings` không tồn tại trong schema hiện hành. Trên Windows còn phát sinh lỗi dọn tệp SQLite sau hai test thất bại. Báo cáo phải ghi đây là hạn chế cần sửa, không công bố bộ test đã đạt 100%.

---

# PHẦN ĐẦU BÁO CÁO

## Trang bìa và trang bìa phụ

- Tên học viện, khoa/bộ môn và hoạt động nghiên cứu khoa học.
- Tên đề tài thống nhất với quyết định giao đề tài.
- Tên sản phẩm: CAMS.
- Giảng viên hướng dẫn, thành viên, mã sinh viên, địa điểm và năm.

## Lời cam đoan

Khẳng định tính trung thực của kết quả; phân biệt mã nhóm tự xây dựng, thư viện nguồn mở và mã tham khảo; trích dẫn đầy đủ.

## Lời cảm ơn

Cảm ơn giảng viên hướng dẫn, khoa, phòng lab và các cá nhân hỗ trợ.

## Tóm tắt và Abstract

Tóm tắt khoảng 250--350 từ, gồm: vấn đề, mục tiêu, phương pháp, kiến trúc, phạm vi chức năng đã làm, kết quả kiểm thử và hạn chế. Abstract là bản tiếng Anh tương đương, không bổ sung tuyên bố mới.

## Danh mục

- Mục lục.
- Danh mục hình.
- Danh mục bảng.
- Danh mục từ viết tắt: ACL, API, CLI, CRUD, DHCP, EIGRP, GUI, NAT, OSPF, PAT, QML, RESTCONF, SSH, VLAN, VRF.

---

# CHƯƠNG 1. TỔNG QUAN ĐỀ TÀI

## 1.1. Bối cảnh và lý do chọn đề tài

Phân tích hạn chế của cấu hình CLI thủ công trong phòng lab: thao tác lặp lại, khó theo dõi cấu hình mong muốn, dễ sai cú pháp và thiếu một nơi quản lý tập trung.

## 1.2. Bài toán nghiên cứu

Xây dựng ứng dụng desktop hỗ trợ quy trình:

> Quản lý thiết bị → kết nối/thu thập → lưu trạng thái → tạo cấu hình mong muốn → preview → push → cập nhật kết quả.

## 1.3. Mục tiêu

### Mục tiêu tổng quát

Xây dựng nền tảng phần mềm desktop phục vụ quản lý và tự động hóa một số tác vụ cấu hình router Cisco IOS trong môi trường học tập/thực nghiệm.

### Mục tiêu cụ thể

- Xây dựng UI QML và bridge PyQt6.
- Quản lý thiết bị và dữ liệu cấu hình bằng SQLite.
- Hỗ trợ kết nối, backup và đồng bộ một phần trạng thái thiết bị.
- Hoàn thiện luồng View & Push cho DHCP, Routing và NAT.
- Xây dựng persistence cho Interface và ACL làm nền tảng hoàn thiện push.
- Kiểm thử logic dữ liệu, UI contract, QML smoke và dev-mode.

## 1.4. Đối tượng và phạm vi

- Đối tượng: router Cisco IOS trong lab; cấu hình interface, DHCP, routing, ACL và NAT.
- Nền tảng: Python 3.11+, PyQt6/QML, SQLite, Jinja2, Netmiko/Nornir; ưu tiên Windows và hướng đến Linux.
- Ngoài phạm vi kết quả hiện tại: quản lý doanh nghiệp quy mô lớn, HA, RBAC hoàn chỉnh, mã hóa secret, switching end-to-end, firewall, syslog và topology automation.

## 1.5. Phương pháp nghiên cứu

Khảo sát nghiệp vụ; phân tích mã/lệnh IOS; thiết kế kiến trúc và schema; cài đặt theo module; kiểm thử tự động; thử nghiệm lab; so sánh với thao tác thủ công.

## 1.6. Đóng góp và cấu trúc báo cáo

Nêu đóng góp ở mức nền tảng tích hợp UI--DB--worker, cơ chế pending/success/dev-mode và thiết kế mở rộng; giới thiệu sáu chương.

---

# CHƯƠNG 2. CƠ SỞ LÝ THUYẾT VÀ CÔNG NGHỆ

## 2.1. Quản lý cấu hình và tự động hóa mạng

Phân biệt current state, desired state, cấu hình pending, preview, apply và verify. Không tuyên bố hệ thống đã hỗ trợ rollback nếu chưa có mã và test.

## 2.2. Giao thức truy cập và quản trị

- SSH/Telnet trong connector hiện tại.
- RESTCONF/NETCONF ở mức nền tảng thư viện và một số worker.
- Rủi ro của Telnet và nguyên tắc ưu tiên SSH.

## 2.3. Nghiệp vụ mạng thuộc phạm vi

- Interface L3/WAN/Tunnel và QoS cơ bản.
- DHCP pool, excluded address, helper.
- Static route, OSPF, EIGRP.
- ACL và binding interface.
- Static NAT, Dynamic NAT, PAT, NAT ACL và route-map.

Chỉ giới thiệu VLAN, BGP, VRF như cơ sở cho hướng mở rộng nếu chưa có luồng sản phẩm.

## 2.4. Nền tảng phần mềm

- Python và mô hình module.
- Qt Quick/QML, PyQt6 signal/slot, context property.
- SQLite, khóa ngoại, quan hệ parent--child và soft delete.
- Jinja2 template.
- Netmiko, Nornir, ncclient và Requests theo đúng nơi sử dụng trong code.

## 2.5. Nguyên tắc kiểm thử

Unit/contract test, QML smoke test, dev-mode safety test và thử nghiệm tích hợp trên lab.

---

# CHƯƠNG 3. PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG

## 3.1. Tác nhân và ca sử dụng

Tác nhân chính là người quản trị/phụ trách lab. Ca sử dụng: quản lý thiết bị, ping/kết nối, đồng bộ, chỉnh cấu hình, preview/push, xem backup, duyệt DB và tùy chỉnh ứng dụng.

## 3.2. Yêu cầu chức năng

Tách yêu cầu bắt buộc hiện tại khỏi yêu cầu mở rộng. Mỗi yêu cầu có mã FR-xx và ánh xạ đến module/minh chứng.

## 3.3. Yêu cầu phi chức năng

- UI nhất quán, không chặn luồng chính khi chạy tác vụ nền.
- Không mở session thật cho host dev-mode.
- Hạn chế lỗi dữ liệu bằng validation và khóa ngoại.
- Tách UI, bridge, nghiệp vụ, worker và template.
- Ghi nhận giới hạn bảo mật secret hiện tại.

## 3.4. Kiến trúc phân lớp

Trình bày bốn lớp: QML UI; PyQt6 bridge/core; backend và SQLite; network worker/connector. Làm rõ `DatabaseManager` là facade được đưa vào QML.

## 3.5. Luồng dữ liệu cốt lõi

### Quản lý và đồng bộ thiết bị

Thêm thiết bị → mở tab → ping/kết nối → lưu running-config → parse interface/OSPF → cập nhật SQLite.

### Lưu cấu hình mong muốn

Form QML → validation → slot → backend persistence → `success=0` hoặc `success=-1` → hiển thị trạng thái pending.

### View & Push

Controller thu thập bản ghi pending → Jinja2 render → preview → worker dùng session → nhận kết quả → cập nhật hoặc xóa bản ghi thành công.

## 3.6. Thiết kế dữ liệu

Nhóm bảng:

- `t01_*`: thiết bị và cấu hình YANG.
- `t02_*`: interface router.
- `t03_*`: DHCP.
- `t04_*`: static route, OSPF, EIGRP.
- `t05_*`: ACL, NAT, route-map.
- `t06_*`, `t07_*`: schema dự phòng cho L2/VRF, chưa phải chức năng hoàn chỉnh.

Giải thích `success`: `0` pending add/update, `1` đã áp dụng, `-1` pending remove/soft delete; giải thích `action_Cfg` nơi còn được worker sử dụng.

## 3.7. Thiết kế giao diện

Trình bày shell, device sidebar, feature bar, lazy Loader, các họ giao diện form/list, process card và View & Push dialog.

## 3.8. Thiết kế an toàn và xử lý lỗi

Dev-mode fail-closed, timeout, validation, không log password, session registry, tác vụ nền. Nêu rõ mã hóa secret và rollback còn là yêu cầu tương lai.

---

# CHƯƠNG 4. XÂY DỰNG PHẦN MỀM

## 4.1. Môi trường và tổ chức mã nguồn

Ghi phiên bản thực tế khi chốt báo cáo. Cây thư mục trọng tâm: `UI`, `core`, `features`, `infrastructure/network`, `infrastructure/database`, `tests`.

## 4.2. Khởi tạo ứng dụng và QML bridge

Mô tả `main.py`, các context property, QML module `UI`, settings và network monitor.

## 4.3. Quản lý thiết bị, kết nối và đồng bộ

Trình bày CRUD/import, tab/session, backup running-config, parsing interface/OSPF và database browser.

## 4.4. Interface

Trình bày UI và persistence cho L3/WAN/Tunnel/QoS. Kết luận mục này phải ghi “chưa có View & Push trong runtime chính”.

## 4.5. DHCP

Trình bày Pool, Excluded, Helper; staged save; pending state; preview/push và cập nhật DB.

## 4.6. Routing

- Static/default route.
- OSPF process, area, network, interface, redistribute, tuning.
- EIGRP process, network, interface và các chính sách liên quan.
- Cơ chế template/worker.
- Lỗi schema đang được phát hiện bởi test hợp đồng.

Không đặt BGP hoặc multi-router topology vào kết quả hiện tại.

## 4.7. ACL

Trình bày UI/persistence các loại ACL, rule có thứ tự và binding nhiều interface. Ghi rõ chưa có controller sinh lệnh/push trong runtime ở root.

## 4.8. NAT/PAT

Trình bày sáu nhóm UI, backend persistence, collector, template, preview/push và cập nhật trạng thái.

## 4.9. Tiện ích hệ thống

Theme, status bar, external tools, terminal, database browser, notification và tác vụ nền.

## 4.10. Các thành phần chưa tích hợp

Các capability chưa qua integration test, BGP template, topology worker, FastAPI và các module độc lập trong `archive/backend/`. Mục đích là minh bạch kỹ thuật, không tính là kết quả desktop đã hoàn thành.

---

# CHƯƠNG 5. THỬ NGHIỆM VÀ ĐÁNH GIÁ

## 5.1. Mục tiêu và môi trường

Ghi cấu hình máy, hệ điều hành, phiên bản Python/Qt, commit, image Cisco IOS, EVE-NG/GNS3 và topology.

## 5.2. Kiểm thử tự động

Nhóm test:

- Persistence: DHCP, ACL, NAT.
- Routing database contract.
- Dev-mode và worker safety.
- UI contract.
- QML smoke/load.

Bảng kết quả phải có số test chạy/đạt/lỗi và nguyên nhân. Trạng thái hiện tại là 28/30 test chức năng đạt; cần chạy lại sau khi sửa schema và cập nhật số cuối cùng.

## 5.3. Kịch bản lab tối thiểu

| Mã | Kịch bản | Kết quả cần xác minh |
|---|---|---|
| LAB-01 | Thêm thiết bị, ping, connect/sync | Có backup và dữ liệu interface/OSPF |
| LAB-02 | DHCP pool/excluded/helper | Client nhận địa chỉ; DB chuyển pending → applied |
| LAB-03 | Static route | Route xuất hiện trong `show ip route` và ping thành công |
| LAB-04 | OSPF | Neighbor/full, route học đúng, DB đồng bộ |
| LAB-05 | EIGRP | Neighbor và route học đúng |
| LAB-06 | NAT/PAT | Có translation và lưu lượng qua được |
| LAB-07 | Dev-mode | Không mở kết nối thật; kết quả mô phỏng có kiểm soát |
| LAB-08 | Sai mật khẩu/mất kết nối | App không treo, báo lỗi và không đánh dấu applied |

ACL và Interface chỉ đưa vào lab push sau khi controller tương ứng được tích hợp.

## 5.4. Đo hiệu năng

Đo thời gian thao tác thủ công và bằng ứng dụng cho 1, 5, 10 thiết bị; thời gian preview/push; tỷ lệ thành công; CPU/RAM nếu có ý nghĩa. Không điền số giả định.

## 5.5. Đánh giá

Ưu điểm: UI tập trung, cấu trúc module, preview/pending state, test dev-mode, database schema rộng. Hạn chế: phạm vi Cisco IOS, secret dạng rõ, parser phụ thuộc CLI, schema routing đang lệch test, mức hoàn thiện không đồng đều, chưa có rollback và kiểm thử quy mô lớn.

---

# CHƯƠNG 6. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 6.1. Kết quả đạt được

Lập bảng mục tiêu--trạng thái--minh chứng dựa trên ma trận ở Mục 2.2 và kết quả test/lab cuối cùng.

## 6.2. Ý nghĩa

Nền tảng thực hành tích hợp kiến thức mạng, Python, desktop UI, dữ liệu và tự động hóa; hỗ trợ giảm thao tác lặp trong lab.

## 6.3. Hạn chế

Nêu trung thực các lỗi test còn lại, bảo mật credential, phạm vi thiết bị, thiếu rollback, thiếu đo quy mô và các module mới có persistence/schema.

## 6.4. Lộ trình phát triển ưu tiên

1. Đồng bộ schema/code OSPF, EIGRP và đưa toàn bộ test về trạng thái đạt.
2. Hoàn thiện View & Push cho Interface và ACL.
3. Bổ sung test worker NAT, test lab và cơ chế verify sau push.
4. Mã hóa secret, audit log, quyền người dùng và rollback.
5. Tích hợp VLAN/Switch Port, sau đó BGP và VRF.
6. Topology discovery và static route đa router.
7. SFTP backup/versioning, Syslog, Serial Console, Firewall và plugin đa hãng.

---

# PHỤ LỤC

## Phụ lục A. Cài đặt và chạy

Yêu cầu hệ thống, chạy app bằng `uv run python main.py`, build database, chạy test và xử lý lỗi thường gặp.

## Phụ lục B. Cấu trúc dự án và ánh xạ module

Cây thư mục rút gọn; bảng QML → slot → backend → table → worker/template.

## Phụ lục C. Schema dữ liệu

ERD và từ điển dữ liệu, đặc biệt quan hệ interface, routing, ACL/NAT và ý nghĩa trạng thái.

## Phụ lục D. Bộ kiểm thử và minh chứng

Danh sách test, log, ảnh lab và lệnh xác minh. Ghi ngày chạy và commit.

## Phụ lục E. Phân công

Ghi công việc thực tế của từng thành viên, commit/minh chứng và tỷ lệ đóng góp nếu biểu mẫu yêu cầu.

---

# DANH SÁCH MINH CHỨNG CẦN BỔ SUNG TRƯỚC KHI NỘP

| STT | Minh chứng | Trạng thái khi rà soát |
|---:|---|---|
| 1 | Ảnh tổng quan app và quản lý thiết bị | Chưa đưa vào `latex/figures` |
| 2 | Sơ đồ kiến trúc và luồng View & Push | Cần dựng |
| 3 | ERD rút gọn đúng schema hiện hành | Cần dựng |
| 4 | Ảnh DHCP, Routing, ACL, NAT, Interface | Cần chụp thống nhất dữ liệu |
| 5 | Log 30 test sau khi sửa routing schema | Hiện 28/30 đạt |
| 6 | Topology và file lab | Chưa xác nhận |
| 7 | Kết quả lệnh `show` trước/sau push | Chưa tổng hợp |
| 8 | Bảng đo thời gian và tỷ lệ thành công | Chưa đo |
| 9 | Kiểm thử Windows/Linux | Chưa có bằng chứng đầy đủ |
| 10 | Phân công và đóng góp thành viên | Cần cập nhật |

Trọng tâm bảo vệ nên là luồng tích hợp đã có bằng chứng: **quản lý thiết bị → lưu desired state → preview → push → cập nhật trạng thái**, minh họa bằng DHCP, Static Routing hoặc NAT. Topology/static route đa router chỉ nên chọn làm điểm nổi bật khi đã tích hợp vào runtime ở root, có UI, test và demo lab ổn định.
