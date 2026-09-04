# Kiểm chứng mã nguồn và chất lượng repository

Cập nhật: **2026-08-16**. Audit này phân biệt bằng chứng tĩnh, automated test và
kiểm chứng thiết bị thật. Nó không nâng claim production từ việc “có code”.

## 1. Phạm vi

- Đọc composition root, facade, feature, infrastructure, QML, schema, script và
  test trong runtime ở root.
- Đối chiếu read-only `archive/api_server.py`, `archive/backend/`, `examples/mock/`, license và vendored
  terminal để xác định ranh giới tích hợp.
- Không chạy worker trên thiết bị thật, không bind listener công cộng và không
  kiểm tra nội dung trong các thư mục được loại khỏi đợt tài liệu.
- Markdown upstream trong `vendor/alacritty/` được giữ nguyên; provenance và
  fork delta do `vendor/README.md` quản lý.

## 2. Bằng chứng cấu trúc

Desktop có 335 file Python toàn repository (bao gồm backend), 256 QML và 37 SQL;
runtime hiện hành được tổ chức theo `core/features/infrastructure/UI`.
Schema sạch tạo được 73 bảng device và 20 bảng collected, với foreign key,
index/trigger và migration trạng thái số legacy.

`scripts/validate_structure.py` khóa README/status feature, qmldir target,
artifact runtime, absolute machine path và boundary core/session. Lần chạy đầu
ngày 2026-08-16 phát hiện thiếu `data/README.md`, `templates/README.md` và status
Interfaces; các lỗi tài liệu này đã được sửa trong đợt cập nhật.

## 3. Trạng thái test tại thời điểm audit

Lệnh full suite được chạy trong môi trường `uv` với CPython 3.14.6. Nhiều nhóm
schema, routing, DHCP/ACL/NAT, dev-mode, session concurrency, menu và Syslog đã
chạy đạt trước khi suite dừng, nhưng baseline **không xanh**:

- contract docstring của database slot còn ít nhất một failure;
- một số test External Tools giả lập Windows thất bại/lỗi trên host Linux;
- QML run kết thúc process khi default `data/device_network.db` chưa tồn tại.

Vì vậy không ghi số “x/y tests passed” và không dùng kết quả này làm chứng nhận
release. Đây là vấn đề code/test environment tồn tại trước thay đổi Markdown;
đợt này không sửa code nghiệp vụ. Cần bootstrap DB test cô lập, phân tách test
platform và sửa contract failure trước khi yêu cầu full-suite gate.

Hai nhóm liên quan trực tiếp tới tài liệu mới được chạy riêng: SFTP đạt 17 test
khả dụng và bỏ qua đúng một test DPAPI trên Linux; Syslog đạt 16/16 test khi Qt
chạy offscreen và socket loopback được cấp quyền. Kết quả này xác nhận contract
cục bộ, không thay thế thử nghiệm SFTP/Syslog trên hạ tầng thật.

## 4. Capability và mức bằng chứng

| Nhóm | Code/UI | Automated evidence | Lab/production claim |
| --- | ---: | ---: | --- |
| Workspace/package/snapshot | Có | Unit/integration | Chưa production-certified |
| Device/session/batch/config history | Có | Fake/temp DB/concurrency | Cần matrix thiết bị |
| DHCP/ACL/NAT/static | Có | Persistence/worker/dev tests | Cisco lab theo model/IOS |
| OSPF/EIGRP/FHRP/Interfaces | Có, một phần giới hạn | CRUD/render/fake session | Chưa đủ vendor/firmware matrix |
| Switching | Có Layer 2 chính | Desired/view-push/sync tests | Pull-sync/rollback còn thiếu |
| Syslog | Có UDP/TCP | Parser/socket/repository/QML | Chưa soak/load/TLS |
| SFTP | Có client tích hợp | Fake service/temp filesystem | Chưa resume/checksum/soak |
| Terminal companion | Manager + fork source | Protocol/lifecycle contract | Packaging/Fedora/Wayland/EVE-NG partial |
| Backend FastAPI | Có code kế thừa | Không có suite end-to-end chuẩn | Không phải API sản phẩm |

Chi tiết người dùng xem tại
[`CURRENT_APP_FEATURES.md`](CURRENT_APP_FEATURES.md).

## 5. Rủi ro ưu tiên

### P0/P1 — trước môi trường production

1. Credential thiết bị/PPP còn có thể plaintext trong workspace mở; cần secret
   reference/store và redaction end-to-end.
2. Một số RESTCONF request còn tắt TLS verification; không mở production trước
   khi có trust/CA policy.
3. API cũ thiếu authentication/authorization, typed request, task status/cancel
   và xác nhận kết quả thiết bị.
4. Push chưa có verify/rollback tự động đồng đều; cần maintenance/backup/verify
   workflow ngoài app.
5. Full test suite chưa xanh trên môi trường audit; cần sửa failure thật và tách
   platform-specific expectations.
6. Topology/sniffer backend có scope/blocking/security risk; không tích hợp trực
   tiếp.

### P2 — khả năng bảo trì

1. `DatabaseManager` vẫn còn slot mixin CRUD/routing/import cần chuyển dần sang
   feature service.
2. `core/external_tools.py` và `features/sftp/controller.py` còn nhiều trách
   nhiệm; tách theo behavior/test thay vì line count.
3. OSPF/EIGRP worker và một số parser thử nghiệm vẫn mang legacy pattern/global
   output; cần injected path/session và fake connector.
4. Compatibility embedded terminal/qtpyTerminal cần xóa sau khi companion đạt
   acceptance để giảm hai implementation.

## 6. Backend và vendor boundary

`archive/backend/` vẫn hữu ích làm nguồn parser/template, và gần đây có thêm sync L2
security/SVI. Tuy nhiên subsystem chưa chia sẻ lifecycle/schema/locking với
desktop; “có file” không làm feature đó thành capability app. Mọi port phải đi
qua feature owner, canonical DB, registry và test.

`vendor/alacritty/` là fork source lớn. Không review lại toàn bộ upstream như
code CAMS trong mỗi PR; review delta CAMS (`--nt-*`, NTTP, hold,
branding/build), lưu provenance và giữ license. Build artifact `target/` không
được track.

## 7. Quality gate đề xuất

```bash
uv run python scripts/validate_structure.py
uv run python -m compileall .
uv run python -m unittest discover -s tests -v
./cams.sh terminal-check
```

Ngoài automated gate, thay đổi network command cần preview snapshot, fake-session
test, redaction test và lab evidence ghi model/OS/transport. Tài liệu capability
phải cập nhật cùng code; xem [`README.md`](README.md) để chọn đúng tài liệu.
