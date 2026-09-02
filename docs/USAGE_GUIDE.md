# Hướng dẫn cài đặt và sử dụng CAMS

Cập nhật: **2026-08-16**. Hướng dẫn này dành cho desktop app trong `app/`.
`api_server.py`/`backend/` không phải bước cài đặt bắt buộc và không được khởi
chạy cùng workspace nếu chưa hoàn tất contract riêng.

## 1. Chuẩn bị và chạy app

Yêu cầu:

- Python 3.11 trở lên và `uv`;
- thư viện hệ thống Qt tương ứng trên Linux;
- TShark/Wireshark nếu dùng Device Logs;
- quyền truy cập hợp lệ tới thiết bị lab;
- Rust toolchain nếu cần tự build terminal companion vendored.

Từ `app/`:

```bash
./cams.sh
```

Trên Windows:

```bat
cams.bat
```

Launcher tương tác kiểm tra `uv`, sync dependency, thử Cython accelerator tùy
chọn, kiểm tra/build terminal companion rồi chạy app. Nếu chỉ muốn chạy môi
trường đã sẵn sàng:

```bash
./cams.sh run
```

Hoặc chạy trực tiếp:

```bash
uv run main.py
```

Database mặc định được tạo trong `app/data/`. Đặt `CAMS_DATA_DIR` trước
khi chạy để đổi vị trí. Không chạy nhiều instance cùng ghi một workspace.

## 2. Project `.ntp`

App mở màn hình Welcome trước. Chọn:

- **Create Project**: chọn file `.ntp`, tùy chọn password;
- **Open Project**: mở package có sẵn;
- **Recent Project**: mở nhanh đường dẫn đã lưu;
- **Save/Save As**: đóng gói database, backup và snapshot ở background;
- **Snapshot History**: tạo, xem và rollback snapshot.

Project mã hóa yêu cầu password mỗi lần mở; app không lưu password vào recent
list. Save kiểm tra xung đột file và thay atomically. Rollback tạo safety snapshot
trước. Luôn giữ bản sao ngoài ứng dụng trước thay đổi lớn.

## 3. Inventory và kết nối

1. Mở Devices, chọn **Add Device** hoặc `Ctrl+N`.
2. Nhập host, tên, protocol, port, username/password, OS và role `rou`/`sw2`/`sw3`.
3. Chỉ thêm SSH algorithm override khi thiết bị legacy thật sự cần; ghi lý do.
4. Lưu rồi dùng context menu để Ping, Connect/Reconnect hoặc **Up (Dev)**.
5. Mở tab thiết bị để thao tác feature; đóng tab không đóng session.

Chế độ multi-select bắt đầu từ context menu **Select multiple**, sau đó click host
để thêm/bỏ. Connect/Get running-config/Disconnect chạy song song giữa host nhưng
serialize trên cùng host. **Save configuration** chỉ dùng session đang mở và lưu
running-config thành startup-config nếu driver có capability; app không tự login.

`Up (Dev)` chặn connect/get-config thật. Routing, DHCP, ACL và NAT có mô phỏng
push; các feature khác có thể báo thiếu session thay vì giả thành công.

## 4. Desired state, Preview và Push

Quy trình an toàn:

1. chọn đúng host/role và mở feature;
2. nhập/lưu desired state;
3. dùng **View** để validate và xem lệnh; preview không kết nối;
4. kiểm tra secret đã được che, vendor/protocol và đối tượng bị gỡ;
5. lấy running-config và tạo backup trước khi Push;
6. Push, theo dõi task/status và xác minh lại trên thiết bị.

Các row lỗi giữ `pending_apply`/`pending_delete`; đừng sửa DB thủ công để đánh dấu
`synchronized`. Switching dùng hash theo module nên một lần View & Push có thể
bao gồm thay đổi STP/VTP/security không nằm trên trang đang mở.

### Router Interfaces

Physical chỉ edit interface đã thu thập. Loopback, Tunnel và Subinterface được
tạo/xóa qua form; backend sinh tên canonical. SVI/EtherChannel thuộc Switching.
Preview che PPP password. Hiện chỉ cam kết Cisco IOS SSH/Telnet, IPv4 và phạm vi
ghi trong [`../app/features/interfaces/README.md`](../app/features/interfaces/README.md).

### Routing và FHRP

- Static và Default Route có form tách riêng.
- OSPF/EIGRP cho process và các child option; xem README protocol trước khi dùng
  tùy chọn chưa được lab-test.
- Routing Group chọn nhiều host, nhập identity riêng và network phù hợp từng host.
- FHRP yêu cầu ít nhất hai member có interface cùng subnet với virtual gateway;
  authentication secret được che trong preview/report.

### DHCP, ACL và NAT

