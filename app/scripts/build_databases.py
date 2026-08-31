"""Build runtime SQLite databases atomically from the canonical schemas."""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from infrastructure.database.paths import (
    DEVICE_NETWORK_DB,
    DEVICE_NETWORK_SCHEMA_DIR,
    INFO_COLLECTED_DB,
    INFO_COLLECTED_SCHEMA_DIR,
    ensure_data_dir,
)

TARGETS = (
    (DEVICE_NETWORK_SCHEMA_DIR, DEVICE_NETWORK_DB),
    (INFO_COLLECTED_SCHEMA_DIR, INFO_COLLECTED_DB),
)

_SCHEMA_OBJECT_ORDER = {"table": 0, "index": 1, "trigger": 2, "view": 3}
_CONNECTION_STATUS_SQL = """
CASE success
    WHEN -1 THEN 'disconnected'
    WHEN 0 THEN 'waiting'
    WHEN 1 THEN 'connected'
END
"""
_SYNC_STATUS_SQL = """
CASE success
    WHEN -1 THEN 'pending_delete'
    WHEN 0 THEN 'pending_apply'
    WHEN 1 THEN 'synchronized'
    WHEN 3 THEN 'skipped'
END
"""


def _natural_key(path: Path) -> tuple[object, ...]:
    return tuple(int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name))


def combine_sql(source_dir: Path) -> str:
    files = sorted(source_dir.glob("*.sql"), key=_natural_key)
    if not files:
        raise FileNotFoundError(f"No SQL source files found in {source_dir}")
    return "\n\n".join(path.read_text(encoding="utf-8-sig").rstrip() for path in files) + "\n"


def _remove_sqlite_side_files(db_path: Path) -> None:
    db_path.unlink(missing_ok=True)
    _remove_sqlite_journal_side_files(db_path)


def _remove_sqlite_journal_side_files(db_path: Path) -> None:
    db_path.with_name(db_path.name + "-shm").unlink(missing_ok=True)
    db_path.with_name(db_path.name + "-wal").unlink(missing_ok=True)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _available_backup_path(db_path: Path) -> Path:
    base = db_path.with_name(db_path.name + ".pre-status-migration.bak")
    if not base.exists():
        return base
    index = 1
    while True:
        candidate = base.with_name(f"{base.name}.{index}")
        if not candidate.exists():
            return candidate
        index += 1


def _legacy_status_tables(db_path: Path) -> list[str]:
    with closing(sqlite3.connect(db_path)) as connection:
        tables = [
            str(row[0])
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        ]
        legacy: list[str] = []
        for table in tables:
            columns = {
                str(row[1]): str(row[2] or "").strip().upper()
                for row in connection.execute(
                    f"PRAGMA table_info({_quote_identifier(table)})"
                )
            }
            # Canonical switching tables intentionally retain a textual
            # `success` status. Only the former INTEGER representation needs
            # the destructive rebuild/mapping migration.
            if columns.get("success", "").startswith("INT"):
                legacy.append(table)
        return legacy


def _validate_legacy_statuses(db_path: Path, tables: list[str]) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        for table in tables:
            allowed = (-1, 0, 1) if table == "t01_devices" else (-1, 0, 1, 3)
            placeholders = ", ".join("?" for _ in allowed)
            row = connection.execute(
                f"""
                SELECT success, COUNT(*)
                FROM {_quote_identifier(table)}
                WHERE success IS NOT NULL AND success NOT IN ({placeholders})
                GROUP BY success
                LIMIT 1
                """,
                allowed,
            ).fetchone()
            if row is not None:
                raise sqlite3.DatabaseError(
                    f"Cannot migrate {table}: unsupported success value "
                    f"{row[0]!r} occurs {row[1]} time(s)."
                )


