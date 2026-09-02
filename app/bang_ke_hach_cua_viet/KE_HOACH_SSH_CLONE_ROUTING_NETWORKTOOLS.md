# KẾ HOẠCH ỔN ĐỊNH SSH LEGACY, CLONE OSPF/EIGRP VÀ ĐỒNG BỘ ROUTING

## 1. Thông tin đánh giá

- Repository: `ntdatphu/CAMS`
- Nhánh đánh giá: `main`
- Commit được rà soát: `b5e88361cb2ecf72641bdfb3ab0f5dd19fb0bcd0`
- Ngày lập kế hoạch: `2026-07-25`
- Phạm vi:
  - SSH algorithm override theo từng thiết bị.
  - Ổn định chức năng Clone OSPF/EIGRP.
  - Bổ sung đồng bộ Static Route và Default Route từ running-config.
  - Bảo đảm tương thích với Netmiko, Paramiko, Nornir và luồng View & Push hiện tại.

---

## 2. Kết luận rà soát hiện trạng

### 2.1. SSH override

Luồng kết nối trực tiếp của ứng dụng hiện nằm tại:

- `app/infrastructure/network/device_connector.py`

Trong `DeviceConnector.connect()`, ứng dụng xây dựng `device_params` rồi gọi trực tiếp:

```python
self.connection = ConnectHandler(**device_params)
```

Tuy nhiên repository còn có các worker sử dụng Netmiko/Nornir ở ngoài `DeviceConnector`. Vì vậy, nếu chỉ sửa `device_connector.py`, override SSH có thể hoạt động trong terminal hoặc luồng đăng nhập nhưng không chắc được áp dụng cho các luồng Push Routing, NAT, DHCP, ACL và các worker khác.

### 2.2. Database builder

Schema runtime chính hiện được xây dựng từ:

```text
app/infrastructure/database/schemas/device_network/*.sql
```

Script:

```text
app/scripts/build_databases.py
```

đã tự động đọc toàn bộ file `*.sql` theo thứ tự tên file. Do đó:

- Không cần thêm tên bảng vào một danh sách thủ công trong builder.
- Chỉ cần thêm file schema đúng thư mục và đúng thứ tự.
- `ensure_runtime_databases()` có khả năng tạo object còn thiếu cho database đang tồn tại.

Khuyến nghị thêm file:

```text
app/infrastructure/database/schemas/device_network/01_ssh_algorithms.sql
```

File này sẽ được chạy sau `01_core_devices.sql`, bảo đảm bảng `t01_devices` đã tồn tại trước khi tạo foreign key.

### 2.3. Clone OSPF/EIGRP

Các thành phần chính:

```text
app/features/routing/clone_service.py
app/core/database/routing_slots.py
app/UI/qml/features/routing/RoutingCloneDialog.qml
app/UI/qml/features/routing/RoutingBatchViewPushDialog.qml
```

Các vấn đề đáng chú ý:

1. Danh sách target lấy toàn bộ thiết bị `success = 1` nhưng không loại source host.
2. QML bắt buộc Router ID hợp lệ cho mọi target, trong khi schema và backend cho phép Router ID để trống.
3. Router ID của source được sao chép mặc định sang tất cả target, dễ tạo nhiều router có cùng Router ID.
4. Mỗi lần sửa Process ID, dialog lặp qua target và gọi database để kiểm tra duplicate từng host; đây là mô hình N+1 query và có thể làm UI chậm.
5. Backend xác định source bằng `source_index`; index không phải định danh ổn định nếu model reload hoặc thứ tự process thay đổi.
6. Clone một process hiện tải toàn bộ process của target, append process mới rồi gọi hàm save toàn bộ payload. Cách này làm phạm vi tác động lớn hơn cần thiết.
7. Cấu hình per-interface của source có thể tham chiếu interface không tồn tại trên target.
8. Preview nhiều target đang được tạo tuần tự trên QML main thread.

### 2.4. Đồng bộ routing

Luồng hiện tại:

```text
app/features/config_sync/service.py
    -> app/features/devices/sync_state.py
```

`sync_state.py` hiện chỉ phân tích và đồng bộ:

- Hostname.
- Interface.
- OSPF.

Parser top-level hiện nhận `router ospf ...`, nhưng chưa nhận:

- `ip route ...`
- `router eigrp ...`

`sync_device_state()` hiện chỉ gọi:

```python
sync_interfaces(...)
sync_ospf_processes(...)
```