DHCP quản lý pool/excluded/helper; ACL quản lý ACL/rule/interface binding; NAT
quản lý static/dynamic/PAT, inside/outside, NAT ACL và route-map. Các feature này
có dev-mode worker. Mọi địa chỉ/mask/range/reference phải qua validation; không
chỉnh quan hệ cha-con trực tiếp bằng Database Browser.

### Switching

Workspace hỗ trợ VLAN, switchport/access/trunk/EtherChannel, Port Security, SVI
và monitoring đã thu thập. Layer 2 View & Push còn bao gồm STP, VTP và DHCP
Snooping/DAI từ DB. Pull-sync chỉ đầy đủ cho VLAN/interface/EtherChannel/VTP; xem
[`../app/features/switching/INTEGRATION_LIMITATIONS.md`](../app/features/switching/INTEGRATION_LIMITATIONS.md).

## 5. Running-config history và Manual Sys

Get running-config tạo commit Dulwich theo host rồi chạy policy sync theo role.
Information View cho xem HEAD, lịch sử và diff hai commit mà không checkout.

Manual Sys hiển thị conflict giữa snapshot thiết bị và desired state. Chọn chế độ
an toàn để giữ row pending; chỉ chọn dùng trạng thái thiết bị khi đã hiểu dữ liệu
sẽ bị thay đổi. Backup là dữ liệu nhạy cảm và nằm trong project.

## 6. System Logs

1. Vào Settings → System Logs.
2. Chọn UDP hoặc TCP, bind IP, advertised IP, port và retention.
3. Validate; dùng port 5514 trong lab nếu không muốn quyền privileged port.
4. Start listener từ Activity Bar/control bar.
5. Với thiết bị connected, dùng sidebar context menu để cấu hình destination.
6. Filter theo host/severity/search; Pause chỉ dừng UI, Clear View không xóa DB.

Không expose listener ra Internet; implementation chưa có TLS/RELP. Xem
[`SYSTEM_LOGS.md`](SYSTEM_LOGS.md).

## 7. SFTP

1. Mở SFTP từ Activity Bar; nếu External Tools có client active, app thử mở client
   đó và fallback về client tích hợp khi thất bại.
2. Nhập host/port/username và password hoặc private key.
3. Với host mới, xác minh fingerprint SHA-256 bằng kênh độc lập rồi mới Accept.
4. Duyệt local/remote, chọn file/folder và Upload/Download; theo dõi queue.
5. Cancel là cooperative; kiểm tra file đích sau task lỗi/hủy.

Folder delete không đệ quy. Lưu password tắt mặc định và chỉ có Windows DPAPI;
ưu tiên key/agent. Xem [`SFTP.md`](SFTP.md).

## 8. Terminal, external tools và Device Logs

- `Ctrl+\`` hoặc action terminal mở/focus `cams-terminal`. Terminal là
  process riêng, SSH tương tác riêng và không dùng session automation.
- Nếu companion thiếu, đặt `CAMS_TERMINAL_BINARY` hoặc chạy
  `./cams.sh terminal-build`; integration vẫn partial.
- External Tools chỉ mở executable đã xác thực; URL catalog không tự cài app và
  `{password}` bị cấm.
- Device Logs/TShark chỉ dùng trên interface/mạng được cấp phép. Không dùng mã
  packet-sniffer legacy để thu credential.

## 9. Kiểm tra và xử lý sự cố

Từ `app/`:

```bash
uv run python scripts/validate_structure.py
uv run python -m compileall .
uv run python -m unittest discover -s tests -v
```

Nếu app không thấy DB, chạy app một lần để bootstrap hoặc kiểm tra
`CAMS_DATA_DIR`. Nếu QML không tải trên Linux, kiểm tra Qt platform/QML
libraries của đúng PyQt wheel. Nếu terminal thiếu, chạy `terminal-check`. Nếu
thiết bị Cisco legacy lỗi SSH, chỉ bật đúng algorithm override cần thiết thay vì
hạ crypto policy toàn hệ thống.

## 10. Backend/API kế thừa

Không cần chạy `api_server.py` để dùng desktop. Backend chưa có dependency/entry
point/auth/task contract độc lập và không được ghi vào workspace đang mở. Nếu
nghiên cứu chuyển feature, đọc [`../backend/README.md`](../backend/README.md) và
[`BACKEND_APP_PARITY.md`](BACKEND_APP_PARITY.md), dùng fake device/DB tạm trước
khi chạm lab.

## 11. An toàn dữ liệu

- Không commit `.ntp`, DB/WAL/journal, backup/running-config, Syslog, pcap,
  credential, private key hoặc log chứa thông tin thật.
- Chỉ cấu hình/capture trên hệ thống được cấp quyền.
- Project encryption không bảo vệ plaintext trong memory/temp directory khi app
  đang mở; khóa workstation và bảo vệ tài khoản hệ điều hành.
- Preview không thay thế backup, peer review, maintenance window, verify và kế
  hoạch rollback ngoài ứng dụng.