def _migrate_legacy_status_schema(source_dir: Path, db_path: Path) -> bool:
    """Atomically rebuild a legacy numeric-status database from canonical schema."""
    legacy_tables = _legacy_status_tables(db_path)
    if not legacy_tables:
        return False
    _validate_legacy_statuses(db_path, legacy_tables)

    migrated = db_path.with_suffix(db_path.suffix + ".status-migration")
    _remove_sqlite_side_files(migrated)
    build_database(source_dir, migrated)
    try:
        with closing(sqlite3.connect(migrated)) as connection:
            connection.execute("PRAGMA foreign_keys = OFF;")
            connection.execute("ATTACH DATABASE ? AS legacy;", (str(db_path),))
            new_tables = [
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT name FROM main.sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY rowid
                    """
                )
            ]
            legacy_names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM legacy.sqlite_master WHERE type = 'table'"
                )
            }
            with connection:
                for table in new_tables:
                    if table not in legacy_names:
                        continue
                    new_columns = [
                        str(row[1])
                        for row in connection.execute(
                            f"PRAGMA main.table_info({_quote_identifier(table)})"
                        )
                    ]
                    old_columns = {
                        str(row[1])
                        for row in connection.execute(
                            f"PRAGMA legacy.table_info({_quote_identifier(table)})"
                        )
                    }
                    targets: list[str] = []
                    expressions: list[str] = []
                    for column in new_columns:
                        if column in old_columns:
                            targets.append(_quote_identifier(column))
                            expressions.append(_quote_identifier(column))
                        elif column == "connection_status" and "success" in old_columns:
                            targets.append(_quote_identifier(column))
                            expressions.append(_CONNECTION_STATUS_SQL)
                        elif column == "sync_status" and "success" in old_columns:
                            targets.append(_quote_identifier(column))
                            expressions.append(_SYNC_STATUS_SQL)
                    if not targets:
                        continue
                    connection.execute(
                        f"""
                        INSERT INTO main.{_quote_identifier(table)}
                            ({", ".join(targets)})
                        SELECT {", ".join(expressions)}
                        FROM legacy.{_quote_identifier(table)}
                        """
                    )
            connection.execute("DETACH DATABASE legacy;")
            connection.execute("PRAGMA foreign_keys = ON;")
            if connection.execute("PRAGMA integrity_check;").fetchone() != ("ok",):
                raise sqlite3.DatabaseError(
                    f"integrity_check failed after status migration for {db_path}"
                )
            errors = connection.execute("PRAGMA foreign_key_check;").fetchall()
            if errors:
                raise sqlite3.DatabaseError(
                    f"foreign_key_check failed after status migration for "
                    f"{db_path}: {errors[:5]}"
                )

        backup = _available_backup_path(db_path)
        with closing(sqlite3.connect(db_path)) as source, closing(
            sqlite3.connect(backup)
        ) as destination:
            source.backup(destination)
        shutil.copystat(db_path, backup)
        _remove_sqlite_journal_side_files(db_path)
        migrated.replace(db_path)
        _remove_sqlite_side_files(db_path.with_suffix(db_path.suffix + ".status-migration"))
        return True
    except Exception:
        _remove_sqlite_side_files(migrated)
        raise


def build_database(source_dir: Path, db_path: Path) -> None:
    """Build one SQLite database directly from ordered modular schema files."""
    script = combine_sql(source_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_db = db_path.with_suffix(db_path.suffix + ".tmp")
    _remove_sqlite_side_files(temp_db)
    try:
        with closing(sqlite3.connect(temp_db)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys = ON;")
                connection.executescript(script)
                if connection.execute("PRAGMA integrity_check;").fetchone() != ("ok",):
                    raise sqlite3.DatabaseError(f"integrity_check failed for {db_path}")
                errors = connection.execute("PRAGMA foreign_key_check;").fetchall()
                if errors:
                    raise sqlite3.DatabaseError(f"foreign_key_check failed for {db_path}: {errors[:5]}")
        temp_db.replace(db_path)
    except Exception:
        _remove_sqlite_side_files(temp_db)
        raise


def _canonical_objects(source_dir: Path) -> list[tuple[str, str, str]]:
    """Return user-defined objects from a clean copy of the canonical schema."""
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(combine_sql(source_dir))
        rows = connection.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
            """
        ).fetchall()
    return sorted(rows, key=lambda row: (_SCHEMA_OBJECT_ORDER.get(row[0], 99), row[1]))


