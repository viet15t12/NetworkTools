# Kế hoạch tích hợp SNMP vào CAMS

## 1. Mục tiêu

Tích hợp SNMP để CAMS có khả năng giám sát trạng thái vận hành của router và switch, thu thập số liệu định kỳ, nhận cảnh báo sự kiện và kiểm chứng kết quả sau khi cấu hình thiết bị bằng SSH/Netmiko.

SNMP trong dự án chỉ đảm nhiệm đọc dữ liệu và nhận thông báo. Giai đoạn NCKH không triển khai SNMP SET.

### Kết quả cuối cùng cần đạt

- Kiểm tra được một thiết bị có phản hồi SNMP hay không.
- Thu thập uptime, tên thiết bị và mô tả hệ điều hành.
- Thu thập trạng thái, lưu lượng và lỗi của interface.
- Hiển thị trạng thái mới nhất trên giao diện QML.
- Lưu dữ liệu lịch sử phục vụ biểu đồ và thí nghiệm.
- Nhận được các trap cơ bản như `linkUp`, `linkDown`, `coldStart` và `warmStart`.
- Hỗ trợ SNMPv2c cho phòng lab và SNMPv3 cho mô hình an toàn hơn.
- Hoạt động độc lập với trạng thái phiên SSH.

## 2. Phạm vi và mức ưu tiên

| Mức | Phạm vi | Nội dung |
|---|---|---|
| P0 | Bắt buộc | Profile SNMP, Test SNMP, polling uptime và interface, lưu trạng thái mới nhất, giao diện Monitoring |
| P1 | Nên có | Lưu lịch sử, biểu đồ lưu lượng, cảnh báo interface, SNMPv3, retention dữ liệu |
| P2 | Mở rộng | Trap receiver, LLDP/CDP, CPU/RAM theo MIB Cisco, xuất dữ liệu thí nghiệm |
| Ngoài phạm vi | Chưa triển khai | SNMP SET, hệ thống cảnh báo qua email, giám sát hàng nghìn thiết bị, thay thế NMS chuyên dụng |

## 3. Vai trò của các thành phần trong app

| Thành phần | Trách nhiệm |
|---|---|
| SSH/Netmiko | Đăng nhập, gửi lệnh cấu hình, lấy running-config và cấu hình thiết bị gửi trap |
| SNMP Poller | Chủ động đọc trạng thái và bộ đếm từ thiết bị theo chu kỳ |
| SNMP Trap Receiver | Nhận sự kiện do thiết bị chủ động gửi về app |
| Syslog Server | Nhận thông báo dạng văn bản và thông tin chẩn đoán chi tiết |
| `device_network.db` | Lưu cấu hình mong muốn, profile và chính sách polling |
| `info_collected.db` | Lưu kết quả polling, trạng thái mới nhất, lịch sử và trap |
| QML Monitoring | Trình bày trạng thái, bảng interface, biểu đồ và sự kiện |

## 4. Vị trí chức năng trên giao diện

### 4.1 Activity/Feature Bar

Không tạo SNMP thành một nhóm cấu hình ngang hàng với DHCP, ACL hoặc NAT. SNMP được đặt bên trong `Monitoring`.

Cho phép `Monitoring` xuất hiện với cả ba loại thiết bị:

```qml
router: ["routing", "dhcp", "acl", "nat", "monitoring"]
sw2:    ["switching", "security", "monitoring"]
sw3:    ["switching", "routing", "services", "security", "monitoring"]
```

### 4.2 Cấu trúc trang Monitoring

| Tab | Nội dung |
|---|---|
| Overview | SNMP status, uptime, sysName, sysDescr, lần polling cuối, latency |
| Interfaces | Tên cổng, admin status, operational status, tốc độ, lỗi, lưu lượng vào/ra |
| Performance | Biểu đồ in/out bps, error rate và uptime |
| Events | Trap SNMP và cảnh báo được sinh từ polling |
| Syslog | Thông báo Syslog liên quan đến host đang chọn |

