"""Shared SQLite connection helpers for the persistence adapters."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def info_connection(path: Path) -> sqlite3.Connection:
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def device_connection(path: Path) -> sqlite3.Connection:
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    return conn
