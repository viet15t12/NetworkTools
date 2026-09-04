from __future__ import annotations

import ipaddress
from typing import Any


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if not minimum <= result <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return result


def boolean(value: Any) -> int:
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "yes", "on", "enabled", "up"})
    return int(bool(value))


def choice(value: Any, field: str, allowed: set[str], default: str) -> str:
    result = text(value).lower() or default
    if result not in allowed:
        raise ValueError(f"Invalid {field}: {result}")
    return result


def optional_vlan(value: Any, field: str) -> int | None:
    return None if value in (None, "") else integer(value, field, 1, 4094)


def validate_ipv4_pair(address: Any, mask: Any) -> tuple[str | None, str | None]:
    ip_text = text(address)
    mask_text = text(mask)
    if not ip_text and not mask_text:
        return None, None
    if not ip_text or not mask_text:
        raise ValueError("IP address and subnet mask must be provided together")
    try:
        ipaddress.IPv4Address(ip_text)
        prefix_or_mask = mask_text.removeprefix("/")
        network = ipaddress.IPv4Network(f"0.0.0.0/{prefix_or_mask}")
    except ipaddress.AddressValueError as exc:
        raise ValueError("Invalid IPv4 address or subnet mask") from exc
    except ipaddress.NetmaskValueError as exc:
        raise ValueError("Invalid subnet mask") from exc
    # IOS configuration commands require a dotted-quad mask.  Normalize CIDR
    # input here so every caller stores and renders the same representation.
    return ip_text, str(network.netmask)


def validate_vlan_expression(value: Any, field: str, default: str) -> str:
    expression = text(value).lower() or default
    if expression in {"all", "none"}:
        return expression
    for part in expression.split(","):
        bounds = [segment.strip() for segment in part.split("-")]
        if len(bounds) not in {1, 2} or any(not item for item in bounds):
            raise ValueError(f"{field} has an invalid format")
        numbers = [integer(item, field, 1, 4094) for item in bounds]
        if len(numbers) == 2 and numbers[0] > numbers[1]:
            raise ValueError(f"{field} contains a reversed VLAN range")
    return expression


def ok(message: str, **values: Any) -> dict[str, Any]:
    return {"ok": True, "success": True, "message": message, **values}


def failed(message: str, **values: Any) -> dict[str, Any]:
    return {"ok": False, "success": False, "message": message, **values}