Do đó Static Route và Default Route chưa được đồng bộ từ running-config.

Ngoài ra, `sync_ospf_processes()` xóa toàn bộ OSPF process của host trước khi insert snapshot mới. Nếu database đang có cấu hình local `success = 0` chưa push hoặc `success = -1` chờ xóa, đồng bộ có thể xóa mất pending changes.

---

## 3. Nguyên tắc triển khai

1. Không tự động bật thuật toán yếu cho mọi thiết bị.
2. Không có bản ghi override hoặc mọi cột đều `NULL` thì giữ nguyên luồng mặc định.
3. Override phải áp dụng theo từng kết nối, không sửa global state của Paramiko.
4. Mọi giá trị từ DB phải được chuẩn hóa, loại trùng và kiểm tra trước khi mở socket.
5. Đồng bộ running-config không được âm thầm xóa pending changes trong DB.
6. Clone phải tác động tối thiểu lên target và trả kết quả riêng cho từng host.
7. Các thay đổi phải có contract test trước khi nối UI.

---

# PHẦN A — SSH ALGORITHM OVERRIDE

## 4. Thiết kế database

### 4.1. Schema đề xuất

Tạo file:

```text
app/infrastructure/database/schemas/device_network/01_ssh_algorithms.sql
```

Nội dung:

```sql
-- ==========================================================
-- SSH ALGORITHM OVERRIDE
-- Chỉ dùng cho thiết bị legacy, quan hệ 1-1 với t01_devices.
-- ==========================================================
CREATE TABLE IF NOT EXISTS t01_ssh_algo (
    host                 TEXT PRIMARY KEY,
    kex_algorithms       TEXT,
    host_key_algorithms  TEXT,
    ciphers              TEXT,
    macs                 TEXT,
    note                 TEXT,
    FOREIGN KEY (host) REFERENCES t01_devices(host)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);
```

### 4.2. Quy ước dữ liệu

- Danh sách thuật toán phân cách bằng dấu phẩy.
- Trim khoảng trắng ở đầu/cuối.
- Loại bỏ phần tử rỗng.
- Loại trùng nhưng giữ thứ tự nhập.
- Override được prepend vào danh sách mặc định, không thay thế toàn bộ.
- Cột `NULL` hoặc chuỗi rỗng: không override nhóm đó.
- Không có row: dùng hoàn toàn mặc định.
- Không lưu cấu hình legacy mặc định vào mọi host.

### 4.3. Không sửa builder không cần thiết

`app/scripts/build_databases.py` đã glob toàn bộ `*.sql`. Việc cần làm là:

- Thêm schema file.
- Thêm test xác nhận builder tạo được bảng.
- Thêm test xác nhận `ensure_runtime_databases()` repair được bảng thiếu.
- Không thêm logic đặc thù `t01_ssh_algo` vào builder.

### 4.4. Schema legacy trùng lặp

Repository còn có schema cũ dưới `backend/PyCode/share/database/...`.

Quy tắc:

- `app/infrastructure/database/schemas/...` là canonical schema cho app mới.
- Chỉ mirror sang backend legacy nếu kiểm tra runtime chứng minh backend cũ vẫn được chạy.
- Không cập nhật hai nơi bằng tay mà không có test chống schema drift.

---

## 5. Kiến trúc SSH override đề xuất

### 5.1. Không dùng monkey-patch class-level làm phương án chính

Không nên dùng trực tiếp:

```python
paramiko.Transport._preferred_kex = ...
```

làm kiến trúc production vì:

- Đây là private API.
- Giá trị nằm ở class-level, ảnh hưởng mọi thread.
- Nornir và background task có thể kết nối nhiều host song song.
- Khóa chỉ quanh `ConnectHandler()` không bảo đảm preference tồn tại cho rekey về sau.
- Một exception hoặc đường thoát không dự kiến có thể làm global state sai.
- Upgrade Paramiko có thể đổi tên hoặc cách sử dụng private attribute.

### 5.2. Phương án chính: Transport riêng cho từng connection

Tạo module:

```text
app/infrastructure/network/ssh_algorithms.py
```

Các thành phần:

```python
@dataclass(frozen=True)
class SshAlgorithmOverride:
    kex: tuple[str, ...] = ()
    key_types: tuple[str, ...] = ()
    ciphers: tuple[str, ...] = ()
    digests: tuple[str, ...] = ()
```

Mapping DB sang Paramiko SecurityOptions:

