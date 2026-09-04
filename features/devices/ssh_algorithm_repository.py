"""Persistence API for opt-in per-device SSH compatibility settings."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from infrastructure.network.ssh_algorithms import (
    SshAlgorithmOverride,
    normalize_algorithm_list,
)


_COLUMNS = {
    "kex_algorithms": "kex",
    "host_key_algorithms": "key_types",
    "ciphers": "ciphers",
    "macs": "digests",
}


def _csv(value: Any) -> str | None:
    normalized = normalize_algorithm_list(value)
    return ",".join(normalized) if normalized else None


def get_ssh_algorithm_settings(db_path: str | Path, host: str) -> dict[str, str] | None:
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT kex_algorithms, host_key_algorithms, ciphers, macs, note
            FROM t01_ssh_algo WHERE host = ?;
            """,
            (str(host or "").strip(),),
        ).fetchone()
    return dict(row) if row else None


def get_ssh_algorithm_override(
    db_path: str | Path, host: str
) -> SshAlgorithmOverride | None:
    row = get_ssh_algorithm_settings(db_path, host)
    if not row:
        return None
    values = {
        target: normalize_algorithm_list(row.get(source))
        for source, target in _COLUMNS.items()
    }
    override = SshAlgorithmOverride(**values)
    return override if override else None


def save_ssh_algorithm_override(
    db_path: str | Path, host: str, payload: dict[str, Any]
) -> dict[str, Any]:
    normalized_host = str(host or "").strip()
    if not normalized_host:
        return {"ok": False, "message": "Host is required."}
    values = tuple(_csv(payload.get(column)) for column in _COLUMNS)
    note = str(payload.get("note") or "").strip() or None
    if not any(values) and note is None:
        return clear_ssh_algorithm_override(db_path, normalized_host)
    try:
        with closing(sqlite3.connect(str(db_path))) as conn, conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute(
                """
                INSERT INTO t01_ssh_algo
                    (host, kex_algorithms, host_key_algorithms, ciphers, macs, note)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(host) DO UPDATE SET
                    kex_algorithms = excluded.kex_algorithms,
                    host_key_algorithms = excluded.host_key_algorithms,
                    ciphers = excluded.ciphers,
                    macs = excluded.macs,
                    note = excluded.note;
                """,
                (normalized_host, *values, note),
            )
        return {"ok": True, "message": "SSH compatibility settings saved."}
    except sqlite3.Error as exc:
        return {"ok": False, "message": str(exc)}


def clear_ssh_algorithm_override(
    db_path: str | Path, host: str
) -> dict[str, Any]:
    try:
        with closing(sqlite3.connect(str(db_path))) as conn, conn:
            conn.execute(
                "DELETE FROM t01_ssh_algo WHERE host = ?;",
                (str(host or "").strip(),),
            )
        return {"ok": True, "message": "SSH compatibility settings reset."}
    except sqlite3.Error as exc:
        return {"ok": False, "message": str(exc)}
