# Logic schema và trạng thái đồng bộ

Cập nhật: **2026-08-16**. Tài liệu này mô tả schema mà desktop app thực sự nạp
từ `infrastructure/database/schemas/`. Đây là nguồn tham chiếu cho code mới;
các SQL trong `archive/backend/` chỉ phục vụ subsystem kế thừa và không phải schema của
workspace desktop.

## 1. Nguồn dữ liệu và quá trình khởi tạo

Desktop dùng ba database:

| Database | Nội dung | Nằm trong project `.ntp` |
| --- | --- | ---: |
| `device_network.db` | Inventory, desired state và trạng thái push | Có |
| `info_collected.db` | Routing/DHCP/ACL/NAT đã thu thập và Syslog | Có |
| `app_state.db` | Danh sách project gần đây | Không |

Path mặc định do `infrastructure/database/paths.py` định nghĩa và có thể đổi bằng
`CAMS_DATA_DIR`. `scripts/build_databases.py` đọc các file SQL theo thứ
tự tên, build qua file tạm, bật foreign key, kiểm tra integrity/foreign key rồi
thay đích atomically. Khi khởi động, app tạo database còn thiếu, bổ sung object
schema còn thiếu và migrate trạng thái số cũ; app không rebuild phá hủy dữ liệu.