| Database | Paramiko `SecurityOptions` |
|---|---|
| `kex_algorithms` | `kex` |
| `host_key_algorithms` | `key_types` |
| `ciphers` | `ciphers` |
| `macs` | `digests` |

Dùng `transport_factory` của Paramiko để tạo một `Transport` riêng, sau đó chỉnh `SecurityOptions` trước khi negotiation bắt đầu:

```python
def make_transport_factory(override):
    def factory(sock, **kwargs):
        transport = paramiko.Transport(sock, **kwargs)
        options = transport.get_security_options()
        options.kex = merge_preferred(override.kex, options.kex)
        options.key_types = merge_preferred(override.key_types, options.key_types)
        options.ciphers = merge_preferred(override.ciphers, options.ciphers)
        options.digests = merge_preferred(override.digests, options.digests)
        return transport
    return factory
```

Ưu điểm:

- Không sửa global state.
- Mỗi host có cấu hình riêng.
- Hoạt động an toàn khi chạy song song.
- Preference tiếp tục thuộc Transport đó khi rekey.
- Có thể unit test độc lập.

### 5.3. Tích hợp Netmiko

Netmiko hiện không nhận `transport_factory` như một tham số public của `ConnectHandler`. Cần tạo adapter riêng:

```text
app/infrastructure/network/netmiko_factory.py
```

Hướng triển khai:

1. Tạo subclass từ driver Netmiko tương ứng, trước mắt là Cisco IOS.
2. Override `_connect_params_dict()`.
3. Gọi `super()._connect_params_dict()`.
4. Nếu có override, thêm `transport_factory` vào dictionary Paramiko connect.
5. Nếu không có override, không thêm gì và giữ nguyên hành vi cũ.

Pseudo-code:

```python
class CAMSCiscoIosSSH(CiscoIosSSH):
    def __init__(self, *args, ssh_algorithm_override=None, **kwargs):
        self._ssh_algorithm_override = ssh_algorithm_override
        super().__init__(*args, **kwargs)

    def _connect_params_dict(self):
        params = super()._connect_params_dict()
        if self._ssh_algorithm_override:
            params["transport_factory"] = make_transport_factory(
                self._ssh_algorithm_override
            )
        return params
```

Tạo factory duy nhất:

```python
connect_device(device_params, db_path)
```

Quy tắc:

- Telnet: không đọc và không áp dụng SSH override.
- SSH không có override: gọi đường cũ.
- SSH có override: dùng Netmiko subclass tương ứng.
- Platform chưa có subclass: trả lỗi rõ ràng, không monkey-patch ngầm.

### 5.4. Tích hợp Nornir

Các worker dùng `nornir-netmiko` phải dùng cùng một connection factory.

Phương án đề xuất:

- Tạo Nornir connection plugin riêng, ví dụ `cams_netmiko`.
- Plugin đọc SSH override theo host và mở connection qua `netmiko_factory.py`.
- Đăng ký plugin một lần khi khởi tạo runtime.
- Routing, DHCP, NAT, ACL và các module push dùng cùng plugin.

Không nên chỉ sửa `DeviceConnector`, vì như vậy Terminal có thể kết nối được nhưng View & Push vẫn thất bại.

### 5.5. Repository đọc cấu hình

Tạo:

```text
app/features/devices/ssh_algorithm_repository.py
```

API tối thiểu:

```python
get_ssh_algorithm_override(db_path, host) -> SshAlgorithmOverride | None
save_ssh_algorithm_override(db_path, host, payload) -> Result
clear_ssh_algorithm_override(db_path, host) -> Result
```

Không truyền raw SQLite connection từ UI xuống tầng network.

### 5.6. Validation

Trước khi mở kết nối:

- Kiểm tra tên thuật toán có nằm trong tập thuật toán Paramiko hỗ trợ.
- Không chỉ kiểm tra trong preferred list hiện tại, vì thuật toán có thể được hỗ trợ nhưng không ưu tiên mặc định.
- Nếu phải đọc registry private của Paramiko, cô lập trong một compatibility adapter duy nhất.
- Log phiên bản Paramiko, Netmiko và Python trong diagnostic output.
- Không log password hoặc secret.

Lỗi phải phân biệt:

```text
UNSUPPORTED_ALGORITHM
NO_MATCHING_KEX
NO_MATCHING_HOST_KEY
NO_MATCHING_CIPHER
NO_MATCHING_MAC
CRYPTO_BACKEND_REJECTED
AUTHENTICATION_FAILED
CONNECTION_TIMEOUT
```

