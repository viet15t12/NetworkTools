"""High-level create/open/save/snapshot lifecycle for `.ntp` workspaces."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .errors import WorkspacePasswordRequired
from .locking import ProjectFileLock
from .package import WorkspaceManifest, WorkspacePackageCodec, WorkspaceSession
from .snapshot import SnapshotRecord, SnapshotService
from .staging import (
    ContentSignature,
    backup_sqlite_database,
    copy_stable_tree,
    normalize_git_metadata_for_package,
    workspace_content_signature,
)


DatabaseInitializer = Callable[[Path, Path], None]


@dataclass(frozen=True, slots=True)
class SaveResult:
    manifest: WorkspaceManifest
    saved_at: str
    reason: str
    skipped: bool
    changed_during_save: bool
    snapshot: SnapshotRecord | None = None


@dataclass(frozen=True, slots=True)
class RollbackResult:
    restored_snapshot: SnapshotRecord
    safety_snapshot: SnapshotRecord
    save: SaveResult


class WorkspaceService:
    """Create/open and serialize one managed workspace at a time."""

    def __init__(
        self,
        codec: WorkspacePackageCodec | None = None,
        *,
        database_initializer: DatabaseInitializer | None = None,
        snapshot_service: SnapshotService | None = None,
    ) -> None:
        self.codec = codec or WorkspacePackageCodec()
        self.snapshot_service = snapshot_service or SnapshotService()
        self._database_initializer = database_initializer or _initialize_databases

    def create_project(
        self,
        project_name: str,
        package_path: str | Path,
        *,
        password: str | None = None,
    ) -> WorkspaceSession:
        """Create canonical databases, pack the first project, and keep it active."""

        target = Path(package_path).expanduser().absolute()
        session = self.codec.new_session(target, project_name)
        try:
            self._database_initializer(
                session.device_network_db, session.info_collected_db
            )
            manifest = self.codec.pack(
                session.working_directory,
                target,
                password=password,
                project_name=project_name,
                base_manifest=session.manifest,
            )
            self.codec.update_session_after_pack(
                session, manifest, encrypted=bool(password)
            )
            _write_live_manifest(session, manifest)
            session.set_password(password)
            session.saved_content_signature = workspace_content_signature(
                session.working_directory
            )
            return session
        except Exception:
            session.close()
            raise

    def open_project(
        self, package_path: str | Path, *, password: str | None = None
    ) -> WorkspaceSession:
        session = self.codec.open(package_path, password)
        try:
            self.snapshot_service.validate_snapshots(session.working_directory)
            session.set_password(password if session.encrypted else None)
            session.saved_content_signature = workspace_content_signature(
                session.working_directory
            )
            return session
        except Exception:
            session.close()
            raise

    def save_project(
        self,
        session: WorkspaceSession,
        *,
        reason: str = "manual",
        password: str | None = None,
        force: bool = True,
        create_snapshot: bool = False,
        snapshot_label: str = "",
        snapshot_reason: str = "manual",
        source_generation: int = 0,
        snapshot_pinned: bool = False,
        package_path: str | Path | None = None,
        _session_lease: bool = False,
    ) -> SaveResult:
        """Build consistent images and atomically replace the project package."""

        operation = nullcontext(session) if _session_lease else session.operation()
        with operation, session.io_lock:
            return self._save_locked(
                session,
                reason=reason,
                password=password,
                force=force,
                create_snapshot=create_snapshot,
                snapshot_label=snapshot_label,
                snapshot_reason=snapshot_reason,
                source_generation=source_generation,
                snapshot_pinned=snapshot_pinned,
                package_path=package_path,
            )

    def _save_locked(
        self,
        session: WorkspaceSession,
        *,
        reason: str,
        password: str | None,
        force: bool,
        create_snapshot: bool,
        snapshot_label: str,
        snapshot_reason: str,
        source_generation: int,
        snapshot_pinned: bool,
        package_path: str | Path | None,
    ) -> SaveResult:
        before = workspace_content_signature(session.working_directory)
        if not force and before == session.saved_content_signature:
            return SaveResult(
                manifest=session.manifest,
                saved_at=_utc_now(),
                reason=reason,
                skipped=True,
                changed_during_save=False,
            )
        effective_password = self._effective_password(session, password)
        destination = (
            Path(package_path).expanduser().absolute()
            if package_path is not None
            else session.project_path
        )
        save_as = destination != session.project_path
        destination_lock = ProjectFileLock.acquire(destination) if save_as else None
        try:
            if save_as and destination.exists():
                raise FileExistsError(f"A project already exists at {destination}.")
            with tempfile.TemporaryDirectory(prefix="cams-save-") as temporary:
                staged = Path(temporary) / "workspace"
                self._stage_workspace(session, staged)
                snapshot = None
                if create_snapshot:
                    snapshot = self.snapshot_service.create_from_staged_workspace(
                        session,
                        staged,
                        label=snapshot_label,
                        reason=snapshot_reason,
                        source_generation=source_generation,
                        pinned=snapshot_pinned,
                    )
                manifest = self.codec.pack(
                    staged,
                    destination,
                    password=effective_password,
                    base_manifest=session.manifest,
                    expected_fingerprint=(
                        None if save_as else session.package_fingerprint
                    ),
                )
        except Exception:
            if destination_lock is not None:
                destination_lock.release()
            raise

        previous_lock = session._project_lock
        session.project_path = destination
        if destination_lock is not None:
            session._project_lock = destination_lock
            if previous_lock is not None:
                previous_lock.release()
        self.codec.update_session_after_pack(
            session, manifest, encrypted=bool(effective_password)
        )
        session.set_password(effective_password)
        _write_live_manifest(session, manifest)
        after = workspace_content_signature(session.working_directory)
        changed_during_save = after != before
        session.saved_content_signature = before if changed_during_save else after
        return SaveResult(
            manifest=manifest,
            saved_at=_utc_now(),
            reason=reason,
            skipped=False,
            changed_during_save=changed_during_save,
            snapshot=snapshot,
        )

    def pack_project(
        self,
        session: WorkspaceSession,
        *,
        package_path: str | Path | None = None,
        password: str | None = None,
    ) -> SaveResult:
        """Compatibility wrapper for explicit Save and Save As."""

        return self.save_project(
            session,
            reason="manual",
            password=password,
            package_path=package_path,
        )

    def rollback_project(
        self,
        session: WorkspaceSession,
        snapshot_id: str,
        *,
        password: str | None = None,
        source_generation: int = 0,
        _session_lease: bool = False,
    ) -> RollbackResult:
        """Create a pinned safety point, restore history, then save atomically."""

        operation = nullcontext(session) if _session_lease else session.operation()
        with operation, session.io_lock:
            effective_password = self._effective_password(session, password)
            with tempfile.TemporaryDirectory(prefix="cams-rollback-") as temporary:
                current_stage = Path(temporary) / "current"
                self._stage_workspace(session, current_stage)
                safety = self.snapshot_service.create_from_staged_workspace(
                    session,
                    current_stage,
                    label="Before rollback",
                    reason="before-rollback",
                    source_generation=source_generation,
                    pinned=True,
                )
                restored = self.snapshot_service.restore_snapshot(
                    session,
                    snapshot_id,
                    recovery_workspace=current_stage,
                )
                result = self._save_locked(
                    session,
                    reason="rollback",
                    password=effective_password,
                    force=True,
                    create_snapshot=False,
                    snapshot_label="",
                    snapshot_reason="manual",
                    source_generation=source_generation + 1,
                    snapshot_pinned=False,
                    package_path=None,
                )
            return RollbackResult(restored, safety, result)

    def list_snapshots(self, session: WorkspaceSession) -> tuple[SnapshotRecord, ...]:
        with session.io_lock:
            return self.snapshot_service.list_snapshots(session.working_directory)

    def is_encrypted(self, package_path: str | Path) -> bool:
        return self.codec.is_encrypted(package_path)

    @staticmethod
    def close_project(session: WorkspaceSession | None) -> None:
        if session is not None:
            session.close()

    @staticmethod
    def _effective_password(
        session: WorkspaceSession, supplied: str | None
    ) -> str | None:
        if supplied is not None:
            return supplied or None
        active_password = session.password()
        if session.encrypted and not active_password:
            raise WorkspacePasswordRequired(
                "Saving a protected project requires its active password."
            )
        return active_password

    @staticmethod
    def _stage_workspace(session: WorkspaceSession, staged: Path) -> None:
        staged.mkdir(parents=True)
        backup_sqlite_database(session.device_network_db, staged / "device_network.db")
        backup_sqlite_database(session.info_collected_db, staged / "info_collected.db")
        copy_stable_tree(session.backup_directory, staged / "backup")
        snapshots = session.working_directory / "snapshots"
        copy_stable_tree(snapshots, staged / "snapshots")
        normalize_git_metadata_for_package(staged)
        _refresh_staged_snapshot_inventories(staged / "snapshots")
        index = staged / "snapshots" / "index.json"
        if not index.exists():
            index.write_text(
                json.dumps({"formatVersion": 1, "snapshots": []}, indent=2) + "\n",
                encoding="utf-8",
            )


def _initialize_databases(device_network_db: Path, info_collected_db: Path) -> None:
    """Build both workspace databases from the installed canonical schemas."""

    from infrastructure.database.paths import (
        DEVICE_NETWORK_SCHEMA_DIR,
        INFO_COLLECTED_SCHEMA_DIR,
    )
    from scripts.build_databases import build_database

    build_database(DEVICE_NETWORK_SCHEMA_DIR, device_network_db)
    build_database(INFO_COLLECTED_SCHEMA_DIR, info_collected_db)


def _refresh_staged_snapshot_inventories(snapshots_root: Path) -> None:
    """Refresh inventories when a legacy ``.git`` path was renamed in staging."""
    if not snapshots_root.is_dir():
        return
    for snapshot_directory in snapshots_root.iterdir():
        if not snapshot_directory.is_dir():
            continue
        metadata_path = snapshot_directory / "snapshot.json"
        if not metadata_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            continue
        metadata["items"] = SnapshotService._inventory(snapshot_directory)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_live_manifest(
    session: WorkspaceSession, manifest: WorkspaceManifest
) -> None:
    """Atomically mirror committed metadata into the disposable live session."""

    path = session.working_directory / "manifest.json"
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(manifest.to_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "DatabaseInitializer",
    "RollbackResult",
    "SaveResult",
    "WorkspaceService",
]
