Có. Nếu xây dựng theo hướng này, mình khuyên tách **Interface module** thành 5 lớp rõ ràng: **Device Profile → Database → Domain Model/Service → IOS Generator → QML UI**. Không nên để QML tự quyết định interface nào được tạo/xóa hay sinh trực tiếp câu lệnh IOS.

Dưới đây là thiết kế chi tiết có thể áp dụng trực tiếp cho CAMS.

---

# Trạng thái triển khai (2026-08-11)

Phần **Router Interface** của kế hoạch đã được triển khai theo schema canonical
`t02_*` hiện hữu để không phá foreign key/dữ liệu đang được DHCP, Routing và
Switching sử dụng.

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Domain type + capability | Hoàn thành | Physical khác Loopback/Tunnel/Subinterface ở backend |
| Canonical naming | Hoàn thành | Gi/Fa/Te/Se/Lo/Tu được chuẩn hóa trước khi lưu |
| Service + validation | Hoàn thành | IP/mask, type/profile, tunnel, parent và VLAN |
| Repository transaction | Hoàn thành | Dùng `t02_interface_name` + bảng profile hiện hữu |
| QML subfeature/dynamic section | Hoàn thành | Physical/Loopback/Tunnel/Subinterface chia bằng SubBar như Routing |
| Physical inventory từ thiết bị | Hoàn thành | DB reconcile running-config + interface brief; không dùng port dựng sẵn |
| Interface name read-only | Hoàn thành | Physical/parent chọn từ DB; virtual do backend sinh |
| IOS preview/push | Hoàn thành | Có redaction và chỉ cập nhật DB sau push thành công |
| SVI/Port-channel | Thuộc Switching | Không nhân đôi desired state trong Router Interface |
| Device-model profile | Chưa triển khai | Schema device hiện chưa có model/profile catalog |
| IPv6/verify/rollback | Chưa triển khai | Backlog của ConfigPlan phase tiếp theo |

Các file triển khai chính nằm ở `features/interfaces/{models,validation,service,
repository,commands,collector,push_state}.py`, contract QML tại
`core/interface_slots.py`, và UI tại `UI/qml/features/interfaces/`.

---

# 1. Kiến trúc tổng thể

```text
┌──────────────────────────────┐
│            QML UI            │
│                              │
│ InterfacePage.qml            │
│ ├─ InterfaceSidebar.qml      │
│ ├─ PhysicalInterfaceForm.qml │
│ ├─ LoopbackForm.qml          │
│ ├─ TunnelForm.qml            │
│ ├─ SviForm.qml               │
│ ├─ PortChannelForm.qml       │
│ └─ SubinterfaceForm.qml      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ InterfaceController / Model  │
│ Python ↔ QML                 │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      InterfaceService        │
│                              │
│ validation                   │
│ CRUD                         │
│ transactions                 │
│ business rules               │
└───────┬─────────────┬────────┘
        │             │
        ▼             ▼
┌──────────────┐  ┌───────────────┐
│ SQLite Repo  │  │ IOS Generator │
│              │  │               │
│ interfaces   │  │ physical      │
│ tunnel attrs │  │ tunnel        │
│ svi attrs    │  │ svi           │
│ ...          │  │ portchannel   │
└──────────────┘  └───────────────┘
```

Nguyên tắc quan trọng:

```text
QML
 ↓
Controller
 ↓
Service
 ↓
Repository / Generator
```

QML không gọi SQL trực tiếp và cũng không tự ghép command kiểu:

```python
f"interface {name}"
```

---

# 2. Phân loại interface

Mình sẽ chia thành enum backend:

```python
from enum import StrEnum


class InterfaceType(StrEnum):
    PHYSICAL = "physical"
    LOOPBACK = "loopback"
    TUNNEL = "tunnel"
    SVI = "svi"
    PORTCHANNEL = "portchannel"
    SUBINTERFACE = "subinterface"
```

Nếu sau này cần mở rộng:

```text
dialer
bdi
nve
vti
management
null
```

thì không phải sửa bảng base quá nhiều.

---

# 3. Database: bảng Interface base

Không nên tạo một bảng kiểu:

```text
interfaces(
    speed,
    duplex,
    tunnel_source,
    tunnel_destination,
    vlan_id,
    dot1q,
    channel_mode,
    ...
)
```

vì sẽ sinh rất nhiều field NULL.

Nên dùng class-table inheritance.

## `interfaces`

```sql
CREATE TABLE IF NOT EXISTS interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    device_id INTEGER NOT NULL,

    interface_type TEXT NOT NULL
        CHECK (
            interface_type IN (
                'physical',
                'loopback',
                'tunnel',
                'svi',
                'portchannel',
                'subinterface'
            )
        ),

    name TEXT NOT NULL,

    description TEXT,

    ip_address TEXT,
    subnet_mask TEXT,

    mtu INTEGER,
    bandwidth INTEGER,
    delay INTEGER,

    shutdown INTEGER NOT NULL DEFAULT 0
        CHECK (shutdown IN (0, 1)),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(device_id, name),

    FOREIGN KEY(device_id)
        REFERENCES devices(id)
        ON DELETE CASCADE
);
```

Ở đây nên dùng:

```text
shutdown = 0 → no shutdown
shutdown = 1 → shutdown
```

thay vì:

```text
admin_status = up/down
```

vì nó map thẳng sang IOS configuration.

`oper_status` lại là chuyện khác, vì đó là trạng thái lấy từ thiết bị:

```text
up/up
down/down
administratively down/down
```

Không nên trộn `admin_status` và `oper_status`.

---

# 4. Physical interface attributes