### 5.7. UI

Thêm section vào form thiết bị:

```text
SSH Compatibility — Legacy devices only
```

Fields:

- KEX Algorithms.
- Host Key Algorithms.
- Ciphers.
- MACs.
- Note.

Hành vi:

- Mặc định tất cả rỗng.
- Hiển thị cảnh báo thuật toán yếu.
- Có nút `Test SSH`.
- Có nút `Reset to default` để xóa row.
- Không tự động đề xuất `group1`, `3des` hoặc SHA-1 cho thiết bị mới.

### 5.8. Fallback tạm thời

Nếu chưa kịp xây Netmiko subclass/Nornir plugin, có thể dùng class-level patch với một `threading.RLock` toàn cục, nhưng phải ghi rõ:

- Chỉ là compatibility bridge.
- Mọi kết nối SSH, kể cả host không override, phải đi qua cùng lock.
- Không chạy song song trong thời gian lock.
- Có test restore state khi exception.
- Có issue kỹ thuật để xóa fallback sau khi per-instance Transport hoàn tất.

Không dùng nhiều lock theo host vì Paramiko state bị sửa là global, không phải per-host.

---

# PHẦN B — ỔN ĐỊNH CLONE OSPF/EIGRP

## 6. Thiết kế lại contract backend

### 6.1. Không dùng source index

Thay:

```text
source_index
```

bằng định danh ổn định:

- OSPF: `ospf_id` hoặc cặp `(host, process_id)`.
- EIGRP: `eigrp_id` hoặc cặp `(host, as_number)`.

Ưu tiên database ID nội bộ để tránh lỗi khi model đổi thứ tự.

### 6.2. Không save toàn bộ target payload

Tạo repository clone chuyên dụng:

```text
app/features/routing/clone_repository.py
```

Mỗi target chạy một transaction chỉ làm:

1. Xác nhận target tồn tại và `success = 1`.
2. Xác nhận Process ID/AS chưa tồn tại.
3. Đọc duy nhất source process cần clone.
4. Chuẩn hóa payload.
5. Insert process mới và child rows.
6. Commit.

Không gọi `save_ospf_routing()` hoặc `save_eigrp_routing()` với toàn bộ process list của target.

Mục tiêu là bảo đảm clone không làm archive hoặc sửa process khác trên target.

### 6.3. Target list

Mặc định loại source host khỏi danh sách target:

```sql
SELECT host
FROM t01_devices
WHERE success = 1 AND host <> ?
ORDER BY host;
```

Không cho clone ngược vào chính source trong luồng chuẩn.

### 6.4. Router ID

Thay đổi UI:

- Router ID là optional.
- Không copy Router ID source sang mọi target.
- Giá trị mặc định trên target là rỗng.
- Chỉ validate IPv4 khi field không rỗng.
- Nếu người dùng nhập cùng Router ID cho nhiều target, cảnh báo trước khi Save.

Không tự suy đoán Router ID từ IP quản trị nếu không có quy tắc rõ ràng.

### 6.5. Kiểm tra interface compatibility

Trước clone, backend trả về:

```json
{
  "missingInterfaces": [],
  "matchedInterfaces": [],
  "conflictingProcessId": false,
  "conflictingRouterId": false
}
```

Chính sách mặc định:

- Process-level settings, networks, redistribute, passive settings: có thể clone.
- Per-interface setting chỉ clone khi target có interface cùng tên.
- Nếu thiếu interface, không insert `NULL iface_id`.
- UI cho chọn:
  - `Block this target` — mặc định an toàn.
  - `Clone process only` — bỏ qua per-interface settings.

Không tự map `GigabitEthernet0/0` sang `Ethernet0/0`.

### 6.6. Batch validation

Thay N lần gọi:

```text
routingCloneProcessExists(host, protocol, process_id)
```

bằng một slot batch:

```python
validateRoutingCloneTargets(
    source_host,
    protocol,
    source_process_id,
    targets
) -> list[TargetValidationResult]
```

Chỉ gọi khi:

- Mở dialog.
- Đổi source process.
- User dừng nhập Process ID trong một khoảng debounce ngắn.
- Bấm Save.

Backend vẫn phải validate lại trong transaction để chống race condition.

### 6.7. Kết quả clone

Return format thống nhất:

```json
{
  "ok": false,
  "partial": true,
  "successful": ["R2"],
  "failed": [
    {
      "host": "R3",
      "code": "PROCESS_EXISTS",
      "reason": "OSPF process 10 already exists"
    }
  ]
}
```

