"""Non-destructive schema upgrades for router-interface dirty masks."""

from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3

from .action_bits import EMPTY_ACTION_CFG


def ensure_schema(connection: sqlite3.Connection) -> list[str]:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 't02_interface_name'"
    ).fetchone()
    if table is None:
        return []
    columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(t02_interface_name)")
    }
    if "action_Cfg" in columns:
        return []
    connection.execute(
        "ALTER TABLE t02_interface_name ADD COLUMN action_Cfg TEXT NOT NULL "
        f"DEFAULT '{EMPTY_ACTION_CFG}' "
        "CHECK(length(action_Cfg) = 13 AND "
        "action_Cfg GLOB '[01][01][01][01][01][01][01][01][01][01][01][01][01]')"
    )
    connection.commit()
    return ["t02_interface_name.action_Cfg"]


__all__ = ["ensure_schema"]