```sql
CREATE TABLE IF NOT EXISTS physical_interface_attrs (
    interface_id INTEGER PRIMARY KEY,

    speed TEXT,
    duplex TEXT
        CHECK (
            duplex IS NULL OR
            duplex IN ('auto', 'half', 'full')
        ),

    negotiation INTEGER
        CHECK (
            negotiation IS NULL OR
            negotiation IN (0, 1)
        ),

    media_type TEXT,

    FOREIGN KEY(interface_id)
        REFERENCES interfaces(id)
        ON DELETE CASCADE
);
```

`speed` mình khuyên để `TEXT` thay vì INTEGER.

Ví dụ Cisco có thể có:

```text
auto
10
100
1000
10000
```

và tùy platform có cách biểu diễn khác nhau.

---

# 5. Loopback

Loopback gần như không cần bảng riêng.

Chỉ cần record:

```text
interfaces
```

Ví dụ:

```text
id              10
device_id        1
interface_type   loopback
name             Loopback0
description      Router ID
ip_address       10.0.0.1
subnet_mask      255.255.255.255
```

Không nên tạo:

```sql
loopback_attrs
```

nếu bảng đó không có field thực sự riêng.

---

# 6. Tunnel

```sql
CREATE TABLE IF NOT EXISTS tunnel_attrs (
    interface_id INTEGER PRIMARY KEY,

    tunnel_source TEXT NOT NULL,
    tunnel_destination TEXT NOT NULL,

    tunnel_mode TEXT NOT NULL DEFAULT 'gre ip',

    tunnel_key INTEGER,

    keepalive_interval INTEGER,
    keepalive_retries INTEGER,

    FOREIGN KEY(interface_id)
        REFERENCES interfaces(id)
        ON DELETE CASCADE
);
```

Ví dụ:

```text
interface Tunnel0
 ip address 10.10.10.1 255.255.255.252
 tunnel source GigabitEthernet0/0
 tunnel destination 203.0.113.2
 tunnel mode gre ip
```

`tunnel_source` có hai dạng:

```text
GigabitEthernet0/0
```

hoặc:

```text
192.168.1.1
```

nên không nên ép FK interface ngay từ đầu.

---

# 7. SVI

```sql
CREATE TABLE IF NOT EXISTS svi_attrs (
    interface_id INTEGER PRIMARY KEY,

    vlan_id INTEGER NOT NULL,

    FOREIGN KEY(interface_id)
        REFERENCES interfaces(id)
        ON DELETE CASCADE,

    FOREIGN KEY(vlan_id)
        REFERENCES vlans(vlan_id)
);
```

Tuy nhiên có một điểm nên lưu ý.

Nếu bảng VLAN hiện tại của bạn dùng PK riêng:

```text
id
device_id
vlan_id
name
```

thì FK tốt hơn là:

```sql
vlan_record_id INTEGER NOT NULL
```

thay vì FK trực tiếp bằng `vlan_id`.

Ví dụ:

```sql
FOREIGN KEY(vlan_record_id)
REFERENCES vlans(id)
ON DELETE RESTRICT
```

Vì:

```text
Router/Switch A → VLAN 10
Router/Switch B → VLAN 10
```

đều có `vlan_id = 10`.

---

# 8. Port-channel

Đây là phần mình sẽ thiết kế khác một chút so với đề xuất ban đầu.

Không nên lưu:

```text
members[]
```

trong `portchannel_attrs`.

Database quan hệ nên có bảng mapping riêng.

## Port-channel

```sql
CREATE TABLE IF NOT EXISTS portchannel_attrs (
    interface_id INTEGER PRIMARY KEY,

    protocol TEXT
        CHECK (
            protocol IS NULL OR
            protocol IN ('lacp', 'pagp', 'static')
        ),

    mode TEXT NOT NULL
        CHECK (
            mode IN (
                'active',
                'passive',
                'desirable',
                'auto',
                'on'
            )
        ),

    layer_mode TEXT NOT NULL DEFAULT 'l2'
        CHECK(layer_mode IN ('l2', 'l3')),

    FOREIGN KEY(interface_id)
        REFERENCES interfaces(id)
        ON DELETE CASCADE
);
```

## Members

```sql
CREATE TABLE IF NOT EXISTS portchannel_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    portchannel_interface_id INTEGER NOT NULL,
    member_interface_id INTEGER NOT NULL UNIQUE,

    FOREIGN KEY(portchannel_interface_id)
        REFERENCES interfaces(id)
        ON DELETE CASCADE,

    FOREIGN KEY(member_interface_id)
        REFERENCES interfaces(id)
        ON DELETE CASCADE,

    CHECK(portchannel_interface_id != member_interface_id)
);
```

Điểm quan trọng:

```sql
member_interface_id INTEGER NOT NULL UNIQUE
```

đảm bảo một physical interface không thể nằm trong hai EtherChannel cùng lúc.

---

# 9. Subinterface

```sql
CREATE TABLE IF NOT EXISTS subinterface_attrs (
    interface_id INTEGER PRIMARY KEY,

    parent_interface_id INTEGER NOT NULL,

    encapsulation TEXT NOT NULL DEFAULT 'dot1q'
        CHECK(encapsulation IN ('dot1q')),

    vlan_id INTEGER NOT NULL
        CHECK(vlan_id BETWEEN 1 AND 4094),

    native_vlan INTEGER NOT NULL DEFAULT 0
        CHECK(native_vlan IN (0, 1)),

    FOREIGN KEY(interface_id)
        REFERENCES interfaces(id)
        ON DELETE CASCADE,

    FOREIGN KEY(parent_interface_id)
        REFERENCES interfaces(id)
        ON DELETE RESTRICT
);
```

Tên interface:

```text
GigabitEthernet0/1.10
```

không nên cho người dùng nhập toàn bộ.

UI chỉ cho nhập:

```text
Parent:
GigabitEthernet0/1

Subinterface ID:
10
```

Backend tự sinh:

```text
GigabitEthernet0/1.10
```

Điều này tránh tên sai.

---

# 10. Device Profile

Đây là phần rất quan trọng.

Không nên tạo physical interface khi người dùng bấm Add.

Physical interface phải được sinh từ **device profile**.

Ví dụ:

```python
DEVICE_PROFILES = {
    "ISR4321": {
        "vendor": "Cisco",
        "interfaces": [
            {
                "name": "GigabitEthernet0/0/0",
                "kind": "ethernet",
                "speed_options": [
                    "auto",
                    "10",
                    "100",
                    "1000",
                ],
            },
            {
                "name": "GigabitEthernet0/0/1",
                "kind": "ethernet",
                "speed_options": [
                    "auto",
                    "10",
                    "100",
                    "1000",
                ],
            },
        ],
    }
}
```

Nhưng sau này tốt hơn nên dùng JSON:

```text
resources/
└── device_profiles/
    ├── cisco/
    │   ├── isr4321.json
    │   ├── isr4331.json
    │   └── c2960.json
    └── ...
```

Ví dụ:

```json
{
  "vendor": "Cisco",
  "model": "ISR4321",
  "interfaces": [
    {
      "name": "GigabitEthernet0/0/0",
      "type": "ethernet",
      "layer3": true,
      "speed": ["auto", "10", "100", "1000"],
      "duplex": ["auto", "full", "half"]
    },
    {
      "name": "GigabitEthernet0/0/1",
      "type": "ethernet",
      "layer3": true,
      "speed": ["auto", "10", "100", "1000"],
      "duplex": ["auto", "full", "half"]
    }
  ]
}
```

---

# 11. Khi tạo Device

Giả sử user tạo:

```text
Cisco ISR4321
hostname R1
```

backend thực hiện:

```text
create device
      ↓
load ISR4321 profile
      ↓
create physical interfaces
      ↓
create physical attrs
```

Pseudo-code:

```python
def initialize_physical_interfaces(device_id, profile):
    for item in profile.interfaces:
        interface_id = interface_repository.create(
            device_id=device_id,
            interface_type="physical",
            name=item.name,
        )

        physical_repository.create(
            interface_id=interface_id,
            speed="auto",
            duplex="auto",
            negotiation=True,
        )
```

Như vậy ngay khi mở router:

```text
Physical Interfaces

Gi0/0/0
Gi0/0/1
```

đã tồn tại.

---

# 12. Backend domain model

Không nên dùng dict xuyên suốt toàn project.

Có thể dùng `dataclass`.

```python
from dataclasses import dataclass


@dataclass
class Interface:
    id: int | None
    device_id: int
    interface_type: InterfaceType

    name: str

    description: str | None = None

    ip_address: str | None = None
    subnet_mask: str | None = None

    mtu: int | None = None
    bandwidth: int | None = None
    delay: int | None = None

    shutdown: bool = False
```

Physical:

```python
@dataclass
class PhysicalInterfaceAttrs:
    interface_id: int

    speed: str | None = None
    duplex: str | None = None
    negotiation: bool | None = None

    media_type: str | None = None
```

Tunnel:

```python
@dataclass
class TunnelAttrs:
    interface_id: int

    tunnel_source: str
    tunnel_destination: str

    tunnel_mode: str = "gre ip"
```

---

# 13. Interface DTO gửi cho QML

QML không cần biết structure DB.

Backend trả:

```python
{
    "id": 15,
    "name": "GigabitEthernet0/0",
    "type": "physical",
    "displayName": "Gi0/0",
    "ipAddress": "192.168.1.1",
    "prefixLength": 24,
    "shutdown": False,
    "canDelete": False,
    "canConfigureL1": True,
    "attrs": {"speed": "auto", "duplex": "auto", "negotiation": True},
}
```

Tunnel:

```python
{
    "id": 22,
    "name": "Tunnel0",
    "type": "tunnel",
    "canDelete": True,
    "canConfigureL1": False,
    "attrs": {
        "tunnelSource": "Gi0/0",
        "tunnelDestination": "1.1.1.1",
        "tunnelMode": "gre ip",
    },
}
```

---

# 14. Interface Service

Đây mới là nơi xử lý business rules.

```text
services/
└── interface_service.py
```

Ví dụ:

```python
class InterfaceService:
    def create_virtual_interface(
        self,
        device_id: int,
        interface_type: InterfaceType,
        data: dict,
    ): ...
```

Không cho:

```python
create_interface(type="physical")
```

Có thể chặn:

```python
if interface_type == InterfaceType.PHYSICAL:
    raise InterfaceValidationError("Physical interfaces cannot be created manually.")
```

---

# 15. Validate tên interface

Tạo validator riêng:

```text
interface_validators.py
```

Ví dụ Loopback:

```python
LOOPBACK_PATTERN = r"^Loopback\d+$"
```

Tunnel:

```python
TUNNEL_PATTERN = r"^Tunnel\d+$"
```

SVI:

```python
SVI_PATTERN = r"^Vlan([1-9]\d{0,3})$"
```

Port-channel:

```python
PORTCHANNEL_PATTERN = r"^Port-channel\d+$"
```

Subinterface:

```python
SUBINTERFACE_PATTERN = r"^(GigabitEthernet|FastEthernet|Ethernet)\S+\.\d+$"
```

Nhưng tốt hơn nữa:

**đừng cho người dùng nhập prefix**.

Ví dụ create Loopback:

```text
Interface type
Loopback

Number
[ 0 ]
```

backend tự tạo:

```python
name = f"Loopback{number}"
```

Tunnel:

```python
name = f"Tunnel{number}"
```

SVI:

```python
name = f"Vlan{vlan_id}"
```

Port-channel:

```python
name = f"Port-channel{group_id}"
```

---

# 16. IP validation

Dùng Python `ipaddress`.

