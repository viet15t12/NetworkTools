# KẾ HOẠCH LÀM LẠI `PanelSideBar` VÀ HỖ TRỢ NHIỀU THIẾT BỊ ĐỒNG THỜI

> Repository: `ntdatphu/CAMS`  
> Commit khảo sát: `33caae7305debc9bcf4d71a1ec2d8a41f2832762`  
> Phạm vi: `app/`  
> Vị trí đề xuất trong repository:  
> `app/bang_ke_hach_cua_viet/KE_HOACH_REFACTOR_PANELSIDEBAR_MULTI_DEVICE_SESSION.md`

---

## 1. Mục tiêu

Làm lại luồng quản lý thiết bị trong `PanelSideBar` để:

1. Chấm dứt lỗi chọn host A nhưng thao tác lại chạy trên host B.
2. Cho phép chọn một hoặc nhiều thiết bị bằng định danh ổn định là `host/IP`, không dùng index của danh sách.
3. Cho phép Connect nhiều thiết bị đồng thời với giới hạn concurrency.
4. Cho phép Get running-config nhiều thiết bị đồng thời.
5. Duy trì đăng nhập SSH/Telnet cho nhiều thiết bị cùng lúc.
6. Không đóng session chỉ vì người dùng đóng tab giao diện.
7. Hiển thị trạng thái và kết quả riêng cho từng host.
8. Giữ tương thích với các slot QML một thiết bị đang được các phần khác sử dụng.
9. Không để hai tác vụ đồng thời sử dụng chung một CLI channel của cùng một host.
10. Đảm bảo lỗi của một host không làm dừng toàn bộ batch.

---

## 2. Kết luận khảo sát hiện trạng

### 2.1. Lựa chọn thiết bị đang dựa trên index không ổn định

`DevicesPanel.qml` hiện lưu:

```qml
property int selectedSection: -1
property int selectedIndex: -1
```

Thiết bị đang chọn được truy ngược từ:

```qml
const list = devicesForSection(selectedSection)
return list[selectedIndex]
```

Trong khi đó, `applyFilters()` liên tục tạo lại ba mảng:

- `connectedSection.devices`
- `waitingSection.devices`
- `disconnectedSection.devices`

Khi tìm kiếm, lọc, reload hoặc trạng thái thiết bị thay đổi, một host có thể:

- đổi vị trí trong cùng section;
- chuyển từ Waiting sang Connected;
- chuyển từ Connected sang Disconnected;
- bị loại khỏi danh sách đang hiển thị.

`selectedIndex` lúc đó vẫn giữ số cũ nhưng có thể trỏ sang một thiết bị khác. Đây là nguyên nhân kiến trúc có khả năng trực tiếp gây lỗi “chọn host này nhưng chạy host kia”.

### 2.2. Event click chỉ truyền index

`DeviceSection.qml` phát:

```qml
signal deviceClicked(int index)
```

`DevicesPanel.qml` sau đó tự lấy lại thiết bị từ mảng theo index. Event không mang theo định danh host bất biến tại thời điểm click.

### 2.3. `PanelSideBar.qml` đang proxy state bằng index

`PanelSideBar.qml` alias trực tiếp:

```qml
property alias selectedSection: devicesPanel.selectedSection
property alias selectedIndex: devicesPanel.selectedIndex
```

`Main.qml` và `DeviceTabs.qml` tiếp tục đồng bộ trạng thái bằng hai giá trị này. Vì vậy lỗi index không chỉ nằm trong một delegate mà lan ra toàn bộ luồng sidebar/tab.

### 2.4. UI đang khóa toàn bộ Connect vào một host

`DevicesPanel.qml` hiện dùng state toàn cục:

```qml
property bool isConnectRunning: false
property string connectTargetIp: ""
property string pendingConnectIp: ""
```

và:

```qml
property bool isRunningConfigRunning: false
property string runningConfigTargetIp: ""
property string pendingRunningConfigIp: ""
```

Do đó, khi một host đang Connect hoặc Get running-config, host khác bị chặn dù backend có thể chạy tác vụ khác key.

### 2.5. Backend task hiện có khả năng chạy nhiều host

`AsyncTaskCoordinator` tạo một `QThread` cho mỗi `task_key` và chỉ từ chối khi key trùng.

Các key hiện đã chứa host:

```python
connect:{host}
running-config:{host}
open-session:{host}
```

Vì vậy backend nền tảng đã có khả năng chạy song song các host khác nhau. Điểm chặn chính hiện nay nằm ở state của QML và thiếu batch coordinator có giới hạn concurrency.

### 2.6. Connect hiện không duy trì đăng nhập

`connectHostAndSync()` tạo `DeviceConnector` cục bộ và luôn gọi:

```python
finally:
    connector.disconnect()
```

Kết quả là thao tác Connect:

1. đăng nhập;
2. lấy running-config;
3. backup/sync;
4. đánh dấu trạng thái;
5. đóng kết nối.

Nó không giữ session sống.

### 2.7. Registry đã có thể chứa nhiều session

`DeviceSessionRegistry` đã lưu:

```python
self._sessions: dict[str, Any] = {}
```

theo `host`, có `RLock`, có các hàm:

- `open(host)`
- `close(host)`
- `close_all()`
- `get_connector(host)`
- `has_session(host)`

Do đó không cần viết lại từ đầu. Cần nâng cấp registry thành owner hoàn chỉnh cho session, trạng thái và khóa thao tác theo từng host.

### 2.8. Vòng đời session đang gắn sai với vòng đời tab

`DeviceTabs.qml` gọi `closeSessionForTab(uid)` khi đóng tab. Điều này khiến session bị đăng xuất chỉ vì người dùng đóng phần giao diện của host.

Ba khái niệm sau phải được tách rời:

1. **Active host:** host đang hiển thị trong ContentArea.
2. **Selected hosts:** các host đang được chọn để chạy batch.
3. **Open sessions:** các host hiện đang giữ đăng nhập SSH/Telnet.

---

## 3. Nguyên tắc thiết kế

1. Host/IP là khóa duy nhất xuyên suốt UI, task và session.
2. Không dùng index để xác định mục tiêu nghiệp vụ.
3. Index chỉ được dùng để render hoặc điều hướng cục bộ trong component.
4. Mọi callback bất đồng bộ phải mang theo `batchId`, `operationId` và `host`.
5. Context menu phải giữ một snapshot `targetHost`, không phụ thuộc lựa chọn thay đổi sau khi menu mở.
6. Một session cho mỗi host.
7. Nhiều host có thể chạy song song.
8. Trên cùng một host, thao tác CLI phải được tuần tự hóa.
9. Connect thành công phải có thể giữ session sống.
10. Đóng tab không đồng nghĩa Disconnect.
11. Lỗi từng host phải được cô lập và tổng hợp cuối batch.
12. Batch phải giới hạn số kết nối đồng thời; không tạo hàng chục hoặc hàng trăm `QThread` không kiểm soát.
13. Các API một host cũ được giữ làm wrapper trong giai đoạn chuyển đổi.
14. QML facade chỉ điều phối; nghiệp vụ batch không đặt trong QML.
15. Không log username/password hoặc payload chứa credential.

---

## 4. Mô hình trạng thái đích

### 4.1. UI selection state

Thay:

```qml
selectedSection
selectedIndex
```

bằng:

```qml
property string activeHost: ""
property var selectedHosts: ({})
property string anchorHost: ""
property string contextTargetHost: ""
```

Trong đó:

- `activeHost`: host đang mở trong tab/ContentArea.
- `selectedHosts`: map `{ "192.168.1.1": true, ... }`.
- `anchorHost`: điểm neo cho Shift-click.
- `contextTargetHost`: host snapshot của context menu.
- `selectedHostList`: danh sách sinh từ `selectedHosts`.

Không dùng array rồi sửa trực tiếp nhiều nơi nếu QML không phát hiện thay đổi. Mỗi lần cập nhật phải clone map/array rồi gán lại property.

Ví dụ:

```qml
function setHostSelected(host, selected) {
    const next = Object.assign({}, selectedHosts)
    if (selected)
        next[host] = true
    else
        delete next[host]
    selectedHosts = next
}
```

### 4.2. Task state

Thay các biến đơn:

```qml
isConnectRunning
connectTargetIp
pendingConnectIp
```

bằng model theo host:

```qml
property var hostOperations: ({})
property string activeBatchId: ""
```

Mỗi host có state:

```json
{
  "host": "192.168.1.1",
  "operation": "connect",
  "state": "queued|running|success|warning|error|cancelled",
  "message": "",
  "progress": 0
}
```

### 4.3. Session state

Backend quản lý:

```python
SessionEntry(
    host=host,
    connector=connector,
    state="opening|connected|stale|closing|closed|error",
    operation_lock=threading.RLock(),
    opened_at=...,
    last_used_at=...,
    last_error="",
    generation=...
)
```

`generation` giúp bỏ qua callback cũ nếu session đã reconnect trong lúc task trước chưa hoàn tất.

---

## 5. Cấu trúc file đề xuất