### 4.3 Settings

Thêm `Settings > SNMP Profiles`:

- Tạo, sửa và xóa profile.
- Chọn SNMPv2c hoặc SNMPv3.
- Nhập port, timeout, retries và polling interval.
- Kiểm tra thông tin xác thực.
- Không hiển thị lại secret dạng rõ sau khi đã lưu.

### 4.4 Tương tác trên host

Menu chuột phải hoặc phần Information của host có các thao tác:

- `Assign SNMP Profile`.
- `Test SNMP`.
- `Start Monitoring`.
- `Stop Monitoring`.
- `Configure Trap Target`.

SSH và SNMP phải có badge riêng:

| Badge | Trạng thái mẫu |
|---|---|
| SSH | Connected / Disconnected / Authentication failed |
| SNMP | Reachable / Timeout / Authentication failed / Disabled |
| Trap | Listening / Receiving / Inactive |

## 5. Luồng tương tác thực tế

### 5.1 Bật giám sát cho một thiết bị

1. Người dùng chọn host trong PanelSideBar.
2. Chọn một SNMP profile hoặc tạo profile mới.
3. Nhấn `Test SNMP`.
4. Backend gửi yêu cầu lấy `sysName.0` và `sysUpTime.0`.
5. Nếu thành công, app lưu liên kết host-profile và cho phép `Start Monitoring`.
6. Poller bắt đầu chạy nền theo chu kỳ.
7. Kết quả được ghi vào `info_collected.db`.
8. Backend phát signal để QML cập nhật Overview và Interfaces.

### 5.2 Phát hiện interface down

1. Poller lấy `ifAdminStatus` và `ifOperStatus`.
2. Nếu `ifAdminStatus = up` nhưng `ifOperStatus = down`, app tạo cảnh báo.
3. Nếu có trap `linkDown`, trạng thái được cập nhật ngay mà không chờ chu kỳ polling.
4. Lần polling tiếp theo xác nhận lại trạng thái để tránh phụ thuộc hoàn toàn vào trap.

### 5.3 Kiểm chứng sau cấu hình

1. App gửi cấu hình interface bằng SSH/Netmiko.
2. Sau khi hoàn thành, service yêu cầu một lần polling tức thời cho interface đó.
3. App so sánh trạng thái mong muốn với `ifAdminStatus` và `ifOperStatus`.
4. Giao diện hiển thị `Configured`, `Operational` hoặc `Mismatch`.

## 6. Thiết kế cơ sở dữ liệu cấu hình

Tạo file:

```text
app/infrastructure/database/schemas/device_network/10_snmp.sql
```

### 6.1 `t10_snmp_profiles`

| Cột | Kiểu | Mục đích |
|---|---|---|
| `profile_id` | INTEGER PK | Định danh profile |
| `profile_name` | TEXT UNIQUE | Tên hiển thị |
| `version` | TEXT | `2c` hoặc `3` |
| `port` | INTEGER | Mặc định 161 |
| `security_name` | TEXT | Username SNMPv3 |
| `security_level` | TEXT | `noAuthNoPriv`, `authNoPriv`, `authPriv` |
| `auth_protocol` | TEXT | `none`, `sha`, tùy thiết bị hỗ trợ |
| `priv_protocol` | TEXT | `none`, `aes`, tùy thiết bị hỗ trợ |
| `credential_ref` | TEXT | Tham chiếu tới nơi lưu secret |
| `context_name` | TEXT | Context SNMPv3 nếu sử dụng |
| `created_at` | TEXT | Thời điểm tạo |
| `updated_at` | TEXT | Thời điểm cập nhật |

Không lưu community, authentication key hoặc privacy key dạng rõ trong bảng này. Database chỉ giữ `credential_ref`.

### 6.2 `t10_device_snmp`

