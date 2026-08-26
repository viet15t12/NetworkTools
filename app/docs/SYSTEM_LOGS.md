# Cisco Syslog Server workflow

Đối chiếu: **2026-08-23**.

Syslog được tổ chức theo các tầng độc lập:

```text
C++ UDP+TCP collector → parser/resolver → info_collected.db
          ↑                                  ↓
     syslog.json                    JSON-line inserted event
                                             ↓
QML ← Python Qt manager/signals ← QProcess bridge

Device config QML → Python service → Cisco worker/verifier → DeviceStateRepository
```

`qt/manager.py` giữ signal/property/slot và khởi động listener C++ bằng `QProcess`.
C++ sở hữu socket, parse, resolve source IP và ghi SQLite. Chỉ sau khi commit
thành công, collector phát một JSON-line event; Python chuyển event đó thành
`messagesInserted` để QML cập nhật. Query, retention và cấu hình Cisco vẫn dùng
application/repository Python. Các module receiver/writer Python được giữ làm
compatibility entry point và phục vụ kiểm thử riêng.

## Ingestion

Collector C++ sở hữu đồng thời socket UDP và TCP trên cùng bind address/port.
Transport giới hạn kích thước message và số TCP client, tách TCP stream theo LF
và trả frame cuối khi peer đóng kết nối. SQLite dùng busy timeout 10 giây. Khi
dừng ứng dụng, Python gửi SIGTERM qua `QProcess` và collector đóng toàn bộ socket.

`SyslogProcessor` gọi parser và TTL-cached source resolver. Parser lần lượt xử lý:

1. RFC PRI (`syslog_pri`, `syslog_facility`, severity fallback).
2. Cisco sequence number và timestamp, gồm milliseconds và dấu `*` báo clock có
   thể chưa đồng bộ.
3. Cisco header `%FACILITY[-SUBFACILITY]-SEVERITY-MNEMONIC`.

Cisco severity trong message header được ưu tiên hơn PRI severity. PRI facility
không bao giờ ghi đè Cisco facility. Message malformed vẫn có `parse_status=raw`
và được lưu nguyên văn.

## Persistence và migration

SQLite phía Python vẫn được chia thành `MessageRepository`, `DeviceStateRepository` và
`DeviceLookupRepository`. Message nhận được nằm trong
`info_collected.db.t12_syslog_messages`; nhiều cấu hình đích và trạng thái push
theo thiết bị nằm trong `device_network.db.t10_syslog_servers`. Ingestion native
ghi từng message đã parse và phát event sau commit. Migration thêm cột khi cần, giữ cột
compatibility `facility`, backfill dữ liệu cũ và copy một lần cấu hình từ bảng
legacy `t12_syslog_device_state` sang device DB. Migration không xóa bảng hoặc
row cũ.

## Cisco device configuration

Command builder và verifier là pure function. Worker là thành phần duy nhất thao
tác Cisco connection. Service kiểm tra thiết bị connected/đúng OS, tìm hoặc nhận
source-interface, apply command, verify running-config, save, verify
startup-config, sau đó mới cập nhật device-state repository. Cancel chỉ gỡ đúng
destination do ứng dụng quản lý.

Router, switch Layer 2 và switch Layer 3 dùng tab **Syslog Server** trong
workspace thiết bị. Một host có thể quản lý nhiều destination; Add/Edit/Delete/
Reload chỉ thay đổi desired state, còn **View & Push** preview rồi áp dụng toàn bộ
row `pending_apply`/`pending_delete`. Cấu hình mới mặc định dùng UDP/5514 và
`logging trap notifications` (severity 5), vì `warnings` (severity 4) không gửi
message `%SYS-5-CONFIG_I`. Màn System Logs ở activity bar không cấu hình thiết
bị: màn này bật/tắt một listener logic nhận đồng thời UDP+TCP, chọn host và lọc
theo nội dung, khoảng thời gian, severity hoặc transport trước khi xem log. Có
thể giới hạn N log gần nhất cho từng host, dùng Smart filter với cú pháp
`key:value`, xem hướng dẫn ngay trên thanh lọc và xuất chính xác tập row đang
hiển thị sang Excel. Listener/writer dùng
tiến trình C++ riêng và `info_collected.db`, không giữ session CLI của View & Push.

## Build và cấu hình native

```bash
native/syslog_collector/build.sh
```

Script dùng CMake, cài binary vào `bin/networktools-syslog-collector`. Listener
đọc `syslog.json` trong thư mục cấu hình ứng dụng. `SyslogSettings` tự migration
một lần các khóa Syslog cũ từ QSettings sang JSON. Thay đổi bind IP/port có hiệu
lực sau khi restart listener.

## Giới hạn hiện tại

TCP đang dùng newline framing; RFC6587 octet-counting và TLS chưa được bật. Module
chưa hướng tới Syslog đa hãng, RELP, SIEM hay alert engine phức tạp.