```text
app/
├── UI/qml/
│   ├── panels/
│   │   ├── PanelSideBar.qml
│   │   ├── DevicesPanel.qml
│   │   └── DeviceBatchActionBar.qml              # mới
│   ├── sidebar/devices/
│   │   ├── DeviceItem.qml
│   │   ├── DeviceSection.qml
│   │   ├── DeviceContextMenu.qml
│   │   ├── DeviceSelectionState.qml              # mới
│   │   ├── DeviceOperationBadge.qml               # mới
│   │   └── DeviceBatchResultDialog.qml            # mới
│   └── devices/
│       └── DeviceTabs.qml
│
├── core/
│   ├── terminal.py
│   ├── tasks.py
│   └── batch_operations.py                       # QML facade mỏng, mới
│
├── features/devices/
│   ├── batch_service.py                          # mới
│   ├── connection_service.py                     # mới
│   ├── running_config_service.py                 # mới hoặc tách từ terminal.py
│   └── models.py                                 # thêm DTO nếu cần
│
├── infrastructure/network/
│   ├── session_registry.py
│   ├── session_entry.py                          # mới
│   ├── device_connector.py
│   └── batch_executor.py                         # bounded worker pool, mới
│
└── tests/
    ├── test_device_selection_contracts.py         # mới
    ├── test_multi_device_batch.py                 # mới
    ├── test_session_registry_concurrency.py       # mới
    ├── test_persistent_session_lifecycle.py       # mới
    └── test_qml_smoke.py
```

Không bắt buộc tạo tất cả file ngay commit đầu. Đây là cấu trúc đích; triển khai theo từng giai đoạn để giảm rủi ro.

---

## 6. Thiết kế lại `PanelSideBar`

### 6.1. Trách nhiệm của `PanelSideBar.qml`

`PanelSideBar.qml` chỉ nên:

1. chuyển panel theo `appMode`;
2. forward signal giữa panel con và `Main.qml`;
3. expose API ổn định cho `Main.qml`;
4. không giữ logic lựa chọn thiết bị theo index;
5. không giữ logic batch;
6. không suy ra host từ section.

API đề xuất:

```qml
property alias allDevices: devicesPanel.allDevices
property alias activeHost: devicesPanel.activeHost
property alias selectedHosts: devicesPanel.selectedHosts
property alias selectedHostList: devicesPanel.selectedHostList

signal deviceActivated(string host, string name, string deviceType, string status)
signal deviceSelectionChanged(var hosts)
signal batchOperationRequested(string operation, var hosts)

function activateDevice(host) {
    devicesPanel.activateDevice(host)
}

function clearDeviceSelection() {
    devicesPanel.clearSelection()
}
```

Giữ alias `selectedSection` và `selectedIndex` tạm thời trong một commit compatibility nếu test cũ còn phụ thuộc, sau đó xóa.

### 6.2. `DevicesPanel.qml`

`DevicesPanel.qml` sở hữu:

- danh sách inventory;
- filter/search;
- active host;
- multi-selection;
- batch toolbar;
- context target;
- ánh xạ kết quả backend theo host.

Không sở hữu connector hoặc nghiệp vụ login.

### 6.3. `DeviceSection.qml`

Đổi signal:

```qml
signal deviceClicked(int index)
```

thành:

```qml
signal deviceActivated(string host, int modifiers)
signal deviceSelectionToggled(string host, int modifiers)
signal deviceContextRequested(string host, string status, real sceneX, real sceneY)
```

Delegate phải truyền `modelData.ip` trực tiếp. Không để parent tra cứu lại bằng index.

### 6.4. `DeviceItem.qml`

Thêm:

```qml
property bool isActive: false
property bool isBatchSelected: false
property string operationState: "idle"
property string operationMessage: ""
```

Tách hiển thị:

- active host: viền/accent chính;
- batch selected: checkbox hoặc lớp nền phụ;
- operation state: spinner/check/error badge;
- connected session: biểu tượng session riêng, không dùng chung với DB status.

### 6.5. Hành vi chọn

Đề xuất hành vi:

- Click thường:
  - đặt `activeHost`;
  - mở/focus tab;
  - nếu không giữ Ctrl/Shift thì không bắt buộc xóa batch selection.
- Click checkbox:
  - chỉ toggle batch selection;
  - không mở tab.
- Ctrl-click trên row:
  - toggle host trong batch.
- Shift-click:
  - chọn dải theo danh sách đang hiển thị từ `anchorHost`.
- Ctrl+A khi focus sidebar:
  - chọn toàn bộ host đang hiển thị sau filter.
- Escape:
  - bỏ batch selection.
- Right-click:
  - đặt `contextTargetHost`;
  - không thay đổi `activeHost` hoặc toàn bộ selection ngoài ý muốn.
- Nếu right-click trên host chưa chọn:
  - context action một host chỉ dùng `contextTargetHost`;
  - batch action dùng `selectedHostList` khi host nằm trong tập chọn.