| Cột | Kiểu | Mục đích |
|---|---|---|
| `host` | TEXT PK/FK | Thiết bị được giám sát |
| `profile_id` | INTEGER FK | Profile được sử dụng |
| `enabled` | INTEGER | Bật/tắt polling |
| `poll_interval_sec` | INTEGER | Chu kỳ polling, mặc định 30 giây |
| `timeout_ms` | INTEGER | Timeout một request |
| `retries` | INTEGER | Số lần thử lại |
| `max_repetitions` | INTEGER | Kích thước GETBULK |
| `success` | INTEGER | Trạng thái áp dụng cấu hình app |
| `updated_at` | TEXT | Thời điểm cập nhật |

Không sử dụng `t01_devices.success` để quyết định polling. Trạng thái SSH và SNMP độc lập với nhau.

### 6.3 `t10_snmp_trap_targets`

| Cột | Kiểu | Mục đích |
|---|---|---|
| `target_id` | INTEGER PK | Định danh target |
| `host` | TEXT FK | Thiết bị gửi trap |
| `server_ip` | TEXT | IP máy chạy CAMS |
| `server_port` | INTEGER | 1162 trong lab hoặc 162 khi triển khai chuẩn |
| `version` | TEXT | `2c` hoặc `3` |
| `security_name` | TEXT | Community label hoặc SNMPv3 user |
| `enabled_traps` | TEXT | Danh sách nhóm trap được bật |
| `enabled` | INTEGER | Bật/tắt target |
| `success` | INTEGER | Trạng thái push cấu hình |

## 7. Thiết kế cơ sở dữ liệu thu thập

Tạo file:

```text
app/infrastructure/database/schemas/info_collected/13_info_snmp.sql
```

### 7.1 Các bảng cần có

| Bảng | Trách nhiệm | Chính sách lưu |
|---|---|---|
| `t13_snmp_device_latest` | Trạng thái thiết bị mới nhất | Một dòng cho mỗi host |
| `t13_snmp_interface_latest` | Trạng thái interface mới nhất | Một dòng cho mỗi host/ifIndex |
| `t13_snmp_interface_samples` | Dữ liệu biểu đồ theo thời gian | Giới hạn theo retention |
| `t13_snmp_traps` | Sự kiện nhận từ thiết bị | Giới hạn theo thời gian/số dòng |
| `t13_snmp_poll_status` | Kết quả polling, lỗi, latency | Giữ trạng thái gần nhất và lịch sử ngắn |

### 7.2 Dữ liệu thiết bị mới nhất

`t13_snmp_device_latest` nên chứa:

- `host`.
- `sys_name`.
- `sys_description`.
- `sys_object_id`.
- `uptime_ticks`.
- `last_poll_at`.
- `latency_ms`.
- `poll_state`.
- `last_error`.

### 7.3 Dữ liệu interface mới nhất

`t13_snmp_interface_latest` nên chứa:

- `host`, `if_index`, `if_name`, `if_alias`.
- `admin_status`, `oper_status`.
- `speed_bps`.
- `in_octets`, `out_octets`.
- `in_errors`, `out_errors`.
- `in_discards`, `out_discards`.
- `in_bps`, `out_bps` đã tính toán.
- `collected_at`.

### 7.4 Retention mặc định cho lab

| Dữ liệu | Thời gian giữ đề xuất |
|---|---|
| Latest tables | Giữ đến khi thiết bị bị xóa |
| Interface samples chi tiết | 7 ngày |
| Dữ liệu tổng hợp theo phút | 30 ngày nếu triển khai downsampling |
| Trap | 30 ngày hoặc tối đa 10.000 dòng |
| Poll error history | 7 ngày |

Chạy cleanup theo ngày hoặc khi khởi động app. Không xóa bảng latest khi cleanup lịch sử.

## 8. OID và MIB cho phiên bản đầu

### 8.1 Thiết bị

