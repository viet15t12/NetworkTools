# Roadmap CAMS

Cập nhật: **2026-08-16**.

Roadmap này mô tả thứ tự ưu tiên kỹ thuật và điều kiện để CAMS tiến từ bản
nghiên cứu sang một bản phát hành có thể tái lập. Mốc phiên bản là mục tiêu, không
phải cam kết ngày; phạm vi được rà soát sau mỗi milestone dựa trên bằng chứng test,
rủi ro và nguồn lực của nhóm.

## 1. Tầm nhìn

CAMS hướng tới một ứng dụng desktop an toàn và có thể kiểm chứng để:

- Quản lý inventory và phiên kết nối thiết bị mạng tập trung.
- Mô hình hóa desired configuration trong SQLite có version/migration.
- Thu thập Running Configuration và operational state về cùng contract dữ liệu.
- Cho phép preview, diff, phê duyệt, push, verify và audit cấu hình theo từng thiết bị.
- Hỗ trợ nghiên cứu Routing, Switching, dịch vụ mạng, Syslog, SFTP và an toàn mạng
  trong môi trường được ủy quyền.

## 2. Nguyên tắc ưu tiên

Thứ tự quyết định:

1. Không làm mất dữ liệu, lộ secret hoặc thay đổi nhầm thiết bị.
2. Contract database/backend có thể tái lập và migration được.
3. Hành vi được chứng minh bằng test tự động và bằng chứng lab phù hợp.
4. Hoàn thiện luồng end-to-end trước khi mở thêm feature mới.
5. Hiệu năng, khả năng tiếp cận và trải nghiệm nhất quán.

Ký hiệu:

| Trạng thái | Ý nghĩa |
| --- | --- |
| `done` | Đạt acceptance criteria và có bằng chứng |
| `in-progress` | Đang triển khai, chưa đủ điều kiện đóng |
| `planned` | Đã xác định phạm vi, chưa bắt đầu |
| `blocked` | Có blocker và owner/điều kiện gỡ blocker rõ ràng |
| `candidate` | Cần discovery trước khi cam kết |

## 3. Baseline — v0.1.0

**Trạng thái:** `done` — baseline phát triển, chưa production-ready.

Đã có:

- Desktop PyQt6/QML, component/theme/navigation và feature workspace chính.
- SQLite bootstrap theo schema mô-đun; persistence cho nhiều feature.
- DHCP, ACL, NAT, Syslog, SFTP và Config Backup có luồng chính; Interfaces và
  Switching có phạm vi Cisco IOS rõ, còn OSPF/EIGRP, Devices/External Tools và
  terminal packaging vẫn `partial`.
- Backend worker/template cho nhiều nhóm Cisco và các luồng sync/push đang được tích
  hợp.
- Unit, integration, QML contract/smoke test và structural validation cho `app/`.
- Tài liệu kiến trúc, sử dụng, database, UI và báo cáo nghiên cứu.

## 4. Milestone v0.2.0 — Nền tảng có thể tái lập và security gate

**Mục tiêu:** một clean checkout có thể build, test và chạy desktop/backend theo
contract dữ liệu thống nhất mà không cần path hoặc dữ liệu riêng của máy phát triển.

| ID | Hạng mục | Ưu tiên | Trạng thái |
| --- | --- | --- | --- |
| FND-01 | Chốt package/entry point backend và loại import/path phụ thuộc cấu trúc cũ | P0 | `in-progress` |
| FND-02 | Chọn schema authority; version hóa DB và tạo migration đầu tiên | P0 | `in-progress` |
| FND-03 | Thêm backend/API smoke test với database tạm và fake device | P0 | `planned` |
| SEC-01 | Lập inventory secret; thay plaintext credential bằng secret provider hoặc migration có kiểm soát | P0 | `planned` |
| SEC-02 | Bật xác minh SSH/NETCONF/RESTCONF an toàn; loại bypass mặc định | P0 | `planned` |
| API-01 | Thêm typed request/response, authentication, authorization và validation cho API | P0 | `planned` |
| API-02 | Thêm task ID, status, cancel, timeout, idempotency và error propagation | P0 | `planned` |
| LIC-01 | Chốt giấy phép dự án và tách/xử lý dependency GPL-2.0-only không tương thích với ứng dụng PyQt6 GPLv3 | P0 | `blocked` |
| CI-01 | Tạo CI chạy structure validation, compile, test và kiểm tra lockfile trên clean environment | P1 | `planned` |
| DOC-01 | Cập nhật tài liệu cũ còn nhắc đường dẫn/schema trước tái cấu trúc | P1 | `done` (2026-08-16) |

