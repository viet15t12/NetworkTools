import argparse

from scapy.all import IP, sniff


def on_packet(packet) -> None:
    print(packet.summary())
    if IP in packet:
        print(f"    IP: {packet[IP].src} -> {packet[IP].dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bat packet bang Scapy")
    parser.add_argument("--count", type=int, default=10, help="So packet can bat")
    parser.add_argument("--iface", default=None, help="Ten interface (tuy chon)")
    parser.add_argument(
        "--bpf",
        default="",
        help="BPF filter, vd: icmp or tcp port 80",
    )
    args = parser.parse_args()

    print(f"Dang bat {args.count} packet bang Scapy")
    if args.iface:
        print(f"Interface: {args.iface}")
    if args.bpf:
        print(f"BPF filter: {args.bpf}")

    sniff(
        count=args.count,
        iface=args.iface,
        filter=args.bpf or None,
        prn=on_packet,
        store=False,
    )


if __name__ == "__main__":
    main()
