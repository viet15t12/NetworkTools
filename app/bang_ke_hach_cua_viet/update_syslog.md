# Kế hoạch thiết kế và tái cấu trúc Cisco Syslog cho CAMS

## 1. Phạm vi

Module này được xác định là:

> **Cisco Syslog Collector for CAMS**

Mục tiêu chính:

- Nhận Syslog từ thiết bị Cisco IOS / IOS-XE.
- Phân tích đúng cấu trúc message Cisco.
- Ánh xạ log vào thiết bị đã quản lý trong CAMS.
- Lưu trữ, tìm kiếm, lọc và hiển thị log.
- Hỗ trợ cấu hình Syslog destination trực tiếp trên thiết bị Cisco.
- Giữ kiến trúc Syslog tách biệt, không trộn socket, parser, database, Cisco CLI và Qt/QML trong cùng một file.

Không ưu tiên ở giai đoạn hiện tại:

- Syslog đa hãng.
- RFC5424 đầy đủ cho mọi vendor.
- RELP.
- SIEM.
- Alert engine phức tạp.
- TLS nếu chưa có nhu cầu thực tế.

---

## 2. Hiện trạng

Syslog hiện đã có các thành phần chính:

- UDP/TCP receiver.
- Queue + batch writer.
- Parser.
- Repository SQLite.
- Retention.
- Source IP → device resolver.
- Cisco Syslog configurator.
- Qt/QML manager.
- Settings.

Vấn đề chính không phải thiếu chức năng, mà là một số file đang chịu quá nhiều trách nhiệm:

- `repository.py`
- `configurator.py`
- `manager.py`
- `writer.py`
- `receiver.py`
- `parser.py`

Mục tiêu refactor là giữ behavior hiện tại trước, sau đó mới nâng cấp parser và transport.

---

# 3. Kiến trúc mục tiêu

```text
QML
 │
 ▼
qt/manager.py
 │
 ▼
application/server_service.py
 │
 ├──────────────────────────────┐
 │                              │
 ▼                              ▼
Syslog pipeline           Cisco device config
 │                              │
 ▼                              ▼
transport                  device_config/service.py
 │                              │
 ▼                              ▼
framing                    device_config/worker.py
 │                              │
 ▼                              ▼
writer                     Cisco session
 │
 ▼
processor
 │
 ├── parsing
 │
 └── source resolver
 │
 ▼
persistence
 │
 ▼
SQLite
```

Nguyên tắc phụ thuộc:

```text
QML
 ↓
Qt adapter
 ↓
Application service
 ↓
Repository / Worker
```

Quy tắc:

- QML không gọi SQL.
- QML không thao tác socket.
- Qt manager không chứa nghiệp vụ Cisco.
- Repository chỉ làm việc với SQLite.
- Worker chỉ làm việc với thiết bị.
- Parser không biết Qt.
- Transport không biết database.
- Writer không biết Cisco CLI.
- Cisco configurator không biết QML.

---

# 4. Cấu trúc thư mục đề xuất

```text
app/features/syslog/
│
├── __init__.py
├── README.md
│
├── domain/
│   ├── __init__.py
│   └── models.py
│
├── transport/
│   ├── __init__.py
│   ├── receiver.py
│   └── framing.py
│
├── parsing/
│   ├── __init__.py
│   ├── parser.py
│   ├── pri.py
│   ├── timestamp.py
│   └── cisco.py
│
├── application/
│   ├── __init__.py
│   ├── server_service.py
│   ├── pipeline.py
│   ├── writer.py
│   ├── processor.py
│   ├── source_resolver.py
│   └── retention.py
│
├── persistence/
│   ├── __init__.py
│   ├── schema.py
│   ├── message_repository.py
│   ├── device_state_repository.py
│   └── device_lookup_repository.py
│
├── device_config/
│   ├── __init__.py
│   ├── service.py
│   ├── commands.py
│   ├── worker.py
│   └── verifier.py
│
└── qt/
    ├── __init__.py
    ├── manager.py
    └── settings.py
```

---

# 5. Trách nhiệm từng nhóm

## 5.1 `domain/`

### `models.py`

Chứa các data object thuần Python.

Không import:

- PyQt6.
- SQLite.
- Netmiko.
- QML.

Ví dụ:

```python
@dataclass(slots=True)
class SyslogMessage:
    source_ip: str
    protocol: str

    severity: int
    message: str
    raw_message: str

    syslog_pri: int | None = None
    syslog_facility: int | None = None

    cisco_facility: str | None = None
    cisco_subfacility: str | None = None
    mnemonic: str | None = None

    sequence_number: int | None = None
    device_time: str | None = None
    clock_unsynchronized: bool = False

    device_host: str = ""
    received_at: str = ""
    parse_status: str = "parsed"
```

