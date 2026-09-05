"""Fail-closed SQLCipher DB-API adapter and plaintext migration helpers.

All production database users import this module as ``sqlite3``.  The master
passphrase is converted to a 256-bit raw SQLCipher key once and retained only
for the lifetime of the process.
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Any

try:
    from sqlcipher3 import dbapi2 as _driver
except ImportError as exc:  # pragma: no cover - depends on the host wheel.
    raise RuntimeError(
        "SQLCipher support is unavailable. Install a compatible binary wheel "
        "with `python -m pip install --only-binary=:all: sqlcipher3-binary`. "
        "CAMS will not fall back to plaintext SQLite."
    ) from exc


Binary = _driver.Binary
Connection = _driver.Connection
Cursor = _driver.Cursor
DataError = _driver.DataError
DatabaseError = _driver.DatabaseError
Error = _driver.Error
IntegrityError = _driver.IntegrityError
InterfaceError = _driver.InterfaceError
InternalError = _driver.InternalError
NotSupportedError = _driver.NotSupportedError
OperationalError = _driver.OperationalError
PARSE_COLNAMES = _driver.PARSE_COLNAMES
PARSE_DECLTYPES = _driver.PARSE_DECLTYPES
ProgrammingError = _driver.ProgrammingError
Row = _driver.Row
Warning = _driver.Warning

_KEY_DERIVATION_SALT = b"CAMS SQLCipher database key v1"
_KEY_DERIVATION_ROUNDS = 600_000
_SQLITE_HEADER = b"SQLite format 3\x00"
_database_key: bytearray | None = None
_key_lock = threading.RLock()
_migration_lock = threading.RLock()


class DatabaseKeyUnavailable(RuntimeError):
    """Raised when code attempts to open a database before app unlock."""


def configure(passphrase: str) -> None:
    """Derive and retain the SQLCipher key without persisting the passphrase."""
    if not isinstance(passphrase, str) or not passphrase:
        raise ValueError("The CAMS master passphrase must not be empty.")
    verify_runtime()
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        _KEY_DERIVATION_SALT,
        _KEY_DERIVATION_ROUNDS,
        dklen=32,
    )
    clear()
    global _database_key
    with _key_lock:
        _database_key = bytearray(derived)


def verify_runtime() -> str:
    """Reject a driver that was built without SQLCipher support."""
    connection = _driver.connect(":memory:")
    try:
        row = connection.execute("PRAGMA cipher_version;").fetchone()
    finally:
        connection.close()
    version = str(row[0]).strip() if row and row[0] else ""
    if not version:
        raise RuntimeError(
            "The installed sqlcipher3 driver has no SQLCipher engine. Install "
            "the sqlcipher3-binary wheel; plaintext SQLite fallback is forbidden."
        )
    return version


def is_configured() -> bool:
    with _key_lock:
        return _database_key is not None


def clear() -> None:
    """Best-effort overwrite of the process-local raw database key."""
    global _database_key
    with _key_lock:
        if _database_key is not None:
            for index in range(len(_database_key)):
                _database_key[index] = 0
        _database_key = None


def _key_literal() -> str:
    with _key_lock:
        if _database_key is None:
            raise DatabaseKeyUnavailable(
                "The encrypted database is locked; provide the CAMS master passphrase first."
            )
        return f'"x\'{bytes(_database_key).hex()}\'"'


def connect(database: str | os.PathLike[str], *args: Any, **kwargs: Any) -> Connection:
    """Open a SQLCipher connection and apply the key before any SQL statement."""
    database_text = os.fspath(database)
    is_file_path = database_text != ":memory:" and not database_text.startswith("file:")
    if is_file_path:
        migrate_plaintext_database(database_text)
    connection = _driver.connect(database, *args, **kwargs)
    try:
        connection.execute(f"PRAGMA key = {_key_literal()};")
        # Force page one to be decoded now so a wrong key fails at the boundary.
        connection.execute("SELECT count(*) FROM sqlite_master;").fetchone()
        if is_file_path:
            try:
                os.chmod(database_text, 0o600)
            except OSError:
                pass
        return connection
    except Exception:
        connection.close()
        raise


def attach_database(connection: Connection, path: str | Path, alias: str) -> None:
    """Attach another CAMS-encrypted database using the active in-memory key."""
    if not alias.replace("_", "").isalnum() or alias[0].isdigit():
        raise ValueError("Invalid database alias.")
    quoted_path = str(Path(path).resolve()).replace("'", "''")
    connection.execute(
        f"ATTACH DATABASE '{quoted_path}' AS {alias} KEY {_key_literal()};"
    )


def is_plaintext_database(path: str | Path) -> bool:
    database = Path(path)
    if not database.is_file() or database.stat().st_size < len(_SQLITE_HEADER):
        return False
    with database.open("rb") as stream:
        return stream.read(len(_SQLITE_HEADER)) == _SQLITE_HEADER


def migrate_plaintext_database(path: str | Path) -> bool:
    """Atomically convert one legacy SQLite file to the active SQLCipher key."""
    database = Path(path)
    with _migration_lock:
        return _migrate_plaintext_database_locked(database)


def _migrate_plaintext_database_locked(database: Path) -> bool:
    if not is_plaintext_database(database):
        return False

    encrypted = database.with_name(database.name + ".sqlcipher-migration")
    for candidate in (encrypted, *(_side_files(encrypted))):
        candidate.unlink(missing_ok=True)
    source = _driver.connect(database, timeout=30.0)
    try:
        source.execute("PRAGMA busy_timeout = 30000;")
        if source.execute("PRAGMA quick_check;").fetchone() != ("ok",):
            raise DatabaseError(f"Cannot migrate damaged SQLite database: {database}")
        quoted_target = str(encrypted.resolve()).replace("'", "''")
        source.execute(
            f"ATTACH DATABASE '{quoted_target}' AS encrypted KEY {_key_literal()};"
        )
        source.execute("SELECT sqlcipher_export('encrypted');")
        source.execute("DETACH DATABASE encrypted;")
    except Exception:
        for candidate in (encrypted, *(_side_files(encrypted))):
            candidate.unlink(missing_ok=True)
        raise
    finally:
        source.close()

    with connect(encrypted, timeout=30.0) as verification:
        if verification.execute("PRAGMA quick_check;").fetchone() != ("ok",):
            encrypted.unlink(missing_ok=True)
            raise DatabaseError(f"SQLCipher migration verification failed: {database}")
    os.replace(encrypted, database)
    for side_file in _side_files(database):
        side_file.unlink(missing_ok=True)
    return True


def _side_files(path: Path) -> tuple[Path, ...]:
    return tuple(path.with_name(path.name + suffix) for suffix in ("-wal", "-shm", "-journal"))


__all__ = [
    "Connection",
    "Cursor",
    "DatabaseError",
    "DatabaseKeyUnavailable",
    "Error",
    "IntegrityError",
    "OperationalError",
    "ProgrammingError",
    "Row",
    "attach_database",
    "clear",
    "configure",
    "connect",
    "is_configured",
    "is_plaintext_database",
    "migrate_plaintext_database",
    "verify_runtime",
]