Các error code:

```text
TARGET_NOT_CONNECTED
SOURCE_PROCESS_NOT_FOUND
PROCESS_EXISTS
ROUTER_ID_CONFLICT
MISSING_INTERFACE
INVALID_PROCESS_ID
INVALID_ROUTER_ID
DATABASE_ERROR
```

### 6.8. Save và Save & Push

- `Save`: insert dữ liệu với `success = 0`.
- `Save & Push`: chỉ mở preview cho target clone thành công.
- Nếu target clone thất bại, không đưa target đó vào push queue.
- Sau push, báo riêng succeeded/failed theo host.
- Không tự đánh dấu `success = 1` chỉ vì connection thành công; phải dựa trên kết quả task/persistence hiện có.

### 6.9. Preview bất đồng bộ

`RoutingBatchViewPushDialog.openPreview()` hiện preview tuần tự trong QML.

Cải tiến:

- Dùng `previewViewPushAsync()` hoặc một batch preview task.
- Hiển thị trạng thái từng host.
- Cho phép Push các host preview thành công, không chặn toàn bộ batch vì một host lỗi.

---

# PHẦN C — ĐỒNG BỘ STATIC ROUTE VÀ DEFAULT ROUTE

## 7. Mở rộng parser running-config

### 7.1. Return model mới

Thay return hiện tại:

```python
hostname, interfaces, ospf_processes
```

bằng dataclass hoặc dict có tên trường:

```python
ParsedRouterConfig(
    hostname=...,
    interfaces=...,
    static_routes=...,
    default_routes=...,
    ospf_processes=...,
    eigrp_processes=...,
    unsupported_routes=...,
)
```

Không tiếp tục mở rộng tuple theo vị trí.

### 7.2. Static route MVP

Hỗ trợ trước các dạng phù hợp schema hiện tại:

```text
ip route <network> <mask> <next-hop>
ip route <network> <mask> <next-hop> <administrative-distance>
```

Ví dụ:

```text
ip route 10.10.0.0 255.255.0.0 192.168.1.2
ip route 10.20.0.0 255.255.0.0 192.168.1.2 10
```

Map vào:

```text
t04_static_routes.network
t04_static_routes.subnet_mask
t04_static_routes.next_hop
t04_static_routes.ad
```

### 7.3. Default route MVP

Nhận:

```text
ip route 0.0.0.0 0.0.0.0 <next-hop>
```

Map vào:

```text
t04_static_default_routes.next_hop_ip
```

Không nhầm với:

```text
ip default-gateway ...
```

### 7.4. Các dạng chưa biểu diễn được trong schema

Schema hiện tại chưa biểu diễn đầy đủ:

- Exit-interface-only route.
- Exit interface kết hợp next-hop.
- Track object.
- Route name.
- Tag.
- Permanent route.
- DHCP next-hop.
- Nhiều default route với AD khác nhau.

MVP không được âm thầm bỏ qua. Parser đưa vào `unsupported_routes` với lý do.

Sau MVP có thể mở schema v2:

```text
exit_interface
track_id
route_name
tag
permanent
```

### 7.5. Nhiều default route

Bảng default hiện tại không có unique constraint theo host nhưng UI/service có xu hướng xử lý một default route.

Quyết định MVP:

- Chỉ đồng bộ một simple default route khi thiết bị có đúng một route phù hợp.
- Nếu có nhiều default route, báo conflict/unsupported thay vì chọn ngẫu nhiên.

---

## 8. Chính sách đồng bộ database

### 8.1. Không xóa pending changes âm thầm

Trước khi đồng bộ từng module, kiểm tra:

```text
success = 0  -> pending setup/update
success = -1 -> pending removal/archive
```

Nếu module có pending changes:

- Không replace module đó tự động.
- Trả về conflict.
- Các module không conflict vẫn có thể sync.

Return mẫu:

```json
{
  "interfaces": 6,
  "static_routes": 2,
  "default_routes": 1,
  "ospf_processes": 1,
  "conflicts": ["ospf"],
  "unsupported_routes": 0
}
```

### 8.2. Chế độ đồng bộ

Định nghĩa ba mode rõ ràng:

1. `safe` — mặc định:
   - Không ghi đè module có pending data.
2. `force_device_state`:
   - Xóa pending local và lấy thiết bị làm nguồn chuẩn.
   - UI phải xác nhận rõ.
