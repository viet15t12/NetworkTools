import pyshark
import json
import os
import threading
import asyncio

class PacketSnifferService:
    def __init__(self):
        self.is_running = False
        self.capture_thread = None
        # Đường dẫn tuyệt đối đến file output
        self.output_file = os.path.join(os.getcwd(), "Tmp", "packet_output.json")
        # Đường dẫn TShark mặc định trên Windows
        self.tshark_path = r'C:\Program Files\Wireshark\tshark.exe'

    def start(self, target_ip, type_sniffer, interface, bpf_filter):
        if self.is_running:
            print("[!] Sniffer đã đang chạy rồi.")
            return

        self.is_running = True
        
        # 1. Xử lý logic Filter
        actual_filter = "" if not bpf_filter or bpf_filter.lower() == "all" else bpf_filter
        
        # 2. Quyết định interface (Nếu là device, pyshark thường dùng 'any' trên Linux 
        # nhưng trên Windows cậu nên truyền đúng interface chính xác)
        sniff_on = interface if type_sniffer == "interface" else interface

        print(f"[*] Khởi động Sniffer | Target: {target_ip} | Interface: {sniff_on} | Filter: {actual_filter}")
        
        # 3. Chạy trong luồng riêng để không treo Controller
        self.capture_thread = threading.Thread(
            target=self._run_capture, 
            args=(sniff_on, actual_filter),
            daemon=True # Tự tắt khi chương trình chính tắt
        )
        self.capture_thread.start()

    def _run_capture(self, interface, bpf):
        # --- QUAN TRỌNG: Thiết lập Event Loop cho Thread mới ---
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        capture = None
        captured_packets = []

        try:
            # Khởi tạo LiveCapture với tshark_path để tránh lỗi môi trường Windows
            capture = pyshark.LiveCapture(
                interface=interface, 
                bpf_filter=bpf,
                tshark_path=self.tshark_path
            )

            print(f"[*] Đang thực sự tóm gói tin...")

            for packet in capture.sniff_continuously():
                if not self.is_running:
                    break
                
                try:
                    # Bóc tách dữ liệu an toàn (Chống crash khi gói tin không có Layer IP)
                    src_addr = "N/A"
                    dst_addr = "N/A"

                    if hasattr(packet, 'ip'):
                        src_addr = packet.ip.src
                        dst_addr = packet.ip.dst
                    elif hasattr(packet, 'ipv6'):
                        src_addr = packet.ipv6.src
                        dst_addr = packet.ipv6.dst
                    elif hasattr(packet, 'arp'):
                        src_addr = packet.arp.src_hw_mac
                        dst_addr = packet.arp.dst_hw_mac
                    elif hasattr(packet, 'eth'):
                        src_addr = packet.eth.src
                        dst_addr = packet.eth.dst

                    packet_data = {
                        "id": packet.number,
                        "time": packet.sniff_time.strftime("%H:%M:%S"),
                        "src": src_addr,
                        "dst": dst_addr,
                        "proto": packet.highest_layer,
                        "len": packet.length
                    }
                    
                    captured_packets.append(packet_data)
                    
                    # Giới hạn 50 gói mới nhất để file nhẹ, UI đọc nhanh
                    if len(captured_packets) > 50:
                        captured_packets.pop(0)
                    
                    # Ghi file JSON (Ghi đè hoàn toàn để UI luôn có data mới nhất)
                    with open(self.output_file, 'w', encoding='utf-8') as f:
                        json.dump(captured_packets, f, indent=4)

                except Exception as e:
                    # Nếu lỗi 1 gói tin thì bỏ qua để bắt tiếp gói sau
                    continue

        except Exception as e:
            print(f"[!] Lỗi Sniffer: {e}")
        finally:
            if capture:
                capture.close()
            loop.close()
            print("[*] Luồng capture đã dừng và giải phóng tài nguyên.")

    def stop(self):
        self.is_running = False
        print("[*] Đã nhận lệnh ngắt Sniffer.")