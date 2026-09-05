# Kiến trúc cơ sở dữ liệu CAMS

Cập nhật: **2026-08-16**. Desktop app và backend kế thừa không dùng chung một
schema authority. Phần dưới mô tả chính xác schema của desktop trước, sau đó ghi
riêng ranh giới backend để không trộn tên bảng hoặc trạng thái.

## 1. Database của desktop

| File mặc định | Authority | Vai trò | Project `.ntp` |
| --- | --- | --- | ---: |
| `data/device_network.db` | `infrastructure/database/schemas/device_network/*.sql` | Inventory, desired state, trạng thái push | Có |
| `data/info_collected.db` | `infrastructure/database/schemas/info_collected/*.sql` | Dữ liệu quan sát và Syslog | Có |
| `data/app_state.db` | `recent_projects.py` | Recent project metadata | Không |

`CAMS_DATA_DIR` đổi thư mục mặc định. Khi project mở, các service được
route đến hai database giải nén trong workspace; khi đóng project, chúng quay về
database mặc định. `app_state.db` không đi theo workspace.

## 2. Build, bootstrap và upgrade

`scripts/build_databases.py` ghép các file SQL theo thứ tự tên, build vào file
tạm, bật foreign key, chạy `integrity_check` và `foreign_key_check`, sau đó thay
đích atomically.

Startup thực hiện ba thao tác không phá hủy:

1. tạo database bị thiếu;
2. migrate cột trạng thái số legacy `success` sang `connection_status` hoặc
   `sync_status`, đồng thời tạo backup `.pre-status-migration.bak`;
3. bổ sung table/index/trigger canonical bị thiếu vào DB hiện có.

Startup không drop bảng người dùng và không rebuild toàn bộ database đang có.
Thư mục `infrastructure/database/migrations/` dành cho migration có version nhưng
chưa có framework migration tổng quát; thay đổi không tương thích phải kèm code
upgrade và test riêng.

## 3. `device_network.db` — 73 bảng

| Nhóm | Bảng và trách nhiệm |
| --- | --- |
| `t01` | `t01_devices`, `t01_ssh_algo`: inventory, connection/dev flag và SSH override |
| `t02` | 5 bảng interface router: base name, L3, subinterface, tunnel, WAN |
| `t03` | 3 bảng DHCP: pool, excluded address, helper binding |
| `t04` | 19 bảng routing: static/default, OSPF, EIGRP và interface binding |
| `t05` | 20 bảng ACL/NAT: ACL/rules/bindings, route-map, NAT ACL và NAT engine |
| `t06` | 15 bảng switching: VLAN, port/trunk/access, STP, EtherChannel, security, push hash, SVI/L3 |
| `t08` | 6 bảng FHRP: group, member, HSRP/VRRP/GLBP options và track |
| `t09` | 3 bảng VTP: domain, switch membership và database mode |

Schema còn có 12 index khai báo và 16 trigger cho validation/updated timestamp.
SQLite tự tạo thêm internal index cho primary/unique key; chúng không được tính
vào số bảng.

### Quan hệ chính

```text
t01_devices(host)
  ├─ t01_ssh_algo
  ├─ t02_interface_name(iface_id)
  │    ├─ t02_router_iface_l3 / tunnel / wan
  │    ├─ t02_router_iface_subif
  │    ├─ t03_router_iface_helper
  │    └─ t04/t05 interface bindings
  ├─ t03 DHCP, t04 routing, t05 ACL/NAT
  ├─ t06 switching → VLAN/interface/SVI/security/push state
  ├─ t08_fhrp_groups → members → protocol options/tracks
  └─ t09_vtp_domains → switches → database modes
```

Delete/update cascade được định nghĩa ở schema tùy quan hệ. Repository vẫn phải
dùng transaction vì cascade không thay thế validation nghiệp vụ hoặc lifecycle
push.

### Trạng thái

`t01_devices.connection_status` dùng `waiting`, `connected`, `disconnected`.
Desired-state row dùng `pending_apply`, `synchronized`, `pending_delete`,
`skipped`. Switching phần lớn theo dõi cả module bằng
`t06_switch_push_state.payload_hash`; Port Security/SVI và member FHRP dùng
trạng thái theo row. Chi tiết ở
[`SCHEMA_LOGIC.md`](SCHEMA_LOGIC.md).

## 4. `info_collected.db` — 20 bảng

| Nhóm | Số bảng | Nội dung |
| --- | ---: | --- |
| `t08` | 1 | Routing table |
| `t09` | 5 | DHCP pool, binding, conflict, server statistics và database |
| `t10` | 5 | ACL collection, ACL/rules, interface binding và MAC ACL detail |
| `t11` | 7 | NAT collection, definitions, pool/static/dynamic, translation và statistics |
| `t12` | 2 | Syslog messages và device configuration state |

Database có 71 index khai báo để phục vụ host/time, collection state, lookup
DHCP/ACL/NAT và filter Syslog. Đây là observed/collected data; không dùng
`sync_status` để ra lệnh push. Retention hiện được triển khai rõ cho Syslog; các
collector khác cần policy snapshot/retention riêng khi được mở rộng.

## 5. Dữ liệu khác

- `backup/<host>/cfg`: Git object Dulwich và `running-config.txt`, không phải
  SQLite nhưng được đóng gói trong workspace.
- `snapshots/`: full-state snapshot của project với inventory/index riêng.
- `QSettings`: theme, window/menu/status bar, Syslog settings và SFTP profiles;
  không nằm trong project.
- SFTP password được lưu riêng bằng Windows DPAPI khi opt-in; profile JSON chỉ có
  cờ capability.
- `features/external_tools/cre_external_tools_db.py` là helper độc lập/legacy;
  composition root không coi một `external_tools.db` là database workspace.

## 6. Backend kế thừa

`archive/backend/sql/` và `archive/backend/PyCode/share/database/` chứa SQL/builder riêng. Một số
tên và map đã được cập nhật theo prefix `tNN_`, nhưng subsystem vẫn có path,
dependency và ownership riêng. Không lấy SQL backend để repair/migrate database
desktop và không để FastAPI/backend ghi đồng thời vào workspace đang mở.

Muốn hợp nhất phải có schema version chung, migration/backup, path injection,
locking/busy-timeout, auth/task contract và integration test API → fake worker →
DB. Xem [`BACKEND_APP_PARITY.md`](BACKEND_APP_PARITY.md) và
[`../archive/backend/README.md`](../archive/backend/README.md).

## 7. Bảo mật và vận hành

- Database được mã hóa toàn file bằng SQLCipher. Credential đăng nhập thiết bị
  còn được bọc riêng bằng RSA-OAEP + Fernet; PPP desired state hiện dựa vào lớp
  SQLCipher và chưa có field-level encryption riêng.
- SQLite browser thông thường không thể đọc database mã hóa; công cụ bảo trì
  phải hỗ trợ SQLCipher và chỉ nhận passphrase tương tác, không qua argv/config.
- Không commit DB/WAL/journal, backup, running-config, private key, Syslog hoặc
  workspace đã giải nén.
- Không chạy builder phá hủy trên DB cần giữ; dùng startup repair/migration hoặc
  bản sao có kiểm chứng.