```python
import ipaddress


def validate_ipv4(address: str, mask: str):
    ipaddress.IPv4Interface(f"{address}/{mask}")
```

Ví dụ:

```text
192.168.1.1
255.255.255.0
```

OK.

```text
192.168.1.999
```

reject ngay.

---

# 17. Không lưu cả mask và prefix nếu không cần

Ở UI bạn có thể cho user chọn:

```text
192.168.1.1 / 24
```

backend convert:

```python
network = ipaddress.IPv4Interface("192.168.1.1/24")

str(network.netmask)
```

→

```text
255.255.255.0
```

Nếu schema hiện tại đã dùng subnet mask thì cứ giữ.

---

# 18. UI tổng thể

Mình đề xuất layout:

```text
┌───────────────────────────────────────────────────────────────┐
│ Interfaces                                                    │
├───────────────────────┬───────────────────────────────────────┤
│ Saved interfaces      │ GigabitEthernet0/0                    │
│                       │                                       │
│ ▼ Physical            │ Description                           │
│   ● Gi0/0             │ [ WAN Interface                    ]   │
│   ● Gi0/1             │                                       │
│   ○ Gi0/2             │ Layer 3                               │
│   ○ Gi0/3             │ IP Address    [192.168.122.101]        │
│                       │ Prefix        [/24]                    │
│ ▼ Virtual        [+]  │                                       │
│   Loopback0           │ Interface settings                    │
│   Tunnel0             │ MTU           [1500]                  │
│   Vlan10              │ Bandwidth     [     ]                  │
│                       │ Delay         [     ]                  │
│                       │                                       │
│                       │ Physical settings                     │
│                       │ Speed         [Auto ▼]                │
│                       │ Duplex        [Auto ▼]                │
│                       │ Negotiation   [✓]                     │
│                       │                                       │
│                       │ [Shutdown]              [Save]         │
└───────────────────────┴───────────────────────────────────────┘
```

---

# 19. Sidebar structure

QML model có thể trả:

```python
[
    {"section": "Physical Interfaces", "interfaces": [...]},
    {"section": "Virtual Interfaces", "interfaces": [...]},
]
```

Hoặc đơn giản hơn có hai ListView riêng.

```qml
Column {
    InterfaceSection {
        title: "Physical Interfaces"
        model: interfaceController.physicalInterfaces
        addVisible: false
    }

    InterfaceSection {
        title: "Virtual Interfaces"
        model: interfaceController.virtualInterfaces
        addVisible: true
    }
}
```

Mình thích cách thứ hai hơn vì ít logic QML.

---

# 20. Add Virtual Interface dialog

Khi bấm:

```text
+ Thêm
```

mở:

```text
Create Virtual Interface

Interface type
┌─────────────────────────┐
│ Loopback              ▼ │
└─────────────────────────┘

Interface Number
┌─────────────────────────┐
│ 0                       │
└─────────────────────────┘

Result:
Loopback0

             [Cancel] [Create]
```

Nếu chọn Tunnel:

```text
Tunnel
Number 0

→ Tunnel0
```

SVI:

```text
SVI

VLAN
[10 - USERS ▼]

→ Vlan10
```

Port-channel:

```text
Port-channel

Group
[1]

Protocol
[LACP]

Mode
[active]

→ Port-channel1
```

Subinterface:

```text
Subinterface

Parent
[GigabitEthernet0/1 ▼]

VLAN
[10]

→ GigabitEthernet0/1.10
```

---

# 21. Dynamic form

Đừng viết một QML form khổng lồ kiểu:

```qml
visible: selectedType === "tunnel"
```

50 lần.

Nên dùng `Loader`.

```qml
Loader {
    id: interfaceFormLoader

    sourceComponent: {
        switch (interfaceController.selectedType) {
        case "physical":
            return physicalForm

        case "loopback":
            return loopbackForm

        case "tunnel":
            return tunnelForm

        case "svi":
            return sviForm

        case "portchannel":
            return portChannelForm

        case "subinterface":
            return subinterfaceForm
        }
    }
}
```

Components:

```text
qml/
└── interfaces/
    ├── InterfacePage.qml
    ├── InterfaceSidebar.qml
    ├── InterfaceListItem.qml
    ├── AddInterfaceDialog.qml
    │
    └── forms/
        ├── PhysicalInterfaceForm.qml
        ├── LoopbackInterfaceForm.qml
        ├── TunnelInterfaceForm.qml
        ├── SviInterfaceForm.qml
        ├── PortChannelInterfaceForm.qml
        └── SubinterfaceForm.qml
```

---

# 22. Physical form

```text
General
────────────────────────────

Name
GigabitEthernet0/0
(read only)

Description
[...........................]

Administration
[✓] Enabled


IPv4
────────────────────────────

IP Address
[192.168.122.101]

Prefix
[24]


Interface Parameters
────────────────────────────

MTU
[1500]

Bandwidth
[        ]

Delay
[        ]


Physical Layer
────────────────────────────

Speed
[Auto ▼]

Duplex
[Auto ▼]

Negotiation
[✓]


IPv4 Options
────────────────────────────

[✓] Proxy ARP
[✓] ICMP Unreachables
[ ] Directed Broadcast


                            [Save]
```

Name phải read-only.

Không có Delete.

---

# 23. Loopback form

Cực gọn:

```text
Loopback0

Description
[Router ID]

IPv4 Address
[10.0.0.1]

Prefix
[32]

                    [Delete] [Save]
```

Không hiện:

```text
speed
duplex
negotiation
media-type
```

Mình cũng sẽ không hiện bandwidth/delay mặc định để UI sạch.

Nếu sau này muốn advanced mode thì cho vào:

```text
Advanced ▼
```

---

# 24. Tunnel form

