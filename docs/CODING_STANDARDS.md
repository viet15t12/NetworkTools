# Quy tắc lập trình CAMS

Tài liệu này là chuẩn bắt buộc cho code mới và phần code được sửa. Code legacy
không cần được format hoặc refactor hàng loạt nếu không thuộc phạm vi thay đổi.
Trong trường hợp xung đột, an toàn vận hành và tính nhất quán của module đang sửa
được ưu tiên hơn thay đổi thuần hình thức.

## 1. Ranh giới kiến trúc

Luồng phụ thuộc chuẩn:

```text
QML → QObject/slot → service → repository → SQLite
                         └──→ worker → infrastructure/network → device
```

- `app/UI/` chỉ trình bày trạng thái và phát ý định người dùng; không chứa SQL,
  command thiết bị hoặc logic nghiệp vụ dài.
- `app/core/` giữ facade/context dùng chung; không nhận repository hoặc nghiệp vụ
  feature mới.
- `app/features/<feature>/` sở hữu model, validation, service, repository, worker,
  parser và template của feature.
- `app/infrastructure/` chỉ chứa adapter kỹ thuật; không import QML và không quyết
  định chính sách nghiệp vụ.
- Repository chỉ làm việc với persistence. Worker chỉ làm việc với thiết bị hoặc
  tác vụ nền. Service điều phối validation, transaction và chuyển trạng thái.
- Feature không đọc trực tiếp bảng riêng của feature khác. Giao tiếp qua public
  service/DTO hoặc contract dùng chung đã được tài liệu hóa.
- Adapter legacy phải có consumer xác định, ghi rõ thời hạn loại bỏ và test bảo vệ
  contract tương thích.

Xem thêm [quy tắc kiến trúc của app](../app/ARCHITECTURE_RULES.md).

## 2. Python

