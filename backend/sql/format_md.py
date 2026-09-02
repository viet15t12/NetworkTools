import re

with open('e:/CAMS/backend/sql/database.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix Line 1
line1_old = """🌐 CẤU TRÚC DATABASE QUẢN LÝ THIẾT BỊ MẠNG (NETWORK ADMIN)Bảng dưới đây tóm tắt các phân vùng chính trong hệ thống:Phân vùngMục tiêu quản lýSố lượng bảngCore InfrastructureThiết bị gốc và thông tin đăng nhập2L3 ConnectivityInterface, Sub-interface, Tunnel, WAN, QoS6IP ServicesDHCP Pool, Excluded Address, Helper IP3Dynamic RoutingStatic, OSPF, EIGRP (đầy đủ các tham số tuning)18Security & NATACL (Standard/Extended), Route-map, NAT Rules14L2 SwitchingVLAN, EtherChannel, STP, Port Security, Monitor12🏗️ 1. HỆ THỐNG THIẾT BỊ CỐT LÕI (CORE DEVICES)Đây là "xương sống" của toàn bộ Database. Mọi cấu hình khác đều phải tham chiếu về bảng devices.Lưu ý kỹ thuật: > * Sử dụng PRAGMA foreign_keys = ON để đảm bảo tính toàn vẹn dữ liệu giữa các bảng.Chế độ WAL (Write-Ahead Logging) giúp tối ưu hóa hiệu suất ghi.SQLPRAGMA foreign_keys = ON;"""
line1_new = """# 🌐 CẤU TRÚC DATABASE QUẢN LÝ THIẾT BỊ MẠNG (NETWORK ADMIN)

Bảng dưới đây tóm tắt các phân vùng chính trong hệ thống:

| Phân vùng | Mục tiêu quản lý | Số lượng bảng |
| :--- | :--- | :--- |
| Core Infrastructure | Thiết bị gốc và thông tin đăng nhập | 2 |
| L3 Connectivity | Interface, Sub-interface, Tunnel, WAN, QoS | 6 |
| IP Services | DHCP Pool, Excluded Address, Helper IP | 3 |
| Dynamic Routing | Static, OSPF, EIGRP (đầy đủ các tham số tuning) | 18 |
| Security & NAT | ACL (Standard/Extended), Route-map, NAT Rules | 14 |
| L2 Switching | VLAN, EtherChannel, STP, Port Security, Monitor | 12 |

## 🏗️ 1. HỆ THỐNG THIẾT BỊ CỐT LÕI (CORE DEVICES)

Đây là "xương sống" của toàn bộ Database. Mọi cấu hình khác đều phải tham chiếu về bảng `devices`.

**Lưu ý kỹ thuật:** 
> * Sử dụng `PRAGMA foreign_keys = ON` để đảm bảo tính toàn vẹn dữ liệu giữa các bảng.
> * Chế độ WAL (Write-Ahead Logging) giúp tối ưu hóa hiệu suất ghi.

```sql
PRAGMA foreign_keys = ON;"""
content = content.replace(line1_old, line1_new)

# Fix Line 25
line25_old = """🔌 2. QUẢN LÝ INTERFACE (ROUTER / LAYER 3)Cấu trúc phân cấp từ Interface vật lý đến các tính năng mở rộng như Tunnel, QoS và WAN.Interface Name: Bảng gốc lưu thông tin IP cơ bản.L3 Extension: Các thông số nâng cao như MTU, Bandwidth, Proxy ARP.Sub-interfaces: Hỗ trợ chia VLAN (dot1q) trên cổng Router.SQLCREATE TABLE interface_name ("""
line25_new = """```

## 🔌 2. QUẢN LÝ INTERFACE (ROUTER / LAYER 3)

Cấu trúc phân cấp từ Interface vật lý đến các tính năng mở rộng như Tunnel, QoS và WAN.
* **Interface Name**: Bảng gốc lưu thông tin IP cơ bản.
* **L3 Extension**: Các thông số nâng cao như MTU, Bandwidth, Proxy ARP.
* **Sub-interfaces**: Hỗ trợ chia VLAN (dot1q) trên cổng Router.

```sql
CREATE TABLE interface_name ("""
content = content.replace(line25_old, line25_new)

# Fix Line 120
line120_old = """🛠️ 3. DỊCH VỤ IP (DHCP & HELPER)Phần này quản lý việc cấp phát IP động cho các mạng LAN.SQLCREATE TABLE dhcp_pool ("""
line120_new = """```

## 🛠️ 3. DỊCH VỤ IP (DHCP & HELPER)

Phần này quản lý việc cấp phát IP động cho các mạng LAN.

```sql
CREATE TABLE dhcp_pool ("""
content = content.replace(line120_old, line120_new)

# Fix Line 152
line152_old = """🛣️ 4. ĐỊNH TUYẾN (ROUTING)Bao gồm các bảng dành cho Static Route, OSPF (đa vùng) và EIGRP (AS).📍 4a. Static RoutesSQLCREATE TABLE static_default_routes ("""
line152_new = """```

## 🛣️ 4. ĐỊNH TUYẾN (ROUTING)

Bao gồm các bảng dành cho Static Route, OSPF (đa vùng) và EIGRP (AS).

### 📍 4a. Static Routes

```sql
CREATE TABLE static_default_routes ("""
content = content.replace(line152_old, line152_new)

# Fix Line 170
line170_old = """🦉 4b. OSPF (Open Shortest Path First)Hỗ trợ đầy đủ Area, Network, Tuning và Redistribution.SQLCREATE TABLE IF NOT EXISTS ospf_processes ("""
line170_new = """```

### 🦉 4b. OSPF (Open Shortest Path First)

Hỗ trợ đầy đủ Area, Network, Tuning và Redistribution.

```sql
CREATE TABLE IF NOT EXISTS ospf_processes ("""
content = content.replace(line170_old, line170_new)

# Fix Line 304
line304_old = """🐆 4c. EIGRP (Enhanced Interior Gateway Routing Protocol)SQLCREATE TABLE eigrp_processes ("""
line304_new = """```

### 🐆 4c. EIGRP (Enhanced Interior Gateway Routing Protocol)

```sql
CREATE TABLE eigrp_processes ("""
content = content.replace(line304_old, line304_new)

# Fix Line 458
line458_old = """🛡️ 5. BẢO MẬT & NAT (SECURITY, ACL & NAT)Hệ thống quản lý quyền truy cập và chuyển đổi địa chỉ.📜 5a. ACL Database (Access Control Lists)Bao gồm quy tắc Standard, Extended, Dynamic, Reflexive và cả MAC ACL.SQLCREATE TABLE ACL_DB ("""
line458_new = """```

## 🛡️ 5. BẢO MẬT & NAT (SECURITY, ACL & NAT)

Hệ thống quản lý quyền truy cập và chuyển đổi địa chỉ.

### 📜 5a. ACL Database (Access Control Lists)

Bao gồm quy tắc Standard, Extended, Dynamic, Reflexive và cả MAC ACL.

```sql
CREATE TABLE ACL_DB ("""
content = content.replace(line458_old, line458_new)

# Fix Line 557
line557_old = """🧭 5b. Route Map & NAT CoreĐiều hướng traffic và xử lý địa chỉ NAT Inside/Outside.SQLCREATE TABLE route_map_db ("""
line557_new = """```

### 🧭 5b. Route Map & NAT Core

Điều hướng traffic và xử lý địa chỉ NAT Inside/Outside.

```sql
CREATE TABLE route_map_db ("""
content = content.replace(line557_old, line557_new)

# Fix Line 736
line736_old = """🏗️ 6. HỆ THỐNG QUẢN LÝ SWITCH L2 (L2 SWITCHING)Dành cho các thiết bị Switch (Access/Distribution), bao gồm VLAN, STP và Security.SQLCREATE TABLE IF NOT EXISTS vlan_db ("""
line736_new = """```

## 🏗️ 6. HỆ THỐNG QUẢN LÝ SWITCH L2 (L2 SWITCHING)

Dành cho các thiết bị Switch (Access/Distribution), bao gồm VLAN, STP và Security.

```sql
CREATE TABLE IF NOT EXISTS vlan_db ("""
content = content.replace(line736_old, line736_new)

# Add closing code fence at the end
content = content.strip() + '\n```\n'

with open('e:/CAMS/backend/sql/database.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("Format complete.")
