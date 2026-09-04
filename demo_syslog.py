"""
Demo SSH song song 4 thiết bị Cisco và tạo NHIỀU Syslog để demo collector/app.

Mặc định:
- SSH đồng thời R1 / R2 / R4 / SW1.
- Gửi custom Syslog đủ severity 0..7 trên mỗi thiết bị.
- Router: flap Loopback99 nhiều vòng để sinh LINK/LINEPROTO log thật.
- Switch: flap Gi1/3 nhiều vòng để sinh LINK/LINEPROTO log thật.

Cài:
    uv add netmiko

Chạy mặc định:
    uv run python demo_syslog_multi.py

Ví dụ tạo nhiều log hơn:
    uv run python demo_syslog_multi.py --cycles 10 --bursts 3 --delay 0.5
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from netmiko import ConnectHandler

USERNAME = "admin"
PASSWORD = "Cisco@123"

DEVICES = [
    {
        "name": "R1",
        "device_type": "cisco_ios",
        "host": "192.168.122.101",
        "username": USERNAME,
        "password": PASSWORD,
        "kind": "router",
    },
    {
        "name": "R2",
        "device_type": "cisco_ios",
        "host": "192.168.122.102",
        "username": USERNAME,
        "password": PASSWORD,
        "kind": "router",
    },
    {
        "name": "R4",
        "device_type": "cisco_ios",
        "host": "192.168.122.103",
        "username": USERNAME,
        "password": PASSWORD,
        "kind": "router",
    },
    {
        "name": "SW1",
        "device_type": "cisco_ios",
        "host": "192.168.122.104",
        "username": USERNAME,
        "password": PASSWORD,
        "kind": "switch",
    },
]

# Syslog severity chuẩn: 0 nghiêm trọng nhất -> 7 debug.
SEVERITIES = {
    0: "EMERGENCY",
    1: "ALERT",
    2: "CRITICAL",
    3: "ERROR",
    4: "WARNING",
    5: "NOTICE",
    6: "INFORMATIONAL",
    7: "DEBUG",
}


def log_local(device_name: str, message: str) -> None:
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{now}] [{device_name:<3}] {message}", flush=True)


def send_custom_syslog(
    conn,
    device_name: str,
    severity: int,
    message: str,
) -> bool:
    """Gửi một custom Syslog bằng lệnh EXEC `send log`."""
    command = f"send log {severity} {message}"
    output = conn.send_command_timing(command, strip_prompt=False, strip_command=False)

    bad_markers = (
        "Invalid input",
        "Incomplete command",
        "Ambiguous command",
        "% Invalid",
    )

    if any(marker in output for marker in bad_markers):
        log_local(
            device_name,
            f"IOS không hỗ trợ '{command}'. Sẽ tiếp tục bằng log interface.",
        )
        return False

    log_local(
        device_name, f"SYSLOG severity={severity} {SEVERITIES[severity]}: {message}"
    )
    return True


def send_severity_burst(conn, name: str, burst_no: int, pause: float) -> int:
    """Gửi 8 message, mỗi message một severity từ 0 đến 7."""
    sent = 0

    for severity, label in SEVERITIES.items():
        message = (
            f"DEMO-{name} BURST={burst_no} "
            f"SEVERITY={severity}-{label} "
            f"TIME={datetime.now().strftime('%H:%M:%S')}"
        )
        if send_custom_syslog(conn, name, severity, message):
            sent += 1
        time.sleep(pause)

    return sent


def router_demo(conn, name: str, cycles: int, delay: float) -> int:
    """Flap Loopback99 nhiều vòng, không đụng interface SSH."""
    interface = "Loopback99"
    events = 0

    log_local(name, f"Tạo {interface}...")
    conn.send_config_set(
        [
            f"interface {interface}",
            "description SYSLOG-DEMO",
            "ip address 10.255.99.1 255.255.255.255",
            "no shutdown",
        ]
    )
    time.sleep(delay)

    for cycle in range(1, cycles + 1):
        log_local(name, f"[{cycle}/{cycles}] shutdown {interface} -> DOWN")
        conn.send_config_set(
            [
                f"interface {interface}",
                "shutdown",
            ]
        )
        events += 1
        time.sleep(delay)

        # Marker custom giúp app dễ nhìn giữa các log thật của IOS.
        send_custom_syslog(
            conn,
            name,
            4,
            f"DEMO-{name} CYCLE={cycle}/{cycles} {interface}=DOWN",
        )
        time.sleep(delay)

        log_local(name, f"[{cycle}/{cycles}] no shutdown {interface} -> UP")
        conn.send_config_set(
            [
                f"interface {interface}",
                "no shutdown",
            ]
        )
        events += 1
        time.sleep(delay)

        send_custom_syslog(
            conn,
            name,
            5,
            f"DEMO-{name} CYCLE={cycle}/{cycles} {interface}=UP",
        )
        time.sleep(delay)

    log_local(name, f"Xóa {interface}...")
    conn.send_config_set([f"no interface {interface}"])
    events += 1
    return events


def switch_demo(conn, name: str, cycles: int, delay: float) -> int:
    """Flap cổng demo Gi1/3 nhiều vòng."""
    demo_port = "GigabitEthernet1/3"
    events = 0

    log_local(name, f"Dùng {demo_port} làm cổng demo.")
    conn.send_config_set(
        [
            f"interface {demo_port}",
            "description SYSLOG-DEMO-PORT",
        ]
    )

    for cycle in range(1, cycles + 1):
        log_local(name, f"[{cycle}/{cycles}] shutdown {demo_port} -> DOWN")
        conn.send_config_set(
            [
                f"interface {demo_port}",
                "shutdown",
            ]
        )
        events += 1
        time.sleep(delay)

        send_custom_syslog(
            conn,
            name,
            4,
            f"DEMO-{name} CYCLE={cycle}/{cycles} {demo_port}=DOWN",
        )
        time.sleep(delay)

        log_local(name, f"[{cycle}/{cycles}] no shutdown {demo_port} -> UP")
        conn.send_config_set(
            [
                f"interface {demo_port}",
                "no shutdown",
            ]
        )
        events += 1
        time.sleep(delay)

        send_custom_syslog(
            conn,
            name,
            5,
            f"DEMO-{name} CYCLE={cycle}/{cycles} {demo_port}=UP",
        )
        time.sleep(delay)

    return events


def run_device(device: dict, cycles: int, bursts: int, delay: float) -> str:
    name = device["name"]

    params = {
        "device_type": device["device_type"],
        "host": device["host"],
        "username": device["username"],
        "password": device["password"],
        "conn_timeout": 10,
        "banner_timeout": 15,
        "auth_timeout": 10,
        "fast_cli": False,
    }

    log_local(name, f"Đang SSH tới {device['host']}...")
    conn = None
    custom_sent = 0
    physical_events = 0

    try:
        conn = ConnectHandler(**params)
        prompt = conn.find_prompt()
        log_local(name, f"SSH thành công: {prompt}")

        send_custom_syslog(
            conn,
            name,
            5,
            f"DEMO-{name} START SSH_SESSION_OK",
        )

        # Mỗi burst = 8 log custom (severity 0..7).
        for burst_no in range(1, bursts + 1):
            log_local(name, f"Gửi severity burst {burst_no}/{bursts}...")
            custom_sent += send_severity_burst(conn, name, burst_no, delay)

        # Sau đó sinh log thật bằng interface state changes.
        if device["kind"] == "router":
            physical_events += router_demo(conn, name, cycles, delay)
        else:
            physical_events += switch_demo(conn, name, cycles, delay)

        send_custom_syslog(
            conn,
            name,
            6,
            (
                f"DEMO-{name} FINISH CUSTOM_SENT={custom_sent} "
                f"INTERFACE_EVENTS={physical_events}"
            ),
        )

        log_local(
            name,
            f"Hoàn tất: {custom_sent} custom log + {physical_events} interface actions.",
        )
        return (
            f"{name}: OK | custom={custom_sent} | interface_actions={physical_events}"
        )

    except Exception as exc:
        log_local(name, f"LỖI: {exc}")
        return f"{name}: ERROR - {exc}"

    finally:
        if conn is not None:
            try:
                conn.disconnect()
                log_local(name, "Đã đóng SSH.")
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo nhiều Syslog trên R1/R2/R4/SW1 để demo collector/app."
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=5,
        help="Số vòng shutdown/no shutdown trên mỗi thiết bị (mặc định: 5).",
    )
    parser.add_argument(
        "--bursts",
        type=int,
        default=2,
        help="Số burst severity 0..7; mỗi burst có 8 custom log (mặc định: 2).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Khoảng nghỉ giữa các hành động, đơn vị giây (mặc định: 0.8).",
    )
    args = parser.parse_args()

    if args.cycles < 1:
        parser.error("--cycles phải >= 1")
    if args.bursts < 1:
        parser.error("--bursts phải >= 1")
    if args.delay < 0:
        parser.error("--delay phải >= 0")

    return args


def main() -> None:
    args = parse_args()

    print("=" * 78)
    print("   DEMO SSH SONG SONG + MULTI SYSLOG - R1 / R2 / R4 / SW1")
    print("=" * 78)
    print(f"cycles : {args.cycles}")
    print(f"bursts : {args.bursts}  ({args.bursts * 8} custom severity logs/device)")
    print(f"delay  : {args.delay}s")
    print()
    print("Router : Loopback99 shutdown/no shutdown nhiều vòng.")
    print("Switch : Gi1/3 shutdown/no shutdown nhiều vòng.")
    print("Custom : severity 0,1,2,3,4,5,6,7.")
    print()

    results = []

    with ThreadPoolExecutor(max_workers=len(DEVICES)) as executor:
        futures = {
            executor.submit(
                run_device,
                device,
                args.cycles,
                args.bursts,
                args.delay,
            ): device["name"]
            for device in DEVICES
        }

        for future in as_completed(futures):
            results.append(future.result())

    print()
    print("=" * 78)
    print("KẾT QUẢ")
    print("=" * 78)
    for result in sorted(results):
        print(result)


if __name__ == "__main__":
    main()