3. `preview`:
   - Chỉ parse và trả diff, không ghi DB.

Manual `Sys` nên chạy `preview` trước, sau đó mới cho người dùng chọn `safe` hoặc `force_device_state` khi có conflict.

### 8.3. Đồng bộ Static/Default

Tạo các hàm:

```python
parse_static_route_line(...)
sync_static_routes(...)
sync_default_routes(...)
```

Trong mode không conflict:

- Replace snapshot thực tế của host trong một transaction.
- Record thực tế từ thiết bị có `success = 1`.
- Sync lặp lại cùng config không tạo duplicate.
- Nếu thiết bị không còn route và không có pending local, database phải phản ánh trạng thái không còn route.

### 8.4. Làm cứng OSPF sync hiện tại

Trước khi bổ sung EIGRP, sửa OSPF sync:

- Không `DELETE` toàn bộ process khi có pending OSPF.
- Thực hiện conflict check trước.
- Tách parser, persistence và orchestration.
- Preserve transaction rollback khi child row lỗi.

### 8.5. EIGRP sync

EIGRP chưa nằm trong yêu cầu Static/Default bắt buộc, nhưng nên đưa vào phase kế tiếp để routing sync đồng nhất.

MVP EIGRP classic mode:

```text
router eigrp <AS>
 network ...
 eigrp router-id ...
 passive-interface ...
 passive-interface default
 no passive-interface ...
 variance ...
 maximum-paths ...
 distance eigrp ...
 redistribute ...
```

Named EIGRP mode chưa phù hợp schema hiện tại và phải báo unsupported.

---

# PHẦN D — CẤU TRÚC FILE ĐỀ XUẤT

## 9. File mới

```text
app/infrastructure/database/schemas/device_network/01_ssh_algorithms.sql
app/features/devices/ssh_algorithm_repository.py
app/infrastructure/network/ssh_algorithms.py
app/infrastructure/network/netmiko_factory.py
app/infrastructure/network/nornir_netmiko_plugin.py
app/features/routing/clone_repository.py
app/features/routing/clone_validation.py
app/features/devices/running_config_parser.py
app/features/devices/routing_sync.py
app/tests/test_ssh_algorithm_schema.py
app/tests/test_ssh_algorithm_override.py
app/tests/test_routing_clone_hardening.py
app/tests/test_static_route_sync.py
```

## 10. File cần sửa

```text
app/infrastructure/network/device_connector.py
app/features/config_sync/service.py
app/features/devices/sync_state.py
app/features/routing/clone_service.py
app/core/database/routing_slots.py
app/UI/qml/features/routing/RoutingCloneDialog.qml
app/UI/qml/features/routing/RoutingBatchViewPushDialog.qml
app/tests/test_database_routing_contract.py
app/pyproject.toml
```

Có thể cần sửa thêm các worker đang tự tạo Netmiko/Nornir connection sau khi hoàn tất inventory call site.

---

# PHẦN E — TRÌNH TỰ TRIỂN KHAI

## 10.1. Baseline triển khai thực tế

- Nhánh: `feature/ssh-routing-hardening`.
- Commit baseline: `a367ef2`.
- Python: `3.14`.
- Netmiko: `4.7.0`.
- Paramiko: `4.0.0`.
- Nornir: `3.5.0`.
- nornir-netmiko: `1.0.1`.
- Inventory kết nối: Terminal qua `DeviceConnector`; Routing, DHCP và NAT
  qua connection plugin `cams_netmiko`; SFTP giữ facade Paramiko riêng.

## 11. Work package 0 — Baseline và inventory

- [x] Tạo branch: `feature/ssh-routing-hardening`.
- [x] Ghi lại commit baseline.
- [x] Chạy toàn bộ test hiện có.
- [x] Tìm tất cả `ConnectHandler`, `nornir-netmiko`, connection plugin và SSH client call site.
- [x] Xác định canonical connection path cho app mới.
- [x] Ghi phiên bản thực tế từ `uv.lock`.
- [x] Thêm test tái hiện Clone và Static sync đang thiếu.

**Exit criteria:** có danh sách đầy đủ nơi mở SSH và test baseline chạy được.

## 12. Work package 1 — Database SSH override

- [x] Thêm `01_ssh_algorithms.sql`.
- [x] Test clean build.
- [x] Test repair existing database.
- [x] Test cascade delete/update.
- [x] Thêm repository get/save/clear.
- [x] Thêm CSV normalization.

**Exit criteria:** DB mới và DB cũ đều có bảng, không mất dữ liệu.

