# Third-party source (`vendor/`)

Cập nhật provenance/contract: **2026-08-18**. Markdown bên trong snapshot
Alacritty thuộc upstream và không phải tài liệu CAMS.

Thư mục `vendor/` chứa mã nguồn bên thứ ba được đưa trực tiếp vào repository
CAMS khi dự án cần build một phiên bản đã chỉnh sửa và không thể chỉ
dùng package hệ thống.

## `vendor/alacritty`

`vendor/alacritty` là snapshot từ repository upstream
<https://github.com/alacritty/alacritty>. CAMS giữ source trong cùng
repository để `networktools.sh setup` có thể build terminal companion đồng bộ
với contract Python/QML hiện tại, không phụ thuộc một binary cài sẵn trên máy.

Đường dẫn canonical là `app/vendor/alacritty`, không có
`app/src/vendor/alacritty`. `src/` bên trong `vendor/alacritty/alacritty/` chỉ là
source Rust của crate upstream. Đặt third-party source ở `vendor/` cấp app giúp
tách nó khỏi code do CAMS sở hữu trong `core/`, `features/` và
`infrastructure/`.

Snapshot đã được đối chiếu với upstream baseline:

```text
repository: https://github.com/alacritty/alacritty
commit:     1b2b36a64e88068ad02c95fad00ee2fad31c00bf
date:       2026-08-03
version:    0.18.0-dev
imported:   aeff1063ac77f0a1a731d98224de1d45b23f392e
```

Danh sách file thay đổi và notice giấy phép nằm tại
[`alacritty/NETWORKTOOLS-CHANGES.md`](alacritty/NETWORKTOOLS-CHANGES.md).

Fork cục bộ này khác Alacritty upstream ở các điểm chính:

- binary release có tên `networktools-terminal`;
- nhận các tham số managed `--nt-*`;
- kết nối NTTP/1 qua Unix local socket;
- xử lý focus, close, title, ping và session info từ CAMS;
- giữ cửa sổ mở khi SSH child thoát để người dùng đọc lỗi;
- dùng Alacritty làm renderer/PTY cho interactive SSH child của CAMS.

Phần Python quản lý companion nằm tại `features/terminal/`. Cisco IOS legacy
dùng adapter `features/terminal/interactive_ssh.py` vì Fedora libcrypto có thể
từ chối chữ ký RSA/SHA-1 của IOS cũ. Password không được truyền qua argv,
environment hay NTTP.

## Build và kiểm tra

Từ thư mục `app/`:

```bash
./networktools.sh terminal-build
./networktools.sh terminal-check
```

Binary sinh ra tại:

```text
vendor/alacritty/target/release/networktools-terminal
```

Toàn bộ `vendor/alacritty/target/` là build artifact và đã được ignore bởi
`.gitignore` của repository CAMS. Không dùng `git add -f` cho thư mục
này. Trước
khi push, nên kiểm tra:

```bash
git status --short
git check-ignore -v vendor/alacritty/target/release/networktools-terminal
```

Tại thời điểm audit, `target/` local làm thư mục vendor chiếm khoảng 1,1 GB,
nhưng không file nào dưới `target/` được Git track. Đây là dung lượng build trên
máy phát triển, không phải 1,1 GB source trong repository. Có thể chạy
`cargo clean --manifest-path vendor/alacritty/Cargo.toml` khi chủ động muốn thu
hồi dung lượng; không chạy tự động trong setup hoặc test vì sẽ xóa cache build.

## Có xóa `.builds` và `.github` không?

Không bắt buộc xóa:

- `vendor/alacritty/.builds/` là cấu hình CI của upstream;
- `vendor/alacritty/.github/` là workflow và pull-request template của upstream;
- vì chúng không nằm tại `.github/` ở root repository CAMS, GitHub
  không chạy các workflow lồng này cho CAMS;
- tổng dung lượng hai thư mục rất nhỏ và việc giữ lại giúp snapshot gần với
  upstream hơn khi đối chiếu hoặc cập nhật.

Chỉ xóa hai thư mục trên nếu dự án chủ động áp dụng chính sách "vendor tối
thiểu". Việc xóa không làm thay đổi runtime hoặc kết quả build, nhưng sẽ tạo
thêm khác biệt khi đồng bộ một phiên bản Alacritty upstream mới. Mặc định của
CAMS là **giữ lại**.

## License và cập nhật upstream

Phải giữ `LICENSE-APACHE`, `LICENSE-MIT` và các notice/license nằm trong source
Alacritty. Không thay thế chúng bằng license riêng của CAMS.

Việc giữ fork trong repository phù hợp với policy hiện tại vì:

- Alacritty cho phép dùng, sửa và phân phối source theo Apache-2.0/MIT;
- hai license upstream được giữ nguyên;
- baseline upstream và các file đã sửa được ghi rõ;
- file sửa có notice trỏ đến `NETWORKTOOLS-CHANGES.md`;
- build artifact, database, credential và key không được Git track.

Kết luận này là audit kỹ thuật đối với repository, không phải tư vấn pháp lý.
Khi phát hành binary ra ngoài, gói phát hành vẫn phải kèm license/notice
upstream và license của toàn bộ dependency Rust tương ứng; `Cargo.lock` không
thay thế nghĩa vụ tạo third-party notices/SBOM cho bản phân phối.

Khi cập nhật upstream:

1. ghi lại commit/tag Alacritty nguồn trong pull request và cập nhật
   `NETWORKTOOLS-CHANGES.md`;
2. cập nhật source nhưng không chép `.git/` của repository lồng vào đây;
3. áp dụng lại các thay đổi CAMS trong CLI, event loop và NTTP client;
4. chạy `./networktools.sh terminal-build` và test terminal contract;
5. kiểm tra chắc chắn `target/` không được Git track.

Nếu fork ngày càng khác upstream hoặc cần phát hành độc lập, nên chuyển nó sang
một repository fork riêng rồi tham chiếu bằng Git submodule. Với cách vendoring
hiện tại, mọi source cần thiết để build phải được commit trực tiếp trong
CAMS.
