from __future__ import annotations

import ipaddress
import re
from typing import Any

_POOL_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def ipv4(value: Any, field: str) -> str:
    text = str(value or "").strip()
    try:
        return str(ipaddress.IPv4Address(text))
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"Invalid {field}: {text}") from exc


def optional_ipv4(value: Any, field: str) -> str | None:
    text = str(value or "").strip()
    return ipv4(text, field) if text else None


def pool_values(
    pool: Any, network: Any, subnetmask: Any, default_router: Any, dns: Any, lease: Any,
) -> dict[str, str | None]:
    name = str(pool or "").strip()
    if not _POOL_RE.fullmatch(name):
        raise ValueError("Invalid Cisco DHCP pool name")
    network_text = str(network or "").strip()
    mask_text = str(subnetmask or "").strip()
    if mask_text.startswith("/"):
        mask_text = mask_text[1:]
    try:
        subnet = ipaddress.IPv4Network(f"{network_text}/{mask_text}", strict=True)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError) as exc:
        raise ValueError("Network must be an IPv4 network with a contiguous mask") from exc
    lease_text = str(lease or "1").strip().lower()
    _validate_lease(lease_text)
    gateway = optional_ipv4(default_router, "default router")
    if gateway and ipaddress.IPv4Address(gateway) not in subnet:
        raise ValueError("Default router must belong to the DHCP subnet")
    dns_values = [ipv4(item, "DNS server") for item in str(dns or "").replace(",", " ").split()]
    return {
        "pool": name,
        "network": str(subnet.network_address),
        "subnetmask": str(subnet.netmask),
        "defaut": gateway,
        "dns": " ".join(dns_values) or None,
        "lease": lease_text,
    }


def _validate_lease(value: str) -> None:
    if value == "infinite":
        return
    parts = value.split()
    if not 1 <= len(parts) <= 3 or not all(part.isdigit() for part in parts):
        raise ValueError("Lease must be 'infinite' or: days [hours [minutes]]")
    days, hours, minutes = [int(item) for item in parts + ["0"] * (3 - len(parts))]
    if days < 0 or not 0 <= hours <= 23 or not 0 <= minutes <= 59:
        raise ValueError("Invalid Cisco DHCP lease range")


def excluded_range(start: Any, end: Any) -> tuple[str, str]:
    first = ipv4(start, "excluded start address")
    last = ipv4(end or start, "excluded end address")
    if int(ipaddress.IPv4Address(first)) > int(ipaddress.IPv4Address(last)):
        raise ValueError("Excluded start address must not exceed end address")
    return first, last
