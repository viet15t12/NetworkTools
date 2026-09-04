"""Helpers for distinguishing local drafts from device-backed switch rows."""

from __future__ import annotations

from typing import Any


def is_device_backed(row: Any, status_field: str = "success") -> bool:
    """Return whether deleting a row must also remove configuration on-device.

    ``pending_apply`` alone cannot answer this question because it represents
    both a new draft and an edit to synchronized state.  ``device_present``
    preserves that distinction.  The status fallback keeps old databases and
    tests that predate the presence column safe during migration.
    """
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    if "device_present" in keys and bool(row["device_present"]):
        return True
    return str(row[status_field] or "pending_apply") in {
        "synchronized",
        "pending_delete",
    }


__all__ = ["is_device_backed"]
