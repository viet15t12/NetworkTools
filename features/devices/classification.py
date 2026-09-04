"""Canonical device classification based on the inventory role."""

from __future__ import annotations

from typing import Any


ROLE_ALIASES = {
    "rou": "rou",
    "router": "rou",
    "sw2": "sw2",
    "switch": "sw2",
    "switch_l2": "sw2",
    "sw3": "sw3",
    "switch_l3": "sw3",
}


def normalize_device_role(role: Any, legacy_device_type: Any = None) -> str:
    value = str(role or "").strip().lower()
    legacy = str(legacy_device_type or "").strip().lower()
    return ROLE_ALIASES.get(value) or ROLE_ALIASES.get(legacy) or ""


def device_type_for_role(role: Any) -> str:
    normalized = normalize_device_role(role)
    if normalized == "rou":
        return "router"
    return normalized if normalized in {"sw2", "sw3"} else "unknown"
