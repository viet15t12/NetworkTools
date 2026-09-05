"""Consistent SQLite imaging and stable tree-copy helpers for workspace saves."""

from __future__ import annotations

import hashlib
import shutil
from infrastructure.database import sqlcipher as sqlite3
import time
from contextlib import closing
from pathlib import Path

from .errors import InvalidWorkspacePackage, WorkspacePackageError
from .package import REQUIRED_DATABASES


ContentSignature = tuple[tuple[str, int, int], ...]
PACKAGE_GIT_METADATA_DIRECTORY = ".cams-git"


def workspace_content_signature(root: str | Path) -> ContentSignature:
    """Return a metadata signature for live databases and backup content."""

    workspace = Path(root)
    entries: list[tuple[str, int, int]] = []
    for database_name in REQUIRED_DATABASES:
        path = workspace / database_name
        metadata = path.stat()
        entries.append((database_name, metadata.st_size, metadata.st_mtime_ns))
        # WAL/journal bytes can contain committed logical changes.  The SHM
        # file is lock/index state and may change merely because a reader ran.
        for suffix in ("-wal", "-journal"):
            side_file = path.with_name(path.name + suffix)
            if side_file.exists():
                side_metadata = side_file.stat()
                entries.append(
                    (
                        database_name + suffix,
                        side_metadata.st_size,
                        side_metadata.st_mtime_ns,
                    )
                )
    backup = workspace / "backup"
    if backup.is_symlink() or not backup.is_dir():
        raise InvalidWorkspacePackage("The workspace backup path is invalid.")
    for path in sorted(backup.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise InvalidWorkspacePackage(
                f"Symbolic links are forbidden in workspace backups: {path}."
            )
        relative = path.relative_to(workspace).as_posix()
        metadata = path.stat()
        entries.append(
            (
                relative + ("/" if path.is_dir() else ""),
                0 if path.is_dir() else metadata.st_size,
                metadata.st_mtime_ns,
            )
        )
    return tuple(entries)


def backup_sqlite_database(source: str | Path, destination: str | Path) -> None:
    """Create and validate a transactionally consistent SQLite backup image."""

    source_path = Path(source)
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.unlink(missing_ok=True)
    try:
        with closing(
            sqlite3.connect(
                source_path.resolve().as_uri() + "?mode=ro",
                uri=True,
                timeout=30.0,
            )
        ) as source_db, closing(sqlite3.connect(destination_path)) as target_db:
            source_db.execute("PRAGMA busy_timeout = 30000;")
            target_db.execute("PRAGMA busy_timeout = 30000;")
            source_db.backup(target_db, pages=1024, sleep=0.005)
            target_db.commit()
            if target_db.execute("PRAGMA quick_check;").fetchall() != [("ok",)]:
                raise InvalidWorkspacePackage(
                    f"SQLite quick_check failed for staged {source_path.name}."
                )
            foreign_keys = target_db.execute(
                "PRAGMA foreign_key_check;"
            ).fetchmany(5)
            if foreign_keys:
                raise InvalidWorkspacePackage(
                    f"SQLite foreign_key_check failed for staged {source_path.name}."
                )
    except Exception:
        destination_path.unlink(missing_ok=True)
        _remove_sqlite_side_files(destination_path)
        raise
    _remove_sqlite_side_files(destination_path)


def copy_stable_tree(
    source: str | Path,
    destination: str | Path,
    *,
    attempts: int = 3,
    chunk_size: int = 1024 * 1024,
) -> None:
    """Copy a regular-file tree, retrying if its metadata changes mid-copy."""

    if attempts <= 0 or chunk_size <= 0:
        raise ValueError("attempts and chunk_size must be positive")

    source_root = Path(source)
    destination_root = Path(destination)
    if source_root.is_symlink() or not source_root.is_dir():
        raise InvalidWorkspacePackage(f"Workspace tree is invalid: {source_root}.")
    for attempt in range(attempts):
        try:
            before = tree_signature(source_root)
            shutil.rmtree(destination_root, ignore_errors=True)
            destination_root.mkdir(parents=True, exist_ok=True)
            for path in sorted(source_root.rglob("*"), key=lambda item: item.as_posix()):
                relative = path.relative_to(source_root)
                target = destination_root / relative
                if path.is_symlink():
                    raise InvalidWorkspacePackage(
                        f"Symbolic links are forbidden in workspace trees: {path}."
                    )
                if path.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not path.is_file():
                    raise InvalidWorkspacePackage(
                        f"Special files are forbidden in workspace trees: {path}."
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                _copy_regular_file(path, target, chunk_size)
            after = tree_signature(source_root)
            if before == after:
                return
        except InvalidWorkspacePackage:
            shutil.rmtree(destination_root, ignore_errors=True)
            raise
        except (WorkspacePackageError, OSError) as exc:
            if attempt + 1 >= attempts:
                shutil.rmtree(destination_root, ignore_errors=True)
                raise WorkspacePackageError(
                    "Workspace backup content could not be copied consistently."
                ) from exc
        if attempt + 1 < attempts:
            time.sleep(0.02)
    shutil.rmtree(destination_root, ignore_errors=True)
    raise WorkspacePackageError(
        "Workspace backup content kept changing while the save image was created."
    )


def normalize_git_metadata_for_package(root: str | Path) -> None:
    """Rename legacy internal Git control directories in a disposable stage."""
    stage = Path(root)
    legacy_directories = sorted(
        (path for path in stage.rglob(".git") if path.name == ".git"),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for legacy in legacy_directories:
        if legacy.is_symlink() or not legacy.is_dir():
            raise InvalidWorkspacePackage(f"Invalid Git metadata path: {legacy}.")
        replacement = legacy.with_name(PACKAGE_GIT_METADATA_DIRECTORY)
        if replacement.exists():
            raise InvalidWorkspacePackage(
                f"Conflicting backup metadata directories: {legacy.parent}."
            )
        legacy.rename(replacement)


def tree_signature(root: str | Path) -> ContentSignature:
    source_root = Path(root)
    entries: list[tuple[str, int, int]] = []
    for path in sorted(source_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise InvalidWorkspacePackage(f"Symbolic links are forbidden: {path}.")
        metadata = path.stat()
        entries.append(
            (
                path.relative_to(source_root).as_posix()
                + ("/" if path.is_dir() else ""),
                0 if path.is_dir() else metadata.st_size,
                metadata.st_mtime_ns,
            )
        )
    return tuple(entries)


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_regular_file(source: Path, destination: Path, chunk_size: int) -> None:
    before = source.stat()
    with source.open("rb") as input_stream, destination.open("xb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream, chunk_size)
    after = source.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or destination.stat().st_size != after.st_size
    ):
        raise WorkspacePackageError(f"Workspace file changed while copying: {source}.")
    shutil.copystat(source, destination)


def _remove_sqlite_side_files(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        path.with_name(path.name + suffix).unlink(missing_ok=True)


__all__ = [
    "ContentSignature",
    "backup_sqlite_database",
    "copy_stable_tree",
    "normalize_git_metadata_for_package",
    "sha256_file",
    "tree_signature",
    "workspace_content_signature",
]