def _repair_missing_objects(source_dir: Path, db_path: Path) -> list[str]:
    """Create schema objects that are absent without replacing user data."""
    canonical = _canonical_objects(source_dir)
    with closing(sqlite3.connect(db_path)) as connection:
        present = {
            (row[0], row[1])
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }
        missing = [row for row in canonical if (row[0], row[1]) not in present]
        if not missing:
            return []

        with connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            for _object_type, _name, sql in missing:
                connection.execute(sql)
            if connection.execute("PRAGMA integrity_check;").fetchone() != ("ok",):
                raise sqlite3.DatabaseError(f"integrity_check failed for {db_path}")
            errors = connection.execute("PRAGMA foreign_key_check;").fetchall()
            if errors:
                raise sqlite3.DatabaseError(f"foreign_key_check failed for {db_path}: {errors[:5]}")
    return [name for _object_type, name, _sql in missing]


def _repair_info_collected_feature_schema(db_path: Path) -> list[str]:
    """Apply column-level Syslog upgrades before canonical indexes are repaired."""
    from features.syslog.persistence.schema import ensure_schema

    with closing(sqlite3.connect(db_path)) as connection:
        before_objects = {
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }
        before_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(t12_syslog_messages)")
        }
        ensure_schema(connection)
        after_objects = {
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }
        after_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(t12_syslog_messages)")
        }

    changes = [
        f"t12_syslog_messages.{name}"
        for name in sorted(after_columns - before_columns)
    ]
    changes.extend(name for _kind, name in sorted(after_objects - before_objects))
    return changes


def _repair_device_network_feature_schema(db_path: Path) -> list[str]:
    """Apply feature-owned, non-destructive upgrades without rebuilding data."""
    from features.fhrp.schema import ensure_schema as ensure_fhrp_schema
    from features.interfaces.schema import ensure_schema as ensure_interface_schema
    from features.routing.ospf.schema import ensure_schema as ensure_ospf_schema

    with closing(sqlite3.connect(db_path)) as connection:
        changes = ensure_interface_schema(connection)
        changes.extend(ensure_fhrp_schema(connection))
        changes.extend(ensure_ospf_schema(connection))
        return changes


def build_all() -> None:
    ensure_data_dir()
    for source_dir, db_path in TARGETS:
        build_database(source_dir, db_path)
        print(f"Built {db_path} from {source_dir}")


def build_missing_databases() -> list[Path]:
    ensure_data_dir()
    built = []
    for source_dir, db_path in TARGETS:
        if not db_path.is_file():
            build_database(source_dir, db_path)
            built.append(db_path)
    return built


def ensure_runtime_databases() -> dict[str, object]:
    """Create missing databases and non-destructively complete existing schemas."""
    ensure_data_dir()
    created: list[str] = []
    repaired: dict[str, list[str]] = {}
    for source_dir, db_path in TARGETS:
        if not db_path.is_file():
            build_database(source_dir, db_path)
            created.append(db_path.name)
            continue
        if source_dir == DEVICE_NETWORK_SCHEMA_DIR and _migrate_legacy_status_schema(
            source_dir, db_path
        ):
            repaired[db_path.name] = ["textual status migration"]
            continue
        changes: list[str] = []
        if source_dir == DEVICE_NETWORK_SCHEMA_DIR:
            changes.extend(_repair_device_network_feature_schema(db_path))
        if source_dir == INFO_COLLECTED_SCHEMA_DIR:
            # Existing workspaces can have the original Syslog table. Its new
            # indexes reference columns that ALTER TABLE must add first.
            changes.extend(_repair_info_collected_feature_schema(db_path))
        changes.extend(_repair_missing_objects(source_dir, db_path))
        if changes:
            repaired[db_path.name] = list(dict.fromkeys(changes))

    created_count = len(created)
    repaired_count = sum(len(names) for names in repaired.values())
    if created_count:
        detail = f"Created {', '.join(created)} with the complete schema."
        status_text = f"DB CREATED: {created_count}"
    elif repaired_count:
        parts = [f"{name}: {', '.join(objects)}" for name, objects in repaired.items()]
        detail = f"Restored {repaired_count} missing database object(s): " + "; ".join(parts)
        status_text = f"DB REPAIRED: {repaired_count}"
    else:
        detail = "Python runtime and both database schemas are ready."
        status_text = "SYSTEM READY"
    return {
        "ok": True,
        "statusText": status_text,
        "message": detail,
        "created": created,
        "repaired": repaired,
    }


def main() -> int:
    argparse.ArgumentParser(description="Build CAMS SQLite databases.").parse_args()
    try:
        build_all()
    except (OSError, sqlite3.Error) as exc:
        print(f"Database build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
