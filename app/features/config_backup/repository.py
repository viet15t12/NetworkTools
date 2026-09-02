"""Dulwich-backed storage for immutable running-configuration snapshots."""

from __future__ import annotations

import os
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from typing import Iterator

from dulwich.objects import Blob, Commit, Tree
from dulwich.repo import Repo

from .models import ConfigCommit, ConfigSnapshot
from .paths import repository_path, validate_host


CONFIG_FILENAME = "running-config.txt"
METADATA_DIRECTORY = ".cams-git"
AUTHOR = b"CAMS <cams@localhost>"
_COMMIT_ID = re.compile(r"^[0-9a-fA-F]{40}$")


class ConfigBackupRepository:
    """Create and query one local Git repository for every network device."""

    def __init__(self, backup_root: Path) -> None:
        """Store the runtime root and initialize per-host re-entrant locks."""
        self.backup_root = Path(backup_root)
        self._locks_guard = threading.Lock()
        self._host_locks: dict[str, threading.RLock] = {}

    def _lock_for(self, host: str) -> threading.RLock:
        """Return the process-local lock that serializes access for one host."""
        normalized = validate_host(host)
        with self._locks_guard:
            return self._host_locks.setdefault(normalized, threading.RLock())

    @contextmanager
    def locked(self, host: str) -> Iterator[None]:
        """Hold the host lock across a multi-step service operation."""
        with self._lock_for(host):
            yield

    def ensure_repository(self, host: str) -> Path:
        """Create and return the working-tree repository for a validated host."""
        path = repository_path(self.backup_root, host)
        with self._lock_for(host):
            path.mkdir(parents=True, exist_ok=True)
            metadata = self._metadata_path(path)
            if not metadata.is_dir():
                if any(path.iterdir()):
                    raise RuntimeError(f"Backup directory is not an initialized repository: {path}")
                Repo.init_bare(metadata, mkdir=True).close()
        return path

    @staticmethod
    def _metadata_path(path: Path) -> Path:
        """Migrate legacy ``.git`` metadata to the package-safe internal name."""
        metadata = path / METADATA_DIRECTORY
        legacy = path / ".git"
        if legacy.exists():
            if legacy.is_symlink() or not legacy.is_dir():
                raise RuntimeError(f"Invalid legacy backup metadata: {legacy}")
            if metadata.exists():
                raise RuntimeError(f"Conflicting backup metadata directories: {path}")
            os.replace(legacy, metadata)
        return metadata

    def has_commits(self, host: str) -> bool:
        """Report whether the device repository currently has a HEAD commit."""
        path = repository_path(self.backup_root, host)
        with self._lock_for(host):
            metadata = self._metadata_path(path)
            if not metadata.is_dir():
                return False
        with self._lock_for(host), Repo(metadata) as repo:
            try:
                repo.head()
                return True
            except KeyError:
                return False

    def _normalize_content(self, content: str) -> str:
        """Reject empty command output and ensure a stable trailing newline."""
        text = str(content or "")
        if not text.strip():
            raise ValueError("Running-config output is empty.")
        return text if text.endswith("\n") else f"{text}\n"

    def _write_latest_atomically(self, path: Path, content: str) -> None:
        """Replace the latest working-tree snapshot without exposing partial data."""
        temporary_name = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=path,
                prefix=".running-config.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            os.replace(temporary_name, path / CONFIG_FILENAME)
        finally:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)

    def _timezone_offset(self, timestamp: int) -> int:
        """Return the local UTC offset in seconds for Dulwich commit metadata."""
        offset = datetime.fromtimestamp(timestamp).astimezone().utcoffset()
        return int(offset.total_seconds()) if offset is not None else 0

    def _read_blob(self, repo: Repo, commit: Commit) -> bytes:
        """Read running-config.txt directly from a commit tree without checkout."""
        tree = repo[commit.tree]
        if not isinstance(tree, Tree):
            raise RuntimeError("Commit tree is invalid.")
        _mode, blob_id = tree.lookup_path(repo.__getitem__, CONFIG_FILENAME.encode("utf-8"))
        blob = repo[blob_id]
        if not isinstance(blob, Blob):
            raise RuntimeError("Configuration object is not a Git blob.")
        return blob.data

    def _is_changed(self, repo: Repo, content: bytes) -> bool:
        """Compare new bytes with HEAD while treating the first snapshot as changed."""
        try:
            head = repo[repo.head()]
        except KeyError:
            return True
        if not isinstance(head, Commit):
            raise RuntimeError("Repository HEAD is not a commit.")
        return self._read_blob(repo, head) != content

    def commit_snapshot(
        self,
        host: str,
        content: str,
        message: str | None = None,
        timestamp: int | None = None,
    ) -> dict[str, object]:
        """Atomically update the latest file and always create a new Git commit."""
        normalized_host = validate_host(host)
        normalized_content = self._normalize_content(content)
        path = self.ensure_repository(normalized_host)
        with self._lock_for(normalized_host), Repo(self._metadata_path(path)) as repo:
            content_bytes = normalized_content.encode("utf-8")
            changed = self._is_changed(repo, content_bytes)
            self._write_latest_atomically(path, normalized_content)

            blob = Blob.from_string(content_bytes)
            tree = Tree()
            tree.add(CONFIG_FILENAME.encode("utf-8"), 0o100644, blob.id)
            repo.object_store.add_object(blob)
            repo.object_store.add_object(tree)

            commit_time = int(timestamp if timestamp is not None else time.time())
            date_time = datetime.fromtimestamp(commit_time).astimezone().strftime("%d/%m/%Y %H:%M:%S")
            commit = Commit()
            commit.tree = tree.id
            try:
                commit.parents = [repo.head()]
            except KeyError:
                commit.parents = []
            commit.author = AUTHOR
            commit.committer = AUTHOR
            commit.author_time = commit_time
            commit.commit_time = commit_time
            timezone = self._timezone_offset(commit_time)
            commit.author_timezone = timezone
            commit.commit_timezone = timezone
            commit.message = (message or date_time).encode("utf-8")
            repo.object_store.add_object(commit)
            repo.refs[b"HEAD"] = commit.id

            payload = self._commit_payload(normalized_host, commit, changed)
            payload.update({"ok": True, "commitCreated": True, "path": str(path / CONFIG_FILENAME)})
            return payload

    def _commit_payload(self, host: str, commit: Commit, changed: bool) -> dict[str, object]:
        """Convert a Dulwich commit into the stable public history contract."""
        commit_id = commit.id.decode("ascii")
        timestamp = int(commit.commit_time)
        author = commit.author.decode("utf-8", errors="replace").split(" <", 1)[0]
        model = ConfigCommit(
            commitId=commit_id,
            shortCommitId=commit_id[:7],
            message=commit.message.decode("utf-8", errors="replace").strip(),
            timestamp=timestamp,
            dateTime=datetime.fromtimestamp(timestamp).astimezone().strftime("%d/%m/%Y %H:%M:%S"),
            author=author,
            host=host,
            changed=changed,
        )
        payload = model.to_dict()
        payload["displayText"] = f"{model.dateTime} · {model.shortCommitId}"
        return payload

    def _commit_changed(self, repo: Repo, commit: Commit) -> bool:
        """Compare a commit snapshot with its first parent for history metadata."""
        if not commit.parents:
            return True
        parent = repo[commit.parents[0]]
        if not isinstance(parent, Commit):
            raise RuntimeError("Commit parent is invalid.")
        return self._read_blob(repo, commit) != self._read_blob(repo, parent)

    def list_commits(self, host: str, limit: int = 100) -> list[dict[str, object]]:
        """List newest reachable commits with a bounded result size."""
        normalized_host = validate_host(host)
        bounded_limit = max(1, min(int(limit), 500))
        path = repository_path(self.backup_root, normalized_host)
        with self._lock_for(normalized_host):
            metadata = self._metadata_path(path)
            if not metadata.is_dir():
                return []
        with self._lock_for(normalized_host), Repo(metadata) as repo:
            try:
                entries = repo.get_walker(max_entries=bounded_limit)
                commits = [entry.commit for entry in entries]
            except KeyError:
                return []
            payloads: list[dict[str, object]] = []
            for commit in commits:
                payloads.append(self._commit_payload(normalized_host, commit, self._commit_changed(repo, commit)))
            return payloads

    def _reachable_commit(self, repo: Repo, commit_id: str) -> Commit:
        """Resolve only a full commit ID reachable from this repository's HEAD."""
        if not _COMMIT_ID.fullmatch(commit_id or ""):
            raise ValueError("Commit ID must contain exactly 40 hexadecimal characters.")
        wanted = commit_id.lower().encode("ascii")
        try:
            for entry in repo.get_walker():
                if entry.commit.id == wanted:
                    return entry.commit
        except KeyError as exc:
            raise LookupError("Repository has no commits.") from exc
        raise LookupError("Commit was not found in this device history.")

    def read_commit(self, host: str, commit_id: str) -> dict[str, object]:
        """Read one reachable snapshot directly from Git objects without checkout."""
        normalized_host = validate_host(host)
        path = repository_path(self.backup_root, normalized_host)
        with self._lock_for(normalized_host):
            metadata = self._metadata_path(path)
            if not metadata.is_dir():
                raise LookupError("No configuration backup repository exists for this host.")
        with self._lock_for(normalized_host), Repo(metadata) as repo:
            commit = self._reachable_commit(repo, commit_id)
            snapshot = ConfigSnapshot(
                host=normalized_host,
                commitId=commit.id.decode("ascii"),
                content=self._read_blob(repo, commit).decode("utf-8", errors="replace"),
                path=str(path / CONFIG_FILENAME),
                dateTime=datetime.fromtimestamp(int(commit.commit_time)).astimezone().strftime("%d/%m/%Y %H:%M:%S"),
            )
            payload = snapshot.to_dict()
            payload["shortCommitId"] = snapshot.commitId[:7]
            return payload

    def diff_commits(
        self,
        host: str,
        base_commit_id: str,
        target_commit_id: str,
    ) -> dict[str, object]:
        """Return a unified diff between any two reachable history snapshots."""
        normalized_host = validate_host(host)
        path = repository_path(self.backup_root, normalized_host)
        with self._lock_for(normalized_host):
            metadata = self._metadata_path(path)
            if not metadata.is_dir():
                raise LookupError("No configuration backup repository exists for this host.")

        with self._lock_for(normalized_host), Repo(metadata) as repo:
            base_commit = self._reachable_commit(repo, base_commit_id)
            target_commit = self._reachable_commit(repo, target_commit_id)
            base_content = self._read_blob(repo, base_commit).decode("utf-8", errors="replace")
            target_content = self._read_blob(repo, target_commit).decode("utf-8", errors="replace")
            base_id = base_commit.id.decode("ascii")
            target_id = target_commit.id.decode("ascii")
            diff_lines = list(
                unified_diff(
                    base_content.splitlines(keepends=True),
                    target_content.splitlines(keepends=True),
                    fromfile=f"running-config@{base_id[:7]}",
                    tofile=f"running-config@{target_id[:7]}",
                    lineterm="\n",
                )
            )

            # Repositories are intentionally linear today.  The span tells the
            # UI whether the selected endpoints cover two adjacent snapshots or
            # a cumulative range across several Git versions.
            history_ids = [entry.commit.id for entry in repo.get_walker()]
            base_index = history_ids.index(base_commit.id)
            target_index = history_ids.index(target_commit.id)
            version_span = abs(base_index - target_index) + 1
            additions = sum(
                1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
            )
            deletions = sum(
                1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
            )
            return {
                "ok": True,
                "host": normalized_host,
                "baseCommitId": base_id,
                "targetCommitId": target_id,
                "baseDateTime": datetime.fromtimestamp(int(base_commit.commit_time))
                .astimezone()
                .strftime("%d/%m/%Y %H:%M:%S"),
                "targetDateTime": datetime.fromtimestamp(int(target_commit.commit_time))
                .astimezone()
                .strftime("%d/%m/%Y %H:%M:%S"),
                "diff": "".join(diff_lines),
                "changed": base_content != target_content,
                "additions": additions,
                "deletions": deletions,
                "versionSpan": version_span,
                "path": str(path / CONFIG_FILENAME),
            }

    def read_latest(self, host: str) -> dict[str, object]:
        """Read HEAD for a host, returning the same shape as read_commit()."""
        normalized_host = validate_host(host)
        path = repository_path(self.backup_root, normalized_host)
        with self._lock_for(normalized_host):
            metadata = self._metadata_path(path)
            if not metadata.is_dir():
                raise LookupError("No configuration backup repository exists for this host.")
        with self._lock_for(normalized_host), Repo(metadata) as repo:
            try:
                commit_id = repo.head().decode("ascii")
            except KeyError as exc:
                raise LookupError("No configuration backup commits exist for this host.") from exc
        return self.read_commit(normalized_host, commit_id)