---

# 6. Transport

## 6.1 `transport/receiver.py`

Chỉ chịu trách nhiệm:

- Bind socket.
- UDP receive.
- TCP accept.
- Quản lý client.
- Giới hạn message size.
- Giới hạn client.
- Start / stop.
- Truyền raw bytes cho tầng tiếp theo.

Không làm:

- Parse Cisco.
- Query database.
- Resolve device.
- Emit Qt signal.
- Ghi SQLite.

---

## 6.2 `transport/framing.py`

Tách framing khỏi receiver.

Interface đề xuất:

```python
class SyslogFramer:
    def feed(self, data: bytes) -> list[bytes]: ...
```

Các implementation:

```text
SyslogFramer
├── LineFramer
└── OctetCountingFramer
```

Giai đoạn đầu:

- Giữ newline framing đang có.
- Sau đó bổ sung RFC6587 octet-counting nếu cần.

---

# 7. Cisco parsing

Đây là phần quan trọng nhất của module.

Pipeline:

```text
raw bytes
   │
   ▼
parse PRI
   │
   ▼
parse sequence number
   │
   ▼
parse Cisco timestamp
   │
   ▼
parse Cisco message header
   │
   ▼
SyslogMessage
```

---

## 7.1 `parsing/pri.py`

Phân tích:

```text
<189>
```

Lưu riêng:

```text
syslog_pri
syslog_facility
severity_from_pri
```

Không dùng chung `facility` với Cisco facility.

---

## 7.2 `parsing/timestamp.py`

Xử lý các dạng Cisco timestamp.

Ví dụ:

```text
Aug 22 19:32:10
Aug 22 19:32:10.039
000013: Aug 22 19:32:10.039
*Aug 22 19:32:10.039
```

Kết quả:

```text
sequence_number
device_time
milliseconds
clock_unsynchronized
```

Dấu `*` trước timestamp nên được lưu để biết clock thiết bị có thể chưa đồng bộ.

---

## 7.3 `parsing/cisco.py`

Parse Cisco system message.

Dạng cơ bản:

```text
%FACILITY-SEVERITY-MNEMONIC: message
```

Có thể có:

```text
%FACILITY-SUBFACILITY-SEVERITY-MNEMONIC: message
```

Kết quả:

```text
cisco_facility
cisco_subfacility
severity
mnemonic
message
```

Ví dụ:

```text
%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down
```

Kết quả:

```text
cisco_facility = LINK
severity       = 3
mnemonic       = UPDOWN
message        = Interface GigabitEthernet0/1, changed state to down
```

---

## 7.4 `parsing/parser.py`

Đóng vai trò orchestrator.

Không chứa regex lớn cho tất cả mọi thứ.

Ví dụ:

```text
parser.py
 │
 ├── pri.py
 ├── timestamp.py
 └── cisco.py
```

---

# 8. Không trộn Syslog facility với Cisco facility

Đây là thay đổi quan trọng.

Một packet có thể có:

```text
<189>Aug 22 19:32:10: %LINK-3-UPDOWN: ...
```

Trong đó:

```text
<189>
  ↓
Syslog PRI
```

và:

```text
%LINK-3-UPDOWN
  │    │   │
  │    │   └── mnemonic
  │    └────── severity
  └─────────── Cisco facility
```

Không nên dùng chung:

```text
facility
```

Nên dùng:

```text
syslog_pri
syslog_facility

cisco_facility
cisco_subfacility
severity
mnemonic
```

---

# 9. Application layer

## 9.1 `application/server_service.py`

Là service cấp cao cho Syslog server.

Chịu trách nhiệm:

- Start server.
- Stop server.
- Restart.
- Apply settings.
- Gọi retention.
- Gọi query service.
- Điều phối các thành phần.

Không import QML.

---

## 9.2 `application/pipeline.py`

Giữ lifecycle:

```text
receiver + writer
```

Yêu cầu:

- Start atomic.
- Bind lỗi → rollback.
- Stop receiver trước.
- Flush writer sau.
- Không để thread zombie.

---

## 9.3 `application/writer.py`

Chỉ làm:

- Bounded queue.
- Backpressure.
- Dropped count.
- Batch.
- Flush theo size/time.
- Gọi processor.
- Gọi repository.

Không trực tiếp parse Cisco.

---

## 9.4 `application/processor.py`

Nhận raw event:

```text
bytes
source_ip
protocol
```

Sau đó:

```text
parse
 ↓
resolve device
 ↓
normalize
 ↓
SyslogMessage
```

Pseudo flow:

