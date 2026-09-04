"""Application service for backup commits, legacy migration, and UI payloads."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .paths import host_directory_name, legacy_backup_paths, validate_host
from .repository import ConfigBackupRepository


class ConfigBackupService:
    """Coordinate safe migration and repository operations for config backups."""

    def __init__(self, backup_root: Path) -> None:
        """Create a repository adapter rooted at the application's backup folder."""
        self.repository = ConfigBackupRepository(backup_root)

    def _read_legacy_text(self, path: Path) -> str:
        """Decode an existing backup using the encodings supported by the old UI."""
        for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace")

    def migrate_legacy_backup(self, host: str) -> dict[str, object]:
        """Import one legacy text file exactly once and preserve it as .migrated."""
        normalized_host = validate_host(host)
        with self.repository.locked(normalized_host):
            if self.repository.has_commits(normalized_host):
                return {"ok": True, "migrated": False}
            legacy = next((path for path in legacy_backup_paths(self.repository.backup_root, normalized_host) if path.is_file()), None)
            if legacy is None:
                return {"ok": True, "migrated": False}
            timestamp = int(legacy.stat().st_mtime)
            date_time = datetime.fromtimestamp(timestamp).astimezone().strftime("%d/%m/%Y %H:%M:%S")
            result = self.repository.commit_snapshot(
                normalized_host,
                self._read_legacy_text(legacy),
                message=f"Import legacy backup - {date_time}",
                timestamp=timestamp,
            )
            migrated_path = legacy.with_name(f"{legacy.name}.migrated")
            if not migrated_path.exists():
                legacy.replace(migrated_path)
            return {**result, "migrated": True, "legacyPath": str(migrated_path)}

    def save_snapshot(self, host: str, content: str) -> dict[str, object]:
        """Migrate old data when needed, then append every successful collection."""
        normalized_host = validate_host(host)
        self.migrate_legacy_backup(normalized_host)
        return self.repository.commit_snapshot(normalized_host, content)

    def delete_host_data(self, host: str) -> bool:
        """Permanently remove every configuration backup owned by one host."""
        normalized_host = validate_host(host)
        backup_root = self.repository.backup_root.resolve()
        host_directory = (
            backup_root / host_directory_name(normalized_host)
        ).resolve()
        if backup_root not in host_directory.parents:
            raise ValueError("Resolved backup path is outside the backup root.")
        with self.repository.locked(normalized_host):
            if not host_directory.exists():
                return False
            if host_directory.is_symlink() or not host_directory.is_dir():
                raise RuntimeError("Host backup path is not a safe directory.")
            shutil.rmtree(host_directory)
        return True

    def list_history(self, host: str, limit: int = 100) -> dict[str, object]:
        """Return newest-first commit history for QML with structured failures."""
        try:
            normalized_host = validate_host(host)
            self.migrate_legacy_backup(normalized_host)
            return {"ok": True, "host": normalized_host, "commits": self.repository.list_commits(normalized_host, limit)}
        except Exception as exc:
            return {"ok": False, "host": (host or "").strip(), "commits": [], "message": str(exc)}

    def read_commit(self, host: str, commit_id: str) -> dict[str, object]:
        """Return a historical snapshot without changing HEAD or the working tree."""
        try:
            normalized_host = validate_host(host)
            self.migrate_legacy_backup(normalized_host)
            return self.repository.read_commit(normalized_host, (commit_id or "").strip())
        except Exception as exc:
            return {"ok": False, "host": (host or "").strip(), "commitId": commit_id or "", "content": "", "path": "", "message": str(exc)}

    def diff_commits(
        self,
        host: str,
        base_commit_id: str,
        target_commit_id: str,
    ) -> dict[str, object]:
        """Compare two reachable snapshots, including non-adjacent range endpoints."""
        try:
            normalized_host = validate_host(host)
            self.migrate_legacy_backup(normalized_host)
            return self.repository.diff_commits(
                normalized_host,
                (base_commit_id or "").strip(),
                (target_commit_id or "").strip(),
            )
        except Exception as exc:
            return {
                "ok": False,
                "host": (host or "").strip(),
                "baseCommitId": base_commit_id or "",
                "targetCommitId": target_commit_id or "",
                "diff": "",
                "message": str(exc),
            }

    def read_latest(self, host: str) -> dict[str, object]:
        """Return the most recent stored snapshot after optional legacy migration."""
        try:
            normalized_host = validate_host(host)
            self.migrate_legacy_backup(normalized_host)
            return self.repository.read_latest(normalized_host)
        except Exception as exc:
            return {"ok": False, "host": (host or "").strip(), "commitId": "", "content": "", "path": "", "message": str(exc)}