```text
Tunnel0

Description
[GRE to R2]


IPv4
────────────────────

Address
[10.10.10.1]

Prefix
[30]


Tunnel
────────────────────

Source
[GigabitEthernet0/0 ▼]

Destination
[203.0.113.2]

Mode
[GRE/IP ▼]

Key
[            ]


Administration
────────────────────

[✓] Enabled


              [Delete] [Save]
```

Source dropdown nên cho:

```text
Interfaces
──────────
GigabitEthernet0/0
GigabitEthernet0/1
Loopback0

Custom IP
──────────
192.168.x.x
```

---

# 25. SVI form

```text
Vlan10

VLAN
[10 - USERS ▼]

Description
[Users gateway]

IPv4
192.168.10.1
/24

Administration
[✓] Enabled

                  [Delete] [Save]
```

Dropdown chỉ lấy VLAN của **device hiện tại**.

Không phải toàn database.

---

# 26. Port-channel form

Đây nên là form phức tạp nhất.

```text
Port-channel1

Layer Mode
(●) Layer 2
( ) Layer 3


EtherChannel
──────────────────

Protocol
[LACP ▼]

Mode
[Active ▼]


Members
──────────────────

[x] GigabitEthernet0/1
[x] GigabitEthernet0/2
[ ] GigabitEthernet0/3

Only eligible interfaces are shown.


Layer 3
──────────────────

IP Address
[              ]

Prefix
[              ]


                 [Delete] [Save]
```

Nếu chọn Layer 2:

```text
IP fields disabled
```

Nếu Layer 3:

```text
switchport → disabled
IP fields → enabled
```

---

# 27. Port-channel protocol/mode relationship

Không nên để dropdown Mode hiện tất cả giá trị.

Nếu:

```text
Protocol = LACP
```

chỉ hiện:

```text
active
passive
```

Nếu:

```text
PAgP
```

chỉ hiện:

```text
desirable
auto
```

Nếu:

```text
Static
```

chỉ hiện:

```text
on
```

Backend vẫn phải validate lại, không được chỉ tin UI.

---

# 28. Subinterface form

```text
GigabitEthernet0/1.10

Parent Interface
[GigabitEthernet0/1 ▼]

Subinterface ID
[10]

Encapsulation
[802.1Q ▼]

VLAN ID
[10]

[ ] Native VLAN

IPv4 Address
[192.168.10.1]

Prefix
[24]

                 [Delete] [Save]
```

Backend sinh:

```text
interface GigabitEthernet0/1.10
 encapsulation dot1Q 10
 ip address 192.168.10.1 255.255.255.0
```

---

# 29. Config generator architecture

Đừng làm:

```python
def generate_interface_config(interface):
    if type == ...
    elif type == ...
    elif type == ...
```

khi module lớn dần.

Tách thành strategy.

```text
config_generators/
└── interfaces/
    ├── base.py
    ├── physical.py
    ├── loopback.py
    ├── tunnel.py
    ├── svi.py
    ├── portchannel.py
    └── subinterface.py
```

Base:

```python
from abc import ABC, abstractmethod


class InterfaceConfigGenerator(ABC):
    @abstractmethod
    def generate(self, interface, attrs) -> list[str]: ...
```

---

# 30. Physical generator

```python
class PhysicalInterfaceGenerator(InterfaceConfigGenerator):
    def generate(self, interface, attrs):
        commands = [f"interface {interface.name}"]

        if interface.description:
            commands.append(f"description {interface.description}")
        else:
            commands.append("no description")

        if interface.ip_address:
            commands.append(
                f"ip address {interface.ip_address} {interface.subnet_mask}"
            )
        else:
            commands.append("no ip address")

        if attrs.speed:
            commands.append(f"speed {attrs.speed}")

        if attrs.duplex:
            commands.append(f"duplex {attrs.duplex}")

        commands.append("shutdown" if interface.shutdown else "no shutdown")

        return commands
```

---

# 31. Tunnel generator

```python
class TunnelInterfaceGenerator(InterfaceConfigGenerator):
    def generate(self, interface, attrs):

        commands = [f"interface {interface.name}"]

        if interface.description:
            commands.append(f"description {interface.description}")

        commands.append(f"tunnel source {attrs.tunnel_source}")

        commands.append(f"tunnel destination {attrs.tunnel_destination}")

        commands.append(f"tunnel mode {attrs.tunnel_mode}")

        if interface.ip_address:
            commands.append(
                f"ip address {interface.ip_address} {interface.subnet_mask}"
            )

        commands.append("shutdown" if interface.shutdown else "no shutdown")

        return commands
```

---

# 32. Delete Virtual Interface

Không delete database trước rồi mới SSH.

Flow đúng hơn:

```text
User Delete
   ↓
Service validation
   ↓
generate:
no interface Loopback0
   ↓
push successful?
   ↓ yes
delete DB
```

Nếu đang sử dụng kiểu:

```text
Save
Save & Push
```

thì có thể chia:

### Save

```text
delete DB only
```

### Save & Push

```text
push configuration
→ success
→ commit DB
```

Nhưng với architecture offline configuration của CAMS, mình khuyên lưu **desired state** trong DB trước rồi generator tính diff về sau sẽ mạnh hơn.

---

# 33. Port-channel transaction

Ví dụ user chọn:

```text
Port-channel1

Members:
Gi0/1
Gi0/2
```

Backend cần tạo:

```text
interface Port-channel1
```

và thay đổi:

```text
Gi0/1
Gi0/2
```

nên phải transaction.

Pseudo-code:

```python
with db.transaction():
    portchannel_id = create_portchannel(...)

    add_member(portchannel_id, gi01)
    add_member(portchannel_id, gi02)

    validate_all(...)
```

Nếu có lỗi:

```text
ROLLBACK
```

Không để DB ở trạng thái:

```text
Port-channel tồn tại
nhưng chỉ có 1 member
```

---

# 34. Config sinh cho Port-channel

Ví dụ LACP:

```text
interface GigabitEthernet0/1
 no ip address
 channel-group 1 mode active
 no shutdown
!
interface GigabitEthernet0/2
 no ip address
 channel-group 1 mode active
 no shutdown
!
interface Port-channel1
 ip address 192.168.10.1 255.255.255.0
 no shutdown
```

Generator trả về **configuration plan**, không chỉ một list command.

Ví dụ:

```python
ConfigPlan(
    global_commands=[],
    interface_commands={
        "GigabitEthernet0/1": [
            "no ip address",
            "channel-group 1 mode active",
        ],
        "GigabitEthernet0/2": [
            "no ip address",
            "channel-group 1 mode active",
        ],
        "Port-channel1": ["ip address 192.168.10.1 255.255.255.0"],
    },
)
```

Cách này rất phù hợp với CAMS về lâu dài.

---

# 35. ConfigPlan nên trở thành abstraction chung

Bạn có thể tạo:

```python
@dataclass
class ConfigBlock:
    context: str
    commands: list[str]


@dataclass
class ConfigPlan:
    blocks: list[ConfigBlock]
```

Ví dụ:

```python
ConfigPlan(
    blocks=[
        ConfigBlock(
            context="interface GigabitEthernet0/1",
            commands=["channel-group 1 mode active"],
        ),
        ConfigBlock(
            context="interface GigabitEthernet0/2",
            commands=["channel-group 1 mode active"],
        ),
        ConfigBlock(
            context="interface Port-channel1",
            commands=[
                "ip address 192.168.1.1 255.255.255.0",
                "no shutdown",
            ],
        ),
    ]
)
```

Sau đó SSH engine chỉ biết:

```text
execute(ConfigPlan)
```

không cần biết Port-channel hay OSPF.

---

# 36. Validation layer

Nên có:

```text
validators/
└── interface_validator.py
```

với các validation cụ thể.

## Physical

```python
validate_physical(interface)
```

Rules:

```text
✓ interface phải đến từ Device Profile
✓ không create
✓ không delete
✓ speed phải được profile support
✓ duplex phải được profile support
```

---

# 37. Loopback

```text
✓ number >= 0
✓ không trùng tên
✓ IP hợp lệ nếu có
✓ không speed
✓ không duplex
```

---

# 38. Tunnel

```text
✓ source bắt buộc
✓ destination bắt buộc
✓ destination phải IPv4 hợp lệ
✓ source interface phải tồn tại nếu chọn interface
✓ source và destination không được rỗng
✓ tunnel mode thuộc supported modes
```

---

# 39. SVI

```text
✓ VLAN 1..4094
✓ VLAN tồn tại
✓ Vlan10 không tồn tại trước đó
✓ device phải support SVI
```

Điểm cuối quan trọng.

Router thường và multilayer switch không giống nhau.

Device Profile nên có capability:

```json
{
    "capabilities": {
        "svi": true,
        "etherchannel": true,
        "subinterface": true,
        "gre_tunnel": false
    }
}
```

UI dựa vào đây để không hiện option không hỗ trợ.

---

# 40. Port-channel

Validation:

```text
✓ member là physical
✓ member cùng device
✓ member chưa thuộc Port-channel khác
✓ member không có L3 IP nếu Port-channel yêu cầu clean membership
✓ mode phù hợp protocol
✓ ít nhất 1 member
✓ tất cả member tương thích
```

Có thể thêm:

```text
same speed
same duplex
same switchport mode
same trunk/access configuration
```

ở version sau.

---

# 41. Subinterface

```text
✓ parent physical
✓ parent cùng device
✓ parent không phải switchport L2
✓ parent active
✓ VLAN 1..4094
✓ parent + subinterface ID unique
✓ encapsulation dot1q
```

Một điểm mình sẽ chỉnh đề xuất ban đầu:

Không nhất thiết bắt parent đang `no shutdown` mới cho tạo subinterface trong database.

Có thể cho cấu hình:

```text
Gi0/1 shutdown
Gi0/1.10 configured
```

IOS vẫn có thể lưu config đó.

Nên chỉ cảnh báo:

```text
⚠ Parent interface is administratively down.
The subinterface will not become operational.
```

thay vì block hoàn toàn.

---

# 42. Quan hệ với running-config

Bạn đang có chức năng lấy running config, do đó nên phân biệt hai trạng thái:

```text
desired configuration
```

và:

```text
observed configuration
```

Rất đáng làm.

Ví dụ DB config:

```text
Gi0/1
192.168.10.1/24
no shutdown
```

nhưng thiết bị hiện tại:

```text
Gi0/1
192.168.20.1/24
shutdown
```

UI có thể hiện:

```text
Configuration drift detected
```

Đây là hướng rất phù hợp với tool quản trị mạng.

---

# 43. Interface state nên chia 3 kiểu

### Configured state

Lấy DB:

```text
shutdown = false
IP = 192.168.1.1
```

### Running state

Lấy `show running-config`.

### Operational state

Lấy:

```text
show ip interface brief
```

Ví dụ:

```text
Gi0/0
configured: no shutdown
oper status: up/up
```

Không nên lưu chúng chung một cột.

---

# 44. Sidebar có thể hiển thị status

Ví dụ:

```text
▼ Physical Interfaces

● Gi0/0     192.168.122.101/24
● Gi0/1     192.168.10.1/24
○ Gi0/2     Unconfigured
⊘ Gi0/3     Shutdown
```

Virtual:

```text
▼ Virtual Interfaces

● Loopback0    10.0.0.1/32
● Tunnel0      10.10.10.1/30
⊘ Vlan20       Shutdown
```

---

# 45. Không dùng tab theo loại interface ở đầu nữa