| Thuộc tính | OID/MIB | Mức |
|---|---|---|
| sysDescr | `1.3.6.1.2.1.1.1.0` | P0 |
| sysObjectID | `1.3.6.1.2.1.1.2.0` | P0 |
| sysUpTime | `1.3.6.1.2.1.1.3.0` | P0 |
| sysName | `1.3.6.1.2.1.1.5.0` | P0 |

### 8.2 Interface

| Thuộc tính | MIB | Mức |
|---|---|---|
| ifName, ifAlias | IF-MIB | P0 |
| ifAdminStatus | IF-MIB | P0 |
| ifOperStatus | IF-MIB | P0 |
| ifHighSpeed | IF-MIB | P0 |
| ifHCInOctets, ifHCOutOctets | IF-MIB | P0 |
| ifInErrors, ifOutErrors | IF-MIB | P1 |
| ifInDiscards, ifOutDiscards | IF-MIB | P1 |

Ưu tiên bộ đếm 64-bit `ifHCInOctets/ifHCOutOctets`. Chỉ dùng bộ đếm 32-bit khi thiết bị không hỗ trợ.

### 8.3 Mở rộng Cisco

CPU, RAM, temperature và fan sử dụng MIB riêng của hãng nên đặt ở P2. Backend phải nhận dạng `sysObjectID` trước khi chọn adapter MIB phù hợp.

Không đưa toàn bộ MIB/OID vào database. OID catalog ổn định nên nằm trong module Python hoặc file dữ liệu đi cùng ứng dụng.

## 9. Thiết kế backend

### 9.1 Cấu trúc thư mục đề xuất

```text
app/
├── application/
│   └── monitoring/
│       ├── snmp_service.py
│       ├── poll_scheduler.py
│       └── alert_service.py
├── infrastructure/
│   ├── snmp/
│   │   ├── client.py
│   │   ├── credentials.py
│   │   ├── oid_catalog.py
│   │   ├── rate_calculator.py
│   │   └── trap_receiver.py
│   └── database/
│       └── repositories/
│           ├── snmp_config_repository.py
│           └── snmp_metrics_repository.py
└── UI/
    └── qml/
        └── monitoring/
```

Tên thư mục cụ thể có thể điều chỉnh theo cấu trúc refactor cuối cùng, nhưng phải giữ ranh giới giữa client giao thức, service nghiệp vụ, repository và QML bridge.

### 9.2 Trách nhiệm lớp

| Lớp/module | Trách nhiệm |
|---|---|
| `SnmpClient` | GET, GETBULK, xử lý timeout và lỗi xác thực |
| `CredentialProvider` | Lấy secret từ `credential_ref` |
| `OidCatalog` | Danh sách OID chuẩn và ánh xạ kiểu dữ liệu |
| `RateCalculator` | Tính bps, xử lý counter reset/wrap |
| `PollScheduler` | Lập lịch polling theo từng host |
| `SnmpService` | Điều phối test, poll ngay và start/stop monitoring |
| `TrapReceiver` | Lắng nghe, parse và chuẩn hóa trap |
| `AlertService` | Sinh cảnh báo từ trạng thái hoặc threshold |
| Config repository | Đọc/ghi `device_network.db` |
| Metrics repository | Đọc/ghi `info_collected.db` |
| QML bridge | Cung cấp model, signal và slot cho giao diện |

### 9.3 Đồng thời và SQLite

- Không chạy polling trên UI thread.
- Dùng một worker thread có event loop riêng cho các tác vụ SNMP bất đồng bộ.
- Poller gửi kết quả qua queue về một database writer.
- Hạn chế nhiều worker cùng ghi SQLite trực tiếp.
- Bật WAL và transaction theo batch.
- QML chỉ nhận model/signal; không tự truy cập database.

### 9.4 Tính tốc độ interface

```text
delta_octets = current_counter - previous_counter
bps = delta_octets * 8 / elapsed_seconds
```

Quy tắc xử lý:

