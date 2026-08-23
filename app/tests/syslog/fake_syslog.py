#!/usr/bin/env python3
"""
fake_syslog.py - Sinh log syslog giả lập (theo định dạng Cisco IOS) và gửi
qua UDP hoặc TCP tới một syslog server, để test hệ thống thu thập/giám sát log
(ví dụ NetworkTools).

Cách dùng:
    python3 fake_syslog.py --host 192.168.122.1 --port 5514 --count 20 --interval 1
    python3 fake_syslog.py --dry-run          # chỉ in ra màn hình, không gửi

Mặc định IP nguồn giả lập trong nội dung log là 192.168.122.101.
"""

import argparse
import random
import socket
import time
from datetime import datetime

# Facility.Severity phổ biến trên Cisco IOS
FACILITIES = ["LINK", "SYS", "OSPF", "BGP", "SEC", "IF", "CDP", "SPANTREE"]
SEVERITIES = {
    0: "EMERG", 1: "ALERT", 2: "CRIT", 3: "ERR",
    4: "WARNING", 5: "NOTICE", 6: "INFO", 7: "DEBUG",
}

# Một số mẫu message thường gặp, sẽ được random hoá interface/trạng thái
MESSAGE_TEMPLATES = [
    ("LINK", 3, "UPDOWN: Interface {iface}, changed state to {state}"),
    ("LINEPROTO", 5, "UPDOWN: Line protocol on Interface {iface}, changed state to {state}"),
    ("SYS", 5, "CONFIG_I: Configured from console by admin on vty0 ({src_ip})"),
    ("SEC", 6, "LOGIN_SUCCESS: Login Success [user: admin] [Source: {src_ip}] [localport: 22]"),
    ("SEC", 4, "LOGIN_FAILED: Login failed [user: {user}] [Source: {src_ip}] [localport: 22] [Reason: Login Authentication Failed]"),
    ("OSPF", 5, "ADJCHG: Process 1, Nbr {nbr_ip} on {iface} from FULL to DOWN, Neighbor Down: Dead timer expired"),
    ("SPANTREE", 6, "PORTSTATUS: {iface}: STP status Forwarding"),
    ("SYS", 6, "RELOAD: Reload requested by console. Reload reason: Reload Command"),
]

IFACES = ["GigabitEthernet0/0", "GigabitEthernet0/1", "FastEthernet0/1", "Vlan1", "Loopback0"]
STATES = ["up", "down"]
USERS = ["admin", "guest", "test", "operator"]


def gen_message(src_ip: str, hostname: str) -> str:
    facility, severity, template = random.choice(MESSAGE_TEMPLATES)
    body = template.format(
        iface=random.choice(IFACES),
        state=random.choice(STATES),
        src_ip=f"192.168.122.{random.randint(2, 254)}",
        user=random.choice(USERS),
        nbr_ip=f"192.168.122.{random.randint(2, 254)}",
    )
    # PRI = facility*8 + severity (giả định facility code local7 = 23)
    pri = 23 * 8 + severity
    timestamp = datetime.now().strftime("%b %d %Y %H:%M:%S")
    seq = random.randint(100000, 999999)

    # Định dạng gần giống Cisco IOS thực tế:
    # <PRI>seq: hostname: timestamp: %FACILITY-SEVERITY-MNEMONIC: message
    return f"<{pri}>{seq}: {hostname}: {timestamp}: %{facility}-{severity}-{body}"


def main():
    parser = argparse.ArgumentParser(description="Sinh syslog giả từ host 192.168.122.101")
    parser.add_argument("--host", default="192.168.122.1", help="Địa chỉ syslog server nhận log (mặc định 192.168.122.1)")
    parser.add_argument("--port", type=int, default=5514, help="Cổng Syslog (mặc định 5514)")
    parser.add_argument("--protocol", choices=("udp", "tcp"), default="udp", help="Giao thức gửi (mặc định UDP)")
    parser.add_argument("--src-ip", default="192.168.122.101", help="IP nguồn giả lập trong log")
    parser.add_argument("--hostname", default="R1", help="Hostname thiết bị giả lập")
    parser.add_argument("--count", type=int, default=10, help="Số lượng message sinh ra (0 = vô hạn)")
    parser.add_argument("--interval", type=float, default=1.0, help="Khoảng cách giữa các message (giây)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in ra màn hình, không gửi qua mạng")
    args = parser.parse_args()

    sock = None
    if not args.dry_run:
        sock_type = socket.SOCK_DGRAM if args.protocol == "udp" else socket.SOCK_STREAM
        sock = socket.socket(socket.AF_INET, sock_type)
        if args.protocol == "tcp":
            sock.connect((args.host, args.port))

    print(f"[+] Bắt đầu sinh syslog giả cho host {args.src_ip} "
          f"({'dry-run' if args.dry_run else f'gửi {args.protocol.upper()} tới {args.host}:{args.port}'})")

    i = 0
    try:
        while args.count == 0 or i < args.count:
            msg = gen_message(args.src_ip, args.hostname)
            if args.dry_run:
                print(msg)
            else:
                payload = msg.encode("utf-8")
                if args.protocol == "udp":
                    sock.sendto(payload, (args.host, args.port))
                else:
                    sock.sendall(payload + b"\n")
                print(f"[sent] {msg}")
            i += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[!] Dừng lại theo yêu cầu người dùng.")
    finally:
        if sock:
            sock.close()


if __name__ == "__main__":
    main()
