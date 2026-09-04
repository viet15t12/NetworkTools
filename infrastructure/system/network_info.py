"""Cross-platform network interface and SSID probes."""

from __future__ import annotations

import locale
import os
import socket
import subprocess
import sys
from ipaddress import ip_address
from pathlib import Path
from typing import Any

VIRTUAL_INTERFACE_MARKERS = (
    "bluetooth",
    "docker",
    "hyper-v",
    "loopback",
    "npcap",
    "tap",
    "teredo",
    "tunnel",
    "virtual",
    "virtualbox",
    "vmware",
    "vethernet",
    "wsl",
)

WIFI_INTERFACE_MARKERS = (
    "802.11",
    "airport",
    "wi-fi",
    "wifi",
    "wireless",
    "wlan",
    "wlp",
)

VPN_INTERFACE_MARKERS = (
    "cloudflarewarp",
    "openvpn",
    "ppp",
    "tailscale",
    "utun",
    "vpn",
    "warp",
    "wireguard",
    "zerotier",
)

ETHERNET_INTERFACE_MARKERS = (
    "ethernet",
    "eth",
    "en0",
    "eno",
    "enp",
    "ens",
    "enx",
    "gigabit",
    "lan",
    "local area connection",
)

LAB_INTERFACE_MARKERS = (
    ("PNETLab", ("pnetlab", "pnet")),
    ("EVE-NG", ("eve-ng", "eve_ng", "vunl")),
    ("Cisco CML", ("cml", "virl")),
    ("Huawei eNSP", ("ensp",)),
    ("VMware", ("vmnet", "vmware")),
    ("GNS3", ("gns3", "ubridge")),
    ("VirtualBox", ("vboxnet", "virtualbox")),
    ("Hyper-V", ("vethernet", "hyper-v")),
    ("KVM/libvirt", ("virbr",)),
)


def _is_usable_ip_address(raw_address: str | None) -> bool:
    if not raw_address:
        return False
    try:
        address = ip_address(raw_address.split("%", 1)[0])
    except ValueError:
        return False
    return not (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    )


def _connection_type_for_interface(name: str) -> str:
    normalized = name.casefold()
    if any(marker in normalized for marker in VPN_INTERFACE_MARKERS):
        return "vpn"
    if _lab_platform_for_interface(name):
        return "lab"
    if any(marker in normalized for marker in WIFI_INTERFACE_MARKERS):
        return "wifi"
    if any(marker in normalized for marker in ETHERNET_INTERFACE_MARKERS):
        return "ethernet"
    return "other"


def _lab_platform_for_interface(name: str) -> str:
    normalized = name.casefold()
    for platform, markers in LAB_INTERFACE_MARKERS:
        if any(marker in normalized for marker in markers):
            return platform
    return ""


def _lab_interface_label(name: str) -> str:
    """Keep status-bar labels compact while retaining the OS interface id."""
    normalized = name.casefold()
    for marker in ("vmnet", "pnet", "vboxnet", "virbr", "vunl", "ubridge"):
        position = normalized.find(marker)
        if position >= 0:
            return name[position:].split(maxsplit=1)[0].rstrip(",;)")
    return name


def _is_virtual_interface(name: str) -> bool:
    normalized = name.casefold()
    return bool(_lab_platform_for_interface(name)) or any(
        marker in normalized for marker in VIRTUAL_INTERFACE_MARKERS
    )


def _default_route_local_ip() -> str:
    for family, destination in (
        (socket.AF_INET, ("8.8.8.8", 80)),
        (socket.AF_INET6, ("2001:4860:4860::8888", 80, 0, 0)),
    ):
        try:
            with socket.socket(family, socket.SOCK_DGRAM) as sock:
                sock.connect(destination)
                return str(sock.getsockname()[0])
        except OSError:
            continue
    return ""


def _decode_command_output(data: bytes) -> str:
    encodings = ["utf-8-sig", locale.getpreferredencoding(False)]
    if os.name == "nt":
        encodings.extend(["mbcs", "cp65001", "cp850", "cp437"])

    seen: set[str] = set()
    for encoding in encodings:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue

    return data.decode("utf-8", errors="replace")


