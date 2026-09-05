"""SQLite connection and transaction primitives; contains no feature logic."""

from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def connect(path: str | Path, *, must_exist: bool = True) -> sqlite3.Connection:
    database = Path(path)
    if must_exist and not database.is_file():
        raise FileNotFoundError(f"Database not found: {database}")
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


@contextmanager
def transaction(path: str | Path) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()