### 6.6. Sau reload/filter/status change

Sau `reloadDevices()`:

1. giữ `activeHost` nếu host còn tồn tại;
2. giữ selection theo host;
3. loại host đã bị xóa khỏi `selectedHosts`;
4. không đổi mục tiêu sang host cùng index;
5. nếu active host bị xóa, đặt active host rỗng hoặc chọn tab hiện hành từ `DeviceTabs`, không tự chọn host ngẫu nhiên.

---

## 7. Batch Action Bar

Khi `selectedHostList.length > 0`, hiển thị `DeviceBatchActionBar` ở dưới search hoặc trên Open Editors.

Nút đề xuất:

- Connect & Login
- Get running-config
- Disconnect
- Ping
- Clear selection
- Cancel batch đang chạy

Hiển thị:

```text
5 selected | 2 running | 2 success | 1 failed
```

Không dùng status bar toàn cục để hiển thị từng event vì nhiều task sẽ ghi đè nhau. Status bar chỉ hiển thị:

- lúc bắt đầu batch;
- tiến độ tổng quát;
- kết quả cuối.

Chi tiết từng host hiển thị ngay trong sidebar hoặc dialog kết quả.

---

## 8. Backend nhiều thiết bị

### 8.1. Không đặt vòng lặp batch trong QML

QML không nên gọi `connectHostAndSyncAsync(host)` liên tiếp cho từng host. Cách đó:

- khó giới hạn concurrency;
- khó cancel;
- khó tổng hợp kết quả;
- dễ mất callback;
- buộc UI quản lý quá nhiều state nghiệp vụ.

Tạo một service backend chuyên trách batch.

### 8.2. API QML mới

Trong `TerminalHelper` hoặc facade mới `DeviceBatchController`:

```python
@pyqtSlot("QVariantList", result=str)
def connectHostsAsync(self, hosts: list[str]) -> str:
    ...

@pyqtSlot("QVariantList", result=str)
def getRunningConfigsAsync(self, hosts: list[str]) -> str:
    ...

@pyqtSlot("QVariantList", result=str)
def disconnectHostsAsync(self, hosts: list[str]) -> str:
    ...

@pyqtSlot(str, result=bool)
def cancelBatch(self, batch_id: str) -> bool:
    ...
```

Signal:

```python
batchStarted = pyqtSignal(str, str, int)
hostOperationChanged = pyqtSignal(str, str, str, str, int)
batchProgress = pyqtSignal(str, int, int, int, int)
batchFinished = pyqtSignal(str, bool, object)
sessionStateChanged = pyqtSignal(str, str, str)
```

Ý nghĩa `hostOperationChanged`:

```text
batchId, host, state, message, progress
```

Payload cuối:

```json
{
  "batchId": "...",
  "operation": "connect",
  "total": 5,
  "success": 3,
  "warning": 1,
  "failed": 1,
  "cancelled": 0,
  "results": [
    {
      "host": "192.168.1.1",
      "ok": true,
      "severity": "success",
      "message": "..."
    }
  ]
}
```

### 8.3. Giữ API cũ

Các slot hiện có vẫn giữ:

```python
connectHostAndSyncAsync(host)
saveRunningConfigBackupAsync(host)
openDeviceSessionAsync(host)
```

Nhưng implementation gọi chung service mới với list một phần tử. Sau khi toàn bộ consumer chuyển đổi và test ổn định mới cân nhắc deprecated.

---

## 9. Connect và duy trì đăng nhập

### 9.1. Đổi ý nghĩa Connect

Luồng Connect mới:

1. validate host;
2. load thông tin đăng nhập;
3. mở hoặc reuse session trong `DeviceSessionRegistry`;
4. bảo đảm enable mode và thoát config mode;
5. lấy running-config qua session đang sống;
6. backup Dulwich;
7. sync SQLite;
8. cập nhật trạng thái thiết bị;
9. giữ session trong registry;
10. phát `sessionStateChanged(host, "connected", ...)`.

Không tạo connector cục bộ rồi disconnect trong `finally`.

### 9.2. `DeviceSessionRegistry` là owner duy nhất

Không cho `TerminalHelper`, View & Push hoặc feature khác tự tạo `DeviceConnector` nếu session registry có thể xử lý.

API đích:

```python
open(host)
open_many(hosts)
close(host)
close_many(hosts)
close_all()
has_session(host)
get_state(host)
run(host, operation)
collect_running_config(host)
send_command(host, command)
send_config_set(host, commands)
```

Tốt hơn nữa, không expose connector thô ra ngoài:

```python
with registry.acquire(host) as session:
    session.collect_running_config()
```