## 13. Work package 2 — Per-instance SSH Transport

- [x] Tạo model override.
- [x] Tạo validation adapter cho Paramiko.
- [x] Tạo `transport_factory` per instance.
- [x] Tạo Netmiko subclass/factory.
- [x] Nối `DeviceConnector`.
- [x] Nối Nornir connection plugin.
- [x] Bảo đảm no-override đi đúng đường mặc định.

**Exit criteria:** hai host chạy song song có override khác nhau mà không thay đổi `paramiko.Transport._preferred_*` global.

## 14. Work package 3 — UI SSH compatibility

- [x] Form nhập override.
- [x] Cảnh báo security.
- [x] Test SSH.
- [x] Reset default.
- [x] Diagnostic message rõ nhóm thuật toán lỗi.

**Exit criteria:** user cấu hình được theo host mà không sửa DB tay.

## 15. Work package 4 — Clone backend hardening

- [x] Đổi source index sang stable ID.
- [x] Dedicated clone transaction.
- [x] Loại source khỏi target.
- [x] Router ID optional.
- [x] Batch validation.
- [x] Interface compatibility check.
- [x] Structured result/error code.

**Exit criteria:** clone không sửa process khác và không tạo Router ID trùng mặc định.

## 16. Work package 5 — Clone UI và View & Push

- [x] Router ID optional.
- [x] Không prefill Router ID source.
- [x] Hiển thị trạng thái target.
- [x] Debounce validation.
- [x] Batch preview async.
- [x] Push chỉ target save/preview thành công.

**Exit criteria:** UI không block, không N+1 query, báo kết quả per-host.

## 17. Work package 6 — Static/Default route sync

- [x] Refactor parser sang named result model.
- [x] Parse simple static route.
- [x] Parse simple default route.
- [x] Thu thập unsupported route.
- [x] Thêm pending conflict guard.
- [x] Thêm preview/safe/force mode.
- [x] Mở rộng sync summary và UI notification.

**Exit criteria:** running-config simple static/default được sync idempotent và không xóa pending local.

## 18. Work package 7 — OSPF regression và EIGRP parity

- [x] Áp dụng pending conflict guard cho OSPF.
- [x] Regression test interface/OSPF hiện có.
- [x] Parse EIGRP classic mode.
- [x] Sync EIGRP trong phase sau nếu phạm vi cho phép.

**Exit criteria:** bổ sung Static/Default không làm hỏng OSPF; routing sync có lộ trình EIGRP rõ ràng.

---

# PHẦN F — TEST PLAN

## 19. SSH tests

- [x] Không có row override: không tạo custom Transport.
- [x] Row toàn `NULL`: giống hoàn toàn mặc định.
- [x] CSV trim và deduplicate đúng.
- [x] Algorithm không hỗ trợ bị reject trước kết nối.
- [x] Override chỉ thay đổi instance hiện tại.
- [x] Hai thread, hai host, hai override khác nhau không race.
- [x] Exception khi connect không làm thay đổi global Paramiko state.
- [x] Telnet không đọc SSH override.
- [x] Xóa device cascade xóa override.
- [x] Nornir Push dùng cùng override với Terminal login.

## 20. Clone tests

- [x] Source host không xuất hiện trong target mặc định.
- [x] Router ID rỗng vẫn Save được.
- [x] Router ID sai bị reject khi không rỗng.
- [x] Process ID/AS trùng bị reject.
- [x] Mỗi target dùng Process ID khác nhau.
- [x] Mỗi target dùng Router ID khác nhau.
- [x] Thiếu interface trả `MISSING_INTERFACE`.
- [x] Chế độ process-only bỏ qua interface thiếu.
- [x] Clone không sửa hoặc archive process khác trên target.
- [x] Partial success báo đúng từng host.
- [x] Save & Push chỉ nhận successful hosts.
- [x] Source process bị xóa/reload trong lúc dialog mở được phát hiện bằng stable ID.

## 21. Static/default sync tests

- [x] Parse default route đơn giản.
- [x] Parse static route mặc định AD = 1.
- [x] Parse static route có AD.
- [x] Không parse nhầm `ip default-gateway`.
- [x] Interface-only route được ghi vào unsupported list.
- [x] Hai lần sync cùng config không duplicate.
- [x] Route bị xóa trên device được xóa khỏi observed DB khi không có pending.
- [x] Pending local làm module sync bị skip/conflict.
- [x] Force mode chỉ chạy sau explicit confirmation.
- [x] OSPF data không bị ảnh hưởng khi chỉ sync Static.

