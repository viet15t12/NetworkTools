# Backend kế thừa

Cập nhật: **2026-09-04**. `archive/backend/` và `archive/api_server.py` là subsystem nghiên cứu
kế thừa, **không** được `main.py` khởi tạo và không dùng database workspace
đang mở của desktop.

Subsystem chứa dispatcher/worker cho routing, interface, DHCP, ACL/NAT,
switching, sync và info collection. Một số parser/template vẫn hữu ích làm nguồn
đối chiếu khi chuyển tính năng sang `features`, nhưng đường import, cấu hình,
dependency và schema của nó chưa tạo thành một runtime sản phẩm độc lập.

Các giới hạn bắt buộc phải hiểu trước khi chạy:

- `api_server.py` chưa có authentication/authorization và phản hồi “success” chỉ
  xác nhận đã gọi/xếp dispatcher, không xác nhận thiết bị thành công;
- backend còn dùng global path/output và hai kiểu import package;
- SQL trong `backend/sql/` và `backend/PyCode/share/database/` là schema kế thừa,
  không thay thế schema canonical ở `infrastructure/database/schemas/`;
- `backend/sql/format_md.py` còn hard-code đường dẫn Windows tới tài liệu schema
  cũ đã được loại bỏ; script này không phải generator được hỗ trợ và không được
  chạy trong quy trình tài liệu hiện tại;
- packet-sniffer chỉ là mã thử nghiệm có rủi ro cao, không thuộc desktop runtime;
- không cho backend ghi đồng thời vào project `.ntp` đang mở.

Muốn phục hồi subsystem này cần tạo dependency/entry point riêng, chuẩn hóa path
và schema, thêm request model, task ID/status/cancel, auth, fake-device test và
integration test. Bảng đối chiếu capability nằm tại
[`../../docs/BACKEND_APP_PARITY.md`](../../docs/BACKEND_APP_PARITY.md).
