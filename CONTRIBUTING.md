# Đóng góp cho CAMS

Cảm ơn bạn đã đóng góp cho CAMS. Tài liệu này quy định cách đề xuất thay
đổi, chuẩn bị nhánh, viết commit, mở pull request và chứng minh chất lượng. Quy tắc
chi tiết cho Python, QML, database và worker mạng nằm trong
[Quy tắc lập trình](docs/CODING_STANDARDS.md); chọn đúng tài liệu qua
[bản đồ tài liệu](docs/README.md).

## 1. Nguyên tắc chung

- Mỗi thay đổi phải giải quyết một vấn đề rõ ràng và có phạm vi nhỏ nhất hợp lý.
- Không đánh đổi an toàn thiết bị, dữ liệu hoặc credential để rút ngắn thời gian
  phát triển.
- Không tuyên bố một chức năng “hoàn thành” nếu mới chỉ có UI, schema, fixture hoặc
  template. Claim phải tương ứng với bằng chứng test và môi trường kiểm chứng.
- Không sao chép mã, dữ liệu, icon hoặc tài liệu khi chưa xác định quyền sử dụng và
  nghĩa vụ ghi công.
- Tôn trọng người tham gia review; thảo luận về hành vi của code, không công kích
  cá nhân.

## 2. Trước khi bắt đầu

1. Đọc [README](README.md), [Roadmap](ROADMAP.md),
   [quy tắc kiến trúc](app/ARCHITECTURE_RULES.md) và README của feature liên quan.
2. Kiểm tra issue/PR hiện có để tránh làm trùng.
3. Với thay đổi lớn, tạo issue mô tả vấn đề, phạm vi, phương án, rủi ro và tiêu chí
   nghiệm thu trước khi viết code.
4. Với schema, public QML/Python contract, API hoặc luồng push thiết bị, thống nhất
   thiết kế với ít nhất một thành viên khác của nhóm.

## 3. Chuẩn bị môi trường

Chạy từ thư mục `app/`:

```bash
uv sync
uv run python scripts/validate_structure.py
uv run python -m unittest discover -s tests -v
```

Không dùng database, credential hoặc backup thật làm fixture. Test tự động không
được mở kết nối tới thiết bị thật.

## 4. Nhánh làm việc

Tên nhánh dùng chữ thường, dấu gạch ngang và một mục đích duy nhất:

```text
feat/routing-preview-diff
fix/sftp-worker-cancel
refactor/database-paths
docs/release-process
test/nat-persistence
```

Không phát triển trực tiếp trên `main`. Rebase hoặc merge `main` vào nhánh trước
khi review cuối, nhưng không rewrite lịch sử của nhánh đã được người khác dùng nếu
chưa thống nhất.

## 5. Commit