```python
message = parser.parse(data, source_ip, protocol)
message.device_host = resolver.resolve(source_ip)
return message
```

---

## 9.5 `application/source_resolver.py`

Chỉ ánh xạ:

```text
source IP
   ↓
managed device host
```

Có thể giữ TTL cache như hiện tại.

---

## 9.6 `application/retention.py`

Chỉ chứa policy retention.

Ví dụ:

```text
retention_days
batch_size
```

Repository thực hiện SQL delete.

---

# 10. Persistence

## 10.1 Tách `repository.py`

Không giữ một `SyslogRepository` làm tất cả mọi thứ.

Tách thành ba repository.

### `message_repository.py`

```text
insert_messages()
query_messages()
delete_expired()
```

### `device_state_repository.py`

```text
save_state()
save_attempt()
configured_hosts()
```

### `device_lookup_repository.py`

```text
connected_devices()
resolve_device_host()
source_interface()
is_connected()
device_os()
```

---

# 11. Database schema đề xuất

Bảng message:

```text
t12_syslog_messages
────────────────────────────────
id
device_host
source_ip

received_at
device_time
sequence_number
clock_unsynchronized

syslog_pri
syslog_facility

cisco_facility
cisco_subfacility
severity
mnemonic

message
raw_message

protocol
parse_status
```

---

## UI không cần hiển thị tất cả trường

Bảng chính:

```text
Time
Device
Severity
Facility
Mnemonic
Message
```

Chi tiết message:

```text
Source IP
Protocol
PRI
Syslog Facility
Cisco Facility
Cisco Subfacility
Severity
Mnemonic
Device Timestamp
Sequence Number
Raw Message
Parse Status
```

---

# 12. Có nên dùng Peewee?

Không nên chuyển toàn bộ Syslog ingestion sang Peewee.

Giữ:

```text
message insert   → sqlite3 + executemany
message query    → sqlite3
retention        → sqlite3
```

Lý do:

- Đây là hot path.
- Có batch insert.
- `executemany()` phù hợp.
- WAL phù hợp.
- Ít abstraction hơn.

Có thể cân nhắc Peewee cho:

```text
device state CRUD
```

nhưng không bắt buộc.

---

# 13. Cisco device configuration

Tách `configurator.py`.

Cấu trúc:

```text
device_config/
├── commands.py
├── service.py
├── worker.py
└── verifier.py
```

---

## 13.1 `commands.py`

Pure function.

Sinh command Cisco:

```text
logging host ...
logging trap ...
logging source-interface ...
service timestamps log ...
service sequence-numbers
```

Không truy cập session.

Không truy cập DB.

---

## 13.2 `worker.py`

Chỉ giao tiếp thiết bị.

Ví dụ:

```text
send config commands
show running-config
show logging
save configuration
show startup-config
```

Chỉ làm việc với connector/session.

---

## 13.3 `verifier.py`

Kiểm tra:

```text
destination tồn tại?
protocol đúng?
port đúng?
source-interface đúng?
logging level đúng?
CLI có lỗi?
```

---

## 13.4 `service.py`

Điều phối:

```text
validate device
 ↓
lookup source interface
 ↓
build commands
 ↓
worker apply
 ↓
verify
 ↓
save startup config
 ↓
update device state repository
```

---

# 14. Qt layer

## `qt/manager.py`

Chỉ là QML adapter.

Ví dụ:

```python
class SyslogManager(QObject):
    @pyqtSlot(result="QVariant")
    def startServer(self):
        return self.server_service.start()

    @pyqtSlot(result="QVariant")
    def stopServer(self):
        return self.server_service.stop()
```

Không trực tiếp:

- Parse.
- Socket receive.
- SQL.
- Cisco CLI.
- Retention logic.

---

## `qt/settings.py`

Giữ:

- QSettings.
- Bind IP.
- Advertised IP.
- Port.
- Protocol.
- Retention.
- Enabled on startup.

Không đặt nghiệp vụ Cisco ở đây.

---

# 15. Test structure

```text
tests/syslog/
│
├── domain/
│
├── transport/
│   ├── test_receiver.py
│   └── test_framing.py
│
├── parsing/
│   ├── test_pri.py
│   ├── test_timestamp.py
│   ├── test_cisco.py
│   └── test_parser.py
│
├── application/
│   ├── test_pipeline.py
│   ├── test_writer.py
│   ├── test_processor.py
│   └── test_retention.py
│
├── persistence/
│   ├── test_message_repository.py
│   ├── test_device_state_repository.py
│   └── test_device_lookup_repository.py
│
├── device_config/
│   ├── test_commands.py
│   ├── test_worker.py
│   ├── test_verifier.py
│   └── test_service.py
│
└── qt/
    ├── test_manager.py
    └── test_settings.py
```

