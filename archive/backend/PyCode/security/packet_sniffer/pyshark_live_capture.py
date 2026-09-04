import argparse

import pyshark


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bat packet bang PyShark (can cai TShark truoc)."
    )
    parser.add_argument("--interface", required=True, help="Ten network interface")
    parser.add_argument("--count", type=int, default=10, help="So packet can bat")
    parser.add_argument(
        "--display-filter",
        default="",
        help="Wireshark display filter, vd: tcp or udp.port==53",
    )
    args = parser.parse_args()

    capture = pyshark.LiveCapture(
        interface=args.interface,
        display_filter=args.display_filter or None,
    )

    print(f"Dang bat {args.count} packet tren interface: {args.interface}")
    if args.display_filter:
        print(f"Display filter: {args.display_filter}")

    for i, packet in enumerate(capture.sniff_continuously(packet_count=args.count), start=1):
        highest_layer = getattr(packet, "highest_layer", "N/A")
        length = getattr(packet, "length", "N/A")
        print(f"[{i}] layer={highest_layer} len={length}")

        if hasattr(packet, "ip"):
            src = getattr(packet.ip, "src", "?")
            dst = getattr(packet.ip, "dst", "?")
            print(f"    IP: {src} -> {dst}")


if __name__ == "__main__":
    main()