hoặc:

```python
registry.execute(host, callback)
```

### 9.3. Khóa theo host

Mỗi `SessionEntry` có `operation_lock`.

Cho phép:

- R1 và R2 chạy song song;
- R1 Connect và R2 Get config chạy song song.

Không cho phép trên cùng R1:

- Get running-config;
- View & Push;
- command khác;

cùng ghi/đọc trên một CLI channel tại cùng thời điểm.

Các task cùng host:

- hoặc xếp hàng;
- hoặc trả trạng thái `busy`;
- không chạy song song trên cùng connector.

### 9.4. Vòng đời session

Session được đóng khi:

- người dùng chọn Disconnect;
- thiết bị bị xóa;
- credential/method/port của host bị sửa;
- health check xác định kết nối chết;
- app shutdown;
- idle timeout nếu người dùng bật cấu hình này.

Session không bị đóng khi:

- chuyển tab;
- đóng tab;
- đổi feature;
- filter host khỏi sidebar;
- reload inventory.

### 9.5. Reconnect

Nếu connector không alive:

1. đánh dấu `stale`;
2. khóa host;
3. thử reconnect một lần theo policy;
4. nếu thành công, tăng `generation`;
5. nếu thất bại, đánh dấu `error/disconnected`;
6. không cho callback từ generation cũ ghi đè state mới.

---

## 10. Get running-config nhiều host

### 10.1. Luồng mỗi host

```text
validate
→ acquire/reuse session
→ collect running-config
→ commit backup/<host>/cfg
→ sync DB
→ release per-host operation lock
→ giữ session mở
```

Nếu chưa có session:

- theo mặc định batch Get running-config có thể tự đăng nhập và giữ session;
- hoặc hỗ trợ option `keepSession=true`.

Đề xuất mặc định `keepSession=true` để thống nhất với yêu cầu duy trì đăng nhập.

### 10.2. Giới hạn song song

Tạo `BatchExecutor` với cấu hình:

```python
max_concurrent_hosts = 5
```

Không khởi tạo một `QThread` không giới hạn cho mỗi host.

Cho phép cấu hình trong Settings sau này:

- mặc định: 5;
- tối thiểu: 1;
- tối đa an toàn: 20.

Giới hạn riêng có thể áp dụng:

- Connect/Login: 5;
- Get running-config: 5;
- Disconnect: 10;
- Ping: 10.

### 10.3. SQLite và backup

Dulwich đang tách repo theo `backup/<host>/cfg`, nên các host khác nhau ít xung đột file.

SQLite có thể bị nhiều worker ghi đồng thời. Cần một trong hai cách:

1. writer lock chung cho phần sync database; hoặc
2. SQLite WAL + busy timeout + retry có backoff.

Đề xuất giai đoạn đầu:

- network collect chạy song song;
- backup từng host chạy song song;
- phần sync SQLite đi qua `DatabaseWriteCoordinator` tuần tự.

Cách này đơn giản và an toàn hơn việc cho nhiều transaction ghi cùng lúc.

---

## 11. Tách `DeviceTabs` khỏi session lifecycle

Xóa hành vi:

```qml
closeTab()
    → closeSessionForTab(uid)
```

Thay bằng:

```qml
closeTab()
    → chỉ đóng editor/tab
```

Thêm thao tác riêng:

- Disconnect trong context menu sidebar;
- Disconnect trong tab context menu;
- Disconnect selected;
- Disconnect all sessions.

`DeviceTabs` chỉ hiển thị `sessionState` nhận từ backend, không sở hữu session.

Khi mở tab:

- nếu session đã tồn tại: hiển thị Connected;
- nếu DB status Connected nhưng registry chưa có session: không tự động login nếu policy là explicit connect;
- hoặc tự động mở session nếu giữ hành vi cũ.

Đề xuất rõ ràng hơn:

- click host để mở nội dung không tự đăng nhập;
- nút Connect mới thực sự login và giữ session;
- feature cần kết nối có thể gọi `ensureSession(host)` và báo rõ cho người dùng.

Nếu muốn giữ tương thích hành vi hiện tại trong giai đoạn chuyển đổi, vẫn có thể auto-open session cho host Connected, nhưng không đóng khi đóng tab.

---

## 12. Sửa context menu và shortcut

### 12.1. Context menu

`DeviceContextMenu` phải nhận:

```qml
property string targetHost: ""
property var batchHosts: []
```

Khi mở menu:

```qml
deviceContextMenu.openForHost(host, status, selectedHostList, x, y)
```

Menu không được đọc `selectedIndex` sau khi đã mở.

### 12.2. Shortcut

Các shortcut một host dùng `activeHost`, không dùng `selectedDevice()` theo index:

