"""Retention policy independent from listener and Qt lifecycle."""

from __future__ import annotations

from typing import Protocol


class RetentionStore(Protocol):
    def delete_expired(self, retention_days: int, batch_size: int = 5_000) -> int: ...


def run_retention(
    repository: RetentionStore, retention_days: int, batch_size: int = 5_000
) -> dict[str, object]:
    try:
        deleted = repository.delete_expired(retention_days, batch_size)
        return {"ok": True, "deleted": deleted, "message": f"Removed {deleted} expired syslog messages."}
    except Exception as exc:
        return {"ok": False, "deleted": 0, "message": f"Syslog retention failed: {exc}"}


__all__ = ["run_retention"]
