# Packet-sniffer experiments (legacy)

Trạng thái: **experimental, không thuộc desktop runtime**. Các script trong thư
mục này là thử nghiệm PyShark/Scapy độc lập; `app/main.py` không import chúng và
Device Logs của desktop có workflow TShark riêng.

- `pyshark_live_capture.py`, `scapy_sniff.py`: capture cần quyền hệ điều hành và
  chỉ được dùng trên interface/mạng đã được cấp phép.
- `scapy_send_icmp.py`: sinh traffic ICMP thử nghiệm; không chạy ngoài lab.
- `sniffer_service.py`: prototype service, chưa có scope/retention/auth contract.
- `telnet_hacker.py`: mã thử nghiệm thu credential Telnet, chủ động bị loại khỏi
  sản phẩm; không chạy, phân phối hoặc tích hợp.

Dependency thử nghiệm nằm trong `requirements.txt`, không phải dependency lock
của desktop. Không lưu pcap, credential, token, địa chỉ thật hoặc output capture
vào repository. Nếu tái sử dụng parser/capture, phải chuyển sang feature mới có
authorization scope, interface allowlist, timeout/cancel/size limit, redaction,
retention và test không truy cập mạng thật.