Schema hiện có **72 bảng** trong `device_network.db` và **20 bảng** trong
`info_collected.db`. Danh sách và quan hệ đầy đủ nằm tại
[`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md).

## 2. Hai loại trạng thái không được trộn

### `connection_status`

Chỉ thuộc `t01_devices` và nhận ba giá trị:

| Giá trị | Ý nghĩa |
| --- | --- |
| `waiting` | Chưa có session thật; đây là mặc định |
| `connected` | Registry đang sở hữu session hoạt động |
| `disconnected` | Session đã đóng hoặc kết nối thất bại |

Không dùng `connection_status` để suy ra một cấu hình đã được push.

### `sync_status` / `success`

Các row desired state dùng một trong hai tên cột với cùng vòng đời. Các feature
router cũ dùng `sync_status`; Switching L2 dùng trực tiếp `success`:

| Giá trị | Ý nghĩa và hành động |
| --- | --- |
| `pending_apply` | Cần render và áp dụng lên thiết bị |
| `synchronized` | Thiết bị đã chấp nhận batch tương ứng |
| `pending_delete` | Cần gửi lệnh gỡ; chỉ xóa row sau khi thành công |
| `skipped` | Row được giữ nhưng không tham gia lần push hiện tại |

Vòng đời chuẩn:

```text
create/edit → pending_apply → push thành công → synchronized
delete synchronized → pending_delete → push gỡ thành công → DELETE row
delete pending_apply → DELETE row ngay vì thiết bị chưa từng nhận cấu hình
push lỗi → giữ nguyên trạng thái pending để thử lại
```

Worker không được chuyển trạng thái dựa trên việc đã tạo preview. Preview chỉ
validate và render, không mở transport. Mọi cập nhật sau push phải nằm trong
transaction và chỉ áp dụng cho đúng row/module được report thành công.

## 3. Bảng dùng trạng thái theo row

Các nhóm sau có `sync_status`:

- `t02_*`: interface nền, L3, subinterface, tunnel và WAN;
- `t03_*`: DHCP pool, excluded address và helper;
- `t04_*`: static/default route, OSPF và EIGRP;
- `t05_*`: ACL, NAT ACL, route-map, NAT và các row con;
- `t06_iface_port_security`, `t06_svi_interface`;
- `t08_fhrp_members`, `t08_fhrp_tracks`;
- `t09_vtp_switches`.

Không phải mọi bảng cha đều có trạng thái. Ví dụ FHRP group/options là metadata
chung; member và track mới là đơn vị được render/push. VTP domain/mode là desired
state chung, còn `t09_vtp_switches` theo dõi áp dụng theo thiết bị.

### Edit identity và edit option

- Khi identity CLI thay đổi (tên ACL, process, route, interface ảo...), repository
  phải bảo toàn đủ dữ liệu để worker gỡ identity cũ rồi áp dụng identity mới.
- Khi chỉ thay option có thể ghi đè, repository có thể cập nhật cùng row và đặt
  `pending_apply`.
- Không tự áp dụng mẫu “delete + insert” nếu repository/service của feature đã có
  transaction riêng; xem implementation và test của feature đó.

## 4. Đồng bộ theo cột `success` của Switching

Layer 2 không push lại toàn bộ module khi chỉ một đối tượng thay đổi.
`features/switching` tách desired state thành task theo VLAN, interface,
Port-channel, STP policy, VTP database và từng policy bảo mật. Controller truy
vấn trực tiếp row nghiệp vụ có `success IN ('pending_apply','pending_delete')`.

```text
create/edit row → success = pending_apply → preview/push đúng row
                                      ├─ thiết bị thành công: synchronized
                                      └─ thiết bị lỗi: giữ pending để retry
```

Các module giao diện là `vlan`, `interfaces`, `etherchannel`, `stp`, `vtp`,
`l2_security` và `port_security`. Preview chỉ render các task pending của module
được yêu cầu và preview không thay đổi trạng thái. Kết quả worker có trường
boolean `success`; transaction chỉ cập nhật đúng row của task thành
`synchronized` sau khi thiết bị chấp nhận lệnh. Không dùng hash hoặc bảng trạng
thái song song. `sync_status` còn tồn tại ở Port Security và VTP chỉ là cột tương
thích; luồng SWL2 đọc `success` và giữ hai cột đồng nhất khi ghi các row này.

## 5. `action`, `action_Cfg` và bitmask

Ba khái niệm có tên gần nhau nhưng khác nhau:

- `action` kiểu `TEXT` trong ACL/rule/route-map là hành động CLI như `permit` hoặc
  `deny`; đây **không phải bitmask**.
- `t04_eigrp_processes.action` là bitmask `INTEGER` kế thừa, mặc định `15`.
- `action_Cfg` đánh dấu nhóm option có thể cập nhật trực tiếp.

Các cột `action_Cfg` hiện hành:

| Bảng | Kiểu/mặc định | Nhóm option |
| --- | --- | --- |
| `t02_router_iface_l3` | `TEXT '11111'` | speed, duplex, negotiation, IP flags, secondary |
| `t02_router_iface_tunnel` | `TEXT '111'` | option tunnel |
| `t02_router_iface_wan` | `TEXT '11'` | option WAN/PPP |
| `t03_dhcp_pool` | `TEXT '111'` | default-router, DNS, lease |
| `t04_eigrp_processes` | `TEXT '1111111'` | option process EIGRP |
| `t05_ACL_DB` | `INTEGER 1` | description/remark |
| `t05_NAT_ACL_DB` | `INTEGER 1` | description |
| `t05_NAT_DB` | `INTEGER 1` | description |

Với chuỗi bit, bit ngoài cùng bên phải là bit 0. Mọi thay đổi mapping phải sửa
đồng thời schema, repository, collector/template, dispatcher và test; không suy
diễn mapping chỉ từ độ dài chuỗi.

## 6. Cờ `dev`

`t01_devices.dev` là số nguyên `0/1`:

- `0`: thiết bị thật; use case có thể mở hoặc tái sử dụng session;
- `1`: thiết bị dev; connect/running-config thật bị chặn fail-closed.

Routing, DHCP, ACL và NAT có worker mô phỏng dev-mode: không login, không gửi
lệnh nhưng tạo report thành công để kiểm tra pipeline UI → DB → worker → cập nhật
trạng thái. Router Interfaces, FHRP, Switching, Syslog device configuration,
SFTP và terminal không được mặc định coi là mô phỏng thành công; nếu thiếu
session/capability, chúng phải báo lỗi và giữ desired state.

Nếu việc đọc cờ `dev` thất bại, worker có hỗ trợ dev-mode phải fail-closed, không
được đẩy host nào sang transport thật. Cờ này không thay đổi username, password,
protocol hay port và không phải một cơ chế phân quyền.

## 7. Thu thập thiết bị và bảo vệ desired state

`features/config_sync` chọn pipeline theo `role`:

- router: parse running-config, interface brief và đồng bộ interface/routing;
- switch: đồng bộ VLAN, switchport/trunk, EtherChannel và trạng thái VTP được hỗ
  trợ;
- Manual Sync có preview xung đột. Chế độ an toàn giữ row đang pending; chỉ
  `force_device_state` mới cho phép dùng snapshot thiết bị làm nguồn.

Dữ liệu operational/observed đi vào `info_collected.db` hoặc các bảng trạng thái
được chỉ định. Không ghi đè desired state đang pending chỉ vì một lần thu thập.

## 8. Checklist thay đổi schema

1. Sửa file SQL canonical trong `infrastructure/database/schemas/`.
2. Thêm migration không phá hủy cho database đã tồn tại nếu cần.
3. Cập nhật model/repository/collector/worker và QML consumer liên quan.
4. Thêm test build schema sạch, upgrade schema cũ, foreign key và lifecycle
   `sync_status`.
5. Cập nhật tài liệu này và `docs/DATABASE_SCHEMA.md`.
6. Chạy `uv run python scripts/validate_structure.py` và test liên quan.

Không sửa aggregate SQL đã sinh, không thêm database runtime/WAL/journal vào Git,
và không dùng schema kế thừa trong `archive/backend/` để thay thế schema desktop.