Đây là phần mình sẽ thay đổi so với UI hiện tại.

Nếu đã có sidebar:

```text
Physical
Virtual
```

thì các tab:

```text
GigabitEthernet
FastEthernet
Serial
Tunnel
Loopback
```

ở đầu form thực ra trở nên dư thừa.

Tốt hơn là:

```text
Sidebar quyết định interface
↓
form tự đổi theo interface.type
```

Không cần user chọn:

```text
Tunnel tab
```

rồi lại chọn `Tunnel0`.

Flow tự nhiên hơn:

```text
click Tunnel0
→ Tunnel form
```

---

# 46. Backend API cho QML

Controller nên expose khoảng này thôi:

```python
class InterfaceController(QObject):
    @Slot(int)
    def loadInterfaces(self, device_id): ...

    @Slot(int)
    def selectInterface(self, interface_id): ...

    @Slot(dict)
    def saveInterface(self, payload): ...

    @Slot(str, dict)
    def createVirtualInterface(
        self,
        interface_type,
        payload,
    ): ...

    @Slot(int)
    def deleteInterface(self, interface_id): ...

    @Slot(int)
    def pushInterface(self, interface_id): ...
```

QML không cần biết SQL table.

---

# 47. Payload ví dụ

Physical:

```json
{
  "id": 5,
  "description": "WAN",
  "ipAddress": "192.168.122.101",
  "prefixLength": 24,
  "shutdown": false,

  "physical": {
    "speed": "auto",
    "duplex": "auto",
    "negotiation": true
  }
}
```

Tunnel:

```json
{
  "id": 13,
  "description": "GRE to R2",
  "ipAddress": "10.10.10.1",
  "prefixLength": 30,

  "tunnel": {
    "source": "GigabitEthernet0/0",
    "destination": "192.168.122.102",
    "mode": "gre ip"
  }
}
```

---

# 48. Repository layer

Structure mình đề xuất:

```text
backend/
├── interfaces/
│   ├── models/
│   │   ├── interface.py
│   │   ├── physical.py
│   │   ├── tunnel.py
│   │   ├── svi.py
│   │   ├── portchannel.py
│   │   └── subinterface.py
│   │
│   ├── repositories/
│   │   ├── interface_repository.py
│   │   ├── physical_repository.py
│   │   ├── tunnel_repository.py
│   │   ├── svi_repository.py
│   │   ├── portchannel_repository.py
│   │   └── subinterface_repository.py
│   │
│   ├── services/
│   │   └── interface_service.py
│   │
│   ├── validators/
│   │   └── interface_validator.py
│   │
│   └── generators/
│       ├── physical.py
│       ├── loopback.py
│       ├── tunnel.py
│       ├── svi.py
│       ├── portchannel.py
│       └── subinterface.py
│
└── controllers/
    └── interface_controller.py
```

Không cần tuyệt đối theo tree này, nhưng separation như vậy sẽ tránh `interface.py` thành file 3000 dòng.

---

# 49. Migration SQL

Nếu schema cũ đang có bảng interface, không nên drop ngay.

Migration theo hướng:

```text
001_old_schema
002_split_databases
003_...
004_interface_inheritance
```

Ví dụ:

```sql
BEGIN TRANSACTION;

ALTER TABLE old_interfaces
RENAME TO interfaces_legacy;

CREATE TABLE interfaces (...);

CREATE TABLE physical_interface_attrs (...);
CREATE TABLE tunnel_attrs (...);
CREATE TABLE svi_attrs (...);
CREATE TABLE portchannel_attrs (...);
CREATE TABLE portchannel_members (...);
CREATE TABLE subinterface_attrs (...);

-- migrate dữ liệu phù hợp

COMMIT;
```

Sau khi application chạy ổn vài version mới drop legacy.

---

# 50. CRUD behavior

Có thể định nghĩa ma trận quyền:

| Type         | Create | Edit | Delete | Shutdown |
| ------------ | -----: | ---: | -----: | -------: |
| Physical     |      ❌ |    ✅ |      ❌ |        ✅ |
| Loopback     |      ✅ |    ✅ |      ✅ |        ✅ |
| Tunnel       |      ✅ |    ✅ |      ✅ |        ✅ |
| SVI          |      ✅ |    ✅ |      ✅ |        ✅ |
| Port-channel |      ✅ |    ✅ |      ✅ |        ✅ |
| Subinterface |      ✅ |    ✅ |      ✅ |        ✅ |

UI đọc trực tiếp metadata:

```python
{"canCreate": False, "canDelete": False}
```

thay vì hardcode.

---

# 51. Capability matrix

Thậm chí có thể để profile định nghĩa:

```json
{
  "interfaceCapabilities": {
    "physical": true,
    "loopback": true,
    "tunnel": true,
    "svi": false,
    "portchannel": false,
    "subinterface": true
  }
}
```

Router:

```text
Loopback ✅
Tunnel ✅
Subinterface ✅
SVI ❌
Port-channel tùy platform
```

L3 Switch:

```text
Loopback ✅
SVI ✅
Port-channel ✅
Tunnel tùy model/image
```

UI sẽ tự giới hạn.

---

# 52. Khi Add interface

Flow nên là:

```text
User click Add
      ↓
Get device capabilities
      ↓
Show supported virtual interface types
      ↓
User fills required fields
      ↓
Client validation
      ↓
Backend validation
      ↓
BEGIN TRANSACTION
      ↓
insert interface
      ↓
insert attrs
      ↓
COMMIT
      ↓
refresh UI
```

---

# 53. Save & Push

Flow:

```text
User Save & Push
      ↓
validate payload
      ↓
create proposed state
      ↓
generate ConfigPlan
      ↓
show preview
      ↓
SSH push
      ↓
success
      ↓
save DB state
      ↓
refresh
```

