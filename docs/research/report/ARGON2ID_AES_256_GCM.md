# Argon2id + AES-256-GCM trong ứng dụng CAMS

## 1. Mục đích sử dụng

Trong dự án này, **Argon2id kết hợp AES-256-GCM được dùng để bảo vệ toàn bộ gói dự án `.ntp` bằng mật khẩu**.

Cơ chế này không mã hóa riêng từng trường dữ liệu. Thay vào đó, ứng dụng đóng toàn bộ workspace thành một tệp ZIP, sau đó mã hóa tệp ZIP trước khi ghi thành tệp `.ntp`.

Các thành phần được bảo vệ gồm:

- `device_network.db`;
- `info_collected.db`;
- thư mục backup;
- snapshot và dữ liệu liên quan nằm trong workspace;
- manifest và những nội dung khác được đóng trong gói dự án.

Luồng tổng quát:

```text
Workspace
   |
   v
Đóng gói thành ZIP
   |
   |  Mật khẩu + salt
   |         |
   |         v
   |      Argon2id
   |         |
   |         v
   |   Khóa AES 256-bit
   v         |
AES-256-GCM mã hóa ZIP
   |
   v
Tệp dự án .ntp được bảo vệ
```

Mã nguồn chính của cơ chế này nằm tại [`infrastructure/workspace/crypto.py`](../../../infrastructure/workspace/crypto.py).

## 2. Vai trò của Argon2id

Argon2id không trực tiếp mã hóa dữ liệu. Nó là hàm dẫn xuất khóa, dùng để chuyển mật khẩu do người dùng nhập thành một khóa nhị phân đủ mạnh cho AES-256.

Ứng dụng thực hiện:

```text
Khóa AES = Argon2id(mật khẩu, salt, tham số chi phí)
```

Các tham số mặc định trong ứng dụng:

| Tham số | Giá trị | Ý nghĩa |
|---|---:|---|
| Độ dài salt | 16 byte | Tạo khóa khác nhau ngay cả khi hai dự án dùng cùng mật khẩu |
| Bộ nhớ | 64 MiB | Làm quá trình dò mật khẩu tốn nhiều bộ nhớ |
| Số vòng lặp | 3 | Tăng chi phí tính toán cho mỗi lần thử mật khẩu |
| Số lane | 4 | Mức song song của Argon2id |
| Độ dài khóa đầu ra | 32 byte | Tương ứng khóa AES 256-bit |

Salt được tạo ngẫu nhiên cho từng lần mã hóa bằng `secrets.token_bytes(16)`. Salt không phải thông tin bí mật và được lưu trong header của tệp `.ntp`.

