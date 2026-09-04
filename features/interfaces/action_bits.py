"""Stable dirty-field bit mask for router L3 interfaces.

The stored text is intentionally readable from left to right in the same order
as the editor fields.  The right-most bit is ``shutdown``, so a shutdown-only
change is represented as ``0000000000001``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


ACTION_FIELDS = (
    "description",
    "primary_ip",
    "secondary_ip",
    "mtu",
    "bandwidth",
    "delay",
    "speed",
    "duplex",
    "negotiation",
    "proxy_arp",
    "unreachables",
    "directed_broadcast",
    "shutdown",
)
ACTION_WIDTH = len(ACTION_FIELDS)
EMPTY_ACTION_CFG = "0" * ACTION_WIDTH
FULL_ACTION_CFG = "1" * ACTION_WIDTH

_FIELD_INDEX = {field: index for index, field in enumerate(ACTION_FIELDS)}


def normalize_action_cfg(value: Any) -> str:
    """Return a valid mask, treating missing/legacy values as no dirty fields."""
    bits = str(value or "")
    if len(bits) != ACTION_WIDTH or any(bit not in "01" for bit in bits):
        return EMPTY_ACTION_CFG
    return bits


def action_cfg_for(fields: Iterable[str]) -> str:
    bits = list(EMPTY_ACTION_CFG)
    for field in fields:
        index = _FIELD_INDEX.get(field)
        if index is not None:
            bits[index] = "1"
    return "".join(bits)


def merge_action_cfg(*values: Any) -> str:
    masks = [normalize_action_cfg(value) for value in values]
    return "".join(
        "1" if any(mask[index] == "1" for mask in masks) else "0"
        for index in range(ACTION_WIDTH)
    )


def field_is_dirty(action_cfg: Any, field: str) -> bool:
    index = _FIELD_INDEX.get(field)
    return index is not None and normalize_action_cfg(action_cfg)[index] == "1"


def has_dirty_fields(action_cfg: Any) -> bool:
    return "1" in normalize_action_cfg(action_cfg)


__all__ = [
    "ACTION_FIELDS",
    "ACTION_WIDTH",
    "EMPTY_ACTION_CFG",
    "FULL_ACTION_CFG",
    "action_cfg_for",
    "field_is_dirty",
    "has_dirty_fields",
    "merge_action_cfg",
    "normalize_action_cfg",
]
