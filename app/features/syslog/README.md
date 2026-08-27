# Cisco Syslog

`Syslog Group` dùng cùng cơ chế với Routing Group: chọn từ hai đến năm thiết bị
Cisco đang kết nối, chọn source-interface riêng cho từng host, nhập destination
và message policy một lần, sau đó Save hoặc batch View & Push. Mỗi host được lưu
độc lập nên lỗi ở một host không rollback các host thành công và draft có thể
retry an toàn.

Bộ lọc log hỗ trợ chọn đồng thời nhiều host và nhiều severity bằng dropdown
checkbox. Ô Smart Filter mở visual builder cho message, host, severity, protocol,
facility, mnemonic, khoảng UTC/relative time và giới hạn mới nhất theo host; biểu
thức `key:value` sinh ra vẫn tương thích với API và automation cũ.

Trạng thái: **implemented** cho listener UDP+TCP đồng thời trên cùng port, parser ưu tiên
Cisco IOS/IOS-XE, persistence SQLite và cấu hình destination trên thiết bị.

Luồng nhận log:

```text
C++ UDP+TCP collector → SQLite → JSON-line event → QProcess/Python signal → QML
                                  ↑
                         syslog.json settings

QML device configuration → qt/manager.py → device_config service → Cisco session
```

| Package | Trách nhiệm |
| --- | --- |
| `domain/` | Data object thuần Python |
| `native/syslog_collector/` | C++ UDP/TCP socket, parser, source resolver và SQLite writer |
| `transport/` | Python compatibility receiver dùng bởi unit test/integration cũ |
| `parsing/` | PRI, sequence/timestamp và Cisco system-message header |
| `application/` | Server lifecycle, queue/batch, processor, resolver, retention |
| `persistence/` | Message, device-state và read-only device lookup repository |
| `device_config/` | Pure command builder, verifier, Cisco worker và service |
| `group_service.py`, `group_repository.py` | Validation, inventory ownership và persistence Syslog Group đa host |
| `qt/` | QML adapter và QProcess bridge; không nhận socket hoặc parse message |

Các module cũ như `parser.py`, `repository.py`, `manager.py` vẫn là compatibility
entry point để không phá import hiện hữu. `SyslogRepository` cũng là facade tương
thích, nhưng công việc SQLite thật được giao cho ba repository chuyên trách.

Parser lưu riêng:

- `syslog_pri`, `syslog_facility` từ `<PRI>`;
- `cisco_facility`, `cisco_subfacility`, `severity`, `mnemonic` từ Cisco header;
- `sequence_number`, `device_time`, `clock_unsynchronized` từ Cisco prefix.

Message sai định dạng vẫn được lưu cùng raw text. TCP lưu frame cuối khi client
đóng mà không có newline; message size và client count đều bounded. C++ ghi trực
tiếp vào SQLite với busy timeout, sau đó mới phát row JSON cho Python. Cấu hình
listener nằm ở `syslog.json`; QML ghi file này và C++ đọc khi khởi động. Retention
mặc định 30 ngày vẫn do application service chạy trước khi mở listener.

Build listener native trước khi chạy ứng dụng:

```bash
native/syslog_collector/build.sh
```

Binary được cài cục bộ vào `bin/networktools-syslog-collector`. Có thể override
bằng biến môi trường `NETWORKTOOLS_SYSLOG_COLLECTOR`; đường dẫn JSON có thể
override bằng `NETWORKTOOLS_SYSLOG_SETTINGS`.

Cấu hình Cisco chạy như transaction: kiểm tra source-interface, apply, verify
running-config, lưu startup-config, verify persistence rồi mới ghi trạng thái DB.
Mỗi router/SW2/SW3 có tab **Syslog Server** để lưu nhiều destination độc lập
trong `device_network.db.t10_syslog_servers`, gồm protocol, port, severity,
timestamp và sequence-number. Log nhận được được lưu riêng ở
`info_collected.db.t12_syslog_messages`. Cấu hình mới mặc định UDP/5514 và
severity 5 (`notifications`) để nhận cả `%SYS-5-CONFIG_I`. Các row dùng
`sync_status` và luồng View & Push chung; sửa endpoint đã áp dụng sẽ tạo đồng thời
task gỡ endpoint cũ và task thêm endpoint mới. Activity bar chỉ sở hữu listener,
bộ lọc và bảng log. Bộ lọc hỗ trợ host, khoảng thời gian nhận, severity,
protocol và N log mới nhất trên từng host. Ô Smart filter nhận cú pháp ngắn như
`host:192.0.2.10 last:20`, `since:30m severity:error` hoặc
`facility:LINK mnemonic:UPDOWN`; nút Help trong thanh lọc liệt kê đầy đủ cú pháp.
**Export Excel** chỉ ghi các row đang hiển thị sau khi áp dụng mọi bộ lọc, đồng
thời lưu tóm tắt bộ lọc trong workbook. Cancel chỉ xóa destination do
NetworkTools quản lý.

Chưa hỗ trợ RFC6587 octet-counting, TLS, nhiều bind endpoint/port hoặc alert engine.
Chi tiết vận hành: [`../../docs/SYSTEM_LOGS.md`](../../docs/SYSTEM_LOGS.md).
Test nằm trong `tests/syslog/`, gồm cả các nhóm parsing, transport, application,
persistence và device configuration.