- F2: Edit active host
- Ctrl+Alt+P: Ping active host
- Ctrl+Alt+C: Connect active host
- Ctrl+Alt+R: Reconnect active host
- Delete: Delete active host

Batch shortcut dùng `selectedHostList`:

- Ctrl+Shift+C: Connect selected
- Ctrl+Shift+R: Get running-config selected
- Ctrl+Shift+D: Disconnect selected
- Escape: Clear selection

Nếu không có `activeHost`, shortcut một host phải báo rõ và không tự lấy phần tử đầu của selection.

---

## 13. Trạng thái thiết bị cần tách nghĩa

Hiện `status` trong inventory có thể đang trộn:

- DB success;
- lần kết nối gần nhất;
- session hiện tại;
- dev mode.

Đề xuất payload thiết bị về QML:

```json
{
  "ip": "192.168.1.1",
  "name": "R1",
  "type": "router",
  "inventoryStatus": "waiting|connected|disconnected",
  "sessionState": "closed|opening|connected|stale|error",
  "operationState": "idle|queued|running|success|warning|error",
  "dev": 0
}
```

Trong giai đoạn đầu có thể giữ `status` cũ và bổ sung `sessionState`, không đổi schema ngay.

---

## 14. Trình tự triển khai

### Giai đoạn 0 — Viết regression test trước khi refactor

Thêm test tái hiện:

1. chọn host B;
2. thay filter làm index thay đổi;
3. chạy shortcut;
4. xác nhận backend vẫn nhận host B.

Thêm test:

1. chọn host trong Waiting;
2. reload khiến host chuyển Connected;
3. xác nhận active host vẫn là cùng IP.

Không bắt đầu multi-select trước khi test lỗi chạy nhầm host được khóa lại.

### Giai đoạn 1 — Chuyển selection từ index sang host

Thay đổi:

- `DeviceItem.qml`
- `DeviceSection.qml`
- `DevicesPanel.qml`
- `PanelSideBar.qml`
- `Main.qml`
- `DeviceTabs.qml`

Mục tiêu:

- mọi signal mang host;
- mọi action nhận host;
- `selectedSection/selectedIndex` không còn là source of truth;
- filter/reload không đổi mục tiêu.

Có thể giữ hai property index dưới dạng computed compatibility trong một commit, nhưng không dùng cho nghiệp vụ.

### Giai đoạn 2 — Thêm multi-selection UI

Thêm:

- `selectedHosts`;
- checkbox;
- Ctrl/Shift selection;
- Batch Action Bar;
- context menu hiểu single target và selected targets;
- trạng thái chọn riêng với active host.

Giai đoạn này có thể dùng backend single-host tuần tự để hoàn thiện contract UI, nhưng chưa release chức năng batch chính thức.

### Giai đoạn 3 — Nâng cấp session registry

Thêm:

- `SessionEntry`;
- per-host operation lock;
- state;
- generation;
- last-used;
- health check;
- `execute(host, callback)`;
- signal/publisher state.

Giữ `get_connector()` tạm thời cho View & Push cũ, nhưng đánh dấu cần chuyển dần sang `execute()`.

### Giai đoạn 4 — Tách connection/running-config service

Di chuyển khỏi `core/terminal.py`:

- connect-and-sync;
- collect running-config;
- backup/sync orchestration.

`TerminalHelper` chỉ còn:

- validate payload QML;
- gọi service;
- phát signal.

Không để facade tự tạo `DeviceConnector`.

### Giai đoạn 5 — Batch executor và API nhiều host

Thêm:

- bounded concurrency;
- batch ID;
- per-host result;
- cancel;
- progress aggregate;
- retry policy tối thiểu;
- partial failure.

Single-host API gọi chung batch service với một host.

### Giai đoạn 6 — Duy trì đăng nhập

Đổi Connect sang reuse/retain session.

Xóa disconnect trong `finally` của luồng Connect mới.

Tách đóng tab khỏi disconnect session.

Bổ sung:

- Disconnect host;
- Disconnect selected;
- Disconnect all;
- session badges.

### Giai đoạn 7 — Tích hợp Get running-config batch

Kết nối:

```qml
selectedHostList
→ getRunningConfigsAsync(hosts)
→ hostOperationChanged
→ batchFinished
```

Tổng hợp:

- backup thành công;
- sync thành công;
- warning;
- login failure;
- unsupported protocol;
- cancelled.

### Giai đoạn 8 — Chuyển các feature dùng session chung

Rà:

- Routing View & Push;
- DHCP;
- ACL;
- NAT;
- Switching;
- Manual Sync;
- command execution.

Mỗi feature phải:

