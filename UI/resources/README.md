# UI resources

Cập nhật: **2026-08-16**. Hiện có 124 SVG runtime và không còn thư mục
`_unused`; kiểm kê chi tiết ở `docs/resources/SVG_RESOURCES.md`.

SVG active được chia theo ý nghĩa trong `actions/`, `devices/`, `files/`, `navigation/` và `status/`. QML chỉ tham chiếu asset qua các property ngữ nghĩa trong `../qml/shared/AppAssets.qml`; không ghi literal SVG path ở consumer.

Asset không có runtime consumer phải được xóa thay vì lưu trong cây nguồn. Các
icon loại file của SFTP dùng Material Icon Theme; notice cấp repository nằm trong
`licenses/`, notice cần đóng gói nằm trong `UI/resources/licenses/`.