Mình đặc biệt khuyên có **Config Preview**.

Ví dụ:

```text
Configuration Preview

interface Tunnel0
 description GRE to R2
 ip address 10.10.10.1 255.255.255.252
 tunnel source GigabitEthernet0/0
 tunnel destination 192.168.122.102
 tunnel mode gre ip
 no shutdown

                 [Cancel] [Push]
```

Rất hữu ích khi tool của bạn thực sự chạm vào router/switch.

---

# 54. Save khác Save & Push

Bạn đang có concept này rồi, nên Interface module cũng nên giữ.

### Save

```text
DB only
```

### Save & Push

```text
DB + device configuration
```

UI:

```text
[Save] [Save & Push]
```

Hoặc:

```text
Save ▼
├─ Save
└─ Save & Push
```

---

# 55. Delete cũng cần hai kiểu

Virtual interface:

```text
Delete
```

nếu chỉ xóa DB sẽ nguy hiểm khi thiết bị vẫn có interface.

Nên dialog:

```text
Delete Tunnel0?

○ Remove from CAMS only
● Remove from device and CAMS

Device command:
no interface Tunnel0

[Cancel] [Delete]
```

Nếu offline:

```text
Remove from device
```

disabled.

---

# 56. SVI dependency

Nếu delete VLAN 10 trong VLAN module nhưng còn:

```text
interface Vlan10
```

thì database phải xử lý.

Mình khuyên:

```text
ON DELETE RESTRICT
```

thay vì CASCADE.

Vì không nên xóa VLAN rồi âm thầm xóa luôn interface.

UI báo:

```text
Cannot delete VLAN 10.

Used by:
• Vlan10
```

Tương tự:

```text
Physical Gi0/1
↑
Gi0/1.10
```

physical không delete được nên dễ hơn.

---

# 57. Port-channel dependency

Nếu delete:

```text
Port-channel1
```

thì backend phải:

```text
remove channel-group config
```

trên tất cả member.

Ví dụ:

```text
interface Gi0/1
 no channel-group 1
!
interface Gi0/2
 no channel-group 1
!
no interface Port-channel1
```

Do vậy `delete_interface()` cũng nên trả `ConfigPlan`.

---

# 58. Interface naming utility

Nên có một utility duy nhất:

```python
class InterfaceName:
    @staticmethod
    def loopback(number: int):
        return f"Loopback{number}"

    @staticmethod
    def tunnel(number: int):
        return f"Tunnel{number}"

    @staticmethod
    def svi(vlan_id: int):
        return f"Vlan{vlan_id}"

    @staticmethod
    def portchannel(group: int):
        return f"Port-channel{group}"

    @staticmethod
    def subinterface(parent, number):
        return f"{parent}.{number}"
```

Không để mỗi form sinh tên một kiểu.

---

# 59. Normalize tên interface

Cisco có:

```text
Gi0/0
GigabitEthernet0/0
Gig0/0
```

DB nên lưu canonical:

```text
GigabitEthernet0/0
```

UI có thể hiển thị:

```text
Gi0/0
```

Tạo utility:

```python
short_name("GigabitEthernet0/0")
# Gi0/0
```

Như vậy FK/string compare không bị lỗi vì alias.

---

# 60. Database cuối cùng

Quan hệ tổng thể:

```text
devices
  │
  │ 1:N
  ▼
interfaces
  │
  ├── 1:0..1 physical_interface_attrs
  │
  ├── 1:0..1 tunnel_attrs
  │
  ├── 1:0..1 svi_attrs
  │
  ├── 1:0..1 portchannel_attrs
  │              │
  │              └── 1:N portchannel_members
  │
  └── 1:0..1 subinterface_attrs
                      │
                      └── parent_interface_id
```

Đây là thiết kế hợp lý hơn nhiều so với một bảng interface chứa mọi field.

---

# 61. Thứ tự triển khai thực tế

Không nên làm tất cả cùng lúc.

Mình sẽ triển khai theo 6 phase:

1. **Refactor database**

   * `interfaces`
   * `physical_interface_attrs`
   * `tunnel_attrs`
   * `svi_attrs`
   * `portchannel_attrs`
   * `portchannel_members`
   * `subinterface_attrs`

2. **Device Profile**

   * khai báo physical interface theo model
   * tự populate khi tạo device

3. **InterfaceService**

   * CRUD
   * validation
   * transaction

4. **Config generator**

   * Physical
   * Loopback
   * Tunnel
   * SVI
   * Subinterface
   * Port-channel làm cuối vì phức tạp nhất

5. **Refactor QML**

   * sidebar Physical / Virtual
   * Loader dynamic form
   * Add Virtual Interface

6. **Save & Push**

   * ConfigPlan
   * Preview
   * SSH executor
   * error handling / rollback

---

## Cấu trúc mình khuyên chốt cho CAMS

```text
Interface
├── Physical
│   └── PhysicalAttrs
│
├── Loopback
│
├── Tunnel
│   └── TunnelAttrs
│
├── SVI
│   └── SviAttrs
│
├── Port-channel
│   ├── PortChannelAttrs
│   └── PortChannelMembers
│
└── Subinterface
    └── SubinterfaceAttrs
```

Điểm quan trọng nhất là **Physical và Virtual phải khác nhau ngay từ domain model**, chứ không chỉ khác nhau ở giao diện. Một khi backend đã coi tất cả là một loại `Interface` có CRUD giống nhau thì UI sau này sẽ liên tục phải thêm exception.

Với CAMS hiện tại, mình sẽ ưu tiên làm **Physical + Loopback + Tunnel trước**, sau đó **SVI/Subinterface**, và để **Port-channel cuối cùng** vì Port-channel kéo theo transaction đa-interface, dependency, L2/L3 mode và EtherChannel membership.