Commit tuân theo [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>(<scope>): <mô tả ngắn>
```

Các `type` được dùng:

| Type | Khi sử dụng |
| --- | --- |
| `feat` | Thêm khả năng mới có ý nghĩa với người dùng hoặc public contract |
| `fix` | Sửa lỗi hành vi |
| `refactor` | Đổi cấu trúc nhưng không đổi hành vi dự kiến |
| `perf` | Cải thiện hiệu năng có bằng chứng |
| `test` | Thêm hoặc sửa kiểm thử |
| `docs` | Chỉ thay đổi tài liệu |
| `build` | Dependency, packaging hoặc build |
| `ci` | Pipeline kiểm tra/phát hành |
| `chore` | Bảo trì không thuộc các nhóm trên |

Scope ưu tiên: `ui`, `devices`, `routing`, `dhcp`, `acl`, `nat`, `switching`,
`syslog`, `sftp`, `database`, `backend`, `api`, `docs`, `release`.

Ví dụ:

```text
feat(routing): add per-device configuration preview
fix(database): keep existing database when schema build fails
docs(roadmap): define v0.2.0 exit criteria
```

Mô tả commit nên viết bằng tiếng Anh, ở thể mệnh lệnh, không kết thúc bằng dấu
chấm. Body có thể dùng tiếng Việt hoặc tiếng Anh nhưng phải giải thích “vì sao” và
rủi ro, không lặp lại diff. Breaking change dùng `!` và footer
`BREAKING CHANGE:`.

Không dùng commit message chung chung như `update`, `fix bug`, `new`, `test`,
`add files` hoặc tên nhánh.

## 6. Changelog và phiên bản

- Mọi thay đổi đáng chú ý với người dùng phải được thêm vào mục `Unreleased` của
  [CHANGELOG.md](CHANGELOG.md).
- Không ghi từng commit vào changelog; gộp thành thay đổi có ý nghĩa với người dùng.
- Dùng nhóm `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.
- Phiên bản tuân theo SemVer. Trước `1.0.0`, thay đổi phá vỡ contract phải được ghi
  rõ trong PR và changelog dù có thể chỉ tăng `MINOR`.

## 7. Yêu cầu đối với pull request

PR phải có:

- Vấn đề và lý do cần thay đổi.
- Phạm vi đã làm và phần cố ý chưa làm.
- Cách kiểm thử, lệnh đã chạy và kết quả.
- Ảnh/video trước–sau cho thay đổi UI có thể nhìn thấy.
- Ảnh hưởng tới schema, migration, public contract, cấu hình thiết bị và bảo mật.
- Kế hoạch rollback hoặc phục hồi đối với thay đổi có thể làm mất dữ liệu hay thay
  đổi cấu hình thiết bị.
- Issue liên quan và mục changelog, nếu có.

PR không được chứa:

- Database runtime, WAL/journal, log, backup, private key hoặc credential.
- File sinh tự động không phải artifact được quản lý.
- Refactor không liên quan được trộn vào một bản sửa lỗi.
- Kết quả test được tuyên bố nhưng không thể tái lập.

## 8. Quality gate

Tối thiểu chạy từ `app/`:

```bash
uv run python scripts/validate_structure.py
uv run python -m compileall -q app_facade.py core features infrastructure scripts tests main.py
uv run python -m unittest discover -s tests -v
```

Ngoài ra:

- Schema change phải chạy database bootstrap trên thư mục tạm và có migration test.
- QML/public component change phải có QML smoke hoặc contract test.
- Bug fix phải có regression test thất bại trước bản sửa và đạt sau bản sửa.
- Worker mạng phải có fake connector/session test, timeout và nhánh cancel/error.
- Claim thiết bị thật phải ghi rõ vendor, image/version, topology lab và kết quả xác
  minh sau push; không đưa credential hoặc địa chỉ nhạy cảm vào log.

Nếu một gate không chạy được, PR phải ghi rõ gate nào, nguyên nhân và ai sẽ xác minh
trước khi merge. “Không chạy test” không được xem là kết quả đạt.

## 9. Review và merge

- Cần ít nhất một thành viên khác review trước khi merge.
- Thay đổi database, API, credential hoặc push thiết bị cần review từ người phụ
  trách khu vực đó.
- Mọi nhận xét mức blocking phải được xử lý hoặc có quyết định chấp nhận rủi ro được
  ghi lại.
- Ưu tiên squash merge khi các commit trung gian không có giá trị lịch sử; giữ
  nhiều commit khi mỗi commit độc lập, chạy được và giúp review.
- Không merge khi test bắt buộc đỏ, còn xung đột, thiếu migration hoặc chưa làm rõ
  tác động bảo mật.

## 10. Definition of Done

Một thay đổi chỉ hoàn thành khi:

- Hành vi và tiêu chí nghiệm thu đạt.
- Code tuân thủ ranh giới kiến trúc và quy tắc lập trình.
- Test phù hợp đã được thêm và chạy đạt.
- Error, timeout, cancel và cleanup đã được xử lý.
- README feature, tài liệu cấp ứng dụng, changelog và roadmap được cập nhật nếu
  bị ảnh hưởng theo `docs/README.md`.
- Không có secret, runtime artifact hoặc đường dẫn riêng của máy phát triển.
- Reviewer có thể tái lập kết quả từ hướng dẫn trong PR.

## 11. Quy trình phát hành

1. Đóng phạm vi milestone và xử lý blocker.
2. Chạy toàn bộ quality gate trên clean checkout.
3. Chuyển nội dung `Unreleased` sang phiên bản mới với ngày ISO `YYYY-MM-DD`.
4. Đồng bộ phiên bản trong `app/pyproject.toml` và metadata liên quan.
5. Commit `chore(release): prepare vX.Y.Z`.
6. Tạo annotated tag `vX.Y.Z` và GitHub Release từ nội dung changelog.
7. Lưu checksum, môi trường build và bằng chứng test của artifact phát hành.
