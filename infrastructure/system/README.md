# System infrastructure

Trạng thái: **implemented**. Các adapter phụ thuộc hệ điều hành đọc RAM,
interface/IP/SSID, desktop environment/global-menu capability và virtual-lab
evidence. Terminal companion/process nằm trong `features/terminal`; system layer
không sở hữu terminal session. Facade trong `core` chuyển kết quả thành
property/signal cho QML.
Mọi hàm public phải có docstring, không log credential và phải có fallback an
toàn trên nền tảng không hỗ trợ.

`virtual_lab.py` dò VM/server ở worker có timeout và chỉ gắn trạng thái
`online` khi web endpoint phản hồi. EVE-NG/PNETLab chạy trong VMware hoặc
VirtualBox có thể dùng IP guest do chính hypervisor trả về làm server hint đáng
tin cậy, kể cả khi trang đăng nhập không còn HTML fingerprint cũ. Các IP chỉ lấy
từ neighbor/subnet vẫn phải khớp fingerprint nền tảng để tránh nhận nhầm một
HTTP server khác. API credential là tùy chọn và chỉ cần để phân biệt `idle` với
`active` cũng như đếm node đang chạy.
