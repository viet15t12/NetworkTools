from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
import sys
from contextlib import contextmanager
from typing import Any


@contextmanager
def db_connection(db: Any):
    resource = db._connect()
    if isinstance(resource, sqlite3.Connection):
        try:
            with resource:
                yield resource
        finally:
            # Managed connections close in __exit__; plain test adapters do not.
            try:
                resource.close()
            except sqlite3.ProgrammingError:
                pass
        return
    # Compatibility for injected adapters that expose a context manager.
    with resource as conn:
        yield conn


def normalize_host(value: Any) -> str:
    return str(value or "").strip()


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def log_db_error(operation: str, exc: sqlite3.Error) -> None:
    print(f"[db/interfaces] {operation} failed: {exc}", file=sys.stderr)
