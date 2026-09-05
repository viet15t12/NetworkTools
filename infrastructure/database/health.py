"""Read-only database health checks and legacy worker path configuration."""

from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from pathlib import Path

from .paths import require_database


REQUIRED_DEVICE_TABLES = frozenset(
    {
        "t01_devices",
        "t02_interface_name",
        "t04_ospf_processes",
        "t04_eigrp_processes",
        "t08_fhrp_groups",
        "t08_fhrp_members",
    }
)


def validate_device_database(path: str | Path) -> None:
    """Raise a descriptive error when the managed device schema is incomplete."""
    database = require_database(path)
    with closing(sqlite3.connect(database)) as connection:
        present = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
        }
    missing = sorted(REQUIRED_DEVICE_TABLES - present)
    if missing:
        raise RuntimeError(f"Database schema is incomplete; missing tables: {', '.join(missing)}")


def configure_worker_paths(database_path: str | Path) -> None:
    """Point compatibility network workers at the injected runtime database."""
    from infrastructure.network import config

    config.DB_PATH = str(Path(database_path).resolve())
