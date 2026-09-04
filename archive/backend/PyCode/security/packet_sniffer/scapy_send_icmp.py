import argparse

from scapy.all import ICMP, IP, sr1


def main() -> None:
    parser = argparse.ArgumentParser(description="Gui ICMP Echo Request bang Scapy")
    parser.add_argument("target", help="Dia chi IP dich, vd: 8.8.8.8")
    parser.add_argument("--timeout", type=int, default=2, help="Thoi gian cho phan hoi")
    args = parser.parse_args()

    packet = IP(dst=args.target) / ICMP()
    print(f"Gui ICMP den {args.target}...")

    reply = sr1(packet, timeout=args.timeout, verbose=0)

    if reply is None:
        print("Khong nhan duoc phan hoi.")
        return

    print("Nhan duoc phan hoi:")
    print(reply.summary())


if __name__ == "__main__":
    main()