### Exit criteria v0.2.0

- `uv sync`, database build, desktop smoke test và backend/API smoke test chạy được
  từ clean checkout.
- Chỉ có một schema authority cho từng database; nâng cấp DB cũ không mất dữ liệu và
  có rollback/backup guidance.
- Không có credential thật trong repository, log, fixture hoặc command-line.
- Kết nối production không tắt TLS/host-key verification mặc định.
- API không trả success trước khi có task/result có thể truy vấn.
- CI bắt buộc xanh trước merge; license và third-party notice được xác định rõ.

## 5. Milestone v0.3.0 — Luồng cấu hình end-to-end nhất quán

**Mục tiêu:** các feature cốt lõi dùng cùng một lifecycle cấu hình và có bằng chứng
fake integration trước khi kiểm chứng thiết bị lab.

| ID | Hạng mục | Ưu tiên | Trạng thái |
| --- | --- | --- | --- |
| CFG-01 | Chuẩn hóa lifecycle validate/backup/render/preview/diff/confirm/push/verify/audit | P0 | `planned` |
| CFG-02 | Hoàn thiện Devices service/repository; đưa CRUD/import/YANG khỏi database facade | P1 | `in-progress` |
| CFG-03 | Hoàn thiện Routing persistence, sync và push cho Static/OSPF/EIGRP | P1 | `in-progress` |
| CFG-04 | Hoàn thiện Interfaces và Switching cho VLAN, switchport, SVI/L3 | P1 | `in-progress` — Router Interface Cisco IOS SSH/Telnet đã có preview/push và fake-connector test; còn verify/rollback, RESTCONF/NETCONF và lab matrix |
| CFG-05 | Đưa DHCP, ACL và NAT vào lifecycle chung; bổ sung diff/verify/rollback guidance | P1 | `planned` |
| CFG-06 | Chuẩn hóa template theo vendor/platform và golden test add/update/delete | P1 | `planned` |
| SYNC-01 | Chuẩn hóa parser Running Configuration thành snapshot/versioned collected state | P1 | `planned` |
| VAL-01 | Validation IPv4/IPv6, mask, wildcard, subnet, range và quan hệ cross-field ở backend | P1 | `planned` |
| LAB-01 | Xây dựng ma trận thiết bị/image/protocol và mẫu biên bản kết quả lab không chứa secret | P1 | `planned` |

### Exit criteria v0.3.0

- Feature cốt lõi không gọi worker hoặc SQL trực tiếp từ QML.
- Mỗi loại cấu hình có preview/diff theo thiết bị và kết quả từng thiết bị.
- Fake connector test bao phủ success, validation failure, timeout, cancel và partial
  batch failure.
- Push thật chỉ được tuyên bố cho tổ hợp vendor/image/protocol có bằng chứng lab và
  bước verify sau push.
- Không xóa desired state hoặc inventory khi probe/sync tạm thời thất bại.

## 6. Milestone v0.4.0 — Quan sát, hiệu năng và trải nghiệm

**Mục tiêu:** ứng dụng ổn định với dữ liệu lớn hơn, tác vụ dài và nhiều trạng thái
lỗi mà không block UI hoặc mất khả năng truy vết.

