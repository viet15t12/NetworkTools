"""Read-only access to managed-device inventory for the Syslog feature."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

from .connections import device_connection


class DeviceLookupRepository:
    def __init__(self, device_db: Path) -> None:
        self.device_db = Path(device_db)

    def connected_devices(self) -> list[dict[str, Any]]:
        with closing(device_connection(self.device_db)) as conn:
            rows = conn.execute(
                """SELECT host, device_name, device_type, os FROM t01_devices
                   WHERE connection_status = 'connected'
                   ORDER BY COALESCE(NULLIF(TRIM(device_name), ''), host) COLLATE NOCASE"""
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_device_host(self, source_ip: str) -> str | None:
        with closing(device_connection(self.device_db)) as conn:
            row = conn.execute(
                "SELECT host FROM t01_devices WHERE host = ? LIMIT 1", (source_ip,)
            ).fetchone()
            if row:
                return str(row["host"])
            row = conn.execute(
                """SELECT host FROM t02_interface_name WHERE ip_address = ?
                   ORDER BY CASE sync_status
                     WHEN 'synchronized' THEN 0 WHEN 'pending_apply' THEN 1
                     WHEN 'pending_delete' THEN 2 ELSE 3 END LIMIT 1""",
                (source_ip,),
            ).fetchone()
        return str(row["host"]) if row else None

    def source_interface(self, host: str) -> str | None:
        with closing(device_connection(self.device_db)) as conn:
            row = conn.execute(
                """SELECT interface_name FROM t02_interface_name
                   WHERE host = ? AND ip_address = ? AND COALESCE(shutdown, 0) = 0
                   ORDER BY CASE WHEN sync_status = 'synchronized' THEN 0 ELSE 1 END,
                            iface_id LIMIT 1""",
                (host, host),
            ).fetchone()
        return str(row["interface_name"]) if row else None

    def is_connected(self, host: str) -> bool:
        with closing(device_connection(self.device_db)) as conn:
            row = conn.execute(
                "SELECT 1 FROM t01_devices WHERE host = ? AND connection_status = 'connected'",
                (host,),
            ).fetchone()
        return row is not None

    def device_os(self, host: str) -> str:
        with closing(device_connection(self.device_db)) as conn:
            row = conn.execute("SELECT os FROM t01_devices WHERE host = ?", (host,)).fetchone()
        return str(row["os"] or "").strip().lower() if row else ""


__all__ = ["DeviceLookupRepository"]