Chuẩn nền là Python 3.11+ và [PEP 8](https://peps.python.org/pep-0008/).

### 2.1 Định dạng và đặt tên

- Dùng UTF-8, LF, bốn dấu cách; không dùng tab hoặc trailing whitespace.
- Giới hạn mục tiêu là 100 ký tự mỗi dòng. Có thể vượt khi URL, command fixture
  hoặc chuỗi không thể tách sẽ khó đọc hơn nếu xuống dòng.
- Module, hàm và biến dùng `snake_case`; class dùng `PascalCase`; hằng số dùng
  `UPPER_SNAKE_CASE`.
- Identifier và public API dùng tiếng Anh. Tài liệu người dùng có thể dùng tiếng
  Việt; không trộn hai ngôn ngữ trong cùng một tên định danh.
- Import theo thứ tự standard library, third-party, local; không dùng wildcard
  import và không sửa `sys.path` trong feature code.

### 2.2 API, type và cấu trúc hàm

- Hàm/method public và mọi boundary giữa layer phải có type hint.
- Dùng `dataclass`, `TypedDict`, enum hoặc model rõ ràng cho payload có cấu trúc;
  tránh truyền `dict[str, Any]` xuyên nhiều layer.
- Một hàm thực hiện một trách nhiệm. Tách validation, I/O và biến đổi dữ liệu để có
  thể kiểm thử độc lập.
- Public module/class/function cần docstring mô tả contract, lỗi có thể phát sinh và
  side effect; comment giải thích “vì sao”, không diễn giải lại câu lệnh.
- Không dùng mutable default argument. Không trả `None`, `False`, chuỗi lỗi và
  exception cho cùng một loại kết quả.
- Dependency có side effect như database, connector, filesystem, clock và process
  launcher phải được inject hoặc bọc bằng adapter để test thay thế được.

### 2.3 Lỗi, log và tài nguyên

- Bắt exception cụ thể. Không dùng `except Exception: pass` hoặc biến lỗi thành
  success giả.
- Lỗi qua layer phải giữ nguyên nguyên nhân bằng exception chaining hoặc result có
  cấu trúc; thông báo cho UI phải an toàn và có thể hành động.
- Runtime code dùng logging/service signal, không dùng `print()` trừ CLI/script.
- Log không chứa password, private key, token, full credential URI hoặc running-config
  chưa redaction.
- Mọi connection, cursor, file, thread và session phải có ownership/cleanup rõ ràng;
  ưu tiên context manager và `finally`.
- Mọi I/O mạng phải có timeout hữu hạn, cancel path và trạng thái lỗi phân biệt.

### 2.4 Đường dẫn và cấu hình

- Dùng `pathlib.Path`; không nối path bằng chuỗi và không phụ thuộc current working
  directory.
- Path runtime lấy từ `infrastructure.database.paths` hoặc app path service.
- Không hard-code drive, home directory, host lab, port, username hoặc secret.
- Cấu hình bắt buộc phải được validate khi khởi động; không tự tạo database rỗng khi
  path/schema sai.

## 3. PyQt6 và bất đồng bộ

- Không chạy SSH, RESTCONF, NETCONF, ping subprocess, packet capture, truy vấn lớn
  hoặc filesystem nặng trên UI thread.
- Worker chỉ truyền dữ liệu bất biến/đã serialize qua signal; không chạm QML object
  từ thread nền.
- Mỗi task phải có lifecycle `queued/running/succeeded/failed/cancelled`, task ID và
  cleanup khi QObject bị hủy.
- Signal/slot public phải có kiểu và tên ổn định; thay đổi phá vỡ contract phải cập
  nhật QML test, README feature và changelog.
- Không dùng timer để che race condition. Dùng state machine, generation/request ID
  hoặc cancellation token để loại kết quả cũ.

## 4. QML và Qt Quick

Tuân theo [QML Coding Conventions](https://doc.qt.io/qt-6/qml-codingconventions.html)
của Qt.

### 4.1 Cấu trúc component

Trong object gốc, sắp xếp theo thứ tự:

1. `id`;
2. property và alias;
3. signal;
4. JavaScript function;
5. object properties;
6. child objects;
7. states, transitions và handlers khi cần.

- Dùng `required property` cho dependency bắt buộc từ bên ngoài.
- Tham chiếu property của object cha qua `id` rõ ràng; tránh unqualified lookup.
- Signal handler có tham số phải khai báo tham số tường minh.
- JavaScript dài hơn vài dòng hoặc dùng lại phải chuyển thành function; nghiệp vụ
  phức tạp chuyển sang Python service.
- Component public phải được khai báo trong `qmldir` và có smoke/contract test.

### 4.2 Thiết kế và khả năng sử dụng

- Dùng component chuẩn, theme token và `AppAssets`; không hard-code màu semantic,
  icon path hoặc tự tạo control gần trùng component hiện có.
- Layout phải hoạt động ở kích thước cửa sổ tối thiểu, DPI cao và nội dung dài;
  không dùng tọa độ tuyệt đối nếu layout/anchor phù hợp hơn.
- Control tương tác phải có focus, keyboard path, trạng thái disabled, tooltip hoặc
  accessible name phù hợp.
- Tác vụ bất đồng bộ phải hiển thị progress/busy, cho phép cancel khi khả thi và
  không để người dùng gửi lặp cùng thao tác nguy hiểm.
- Không che lỗi bằng placeholder trống. Empty, loading, partial và error là các
  trạng thái riêng.
- Thay đổi nhìn thấy được cần kiểm tra light/dark theme, accent tùy chỉnh và độ tương
  phản.

## 5. Database và migration

- Các tệp schema mô-đun trong `app/infrastructure/database/schemas/` là nguồn để
  build database desktop. Không sửa database runtime rồi coi đó là schema change.
- Mọi schema change phải gồm: schema nguồn, migration cho database đã tồn tại,
  repository/query liên quan, bootstrap test, migration test và cập nhật tài liệu.
- Dùng parameter binding; không ghép SQL từ dữ liệu người dùng bằng f-string hoặc
  phép cộng chuỗi.
- Bật foreign key, dùng transaction cho thay đổi nhiều bảng và rollback toàn bộ khi
  một bước thất bại.
- Query danh sách phải có ordering xác định. Dữ liệu lớn cần pagination/limit thay
  vì `fetchall()` không giới hạn.
- Không dùng `SELECT *` ở public repository contract. Ghi rõ cột để schema change
  không âm thầm đổi payload.
- Phân biệt desired configuration, collected state và task/audit state; không dùng
  chung một cờ trạng thái với nhiều ý nghĩa.
- Không commit `.db`, WAL, journal, backup hoặc dữ liệu chứa credential.

## 6. Kết nối và cấu hình thiết bị

- Mặc định fail-closed: nếu không xác định được host, vendor, role, protocol hoặc
  trạng thái dev thì không được push.
- Mọi luồng thay đổi thiết bị phải theo chuỗi:

```text
validate → select target → backup → render → preview/diff → confirm
→ execute → collect result → verify → audit/rollback guidance
```

- Command template phải deterministic, phân tách theo vendor/platform và có golden
  test cho add/update/delete.
- Không cho output AI hoặc dữ liệu người dùng đi thẳng vào privileged command nếu
  chưa qua allowlist/policy parser và preview theo từng thiết bị.
- Không thêm `verify=False`, `hostkey_verify=False` hoặc auto-accept host key vào
  code production. Ngoại lệ lab phải explicit, mặc định tắt và được cảnh báo/test.
- Batch operation phải giới hạn concurrency, giữ kết quả theo từng thiết bị và
  không báo success chung khi có thiết bị thất bại.
- Không xóa inventory hoặc desired configuration chỉ vì probe mạng tạm thời thất
  bại.
- Packet capture, Telnet analysis và công cụ tương tự chỉ hoạt động trong phạm vi
  được ủy quyền, có giới hạn quyền, thời gian và retention.

## 7. Bảo mật và dữ liệu nhạy cảm

- Không lưu secret mới dưới dạng plaintext nếu có thể dùng OS credential store hoặc
  secret provider. Nếu legacy bắt buộc, phải ghi rõ threat model và migration plan.
- Redact secret tại nguồn trước khi log, thông báo, preview, report hoặc backup.
- Không đưa password vào command-line argument, URL, exception message hoặc fixture.
- Mọi API ngoài localhost cần authentication, authorization, validation, rate limit,
  audit và TLS policy trước khi được bật.
- Dependency hoặc asset mới phải được kiểm tra license, nguồn và phiên bản; cập nhật
  lockfile cùng third-party notice khi cần.
- Lỗ hổng chưa công bố không thảo luận trong issue công khai; báo trực tiếp cho nhóm
  duy trì.

## 8. Kiểm thử

Sắp xếp test theo mục đích:

- `tests/unit/`: validation, parser, model, repository nhỏ;
- `tests/integration/`: SQLite tạm, fake connector và luồng nhiều layer;
- `tests/qml/` cùng `test_qml_*`: harness, module load và UI contract;
- `tests/syslog/`: listener/parser/repository/lifecycle của Syslog.

Quy tắc:

- Test phải deterministic, độc lập thứ tự và tự dọn tài nguyên.
- Không dùng network, thiết bị, clock thật hoặc home directory trong unit/integration
  test; inject fake và dùng temporary directory/database.
- Mỗi bug fix có regression test. Mỗi state transition nguy hiểm có happy path,
  validation failure, I/O failure, timeout và cancel test phù hợp.
- Không giảm assertion chỉ để test đạt. Khi contract đổi, giải thích và cập nhật
  cả implementation lẫn test.
- Test QML không được phát sinh warning mới; component loader/worker phải được hủy
  sạch sau test.

Quality gate chuẩn nằm trong [CONTRIBUTING.md](../CONTRIBUTING.md#8-quality-gate).

## 9. Tài liệu và trạng thái chức năng

- README của feature phải có `implemented`, `partial`, `stub` hoặc `planned`, public
  contract, persistence, worker và giới hạn đã biết.
- Thay đổi contract cập nhật README feature và tài liệu cấp ứng dụng chịu ảnh
  hưởng theo [`docs/README.md`](README.md) trong cùng PR.
- Tài liệu phân biệt rõ: có code, có test fake, có test tích hợp, đã kiểm chứng lab và
  sẵn sàng production.
- Ví dụ lệnh phải chạy được từ vị trí được nêu; path dùng `/` trong tài liệu đa nền
  tảng khi không phải ví dụ PowerShell.
- Quyết định kiến trúc khó đảo ngược cần một ADR ngắn trong `docs/decisions/` trước
  khi implementation được merge.

## 10. Những mẫu bị cấm

- SQL hoặc command thiết bị trong QML.
- Feature import QML, hoặc infrastructure import feature/UI.
- Secret, database runtime, log hoặc backup thật trong Git.
- Absolute path riêng của máy phát triển.
- Network I/O không timeout hoặc chạy trên UI thread.
- `except Exception: pass`, success giả, lỗi chỉ được `print` rồi bỏ qua.
- Merge schema change không có migration và test.
- Xóa dữ liệu trước khi input/build output được xác minh.
- Đánh dấu feature “implemented” chỉ dựa trên UI, schema hoặc fixture.

## 11. Checklist review nhanh

- Ranh giới layer và ownership của code đúng chưa?
- Input, permission, secret và target device đã được validate chưa?
- Failure, timeout, cancel, cleanup và partial success có đúng không?
- Transaction/migration có bảo vệ dữ liệu cũ không?
- UI có loading/empty/error, keyboard và theme states không?
- Test có chứng minh hành vi và không dùng tài nguyên thật không?
- README, function map, changelog và roadmap có cần cập nhật không?
