"""Lifecycle helpers for application-owned temporary files."""

from __future__ import annotations

import shutil
from pathlib import Path

from infrastructure.network.config import TMP_DIR


def cleanup_runtime_tmp(directory: str | Path = TMP_DIR) -> tuple[str, ...]:
    """Remove runtime artifacts while preserving the temporary directory itself.

    Cleanup is best-effort so one locked file does not prevent the remaining
    artifacts from being removed during application shutdown. Symlinks are
    unlinked instead of followed.
    """
    root = Path(directory)
    if not root.exists():
        return ()
    if root.is_symlink() or not root.is_dir():
        return (f"Temporary path is not a real directory: {root}",)

    errors: list[str] = []
    try:
        entries = tuple(root.iterdir())
    except OSError as exc:
        return (f"{root}: {exc}",)

    for entry in entries:
        try:
            if entry.is_symlink() or not entry.is_dir():
                entry.unlink()
            else:
                shutil.rmtree(entry)
        except OSError as exc:
            errors.append(f"{entry}: {exc}")
    return tuple(errors)


__all__ = ["cleanup_runtime_tmp"]