- Mẫu đầu tiên chưa tính bps.
- Nếu `sysUpTime` giảm, coi thiết bị vừa khởi động lại và xóa baseline.
- Nếu counter hiện tại nhỏ hơn counter trước, coi là reset/wrap và bỏ mẫu tốc độ đó.
- Không dùng khoảng thời gian cấu hình; phải dùng thời gian thực giữa hai mẫu.

## 10. Thư viện và cấu hình chạy

Thêm dependency SNMP vào `app/pyproject.toml` sau khi tạo proof of concept tương thích Python của dự án.

Dependency chức năng dự kiến:

- `pysnmp`: SNMP GET, GETBULK và notification receiver.
- `keyring`: lưu community hoặc khóa SNMPv3 ngoài SQLite nếu môi trường hỗ trợ.

Không khóa cứng phiên bản trước khi chạy thử trên Windows và Fedora của dự án.

### Port

| Mục đích | Port |
|---|---|
| Polling tới agent | UDP 161 |
| Trap chuẩn | UDP 162 |
| Trap trong lab không chạy quyền quản trị | UDP 1162 |

Trong giai đoạn phát triển nên dùng 1162. Không chạy toàn bộ ứng dụng bằng quyền root chỉ để chiếm port 162.

## 11. Bảo mật

| Yêu cầu | Cách thực hiện |
|---|---|
| Không lộ secret | Không log community/auth key/priv key |
| Không lưu rõ trong SQLite | Dùng `credential_ref` và credential provider |
| Giới hạn quyền | Chỉ dùng read-only; không dùng read-write community |
| Phiên bản | SNMPv2c cho lab, ưu tiên SNMPv3 `authPriv` cho triển khai thực tế |
| Giới hạn nguồn | ACL trên thiết bị chỉ cho phép IP máy quản lý truy cập UDP 161 |
| Trap | Chỉ nhận từ host đã đăng ký; đánh dấu nguồn không xác định |
| UI | Trường secret dùng password echo mode và không trả secret về QML |

## 12. Kế hoạch triển khai chi tiết

| Giai đoạn | Công việc | File/thành phần chính | Kết quả bàn giao | Tiêu chí hoàn thành | Ước lượng |
|---|---|---|---|---|---|
| 0. Chốt thiết kế | Chốt phạm vi P0/P1/P2, tên bảng, trạng thái và retention | Tài liệu thiết kế | Schema map và sequence flow | Nhóm thống nhất, không còn bảng trùng trách nhiệm | 1 ngày |
| 1. Proof of concept | Thử GET sysName/sysUpTime trên vIOS/vIOS-L2 bằng SNMPv2c | Script thử nghiệm tạm | Kết quả đọc hai OID | Chạy được trên Fedora và Windows | 1 ngày |
| 2. Schema cấu hình | Viết `10_snmp.sql`, constraint, FK và index | `device_network/10_snmp.sql` | Ba bảng cấu hình | Build DB, integrity và FK check đạt | 1–2 ngày |
| 3. Schema thu thập | Viết `13_info_snmp.sql`, latest/history/trap/status | `info_collected/13_info_snmp.sql` | Năm bảng thu thập | Insert/update/query và retention test đạt | 1–2 ngày |
| 4. SNMP client | GET, GETBULK, timeout, retry, chuẩn hóa lỗi | `infrastructure/snmp/client.py` | API client ổn định | Phân biệt timeout/auth/protocol error | 2 ngày |
| 5. Profile và Test | Repository profile, credential provider, nút Test SNMP | Settings backend/QML | Tạo profile và test host | Secret không xuất hiện trong log/QML model | 2–3 ngày |
| 6. Poll scheduler | Start/stop host, chu kỳ riêng, poll ngay | `poll_scheduler.py` | Polling nền | UI không treo, stop app kết thúc worker sạch | 2–3 ngày |
| 7. Thu thập interface | IF-MIB GETBULK, mapping ifIndex, rate calculator | OID catalog/rate calculator | Dữ liệu interface chuẩn hóa | Bps đúng với traffic lab, xử lý reboot/reset | 2–3 ngày |
| 8. Lưu trữ | Upsert latest, batch samples, poll status | Metrics repository | DB cập nhật liên tục | Không lock DB khi nhiều host polling | 2 ngày |
| 9. Monitoring UI | Overview, Interfaces, badge, reload/start/stop | QML Monitoring | UI sử dụng được | Chuyển host không lẫn dữ liệu, trạng thái cập nhật | 3–4 ngày |
| 10. Biểu đồ và retention | Query history, downsample đơn giản, cleanup | Performance UI/cleanup service | Biểu đồ và giới hạn dữ liệu | Không tăng DB vô hạn | 2–3 ngày |
| 11. Trap receiver | Listener, parse linkUp/linkDown/start, lưu DB | `trap_receiver.py` | Events cập nhật gần thời gian thực | Trap hợp lệ được lưu, trap lạ được đánh dấu | 3 ngày |
| 12. Cấu hình trap | Sinh lệnh và push bằng SSH/Netmiko | Trap configuration service | Thiết bị gửi trap về app | Có preview lệnh, kết quả success riêng | 2 ngày |
| 13. Kiểm thử tổng thể | Unit, integration, UI smoke, failure cases | `tests/` | Báo cáo test | Không crash khi timeout, sai secret, DB khóa, device reboot | 3 ngày |
| 14. Thí nghiệm NCKH | Đo latency, request rate, độ chính xác và dung lượng DB | EVE-NG/report scripts | Bảng số liệu và biểu đồ | Thí nghiệm lặp lại được, có dữ liệu gốc | 3–5 ngày |
| 15. Tài liệu | README, sơ đồ kiến trúc, hướng dẫn cấu hình lab | `docs/` và báo cáo | Bộ tài liệu hoàn chỉnh | Thành viên khác làm lại được theo hướng dẫn | 2 ngày |