| ID | Hạng mục | Ưu tiên | Trạng thái |
| --- | --- | --- | --- |
| OBS-01 | Structured logging, correlation/task ID và audit trail đã redaction | P1 | `planned` |
| OBS-02 | Dashboard DHCP/ACL/NAT collected state và trạng thái task theo thiết bị | P2 | `planned` |
| PERF-01 | Pagination/virtualization cho routing, log và database table | P1 | `planned` |
| PERF-02 | Đưa network/resource probe khỏi UI thread; benchmark startup/RAM/task latency | P1 | `planned` |
| UX-01 | Chuẩn hóa loading/empty/error/partial state và dirty-state protection | P1 | `planned` |
| UX-02 | Hoàn thiện keyboard navigation, focus, accessible name, contrast và high-DPI test | P2 | `planned` |
| OPS-01 | Retention/size budget cho log, backup, capture và temporary output | P1 | `planned` |
| PKG-01 | Đóng gói Windows/Linux có checksum, license notice và hướng dẫn nâng cấp | P1 | `planned` |

### Exit criteria v0.4.0

- Không có network/subprocess/query lớn chạy đồng bộ trên UI thread.
- Danh sách lớn có limit/pagination hoặc virtualization và benchmark được lưu lại.
- Tác vụ có progress, cancel, error chi tiết và audit theo correlation ID.
- QML smoke test không warning; luồng chính dùng được bằng bàn phím ở light/dark
  theme và DPI mục tiêu.
- Artifact cài đặt được tạo lặp lại từ tag trên clean build environment.

## 7. Milestone v1.0.0 — Bản phát hành nghiên cứu ổn định

**Mục tiêu:** phát hành có phạm vi hỗ trợ rõ ràng, tái lập được và đủ bằng chứng cho
báo cáo nghiên cứu; không đồng nghĩa với hệ thống quản trị mạng production quy mô
lớn.

### Exit criteria v1.0.0

- Không còn P0/P1 blocker trong phạm vi hỗ trợ đã công bố.
- Public API/QML/database contract được version hóa và có migration policy.
- Full suite, packaging smoke, security review và ma trận lab được lưu cùng release.
- Tài liệu cài đặt, vận hành, backup/restore, troubleshooting và giới hạn hỗ trợ đã
  được kiểm tra từ góc nhìn người dùng mới.
- `CHANGELOG.md`, version metadata, annotated tag và GitHub Release thống nhất.
- Báo cáo chỉ đưa ra claim có bằng chứng tương ứng; source, artifact, checksum và
  citation metadata được lưu trữ.

## 8. Candidate sau v1.0

Chỉ đưa vào milestone khi có use case, threat model và owner:

- Hỗ trợ thêm vendor/platform ngoài ma trận Cisco hiện tại.
- NETCONF/RESTCONF/YANG workflow đầy đủ và capability discovery.
- Topology discovery có concurrency/backpressure và visualization.
- SNMP polling/alerting có retention và permission model.
- Plugin/provider API cho parser, template và connector.
- AI-assisted configuration chỉ ở chế độ đề xuất; không push nếu chưa có command
  policy, per-device diff, approval và rollback độc lập.

## 9. Ngoài phạm vi mặc định

- Điều khiển thiết bị hoặc bắt gói trên hệ thống không được ủy quyền.
- Public Internet API, multi-tenant SaaS hoặc high-availability controller.
- Lưu credential plaintext hoặc thu thập mật khẩu Telnet như chức năng sản phẩm.
- Tuyên bố hỗ trợ production cho vendor/image chưa có ma trận kiểm thử.
- Tự động push output AI không qua policy và phê duyệt theo từng thiết bị.

## 10. Cách duy trì roadmap

- Review roadmap khi đóng milestone hoặc khi xuất hiện rủi ro P0 mới.
- Mỗi item đang làm phải có issue, owner, acceptance criteria và bằng chứng.
- Chuyển item sang `done` chỉ khi exit criteria đạt; merge code chưa đồng nghĩa hoàn
  thành capability.
- Thay đổi phạm vi người dùng thấy được phải đồng thời cập nhật
  [CHANGELOG.md](CHANGELOG.md).
- Khoảng trống chi tiết theo feature được đối chiếu từ code/test, README feature
  và [`docs/CURRENT_APP_FEATURES.md`](docs/CURRENT_APP_FEATURES.md); roadmap chỉ
  giữ mục tiêu cấp release.