---

# PHẦN G — ACCEPTANCE CRITERIA

## 22. SSH

- Thiết bị không override giữ nguyên hành vi hiện tại.
- Thiết bị legacy có thể cấu hình KEX/host-key/cipher/MAC riêng.
- Không sửa class-level Paramiko trong production path.
- Terminal, background task và View & Push dùng cùng connection policy.
- Chạy song song không lẫn thuật toán giữa host.

## 23. Clone

- Source không bị clone vào chính nó theo mặc định.
- Router ID không bị nhân bản tự động.
- Process ID/AS được kiểm tra batch và kiểm tra lại trong transaction.
- Thiếu interface được báo rõ.
- Clone không tác động process ngoài phạm vi.
- Save và Save & Push có report per-host.

## 24. Sync

- Simple Static Route và Default Route từ running-config được lưu `success = 1`.
- Sync idempotent.
- Không âm thầm xóa pending local.
- Route không biểu diễn được được báo rõ.
- Summary hiển thị số route, conflict và unsupported.

---

# PHẦN H — MỨC ƯU TIÊN

## P0 — Bắt buộc

1. Thêm schema `t01_ssh_algo`.
2. Xây connection factory dùng per-instance Transport.
3. Nối cả DeviceConnector và Nornir push path.
4. Sửa Clone: source exclusion, Router ID optional, stable ID, transaction riêng.
5. Parse và sync simple Static/Default Route.
6. Pending conflict guard để tránh mất dữ liệu.
7. Test concurrency, clone side effect và sync idempotency.

## P1 — Nên làm ngay sau P0

1. UI SSH compatibility.
2. Batch clone validation.
3. Interface compatibility report.
4. Async batch preview.
5. OSPF sync conflict hardening.
6. Structured error codes và diagnostic log.

## P2 — Ngoài acceptance criteria của đợt triển khai

EIGRP running-config sync đã được đưa vào phạm vi hoàn thành. Các dạng route
không biểu diễn được bằng schema hiện tại (exit-interface, track, name, tag,
permanent) tiếp tục được báo trong `unsupported_routes`; chúng không bị bỏ qua
âm thầm. Tự động chọn thuật toán SSH yếu không được triển khai vì trái với
nguyên tắc opt-in của kế hoạch; diagnostic chỉ cung cấp error code và phiên bản
runtime để người dùng tự quyết định override.

---

## 25. Quyết định kiến trúc cuối cùng

### Chấp nhận

- Bảng override 1-1 theo host.
- NULL nghĩa là giữ mặc định.
- Prepend override vào default preference.
- Chỉ bật legacy theo từng thiết bị.
- Per-instance `Transport` + `SecurityOptions`.
- Dedicated clone transaction.
- Safe synchronization có conflict detection.

### Không chấp nhận làm kiến trúc lâu dài

- Monkey-patch `paramiko.Transport._preferred_*` không lock.
- Lock riêng theo host cho một global class state.
- Chỉ sửa Terminal connector mà bỏ qua Nornir worker.
- Copy Router ID source sang mọi target.
- Dùng index UI làm định danh process.
- Xóa toàn bộ routing DB khi còn pending local.
- Bỏ qua static route không hỗ trợ mà không báo.

---

## 26. Commit breakdown đề xuất

```text
feat(db): add per-device SSH algorithm override schema
feat(ssh): add validated per-instance Paramiko transport factory
refactor(network): centralize Netmiko and Nornir connection creation
feat(ui): add legacy SSH compatibility settings
refactor(routing): clone processes by stable identifier
fix(routing): validate clone targets and optional router IDs
feat(sync): parse and synchronize static and default routes
fix(sync): preserve pending routing changes during config sync
test(ssh): cover override isolation and concurrent connections
test(routing): cover clone safety and static route sync
docs: document SSH compatibility and routing synchronization
```

---

## 27. Kết quả mong đợi sau triển khai

CAMS sẽ có một chính sách SSH thống nhất cho toàn ứng dụng, hỗ trợ Cisco IOS cũ mà không hạ mức bảo mật cho mọi thiết bị. Clone OSPF/EIGRP sẽ có validation rõ ràng, không sao chép Router ID nguy hiểm và không tác động ngoài phạm vi. Chức năng Manual Sync sẽ thu thập được Static Route/Default Route, đồng thời bảo vệ các thay đổi local chưa push.
