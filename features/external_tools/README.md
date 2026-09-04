# External tools

Quản lý catalog, discovery, default-app association và khởi chạy công cụ ngoài.
**partial**: QObject chính nằm trong `core/external_tools.py`; feature package mới
chỉ giữ helper catalog/database kế thừa. QML entry ở Settings/Content. Catalog URL
là HTTPS allowlist và không tự cài đặt; executable/path/argument phải được kiểm
tra, `{password}` luôn bị chặn. Mỗi category chỉ có một app active. Test:
`test_external_tools.py`; backlog là tách discovery/launcher/repository khỏi
facade Qt và thống nhất persistence.