Tổng ước lượng: khoảng 27–36 ngày công. Với nhóm ba sinh viên làm song song, phạm vi P0 và phần lớn P1 có thể hoàn thành trong 3–4 tuần nếu kiến trúc database/UI đã ổn định.

## 13. Phân công cho nhóm ba người

| Vai trò | Công việc chính |
|---|---|
| Database/Python | Schema, repository, rate calculator, retention, dữ liệu thí nghiệm |
| UI/QML | Settings profile, Monitoring Overview, Interfaces, Performance, Events |
| Network automation | SNMP client, poller, cấu hình Cisco, trap receiver, EVE-NG lab |

Các hợp đồng dữ liệu phải thống nhất trước khi làm song song:

- DTO thiết bị mới nhất.
- DTO interface mới nhất.
- Enum trạng thái polling.
- Signal/slot giữa backend và QML.
- Quy ước timestamp UTC.

## 14. Kế hoạch kiểm thử

### 14.1 Unit test

| Nhóm test | Trường hợp |
|---|---|
| Profile validation | SNMPv2c thiếu credential, SNMPv3 thiếu auth/priv, port sai |
| Error mapping | Timeout, authentication error, malformed response |
| Rate calculation | Mẫu đầu, counter tăng, counter giảm, reboot, elapsed bằng 0 |
| Repository | Upsert latest, insert sample, cleanup retention |
| Trap parser | linkUp, linkDown, coldStart, OID chưa biết |

### 14.2 Integration test

- Hai router và hai switch trong EVE-NG.
- Một host đúng secret, một host sai secret.
- Một host tắt SNMP.
- Rút cáp một interface để tạo linkDown.
- Khởi động lại thiết bị để kiểm tra uptime/counter reset.
- Chạy polling đồng thời tối thiểu bốn host.

### 14.3 UI test

- Chuyển nhanh giữa các host.
- Start/stop monitoring nhiều lần.
- Đóng app khi poller đang chạy.
- Hiển thị trạng thái khi database chưa có dữ liệu.
- Biểu đồ không lỗi khi chỉ có một mẫu.

## 15. Kịch bản thí nghiệm phục vụ báo cáo NCKH

