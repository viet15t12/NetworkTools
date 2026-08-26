#!/usr/bin/env python3
"""
Demo SSH song song 4 thiết bị Cisco và tạo sự kiện Syslog.

Thiết bị:
- R1  : 192.168.122.101
- R2  : 192.168.122.102
- R4  : 192.168.122.103
- SW1 : 192.168.122.104

Yêu cầu:
    uv add netmiko
hoặc:
    pip install netmiko

Chạy:
    uv run python demo_syslog.py
hoặc:
    python3 demo_syslog.py
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

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


def log_local(device_name: str, message: str) -> None:
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{now}] [{device_name:<3}] {message}", flush=True)


def send_custom_syslog(conn, device_name: str, message: str) -> None:
    """
    Cisco IOS thường hỗ trợ lệnh EXEC:
        send log <severity> <message>

    Severity 6 = informational.
    Nếu image IOS không hỗ trợ lệnh này, script vẫn tiếp tục
    tạo log bằng thay đổi trạng thái interface.
    """
    command = f"send log 6 {message}"
    output = conn.send_command_timing(command)

    if "Invalid input" in output or "Incomplete command" in output:
        log_local(device_name, "IOS không hỗ trợ 'send log', bỏ qua custom message.")
    else:
        log_local(device_name, f"Đã gửi custom Syslog: {message}")


def router_demo(conn, name: str) -> None:
    """
    Dùng Loopback99 để tạo log UP/DOWN.
    Không đụng Gi0/0 nên không làm rớt SSH.
    """
    log_local(name, "Tạo Loopback99...")
    conn.send_config_set([
        "interface Loopback99",
        "description SYSLOG-DEMO",
        "ip address 10.255.99.1 255.255.255.255",
        "no shutdown",
    ])

    time.sleep(2)

    send_custom_syslog(
        conn,
        name,
        f"DEMO-{name}: Loopback99 da duoc tao va bat len"
    )

    log_local(name, "Shutdown Loopback99 -> tạo log DOWN...")
    conn.send_config_set([
        "interface Loopback99",
        "shutdown",
    ])

    time.sleep(3)

    log_local(name, "No shutdown Loopback99 -> tạo log UP...")
    conn.send_config_set([
        "interface Loopback99",
        "no shutdown",
    ])

    time.sleep(3)

    send_custom_syslog(
        conn,
        name,
        f"DEMO-{name}: Hoan tat chu ky DOWN-UP"
    )

    time.sleep(2)

    log_local(name, "Xóa Loopback99...")
    conn.send_config_set([
        "no interface Loopback99",
    ])


def switch_demo(conn, name: str) -> None:
    """
    Với switch, dùng một cổng demo không phải đường quản trị.

    Theo mô hình 8 cổng trước đó, Gi1/3 được chọn làm DEMO_PORT.
    Hãy bảo đảm Gi1/3 không phải cổng đang nối thiết bị quan trọng.
    """
    demo_port = "GigabitEthernet1/3"

    send_custom_syslog(
        conn,
        name,
        f"DEMO-{name}: Bat dau demo Syslog tren {demo_port}"
    )

    log_local(name, f"Shutdown {demo_port}...")
    conn.send_config_set([
        f"interface {demo_port}",
        "description SYSLOG-DEMO-PORT",
        "shutdown",
    ])

    time.sleep(3)

    log_local(name, f"No shutdown {demo_port}...")
    conn.send_config_set([
        f"interface {demo_port}",
        "no shutdown",
    ])

    time.sleep(3)

    send_custom_syslog(
        conn,
        name,
        f"DEMO-{name}: Hoan tat chu ky shutdown-no_shutdown"
    )


def run_device(device: dict) -> str:
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
    try:
        conn = ConnectHandler(**params)

        prompt = conn.find_prompt()
        log_local(name, f"SSH thành công: {prompt}")

        # Tạo một Syslog đánh dấu bắt đầu phiên demo.
        send_custom_syslog(
            conn,
            name,
            f"DEMO-{name}: SSH session da ket noi thanh cong"
        )

        if device["kind"] == "router":
            router_demo(conn, name)
        else:
            switch_demo(conn, name)

        log_local(name, "Demo hoàn tất.")
        return f"{name}: OK"

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


def main() -> None:
    print("=" * 72)
    print("      DEMO SSH SONG SONG + SYSLOG - R1 / R2 / R4 / SW1")
    print("=" * 72)
    print()
    print("Script sẽ SSH đồng thời vào 4 thiết bị.")
    print("Router: tạo Loopback99 -> shutdown -> no shutdown -> xóa.")
    print("Switch: shutdown/no shutdown Gi1/3.")
    print()

    # 4 worker => 4 thiết bị chạy gần như đồng thời.
    results = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_device, device): device["name"]
            for device in DEVICES
        }

        for future in as_completed(futures):
            results.append(future.result())

    print()
    print("=" * 72)
    print("KẾT QUẢ")
    print("=" * 72)

    for result in sorted(results):
        print(result)


if __name__ == "__main__":
    main()
