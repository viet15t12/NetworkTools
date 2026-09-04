"""Request-scoped Peewee connection for the active Switching workspace."""

from __future__ import annotations

from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import Any, Iterator

from peewee import SqliteDatabase

from .peewee_models import SwitchingModels, build_switching_models


def switching_database_path(db: Any) -> Path:
    """Resolve the SQLite path exposed by production and test DB adapters."""
    if isinstance(db, (str, PathLike)):
        value = db
    else:
        value = getattr(db, "db_path", None) or getattr(db, "path", None)
    if value is None:
        raise ValueError("Switching database adapter does not expose a database path")
    if str(value) == ":memory:":
        raise ValueError("Peewee lifecycle operations require a file-backed database")
    return Path(value)


@contextmanager
def switching_orm(db: Any) -> Iterator[SwitchingModels]:
    """Open and close an ORM connection without changing the shared DB facade.

    A fresh database object is used for each operation.  This is intentional:
    DatabaseManager can change ``db_path`` when the active workspace changes,
    and QML workers may run concurrently.
    """
    database = SqliteDatabase(
        switching_database_path(db),
        timeout=10.0,
        pragmas={"foreign_keys": 1, "busy_timeout": 10_000},
    )
    models = build_switching_models(database)
    with database.connection_context():
        yield models


__all__ = ["switching_database_path", "switching_orm"]