### 15.1 So sánh polling interval

Chạy các chu kỳ 5, 15, 30 và 60 giây, sau đó đo:

- Thời gian phát hiện link down.
- Số request mỗi phút.
- Lưu lượng quản lý sinh ra.
- Tốc độ tăng kích thước database.
- CPU của app và thiết bị nếu thu thập được.

### 15.2 Polling và trap

Thực hiện 30 lần chuyển trạng thái interface:

- Ghi thời điểm sự kiện thực tế.
- Ghi thời điểm polling phát hiện.
- Ghi thời điểm trap đến app.
- Tính trung bình, min, max và độ lệch chuẩn.
- Mô phỏng mất trap để chứng minh polling vẫn khôi phục được trạng thái.

### 15.3 Kiểm tra độ chính xác

So sánh:

- `ifOperStatus` với `show interfaces`.
- Counter/bps SNMP với traffic tạo trong lab.
- Uptime SNMP với uptime thiết bị.

## 16. Tiêu chí nghiệm thu

| Mã | Tiêu chí |
|---|---|
| AC-01 | Test SNMP trả về thành công hoặc lỗi rõ ràng trong thời gian timeout cấu hình |
| AC-02 | Polling ít nhất bốn thiết bị không làm treo giao diện |
| AC-03 | Interface latest được cập nhật đúng theo host/ifIndex |
| AC-04 | Tốc độ in/out được tính từ counter 64-bit và khoảng thời gian thực |
| AC-05 | Reboot thiết bị không tạo spike lưu lượng giả |
| AC-06 | SSH thất bại không tự động làm SNMP bị Disabled |
| AC-07 | Secret không xuất hiện trong log hoặc QML model |
| AC-08 | Trap linkDown cập nhật Events và trạng thái interface |
| AC-09 | Dữ liệu lịch sử được cleanup theo retention |
| AC-10 | `PRAGMA integrity_check` và `foreign_key_check` không có lỗi |
| AC-11 | App đóng sạch, không còn worker hoặc socket nền |
| AC-12 | Có bộ số liệu và biểu đồ dùng được trong báo cáo NCKH |

## 17. Rủi ro và phương án xử lý

| Rủi ro | Ảnh hưởng | Phương án |
|---|---|---|
| Polling quá nhanh | Tăng tải và dung lượng DB | Mặc định 30 giây, giới hạn tối thiểu 5 giây |
| SQLite bị khóa | Mất mẫu hoặc treo worker | Một writer queue, WAL, transaction batch |
| MIB khác nhau theo thiết bị | CPU/RAM không đồng nhất | P0 chỉ dùng MIB chuẩn, vendor adapter ở P2 |
| Trap bị mất | Bỏ sót sự kiện | Polling định kỳ luôn là nguồn xác nhận |
| Counter reset/wrap | Biểu đồ xuất hiện spike | Theo dõi uptime và bỏ mẫu không hợp lệ |
| Lộ community/key | Rủi ro bảo mật | Credential reference, che secret, không log |
| Port 162 cần quyền cao | App khó chạy trên Linux | Dùng 1162 trong lab hoặc tách listener service |
| QML cập nhật quá nhiều | Giao diện chậm | Batch signal, refresh UI 1–2 giây/lần |

## 18. Thứ tự triển khai khuyến nghị

Không bắt đầu bằng trap hoặc biểu đồ. Thứ tự ít rủi ro nhất là:

1. Proof of concept SNMP GET.
2. Hai schema database.
3. Profile và Test SNMP.
4. Poller thiết bị.
5. Poller interface và rate calculator.
6. Latest tables và Monitoring UI.
7. Lịch sử, biểu đồ và retention.
8. SNMPv3.
9. Trap receiver.
10. Thí nghiệm và báo cáo.

Mốc MVP được xem là hoàn thành sau bước 6. Các bước sau nâng giá trị nghiên cứu nhưng không được làm chậm khả năng demo cơ bản.
