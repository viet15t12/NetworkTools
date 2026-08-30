"""SQLite repository owning device inventory and status persistence."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from domain.status import ConnectionStatus, connection_status
from infrastructure.database.paths import DEVICE_NETWORK_DB, require_database


class DeviceRepository:
    """Provide transactional access to t01_devices and related device rows."""

    def __init__(self, db_path: str | Path = DEVICE_NETWORK_DB) -> None:
        """Store the injected database path without opening a connection eagerly."""
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        """Open the required database with row and foreign-key support."""
        connection = sqlite3.connect(require_database(self.db_path), timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.execute("PRAGMA busy_timeout = 10000;")
        return connection

    def activate_database(self, db_path: str | Path) -> int:
        """Bind a runtime database and discard connection state from an older run.

        ``connected`` is process-local state: a freshly opened workspace cannot
        own a live session yet, even when that value was persisted in its package.
        """
        self.db_path = Path(db_path)
        return self.reset_connected_to_waiting()

    def get_login(self, host: str) -> dict[str, Any] | None:
        """Read the credential-bearing row used only by connection services."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT host, device_name, method, portnumber, username, password,
                       os, role, dev
                FROM t01_devices
                WHERE host = ?;
                """,
                ((host or "").strip(),),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_role(self, host: str) -> str | None:
        """Return the normalized inventory role for one device."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT role FROM t01_devices WHERE host = ?;",
                ((host or "").strip(),),
            ).fetchone()
        if row is None:
            return None
        return str(row["role"] or "").strip().lower()

    def synchronize_classification(self) -> int:
        """Normalize recognized legacy roles and derive the compatibility type."""
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE t01_devices
                SET role = CASE
                    WHEN lower(trim(COALESCE(role, ''))) IN ('rou', 'router') THEN 'rou'
                    WHEN lower(trim(COALESCE(role, ''))) IN ('sw2', 'switch', 'switch_l2') THEN 'sw2'
                    WHEN lower(trim(COALESCE(role, ''))) IN ('sw3', 'switch_l3') THEN 'sw3'
                    WHEN lower(trim(COALESCE(device_type, ''))) = 'router' THEN 'rou'
                    WHEN lower(trim(COALESCE(device_type, ''))) IN ('sw2', 'switch', 'switch_l2') THEN 'sw2'
                    WHEN lower(trim(COALESCE(device_type, ''))) IN ('sw3', 'switch_l3') THEN 'sw3'
                    ELSE role
                END;
                """
            )
            cursor = connection.execute(
                """
                UPDATE t01_devices
                SET device_type = CASE lower(trim(role))
                    WHEN 'rou' THEN 'router'
                    WHEN 'sw2' THEN 'sw2'
                    WHEN 'sw3' THEN 'sw3'
                    ELSE device_type
                END
                WHERE lower(trim(COALESCE(role, ''))) IN ('rou', 'sw2', 'sw3');
                """
            )
            connection.commit()
            return max(cursor.rowcount, 0)

    def update_connection_status(
        self, host: str, status: ConnectionStatus | str
    ) -> bool:
        """Persist one device connection state."""
        normalized = connection_status(status)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE t01_devices SET connection_status = ? WHERE host = ?;",
                (normalized.value, (host or "").strip()),
            )
            connection.commit()
            return cursor.rowcount > 0

    def reset_to_waiting(self, host: str) -> bool:
        """Reset a closed device session to waiting and non-dev state."""
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE t01_devices SET connection_status = ?, dev = 0 WHERE host = ?;",
                (ConnectionStatus.WAITING.value, (host or "").strip()),
            )
            connection.commit()
            return cursor.rowcount > 0

    def reset_connected_to_waiting(self) -> int:
        """Reset runtime state; tolerate an already-released workspace on shutdown."""
        if not self.db_path.is_file():
            return 0
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE t01_devices
                SET connection_status = ?
                WHERE connection_status = ?;
                """,
                (
                    ConnectionStatus.WAITING.value,
                    ConnectionStatus.CONNECTED.value,
                ),
            )
            connection.commit()
            return max(cursor.rowcount, 0)
