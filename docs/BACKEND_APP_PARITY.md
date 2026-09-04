# Đối chiếu backend cũ và desktop app

Cập nhật: **2026-08-16**. Backend được đối chiếu là `archive/backend/PyCode`; app chuẩn là
runtime ở root theo luồng `QML → core → features → infrastructure`.

| Backend cũ | Trạng thái trong app | Kết luận |
| --- | --- | --- |
| Login/inventory | Có service, repository, batch và session registry | Đã thay thế; CRUD/import còn một phần trong facade |
| Info collect/sync | Running-config, switch `show` collector, Dulwich backup và role-aware config sync | Đã thay thế; app có preview conflict và không thu VTP password |
| Router Interface | `features/interfaces` + View/Push | Đã tích hợp Cisco IOS SSH/Telnet |
| Static/OSPF/EIGRP | `features/routing` | Đã tích hợp; app dùng schema canonical |
| DHCP | `features/dhcp` | Đã tích hợp |
| ACL | `features/acl` | Đã tích hợp |
| NAT | `features/nat` | Đã tích hợp |
| VLAN/interface/STP/VTP/L2 security | `features/switching` | Push đã tích hợp; desktop pull-sync có VLAN/interface/EtherChannel/VTP, backend có thêm parser security/SVI nhưng chưa trở thành desktop contract |
| `state_builder.py` snapshot JSON | Transaction + push hash trong app | Không port file JSON; app dùng DB workspace và conflict policy làm authority |
| SVI/IP routing | Switching repository/UI | Có local CRUD; không nằm trong worker L2 |
| SaveMemories (`write memory`) | `SaveConfigService` + async QML action | Đã bổ sung 2026-08-11 cho active SSH/Telnet session |
| Syslog | `features/syslog` | App có implementation riêng đầy đủ hơn |
| Topology discovery | Không có runtime app | Hoãn vì backend blocking, thiếu guard/cancel/UI/test |
| Packet capture cơ bản | Device Logs/TShark | Có capture được kiểm soát; không port script rời rạc |
| Telnet credential sniffer | Không có | Chủ động loại vì rủi ro thu thập bí mật |
| JSON report manager | Task result, notification và repository theo feature | Không cần port file report dùng chung dễ race |
| FastAPI routes | Không phải desktop runtime | Chưa tích hợp; API cũ thiếu auth, typed task/status/cancel |

Backend hiện có `sync_l2_security.py` và `sync_svi.py`, nhưng “có parser” chưa đủ
để đánh dấu desktop đã hỗ trợ: còn thiếu owner desired-state/conflict, composition,
fake-device integration và UI workflow an toàn. Không gọi trực tiếp các module
này từ QML hoặc cho chúng ghi vào workspace đang mở.

## Nguyên tắc chuyển đổi

- Không copy path, database global, JSON output cố định hoặc credential handling
  từ backend cũ.
- Tái sử dụng session registry và worker nền của app.
- Preview không mở kết nối; thao tác thiết bị thật phải có host/session rõ ràng.
- Chức năng nhạy cảm hoặc có thể quét ngoài phạm vi phải có authorization scope,
  cancel/timeout/limit, retention và test trước khi mở UI.