def _run_text_command(command: list[str], timeout: float = 2.0) -> str:
    try:
        kwargs: dict[str, Any] = {
            "capture_output": True,
            "check": False,
            "timeout": timeout,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        result = subprocess.run(command, **kwargs)
    except (OSError, subprocess.TimeoutExpired):
        return ""

    output = result.stdout or result.stderr or b""
    return _decode_command_output(output).strip()


def _read_windows_wifi_ssid(interface_name: str) -> str:
    output = _run_text_command(["netsh", "wlan", "show", "interfaces"])
    if not output:
        return ""

    blocks: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for raw_line in output.splitlines():
        if ":" not in raw_line:
            continue

        key, value = raw_line.split(":", 1)
        key = key.strip().casefold()
        value = value.strip()

        if key == "name":
            if current:
                blocks.append(current)
            current = {"name": value}
        elif key == "ssid" and value:
            current["ssid"] = value

    if current:
        blocks.append(current)

    interface_key = interface_name.casefold()
    for block in blocks:
        if block.get("name", "").casefold() == interface_key and block.get("ssid"):
            return block["ssid"]

    for block in blocks:
        if block.get("ssid"):
            return block["ssid"]

    return ""


def _read_macos_wifi_ssid(interface_name: str) -> str:
    output = _run_text_command(["networksetup", "-getairportnetwork", interface_name])
    if not output or ":" not in output:
        return ""
    return output.split(":", 1)[1].strip()


def _read_linux_wifi_ssid(interface_name: str) -> str:
    output = _run_text_command(["iwgetid", interface_name, "-r"])
    if output:
        return output.splitlines()[0].strip()

    output = _run_text_command(["iw", "dev", interface_name, "link"])
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("SSID:"):
            return stripped.split(":", 1)[1].strip()
    return ""


def _read_wifi_ssid(interface_name: str) -> str:
    if os.name == "nt":
        return _read_windows_wifi_ssid(interface_name)
    if sys.platform == "darwin":
        return _read_macos_wifi_ssid(interface_name)
    return _read_linux_wifi_ssid(interface_name)


def read_network_info() -> tuple[bool, str, str, str]:
    try:
        import psutil  # type: ignore
    except Exception:
        return False, "none", "", ""

    try:
        stats_by_name = psutil.net_if_stats()
        addrs_by_name = psutil.net_if_addrs()
    except Exception:
        return False, "none", "", ""

    default_ip = _default_route_local_ip()
    candidates: list[dict[str, Any]] = []

    for name, addrs in addrs_by_name.items():
        stats = stats_by_name.get(name)
        if stats is None or not stats.isup:
            continue

        usable_addresses = []
        for addr in addrs:
            if addr.family in {socket.AF_INET, socket.AF_INET6} and _is_usable_ip_address(addr.address):
                usable_addresses.append(addr.address.split("%", 1)[0])

        if not usable_addresses:
            continue

        connection_type = _connection_type_for_interface(name)
        is_default = default_ip in usable_addresses
        is_virtual = _is_virtual_interface(name)
        type_rank = 0 if connection_type in {"wifi", "ethernet"} else 1
        virtual_rank = 1 if is_virtual else 0

        candidates.append(
            {
                "name": name,
                "type": connection_type,
                "lab_platform": _lab_platform_for_interface(name),
                "is_default": is_default,
                "is_virtual": is_virtual,
                "rank": (0 if is_default else 1, virtual_rank, type_rank, name.casefold()),
            }
        )

    if not candidates:
        return False, "none", "", ""

    candidates.sort(key=lambda item: item["rank"])
    selected = candidates[0]
    network_name = selected["name"]
    if selected["type"] == "wifi":
        network_name = _read_wifi_ssid(network_name) or network_name

    lab_candidates = [item for item in candidates if item["lab_platform"]]
    lab_candidates.sort(key=lambda item: (0 if item["is_default"] else 1, item["name"].casefold()))
    virtual_lab_name = ""
    if lab_candidates:
        lab = lab_candidates[0]
        virtual_lab_name = f"{lab['lab_platform']} · {_lab_interface_label(lab['name'])}"
    return True, selected["type"], network_name, virtual_lab_name