- nhận host rõ ràng;
- dùng registry;
- dùng per-host lock;
- không tự tạo connector song song với session đang sống.

### Giai đoạn 9 — Dọn compatibility

Sau khi test và consumer chuyển hết:

- xóa `selectedSection/selectedIndex` khỏi public API;
- xóa global `isConnectRunning`;
- xóa `pendingConnectIp`;
- xóa `runningConfigTargetIp`;
- xóa `pendingRunningConfigIp`;
- loại code tự tạo connector trong facade;
- cập nhật README và function map.

---

## 15. Danh sách thay đổi theo file

### `app/UI/qml/panels/PanelSideBar.qml`

- bỏ source of truth `selectedSection/selectedIndex`;
- expose `activeHost`, `selectedHosts`, `selectedHostList`;
- forward `deviceActivated`;
- forward batch request/result;
- giữ vai trò router của panel.

### `app/UI/qml/panels/DevicesPanel.qml`

- thay selection index bằng host;
- thêm selection store;
- thêm batch operation state;
- bỏ global one-host lock;
- callback async cập nhật theo `batchId + host`;
- giữ selection qua reload/filter;
- thêm batch action bar.

### `app/UI/qml/sidebar/devices/DeviceSection.qml`

- event truyền host;
- nhận selected-host map;
- hỗ trợ modifier;
- không dùng index làm target nghiệp vụ.

### `app/UI/qml/sidebar/devices/DeviceItem.qml`

- checkbox/multi-select;
- active state;
- selected state;
- session state;
- operation badge;
- signal mang host.

### `app/UI/qml/sidebar/devices/DeviceContextMenu.qml`

- target immutable;
- single-host action;
- selected-host action;
- Connect/Get config/Disconnect nhiều host.

### `app/UI/qml/devices/DeviceTabs.qml`

- không đóng session khi đóng tab;
- nhận session state từ backend;
- active tab chỉ điều khiển content;
- không làm owner session.

### `app/core/terminal.py`

- giữ QML facade;
- thêm wrapper batch;
- xóa dần business logic connect/backup;
- signal phải mang host/batch ID;
- không tạo connector trực tiếp sau giai đoạn chuyển đổi.

### `app/core/tasks.py`

Hai lựa chọn:

1. giữ cho các task UI nhỏ;
2. không dùng một `QThread`/host cho batch lớn.

Batch dùng executor riêng có giới hạn concurrency.

### `app/infrastructure/network/session_registry.py`

- session entry;
- state;
- per-host lock;
- execute;
- reconnect;
- open/close many;
- state snapshot;
- không expose connector raw về lâu dài.

### `app/infrastructure/network/device_connector.py`

- bảo đảm mode trước mỗi operation;
- lỗi phải chứa host và phase;
- `collect_running_config()` không che mất nguyên nhân lỗi;
- không lưu password vào log;
- chuẩn hóa timeout/cancel boundary.

### `app/features/devices/batch_service.py`

- validate/deduplicate hosts;
- lập batch;
- gọi executor;
- gọi session registry;
- tổng hợp result;
- phát progress;
- cancel.

---

## 16. Kiểm thử bắt buộc

### 16.1. Selection

- chọn host vẫn đúng sau search;
- vẫn đúng sau filter status;
- vẫn đúng sau reload;
- vẫn đúng khi host chuyển section;
- xóa host không chọn nhầm host kế bên;
- context menu giữ đúng target dù selection thay đổi;
- active host và selected hosts độc lập.

### 16.2. Multi-selection

- Ctrl-click toggle;
- Shift-click chọn dải;
- Ctrl+A chỉ chọn danh sách đang hiển thị;
- Clear selection;
- host bị xóa được loại khỏi selection;
- host bị filter ẩn vẫn có policy rõ ràng: giữ hoặc bỏ, không ngẫu nhiên.

Đề xuất: giữ selection khi filter ẩn và hiển thị số selected tổng; có nút “Select visible” và “Clear hidden selection” nếu cần.

### 16.3. Concurrency

- R1 và R2 Connect chạy thực sự overlap;
- R1 và R2 Get config chạy overlap;
- hai operation cùng R1 không dùng connector đồng thời;
- duplicate host trong input chỉ chạy một lần;
- concurrency không vượt cấu hình;
- cancel dừng task chưa bắt đầu;
- task đang gửi lệnh chỉ cancel tại safe boundary.

### 16.4. Session lifecycle

- Connect giữ session;
- mở nhiều host tạo nhiều session;
- đóng tab không đóng session;
- Disconnect một host không ảnh hưởng host khác;
- sửa credential đóng session cũ;
- app shutdown đóng toàn bộ session;
- dead session được phát hiện và reconnect/đánh lỗi đúng.