---

# 16. Bộ test Cisco nên có

Ít nhất nên có log cho:

```text
LINK
LINEPROTO
SYS
SEC_LOGIN
SSH
OSPF
EIGRP
BGP
DHCP
SPANTREE
EC
VLAN
PORT_SECURITY
```

Ví dụ:

```text
%LINK-3-UPDOWN
%LINEPROTO-5-UPDOWN
%SYS-5-CONFIG_I
%SEC_LOGIN-5-LOGIN_SUCCESS
%OSPF-5-ADJCHG
%SPANTREE-2-BLOCK_BPDUGUARD
```

Test cả:

- Có PRI.
- Không PRI.
- Có sequence number.
- Không sequence number.
- Có milliseconds.
- Clock unsynchronized.
- Message malformed.
- Unknown Cisco facility.
- Raw fallback.

---

# 17. Kế hoạch triển khai theo commit

## Commit 1 — Package structure

Tạo:

```text
domain/
transport/
parsing/
application/
persistence/
device_config/
qt/
```

Chỉ move file.

Không đổi behavior.

---

## Commit 2 — Split repository

Tách:

```text
repository.py
```

thành:

```text
message_repository.py
device_state_repository.py
device_lookup_repository.py
```

Chạy toàn bộ Syslog tests.

---

## Commit 3 — Split Cisco configurator

Tách:

```text
configurator.py
```

thành:

```text
commands.py
service.py
worker.py
verifier.py
```

Không đổi command output.

---

## Commit 4 — Split Qt manager

Tạo:

```text
application/server_service.py
qt/manager.py
```

Manager chỉ giữ Qt/QML contract.

---

## Commit 5 — Split processing

Tạo:

```text
processor.py
```

Writer chỉ còn queue + batch.

---

## Commit 6 — Transport cleanup

Tạo:

```text
framing.py
```

Receiver chỉ quản lý socket.

Giữ newline framing trước.

---

## Commit 7 — Cisco parser v2

Tách:

```text
pri.py
timestamp.py
cisco.py
parser.py
```

Bổ sung:

```text
sequence_number
clock_unsynchronized
cisco_subfacility
syslog_pri
syslog_facility
```

---

## Commit 8 — Database migration

Thêm cột mới.

Không xóa dữ liệu cũ.

Có migration tương thích workspace hiện tại.

---

## Commit 9 — UI detail view

Bảng chính giữ gọn.

Thêm detailed message inspector.

---

## Commit 10 — Protocol improvement

Nếu cần:

```text
RFC6587 octet-counting
TCP robustness
TLS
```

TLS chưa phải ưu tiên.

---

# 18. Thứ tự ưu tiên thực tế

Nếu chỉ có thời gian refactor từng phần:

```text
1. repository.py
2. configurator.py
3. manager.py
4. writer.py
5. receiver.py
6. parser.py
7. database migration
8. UI enhancement
```

Không nên sửa parser lớn ngay từ đầu vì sẽ vừa thay kiến trúc vừa thay behavior.

---

# 19. Definition of Done

Syslog refactor được coi là hoàn thành khi:

- Syslog nằm hoàn toàn trong `features/syslog/`.
- Không có nghiệp vụ Syslog mới trong `core/`.
- Qt manager không có SQL.
- Qt manager không gọi Cisco connector trực tiếp.
- Receiver không biết SQLite.
- Writer không biết Cisco CLI.
- Parser không import PyQt.
- Repository không import QML.
- Worker không import QML.
- `syslog_pri` và `cisco_facility` không còn dùng chung một field.
- Test Cisco thực tế chạy qua parser.
- UDP receiver hoạt động ổn định.
- TCP không làm treo UI.
- Shutdown flush được queue.
- Malformed message vẫn được lưu raw.
- Database migration không phá dữ liệu cũ.
- README và SYSTEM_LOGS được cập nhật theo kiến trúc mới.

---

# 20. Kết luận

CAMS không cần trở thành một Syslog server tổng quát.

Hướng phù hợp hơn là:

```text
Cisco device
   ↓
Syslog transport
   ↓
Cisco-aware parser
   ↓
Device resolver
   ↓
SQLite
   ↓
Search / Filter / Troubleshooting UI
```

Trọng tâm:

> **Cisco-first, module hóa rõ ràng, giữ core đơn giản, dễ test và dễ mở rộng sau này.**

Sau khi kiến trúc ổn định, nếu cần hỗ trợ thêm Juniper, Arista hoặc Linux Syslog thì chỉ cần bổ sung parser adapter thay vì viết lại toàn bộ Syslog pipeline.
