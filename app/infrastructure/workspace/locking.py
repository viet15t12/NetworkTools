"""Cross-process ownership leases for editable ``.ntp`` projects."""

from __future__ import annotations

import json
import os
import socket
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from .errors import WorkspaceConflictError


class ProjectFileLock:
    """Hold an exclusive OS lock for the lifetime of one workspace session.

    The small sidecar deliberately remains on disk after release.  Removing a
    lock file creates an inode race on POSIX where two later processes can each
    lock a different file with the same path.  The OS lock, not the metadata in
    the sidecar, is the source of truth.
    """

    def __init__(self, project_path: Path, sidecar_path: Path, stream: BinaryIO) -> None:
        self.project_path = project_path
        self.sidecar_path = sidecar_path
        self._stream: BinaryIO | None = stream

    @classmethod
    def acquire(cls, project_path: str | Path) -> "ProjectFileLock":
        project = Path(project_path).expanduser().resolve(strict=False)
        project.parent.mkdir(parents=True, exist_ok=True)
        sidecar = project.with_name(f".{project.name}.workspace.lock")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        elif sidecar.is_symlink():
            raise WorkspaceConflictError(
                "The workspace lock path is a symbolic link and is unsafe."
            )
        try:
            descriptor = os.open(sidecar, flags, 0o600)
        except OSError as exc:
            raise WorkspaceConflictError(
                "The workspace lock file could not be opened safely."
            ) from exc
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise WorkspaceConflictError(
                "The workspace lock path is not a regular file."
            )
        stream = os.fdopen(descriptor, "r+b", buffering=0)
        try:
            cls._lock(stream)
        except (BlockingIOError, OSError) as exc:
            stream.close()
            raise WorkspaceConflictError(
                "This project is already open in another NetworkTools session. "
                "Close that session before opening it here."
            ) from exc

        lease = cls(project, sidecar, stream)
        try:
            lease._write_metadata()
        except Exception:
            lease.release()
            raise
        return lease

    @staticmethod
    def _lock(stream: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            return

        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(stream: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _write_metadata(self) -> None:
        stream = self._stream
        if stream is None:
            return
        payload = {
            "formatVersion": 1,
            "host": socket.gethostname(),
            "openedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pid": os.getpid(),
            "projectPath": str(self.project_path),
        }
        encoded = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        stream.seek(0)
        stream.truncate()
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())

    def release(self) -> None:
        stream = self._stream
        if stream is None:
            return
        self._stream = None
        try:
            self._unlock(stream)
        finally:
            stream.close()


__all__ = ["ProjectFileLock"]
