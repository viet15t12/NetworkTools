# NAT

Static, dynamic pool, PAT, inside/outside interface, NAT ACL và route-map.
**implemented**, đối chiếu **2026-08-16**. QML
`UI/qml/features/nat/NatView.qml`; slots `core/nat_slots.py`; persistence trong
`nat_db.py`; View & Push trong `collector.py`, `dispatcher.py`, `worker.py` và
`templates/`; DB nhóm NAT/NAT ACL `t05_*`.

Nút View & Push ở header gom và render NAT ACL trước NAT engine, chạy nền, dùng session tab hiện có và chỉ cập nhật tracking row sau kết quả thành công. Preview/dev mode không mở kết nối thật. Validation bao gồm address/port/pool/reference.

Các form dùng contract tên tách biệt `nat_name`, `acl_name` và
`route_map_name`. Dynamic/PAT hiển thị NAT parent name; NAT ACL và route-map
cho phép chọn lại tên đã lưu hoặc tạo tên mới. PAT chỉ nhận outside interface
và dynamic pool đã lưu qua combobox để tránh tham chiếu sai. Repository luôn
trả role QML bằng giá trị xác định; ACL mới được cấp sequence 10, 20, ... thay
vì để `NULL`.
Tab Interfaces cũng chọn `Interface Name` từ inventory router hiện tại thay vì
nhập tự do; bản ghi cũ vẫn được giữ trong danh sách khi sửa.

Thứ tự tab bám theo dependency cấu hình Cisco:
`Interfaces → ACL → Static → Dynamic → PAT → Route Map`. Static NAT dùng input
IPv4 và port 1–65535; NAT ACL cho chọn source `Network`, `Host` hoặc `Any`;
PAT chỉ hiển thị source type đang có dữ liệu tham chiếu và luôn bật overload.
Backend từ chối IPv4, protocol, port, pool range và netmask không hợp lệ trước
khi ghi SQLite.

Test: `test_nat_persistence.py`, dev-mode worker, QML smoke. Backlog: service boundary và transaction cha-con đầy đủ.