### 16.5. Running-config

- backup đúng thư mục từng host;
- không ghi config R1 vào repo R2;
- partial failure không rollback host thành công;
- SQLite không lỗi `database is locked`;
- callback cuối mang đúng host;
- kết quả warning DB sync không bị coi là login failure.

### 16.6. QML contract/smoke

- các component mới có trong `qmldir`;
- không lỗi binding loop;
- không gọi signal cũ bằng sai chữ ký;
- app khởi động với danh sách rỗng;
- app hoạt động khi backend batch chưa được inject, có thông báo fallback rõ.

---

## 17. Tiêu chí hoàn thành

Tính năng được xem là hoàn thành khi:

1. Không còn action nghiệp vụ nào suy host từ `selectedIndex`.
2. Tất cả action backend nhận host hoặc danh sách host rõ ràng.
3. Chọn host không bị đổi sau filter/reload/status migration.
4. Có thể chọn ít nhất 10 thiết bị và Connect/Get running-config theo batch.
5. Số task mạng đồng thời bị giới hạn.
6. Mỗi host có trạng thái riêng.
7. Connect thành công giữ session trong registry.
8. Đóng tab không đóng session.
9. Có thể Disconnect từng host, selected hosts và all sessions.
10. Hai operation trên cùng host được serialize.
11. Lỗi một host không làm batch dừng.
12. Backup và DB sync đúng host.
13. Các API một host cũ vẫn chạy trong giai đoạn migration.
14. Có unit test, integration test và QML smoke cho luồng mới.
15. `TerminalHelper` không còn tự quản lý toàn bộ nghiệp vụ kết nối.
16. Không log credential.
17. App shutdown đóng session sạch.

---

## 18. Ngoài phạm vi đợt này

- Không thay đổi schema routing/DHCP/ACL/NAT/Switching.
- Không viết lại toàn bộ Device Inventory database.
- Không chuyển sang asyncio nếu chưa giải quyết đầy đủ tích hợp Qt event loop.
- Không dùng Nornir chỉ để thay cho một batch executor nhỏ.
- Không tự động push cấu hình hàng loạt trong cùng đợt đầu.
- Không thêm NETCONF.
- Không gộp trạng thái session với trạng thái desired-state/push success.
- Không tự reconnect vô hạn.

---

## 19. Thứ tự commit đề xuất

1. `test(devices): reproduce host selection drift after reload and filtering`
2. `refactor(qml): use host identity for device activation and context actions`
3. `feat(qml): add stable multi-device selection state`
4. `feat(qml): add device batch action bar and per-host operation state`
5. `refactor(network): introduce session entries and per-host operation locks`
6. `refactor(devices): extract persistent connection and running-config services`
7. `feat(devices): add bounded multi-host batch executor`
8. `feat(devices): keep SSH/Telnet sessions after connect`
9. `refactor(tabs): decouple editor tabs from session lifecycle`
10. `feat(devices): collect running-config from selected hosts concurrently`
11. `test(devices): cover partial failure, cancellation, shutdown and DB writes`
12. `docs(app): document multi-device session and batch operation architecture`

Mỗi commit phải chạy test trước khi chuyển sang giai đoạn kế tiếp. Không gộp thay đổi selection QML, session registry và batch backend vào một commit lớn.

---

## 20. Ưu tiên triển khai

### P0 — Sửa lỗi chạy nhầm host

- host-based selection;
- event truyền host;
- immutable context target;
- regression tests.

### P1 — Session nhiều host

- session registry entry;
- giữ session sau Connect;
- không đóng theo tab;
- per-host lock.

### P2 — Batch Connect/Get running-config

- multi-select;
- bounded executor;
- per-host progress;
- partial failure.

### P3 — Hoàn thiện UX và dọn code cũ

- result dialog;
- cancel;
- reconnect policy;
- settings concurrency;
- xóa compatibility state theo index.

---

## 21. Kết luận kiến trúc

Không nên sửa lỗi hiện tại bằng cách chỉ cập nhật `selectedIndex` sau mỗi lần reload. Cách đó vẫn mong manh vì index là thuộc tính của cách hiển thị, không phải định danh nghiệp vụ.

Hướng đúng là:

```text
UI event mang host
→ selection lưu theo host
→ batch request mang danh sách host
→ backend tạo operation theo batchId + host
→ session registry sở hữu connector theo host
→ per-host lock bảo vệ CLI channel
→ kết quả trả về theo đúng host
```

Kiến trúc này vừa sửa lỗi chọn nhầm thiết bị, vừa tạo nền tảng an toàn cho Connect, Get running-config, View & Push và các thao tác nhiều thiết bị về sau.
