# Infrastructure

Adapter kỹ thuật dùng chung cho SQLite, kết nối thiết bị, hệ điều hành và package
workspace. **implemented** theo bốn namespace: `database/` sở hữu path/schema/
connection; `network/` sở hữu connector, registry, runner và batch; `system/` sở
hữu desktop/network/resource/virtual-lab probe; `workspace/` sở hữu `.ntp`, crypto,
staging, save và snapshot. Lớp này không chứa validation/use case nghiệp vụ và
không import QML.

Mỗi project đang mở giữ một OS-level lease qua sidecar ẩn
`.Tên-project.ntp.workspace.lock`. Sidecar được giữ lại sau khi đóng để tránh
inode race; trạng thái khóa của hệ điều hành mới là nguồn sự thật. Vì vậy một
`.ntp` chỉ có một phiên được chỉnh sửa, còn fingerprint khi save là lớp bảo vệ
thứ hai trước thay đổi từ công cụ bên ngoài.
