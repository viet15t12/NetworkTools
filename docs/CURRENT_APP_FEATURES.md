# Chức năng hiện có của CAMS App

Cập nhật: **2026-08-16**. Tài liệu này chỉ ghi những gì composition root
`main.py` thực sự đưa vào desktop. `implemented` nghĩa là có UI/service/test
cục bộ; không đồng nghĩa đã được chứng nhận production trên mọi thiết bị.

## 1. Project và shell ứng dụng

- Tạo/mở/đóng project `.ntp`, recent projects, Save/Save As chạy nền.
- Package version 1 có manifest/checksum, giới hạn giải nén, SQLite snapshot ổn
  định và thay file atomically.
- Mã hóa tùy chọn bằng Argon2id + AES-256-GCM; snapshot/rollback tạo safety
  snapshot trước khi phục hồi.
- Theme/system accent, window state, status bar, notification history và menu
  `Auto`/`Global`/`Custom` theo desktop environment.
- Welcome và workspace là hai top-level QML window; workspace chỉ load sau khi
  project active.

## 2. Thiết bị, session và cấu hình lưu trữ

- Inventory: thêm/sửa/xóa/tìm/nhập hàng loạt; role chuẩn `rou`, `sw2`, `sw3`.
- Per-device SSH algorithm override có opt-in và cảnh báo thuật toán legacy.
- Ping, Connect/Reconnect/Disconnect, Get running-config và batch tối đa mặc định
  5 host; lỗi một host không dừng host khác.
- Session automation được giữ theo host và serialize thao tác trên cùng CLI;
  đóng tab không đóng session.
- Save configuration lưu running-config thành startup-config qua capability của
  session đang mở; không tự kết nối ngầm.
- Lịch sử running-config theo host bằng Dulwich: HEAD, tối đa 100 commit ở UI,
  đọc snapshot và unified diff hai phiên bản.
- Manual Sys preview xung đột; chế độ an toàn giữ desired state chưa push.

## 3. Router và dịch vụ mạng

| Feature | Trạng thái | Phạm vi hiện có |
| --- | --- | --- |
| Router Interfaces | Implemented/giới hạn | Physical chỉ edit row đã sync; tạo/xóa Loopback, Tunnel, 802.1Q Subinterface; IPv4, secondary, L3/WAN; preview/push Cisco IOS SSH/Telnet |
| Static/Default route | Implemented | Form tách riêng, desired state, preview/push và sync parser |
| OSPF | Partial | Process, network, area/range, distance, redistribute, passive, interface và tuning; persistence/preview/push |
| EIGRP | Partial | Process, network, interface, passive, redistribute, distribute/offset list và key chain; persistence/preview/push |
| Routing Group | Implemented/giới hạn | Wizard đa host, lọc connected network, clone và preview/push độc lập theo host |
| FHRP | Implemented/giới hạn | HSRP/VRRP/GLBP đa member, lọc subnet/gateway, redaction secret và push Cisco IOS |
| DHCP | Implemented | Pool, excluded address, helper/relay, parser, preview/push |
| ACL | Implemented | Standard/extended/dynamic/reflexive/MAC, rule, nhiều interface binding, preview/push |
| NAT | Implemented | Static/dynamic, pool, PAT, inside/outside, NAT ACL, route-map, preview/push |

Worker Routing, DHCP, ACL và NAT hỗ trợ mô phỏng `dev = 1` không mở kết nối thật.
Không suy rộng dev-mode đó sang Interface, FHRP hoặc Switching.

## 4. Switching

- Workspace phân loại SW2/SW3; CRUD VLAN, switchport access/trunk, routed port,
  Port Security và SVI theo capability.
- Xem counter và MAC address table đã thu thập.
- Preview/Push Cisco IOS SSH/Telnet cho VLAN, switchport/EtherChannel, STP, VTP,
  DHCP Snooping/DAI và Port Security.
- Module L2 dùng hash desired payload; Port Security và SVI theo dõi per-row.
- Pull-sync hiện có VLAN, interface/trunk, EtherChannel và VTP status. Manual Sys
  giữ pending desired state trừ khi người dùng chọn `force_device_state`.
- Không thu thập `show vtp password` và không lưu password VTP quan sát từ thiết
  bị.

STP, VTP và EtherChannel chưa có trang CRUD riêng. Pull-sync STP/security/SVI,
NETCONF/RESTCONF, verify và rollback tự động chưa hoàn chỉnh. Xem
[`../features/switching/INTEGRATION_LIMITATIONS.md`](../features/switching/INTEGRATION_LIMITATIONS.md).

## 5. Quan sát và truyền file

### System Logs

- Một listener UDP hoặc TCP, bind/advertised IP tách biệt, parser giữ raw message,
  writer queue/batch, dropped counter, filter/keyset pagination và retention.
- Cấu hình/gỡ destination trên Cisco IOS/IOS-XE qua session đang kết nối; yêu cầu
  source interface nếu DB chưa biết.
- Chưa có TLS/RELP/multi-listener/alert engine. Xem [`SYSTEM_LOGS.md`](SYSTEM_LOGS.md).

### SFTP

- Client hai panel, profile, host-key confirmation SHA-256, password/private key,
  local/remote history, multi-selection và upload/download file/thư mục.
- Transfer queue có progress/cancel cooperative; create/rename/delete không đệ
  quy; Windows DPAPI là secure password store duy nhất hiện có.
- Có thể ưu tiên client SFTP ngoài; password không được đưa lên argv. Xem
  [`SFTP.md`](SFTP.md).

### Device Logs và tiện ích

- Device Logs dùng TShark cho capture/inspect trên interface được cấp quyền.
- Database Browser, catalog external SSH/Telnet/SFTP/terminal tool, system/network
  information và virtual-lab discovery best-effort.

## 6. Terminal

CAMS mở/focus terminal companion `cams-terminal` (fork Alacritty)
qua `QProcess` và NTTP/1 local IPC. Password không đi qua argv/environment/IPC;
Cisco IOS legacy có Paramiko PTY child riêng. Terminal tương tác không dùng chung
Netmiko session automation.

Manager/protocol và source fork đã có fake/contract test. Packaging, branding và
acceptance thực tế trên Fedora/Wayland/EVE-NG vẫn **partial**. Embedded
`qtpyTerminal-main` chỉ còn compatibility code, không được composition root dùng.

## 7. Không phải chức năng desktop hiện tại

- `archive/api_server.py` và dispatcher trong `archive/backend/` không được app khởi tạo, chưa có
  auth/task contract và không phải API sản phẩm.
- Topology discovery/draw.io, SNMP, Console Serial và plugin/provider API chưa có
  runtime/UI hoàn chỉnh.
- Packet-sniffer thử nghiệm trong backend không được tích hợp; tuyệt đối không
  dùng mã thu credential Telnet.
- Đa vendor và RESTCONF/NETCONF chỉ xuất hiện ở một số worker/template, không phải
  cam kết hỗ trợ end-to-end.

Đối chiếu subsystem cũ tại [`BACKEND_APP_PARITY.md`](BACKEND_APP_PARITY.md) và
xem mức kiểm chứng tại [`CODE_AUDIT.md`](CODE_AUDIT.md).
