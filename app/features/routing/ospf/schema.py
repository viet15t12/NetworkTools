"""Non-destructive OSPF schema upgrades for existing workspaces."""

from __future__ import annotations

import sqlite3


def ensure_schema(connection: sqlite3.Connection) -> list[str]:
    """Add the OSPF process action mask when opening an older database."""
    columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(t04_ospf_processes);")
    }
    if "action_Cfg" in columns:
        return []
    connection.execute(
        "ALTER TABLE t04_ospf_processes "
        "ADD COLUMN action_Cfg TEXT NOT NULL DEFAULT '1111' "
        "CHECK(length(action_Cfg) = 4 AND action_Cfg GLOB '[01][01][01][01]');"
    )
    connection.commit()
    return ["t04_ospf_processes.action_Cfg"]
