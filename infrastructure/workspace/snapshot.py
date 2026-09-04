"""Bounded full-state snapshots stored under ``snapshots/`` in `.ntp` files."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .errors import InvalidWorkspacePackage
from .package import REQUIRED_DATABASES, SNAPSHOT_INDEX_NAME, WorkspaceSession
from .staging import backup_sqlite_database, copy_stable_tree, sha256_file


SNAPSHOT_FORMAT_VERSION = 1
DEFAULT_AUTOMATIC_LIMIT = 20
_ALLOWED_REASONS = {"manual", "automatic", "before-migration", "before-rollback"}


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    snapshot_id: str
    created_at: str
    label: str
    reason: str
    pinned: bool
    source_generation: int
    size: int
    health: str = "valid"

    @classmethod
    def from_dict(cls, value: object) -> "SnapshotRecord":
        if not isinstance(value, dict):
            raise InvalidWorkspacePackage("A snapshot index entry is invalid.")
        snapshot_id = value.get("id")
        try:
            parsed_id = uuid.UUID(str(snapshot_id))
        except ValueError as exc:
            raise InvalidWorkspacePackage("A snapshot ID is invalid.") from exc
        if str(parsed_id) != snapshot_id:
            raise InvalidWorkspacePackage("A snapshot ID is not canonical.")
        reason = value.get("reason")
        if reason not in _ALLOWED_REASONS:
            raise InvalidWorkspacePackage("A snapshot reason is invalid.")
        source_generation = value.get("sourceGeneration")
        size = value.get("size")
        if (
            isinstance(source_generation, bool)
            or not isinstance(source_generation, int)
            or source_generation < 0
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
        ):
            raise InvalidWorkspacePackage("Snapshot generation or size is invalid.")
        pinned = value.get("pinned", False)
        if not isinstance(pinned, bool):
            raise InvalidWorkspacePackage("A snapshot pinned flag is invalid.")
        created_at = value.get("createdAt")
        if not isinstance(created_at, str) or not created_at.endswith("Z"):
            raise InvalidWorkspacePackage("A snapshot timestamp is invalid.")
        return cls(
            snapshot_id=str(snapshot_id),
            created_at=created_at,
            label=str(value.get("label") or ""),
            reason=str(reason),
            pinned=pinned,
            source_generation=source_generation,
            size=size,
            health=str(value.get("health") or "valid"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "createdAt": self.created_at,
            "health": self.health,
            "id": self.snapshot_id,
            "label": self.label,
            "pinned": self.pinned,
            "reason": self.reason,
            "size": self.size,
            "sourceGeneration": self.source_generation,
        }


class SnapshotService:
    """Create, list, retain, and restore immutable full workspace snapshots."""

    def list_snapshots(self, workspace_root: str | Path) -> tuple[SnapshotRecord, ...]:
        return tuple(self._read_index(Path(workspace_root) / SNAPSHOT_INDEX_NAME))

    def validate_snapshots(
        self, workspace_root: str | Path
    ) -> tuple[SnapshotRecord, ...]:
        root = Path(workspace_root)
        records = self.list_snapshots(root)
        indexed = {record.snapshot_id for record in records}
        present = {
            path.name
            for path in (root / "snapshots").iterdir()
            if path.is_dir()
        }
        if indexed != present:
            raise InvalidWorkspacePackage(
                "The snapshot index does not match the snapshot history folders."
            )
        for record in records:
            self._validate_snapshot_directory(
                root / "snapshots" / record.snapshot_id, record
            )
        return records

    def create_from_staged_workspace(
        self,
        session: WorkspaceSession,
        staged_workspace: str | Path,
        *,
        label: str,
        reason: str,
        source_generation: int,
        pinned: bool = False,
    ) -> SnapshotRecord:
        """Commit one snapshot using the already consistent current-state images."""

        if reason not in _ALLOWED_REASONS:
            raise ValueError(f"Unsupported snapshot reason: {reason}")
        stage = Path(staged_workspace)
        snapshots_root = session.working_directory / "snapshots"
        snapshots_root.mkdir(parents=True, exist_ok=True)
        snapshot_id = str(uuid.uuid4())
        temporary = snapshots_root / f".staging-{snapshot_id}"
        destination = snapshots_root / snapshot_id
        shutil.rmtree(temporary, ignore_errors=True)
        try:
            temporary.mkdir()
            for database_name in REQUIRED_DATABASES:
                shutil.copy2(stage / database_name, temporary / database_name)
            copy_stable_tree(stage / "backup", temporary / "backup", attempts=1)
            inventory = self._inventory(temporary)
            size = sum(int(item["size"]) for item in inventory)
            record = SnapshotRecord(
                snapshot_id=snapshot_id,
                created_at=_utc_now(),
                label=(label or self._default_label(reason)).strip()[:200],
                reason=reason,
                pinned=bool(pinned),
                source_generation=max(0, int(source_generation)),
                size=size,
            )
            metadata = {
                **record.to_dict(),
                "appVersion": session.manifest.last_saved_by_app_version,
                "databaseSchemaVersions": session.manifest.database_schema_versions,
                "formatVersion": SNAPSHOT_FORMAT_VERSION,
                "items": inventory,
            }
            (temporary / "snapshot.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            self._validate_snapshot_directory(temporary, record)
            os.replace(temporary, destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

        records = [record, *self._read_index(snapshots_root / "index.json")]
        records = self._apply_retention(snapshots_root, records)
        self._write_index(snapshots_root / "index.json", records)

        staged_snapshots = stage / "snapshots"
        staged_snapshots.mkdir(exist_ok=True)
        shutil.copytree(destination, staged_snapshots / snapshot_id)
        for removed in {
            path.name
            for path in staged_snapshots.iterdir()
            if path.is_dir()
        } - {item.snapshot_id for item in records}:
            shutil.rmtree(staged_snapshots / removed, ignore_errors=True)
        self._write_index(staged_snapshots / "index.json", records)
        return record

    def restore_snapshot(
        self,
        session: WorkspaceSession,
        snapshot_id: str,
        *,
        recovery_workspace: str | Path | None = None,
    ) -> SnapshotRecord:
        """Restore a validated snapshot into the live extracted workspace."""

        records = {item.snapshot_id: item for item in self.list_snapshots(session.working_directory)}
        record = records.get(snapshot_id)
        if record is None:
            raise KeyError(f"Snapshot not found: {snapshot_id}")
        source = session.working_directory / "snapshots" / snapshot_id
        self._validate_snapshot_directory(source, record)

        recovery = Path(recovery_workspace) if recovery_workspace else None
        # Rollback scratch data must never live at the workspace root. A process
        # failure there would otherwise leave forbidden files that make every
        # later package save fail validation.
        with tempfile.TemporaryDirectory(
            prefix="cams-snapshot-rollback-",
            dir=session.working_directory.parent,
        ) as temporary:
            rollback_root = Path(temporary)
            old_backup = rollback_root / "original-backup"
            backup_swapped = False
            try:
                for database_name in REQUIRED_DATABASES:
                    backup_sqlite_database(
                        source / database_name, rollback_root / database_name
                    )
                copy_stable_tree(
                    source / "backup", rollback_root / "replacement-backup", attempts=1
                )

                os.replace(session.backup_directory, old_backup)
                backup_swapped = True
                os.replace(
                    rollback_root / "replacement-backup", session.backup_directory
                )
                for database_name in REQUIRED_DATABASES:
                    target = session.working_directory / database_name
                    _remove_sqlite_side_files(target)
                    os.replace(rollback_root / database_name, target)
                backup_swapped = False
            except Exception:
                if backup_swapped and old_backup.exists():
                    shutil.rmtree(session.backup_directory, ignore_errors=True)
                    os.replace(old_backup, session.backup_directory)
                    backup_swapped = False
                if recovery is not None:
                    for database_name in REQUIRED_DATABASES:
                        recovery_copy = rollback_root / f"recovery-{database_name}"
                        backup_sqlite_database(recovery / database_name, recovery_copy)
                        target = session.working_directory / database_name
                        _remove_sqlite_side_files(target)
                        os.replace(recovery_copy, target)
                raise
            finally:
                if backup_swapped and old_backup.exists():
                    shutil.rmtree(session.backup_directory, ignore_errors=True)
                    os.replace(old_backup, session.backup_directory)
        return record

    def _read_index(self, path: Path) -> list[SnapshotRecord]:
        if not path.exists():
            return []
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidWorkspacePackage("The snapshot index is invalid.") from exc
        if (
            not isinstance(value, dict)
            or isinstance(value.get("formatVersion"), bool)
            or value.get("formatVersion") != 1
        ):
            raise InvalidWorkspacePackage("The snapshot index version is unsupported.")
        snapshots = value.get("snapshots")
        if not isinstance(snapshots, list):
            raise InvalidWorkspacePackage("The snapshot index is invalid.")
        records = [SnapshotRecord.from_dict(item) for item in snapshots]
        if len({item.snapshot_id for item in records}) != len(records):
            raise InvalidWorkspacePackage("The snapshot index contains duplicate IDs.")
        return records

    @staticmethod
    def _write_index(path: Path, records: list[SnapshotRecord]) -> None:
        payload = {
            "formatVersion": SNAPSHOT_FORMAT_VERSION,
            "snapshots": [record.to_dict() for record in records],
        }
        temporary = path.with_name(path.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _inventory(root: Path) -> list[dict[str, object]]:
        inventory: list[dict[str, object]] = []
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file() and path.name != "snapshot.json":
                inventory.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "sha256": sha256_file(path),
                        "size": path.stat().st_size,
                    }
                )
        return inventory

    def _validate_snapshot_directory(
        self, root: Path, record: SnapshotRecord
    ) -> None:
        metadata_path = root / "snapshot.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidWorkspacePackage("Snapshot metadata is invalid.") from exc
        if (
            not isinstance(metadata, dict)
            or isinstance(metadata.get("formatVersion"), bool)
            or metadata.get("formatVersion") != SNAPSHOT_FORMAT_VERSION
            or metadata.get("id") != record.snapshot_id
        ):
            raise InvalidWorkspacePackage("Snapshot metadata is inconsistent.")
        expected = metadata.get("items")
        if not isinstance(expected, list) or expected != self._inventory(root):
            raise InvalidWorkspacePackage("Snapshot content verification failed.")
        for database_name in REQUIRED_DATABASES:
            probe = root / database_name
            if not probe.is_file():
                raise InvalidWorkspacePackage(
                    f"Snapshot database is missing: {database_name}."
                )

    @staticmethod
    def _apply_retention(
        snapshots_root: Path, records: list[SnapshotRecord]
    ) -> list[SnapshotRecord]:
        automatic_seen = 0
        retained: list[SnapshotRecord] = []
        for record in records:
            if record.reason == "automatic" and not record.pinned:
                automatic_seen += 1
                if automatic_seen > DEFAULT_AUTOMATIC_LIMIT:
                    shutil.rmtree(
                        snapshots_root / record.snapshot_id, ignore_errors=True
                    )
                    continue
            retained.append(record)
        return retained

    @staticmethod
    def _default_label(reason: str) -> str:
        return {
            "automatic": "Automatic save",
            "before-rollback": "Before rollback",
            "before-migration": "Before migration",
            "manual": "Manual snapshot",
        }[reason]


def _remove_sqlite_side_files(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        path.with_name(path.name + suffix).unlink(missing_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


__all__ = [
    "DEFAULT_AUTOMATIC_LIMIT",
    "SNAPSHOT_FORMAT_VERSION",
    "SnapshotRecord",
    "SnapshotService",
]