Đoạn sinh khóa nằm trong hàm `_derive_key()` tại [`crypto.py`](../../../infrastructure/workspace/crypto.py#L280).

## 3. Vai trò của AES-256-GCM

Sau khi Argon2id tạo ra khóa 32 byte, ứng dụng dùng khóa đó với AES ở chế độ GCM để mã hóa ZIP.

AES-256-GCM cung cấp đồng thời:

- **Tính bí mật:** người không có đúng mật khẩu không đọc được nội dung dự án;
- **Tính toàn vẹn:** ứng dụng phát hiện nội dung hoặc metadata đã bị thay đổi;
- **Xác thực dữ liệu:** mật khẩu sai hoặc authentication tag không hợp lệ sẽ làm quá trình mở dự án thất bại.

Mỗi lần mã hóa, ứng dụng tạo một nonce ngẫu nhiên dài 12 byte:

```python
nonce = secrets.token_bytes(12)
```

AES-GCM sinh thêm authentication tag dài 16 byte. Tag được ghi ở cuối tệp mã hóa và được kiểm tra khi giải mã.

Phần header của gói cũng được đưa vào Additional Authenticated Data (AAD):

```python
encryptor.authenticate_additional_data(authenticated_header)
```

Do đó, việc chỉnh sửa header, ciphertext hoặc tag đều có thể làm kiểm tra xác thực thất bại.

Logic mã hóa nằm trong `encrypt_zip_payload()` tại [`crypto.py`](../../../infrastructure/workspace/crypto.py#L72).

## 4. Cấu trúc tệp `.ntp` được mã hóa

Tệp `.ntp` được bảo vệ không phải là một định dạng encrypted ZIP chuẩn. Đây là một envelope riêng của ứng dụng, chứa:

```text
+--------------------------+
| Magic: NTPAES1\0         |
+--------------------------+
| Độ dài header            |
+--------------------------+
| Header JSON              |
+--------------------------+
| ZIP ciphertext           |
+--------------------------+
| GCM authentication tag   |
+--------------------------+
```

Header JSON lưu các thông tin cần thiết để giải mã:

- định dạng và phiên bản envelope;
- thuật toán `AES-256-GCM`;
- KDF `Argon2id`;
- các tham số bộ nhớ, vòng lặp và lane;
- salt dạng Base64;
- nonce dạng Base64;
- độ dài ciphertext và tag.

Ví dụ về cấu trúc logic của header:

```json
{
  "cipher": "AES-256-GCM",
  "ciphertextLength": 123456,
  "envelopeVersion": 1,
  "format": "networktools-encrypted-project",
  "kdf": "Argon2id",
  "kdfParameters": {
    "iterations": 3,
    "lanes": 4,
    "memoryCostKiB": 65536
  },
  "nonce": "<Base64>",
  "salt": "<Base64>",
  "tagLength": 16
}
```

Ứng dụng nhận diện tệp mã hóa bằng magic `NTPAES1\0`, được khai báo tại [`crypto.py`](../../../infrastructure/workspace/crypto.py#L34).

## 5. Quy trình tạo dự án được bảo vệ

Trên giao diện tạo dự án, người dùng chọn **Protect project with a password**, sau đó nhập và xác nhận mật khẩu.

Giao diện được định nghĩa trong [`UI/qml/welcome/CreateProjectDialog.qml`](../../../UI/qml/welcome/CreateProjectDialog.qml#L92).

Quy trình xử lý:

1. Giao diện chuyển mật khẩu tới `WelcomeController`.
2. `WelcomeController` gọi `WorkspaceService.create_project()`.
3. Hai cơ sở dữ liệu SQLite và workspace ban đầu được tạo.
4. `WorkspacePackageCodec.pack()` đóng workspace thành `payload.zip`.
5. `encrypt_zip_payload()` dùng Argon2id để sinh khóa và AES-256-GCM để mã hóa ZIP.
6. Tệp tạm được giải mã và kiểm tra lại.
7. Nếu hợp lệ, tệp tạm thay thế nguyên tử tệp `.ntp` đích.

Các lớp điều phối liên quan:

- [`core/welcome.py`](../../../core/welcome.py#L340);
- [`infrastructure/workspace/service.py`](../../../infrastructure/workspace/service.py#L61);
- [`infrastructure/workspace/package.py`](../../../infrastructure/workspace/package.py#L530).

Nếu người dùng không bật bảo vệ hoặc để mật khẩu trống, `.ntp` được tạo dưới dạng ZIP thông thường, không sử dụng AES-256-GCM.

## 6. Quy trình mở dự án được bảo vệ

Khi mở một tệp `.ntp`, ứng dụng thực hiện:

1. Kiểm tra magic ở đầu tệp để xác định gói có được mã hóa hay không.
2. Nếu tệp được mã hóa nhưng chưa có mật khẩu, phát tín hiệu yêu cầu người dùng nhập mật khẩu.
3. Đọc header, salt, nonce và tham số Argon2id.
4. Dùng mật khẩu nhập vào để sinh lại khóa AES 256-bit.
5. Giải mã ciphertext và xác minh GCM tag.
6. Chỉ khi xác minh thành công, ZIP rõ mới được đưa vào workspace tạm.
7. Kiểm tra manifest, kích thước và SHA-256 của các thành phần trước khi sử dụng.

Hộp thoại nhập mật khẩu nằm tại [`UI/qml/welcome/WorkspacePasswordDialog.qml`](../../../UI/qml/welcome/WorkspacePasswordDialog.qml).

Logic giải mã nằm trong `decrypt_zip_payload()` tại [`crypto.py`](../../../infrastructure/workspace/crypto.py#L130), còn quy trình mở gói nằm tại [`package.py`](../../../infrastructure/workspace/package.py#L466).

Nếu mật khẩu sai, tệp bị hỏng hoặc authentication tag không hợp lệ, ứng dụng trả về thông báo chung:

```text
Unable to unlock this project. The password is incorrect or the file is damaged.
```

Cách thông báo chung này tránh tiết lộ chi tiết không cần thiết về lỗi xác thực.

## 7. Quy trình lưu dự án

Trong phiên làm việc, ứng dụng giữ mật khẩu bảo vệ trong bộ nhớ để có thể mã hóa lại gói ở những lần Save tiếp theo.

Khi lưu:

1. Database và dữ liệu workspace được sao chép sang vùng staging nhất quán.
2. Workspace staging được đóng thành ZIP.
3. Một salt mới và nonce mới được tạo.
4. ZIP được mã hóa thành `<tên-dự-án>.ntp.tmp`.
5. Ứng dụng tự giải mã và kiểm tra tệp tạm.
6. Nếu kiểm tra thành công, `os.replace()` thay thế nguyên tử tệp `.ntp` cũ.

Luồng lưu nằm tại [`infrastructure/workspace/service.py`](../../../infrastructure/workspace/service.py#L111) và [`infrastructure/workspace/package.py`](../../../infrastructure/workspace/package.py#L574).

Việc tạo salt và nonce mới cho mỗi lần lưu giúp tránh tái sử dụng nonce với cùng khóa AES-GCM.

## 8. Xử lý dữ liệu tạm và mật khẩu

Sau khi mở khóa, nội dung dự án phải tồn tại dưới dạng rõ trong một thư mục tạm để SQLite và các phân hệ của ứng dụng có thể sử dụng.

Ứng dụng áp dụng:

- quyền `0700` cho thư mục workspace tạm;
- quyền `0600` cho các tệp được giải nén;
- dọn thư mục tạm khi đóng workspace;
- giữ hoạt động nền hoàn tất trước khi dọn workspace;
- ghi đè bytearray chứa mật khẩu bằng byte `0` khi thay đổi hoặc đóng phiên.

Phần tạo workspace tạm nằm tại [`package.py`](../../../infrastructure/workspace/package.py#L682). Phần quản lý mật khẩu phiên và dọn dẹp nằm tại [`package.py`](../../../infrastructure/workspace/package.py#L339).

Thông báo “CAMS does not store project passwords” nên được hiểu là mật khẩu **không được lưu bền vững vào tệp dự án hoặc cấu hình ứng dụng**. Trong khi dự án đang mở, mật khẩu vẫn được giữ tạm trong RAM để phục vụ thao tác Save.

## 9. Mã hóa theo luồng

Ứng dụng xử lý dữ liệu theo từng khối mặc định 1 MiB thay vì đọc toàn bộ ZIP vào RAM:

```python
_DEFAULT_CHUNK_SIZE = 1024 * 1024
```

Cách này cho phép mã hóa và giải mã những dự án lớn với mức sử dụng bộ nhớ ổn định. Hàm `_transform_stream()` chịu trách nhiệm đọc, biến đổi và ghi từng khối dữ liệu.

Khi giải mã, dữ liệu được ghi vào một tệp `.partial`. Chỉ sau khi `decryptor.finalize()` xác minh GCM tag thành công, tệp partial mới được thay thế thành ZIP đầu ra. Vì vậy, ứng dụng không đưa nội dung giải mã chưa được xác thực vào sử dụng.

## 10. Phạm vi bảo vệ và giới hạn

Cơ chế này bảo vệ dữ liệu **khi tệp `.ntp` đang được lưu trữ hoặc chia sẻ**. Nó không có nghĩa là dữ liệu luôn được mã hóa ở mọi thời điểm.

Cần lưu ý:

- Khi dự án đang mở, dữ liệu đã giải mã tồn tại trong workspace tạm.
- Nội dung nhạy cảm đang được ứng dụng sử dụng có thể tồn tại trong RAM.
- Nếu không đặt mật khẩu, `.ntp` chỉ là ZIP và có thể được mở bằng công cụ giải nén thông thường.
- Nếu quên mật khẩu, ứng dụng không có cơ chế khôi phục.
- Giao diện hiện chỉ yêu cầu mật khẩu không rỗng và hai lần nhập giống nhau; chưa cưỡng chế độ dài hoặc độ mạnh tối thiểu.
- Độ an toàn thực tế vẫn phụ thuộc lớn vào độ mạnh của mật khẩu người dùng.

## 11. Thư viện được sử dụng

Mã nguồn hiện tại sử dụng các thành phần từ thư viện Python `cryptography`:

```python
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
```

Phụ thuộc được khai báo trong [`pyproject.toml`](../../../pyproject.toml):

```toml
"cryptography>=46,<50"
```

Do đó, nếu tài liệu khác ghi rằng phần triển khai này dùng `argon2-cffi`, thông tin đó không khớp với mã nguồn hiện tại. Argon2id trong phiên bản hiện tại được lấy trực tiếp từ `cryptography`.

## 12. Tóm tắt

| Thành phần | Vai trò trong ứng dụng |
|---|---|
| Mật khẩu | Bí mật do người dùng cung cấp |
| Argon2id | Dẫn xuất khóa AES từ mật khẩu |
| Salt 16 byte | Ngăn cùng mật khẩu tạo ra cùng khóa giữa các lần mã hóa |
| Khóa 32 byte | Khóa đầu vào cho AES-256 |
| AES-256-GCM | Mã hóa ZIP và xác thực tính toàn vẹn |
| Nonce 12 byte | Giá trị duy nhất cho mỗi lần mã hóa GCM |
| GCM tag 16 byte | Phát hiện mật khẩu sai hoặc dữ liệu bị thay đổi |
| Header/AAD | Lưu tham số giải mã và được GCM bảo vệ khỏi chỉnh sửa |
| `.ntp` | Envelope chứa header, ciphertext và authentication tag |

Tóm lại, Argon2id chịu trách nhiệm tạo khóa an toàn từ mật khẩu, còn AES-256-GCM dùng khóa đó để bảo vệ toàn bộ nội dung gói dự án `.ntp` cả về tính bí mật lẫn tính toàn vẹn.
