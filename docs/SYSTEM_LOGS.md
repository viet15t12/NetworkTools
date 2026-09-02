# System Logs (Syslog)

Cập nhật: **2026-08-16**. System Logs là receiver Syslog của desktop app; nó
khác Device Logs, nơi dùng TShark để quan sát packet trên interface cục bộ.

## 1. Luồng runtime

```text
UDP datagram hoặc TCP stream
  → SyslogReceiver (socket thread, select + stop event)
  → SyslogWriter (queue có giới hạn, ghi batch)
  → parse_message()
  → SyslogRepository
  → info_collected.db
  → SyslogManager (QObject)
  → SyslogWorkspace.qml
```

`app/main.py` tạo `SyslogManager`, đăng ký cả `syslogManager` và
`syslogSettings`, đổi path khi workspace active thay đổi và gọi `shutdown()` khi
thoát. Listener chỉ auto-start nếu `enabledOnStartup` bật; lỗi bind/start được báo
nhưng không làm hỏng việc tải UI.

Receiver hỗ trợ **một** transport active tại một thời điểm: UDP hoặc TCP. Socket
I/O, parse và SQLite không chạy trên Qt UI thread. Writer dùng queue có giới hạn;
khi quá tải message mới có thể bị drop và counter được phát lên control bar thay
vì tăng RAM vô hạn.

## 2. Parse và model dữ liệu

Parser hỗ trợ PRI, timestamp kiểu RFC và Cisco mnemonic. Mọi message đều giữ
`raw_message`; message lỗi parse vẫn được lưu với `parse_status` để không mất bằng
chứng. `source_ip` đến từ socket peer; `device_host` chỉ được resolve nếu khớp
inventory.

Schema canonical nằm ở
`app/infrastructure/database/schemas/info_collected/12_info_syslog.sql`. Feature
cũng có migration `CREATE ... IF NOT EXISTS` để bổ sung an toàn cho workspace cũ.

| Bảng | Vai trò |
| --- | --- |
| `t12_syslog_messages` | Thời gian nhận/thiết bị, source, facility, severity, mnemonic, message, raw, protocol và parse status |
| `t12_syslog_device_state` | Destination/transport/port/source-interface đã cấu hình theo host |

Các index phục vụ source IP, host/time, severity/time và facility/time. Query dùng
keyset pagination `before_id` với page tối đa 200 row; model UI giữ tối đa 2.000
row. Pause chỉ dừng cập nhật view, không dừng listener/writer; Resume reload để
bù dữ liệu.

Retention mặc định 30 ngày, tối thiểu một ngày, xóa theo batch 5.000 row.
`Clear View` chỉ xóa model đang hiển thị; không xóa database. Retention chạy tách
khỏi listener lifecycle để lỗi cleanup không làm dừng receiver.

## 3. Cấu hình listener

Settings được lưu bằng `QSettings`:

- bật khi khởi động;
- transport `udp` hoặc `tcp`;
- bind IP local và port;
- advertised IP gửi cho thiết bị;
- số ngày retention.

Bind IP `0.0.0.0` được phép cho listener, nhưng advertised IP phải là IPv4 cụ thể
để thiết bị có destination hợp lệ. Port phải nằm trong 1–65535. Đổi settings khi
listener đang chạy cần stop/start để socket nhận cấu hình mới. Port dưới 1024 có
thể cần quyền hệ điều hành; nên dùng port không đặc quyền như 5514 trong lab.

Không expose listener ra mạng công cộng nếu chưa có firewall, phân vùng mạng và
giám sát dung lượng. Syslog UDP không bảo đảm giao hàng; TCP cũng không cung cấp
TLS trong implementation hiện tại.

## 4. Cấu hình thiết bị Cisco

Sidebar chỉ liệt kê thiết bị đang `connected`. Context menu có thể áp dụng hoặc
gỡ destination Syslog trên Cisco IOS/IOS-XE qua session registry hiện hữu. Command
builder validate server IP, protocol, port và tên source interface; không ghép
input tùy ý. Nếu DB chưa biết source interface, UI yêu cầu nhập thủ công và
validate theo allowlist tên interface.

`bindIp` chỉ là địa chỉ socket local; lệnh thiết bị dùng `advertisedIp`. OS không
hỗ trợ, host mất session hoặc command thất bại phải trả lỗi và không ghi trạng
thái configured giả. Lệnh gỡ chỉ xóa destination do CAMS quản lý, không
xóa toàn bộ cấu hình logging khác của thiết bị.

## 5. UI và filter

`SyslogWorkspace` ghép `SyslogControlBar`, `SyslogFilterBar`, `SyslogLogTable`,
`SyslogMessageDetails` và `SyslogServerSettings`. Filter hỗ trợ host, search và
severity; panel thiết bị có search, refresh và trạng thái configured. Các QML
consumer chịu được backend `null` để preview/smoke test vẫn load.

## 6. Giới hạn và kiểm thử

- Chưa hỗ trợ TLS Syslog, RFC 5424 structured data đầy đủ, multi-listener, remote
  forwarding, export hoặc alert/rule engine.
- TCP receiver không được mô tả là RELP; mất kết nối có thể mất message chưa gửi.
- Mapping source IP → inventory có thể mơ hồ khi NAT hoặc nhiều thiết bị dùng
  chung địa chỉ.

Test nằm trong `app/tests/syslog/`: parser, command builder, configurator,
UDP receiver, repository/migration, settings, manager variants và QML. Test suite
mặc định không bind ra interface công cộng hay gửi lệnh đến thiết bị thật.
