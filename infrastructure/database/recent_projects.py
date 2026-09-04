"""Persistent recent-project history stored in the application-state database."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import APP_STATE_DB


_SCHEMA = """
CREATE TABLE IF NOT EXISTS recent_projects (
    path TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    project_url TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    is_encrypted INTEGER NOT NULL DEFAULT 0 CHECK (is_encrypted IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_recent_projects_opened_at
ON recent_projects(opened_at DESC);
"""


def _utc_datetime(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


class RecentProjectRepository:
    """Read and update the bounded recent-project list."""

    def __init__(self, database_path: str | Path = APP_STATE_DB) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    def list(self, *, limit: int = 15) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT name, path, project_url, opened_at, is_encrypted
                FROM recent_projects
                ORDER BY opened_at DESC
                LIMIT ?
                """,
                (max(0, int(limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def record(
        self,
        name: str,
        path: str | Path,
        *,
        is_encrypted: bool = False,
        opened_at: datetime | None = None,
        limit: int = 15,
    ) -> None:
        project_path = Path(path).expanduser().resolve()
        opened_at_text = _utc_datetime(opened_at).isoformat(timespec="microseconds")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO recent_projects
                        (name, path, project_url, opened_at, is_encrypted)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        name = excluded.name,
                        project_url = excluded.project_url,
                        opened_at = excluded.opened_at,
                        is_encrypted = excluded.is_encrypted
                    """,
                    (
                        name or project_path.stem,
                        str(project_path),
                        project_path.as_uri(),
                        opened_at_text,
                        int(is_encrypted),
                    ),
                )
                connection.execute(
                    """
                    DELETE FROM recent_projects
                    WHERE path NOT IN (
                        SELECT path FROM recent_projects
                        ORDER BY opened_at DESC
                        LIMIT ?
                    )
                    """,
                    (max(0, int(limit)),),
                )

    def remove(self, path: str | Path) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM recent_projects WHERE path = ?",
                    (str(path),),
                )
        return cursor.rowcount > 0

    def remove_missing_files(self) -> int:
        missing = [
            str(row["path"])
            for row in self.list(limit=1_000_000)
            if not Path(str(row["path"])).is_file()
        ]
        if not missing:
            return 0
        with closing(self._connect()) as connection:
            with connection:
                connection.executemany(
                    "DELETE FROM recent_projects WHERE path = ?",
                    ((path,) for path in missing),
                )
        return len(missing)


__all__ = ["RecentProjectRepository"]
