"""Safe runtime-path helpers for per-device configuration repositories."""

from __future__ import annotations

import re
from pathlib import Path


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_SUPPORTED_HOST = re.compile(r"^[A-Za-z0-9_.:%-]+$")


def validate_host(host: str) -> str:
    """Return a trimmed safe host or raise when it could escape the backup root."""
    normalized = (host or "").strip()
    if (
        not normalized
        or normalized in {".", ".."}
        or ".." in normalized
        or "/" in normalized
        or "\\" in normalized
        or _CONTROL_CHARACTERS.search(normalized)
        or not _SUPPORTED_HOST.fullmatch(normalized)
    ):
        raise ValueError("Host contains unsupported path characters.")
    return normalized


def host_directory_name(host: str) -> str:
    """Map a validated host to a Windows-safe, stable directory name."""
    return validate_host(host).replace(":", "_")


def repository_path(backup_root: Path, host: str) -> Path:
    """Resolve ``backup/<host>/cfg`` and verify it remains below backup_root."""
    root = Path(backup_root).resolve()
    target = (root / host_directory_name(host) / "cfg").resolve()
    if root not in target.parents:
        raise ValueError("Resolved backup path is outside the backup root.")
    return target


def legacy_backup_paths(backup_root: Path, host: str) -> tuple[Path, ...]:
    """Return legacy filename candidates without allowing untrusted path traversal."""
    normalized = validate_host(host)
    host_dir = Path(backup_root).resolve() / host_directory_name(normalized)
    safe_filename_host = normalized.replace(":", "_")
    candidates = [host_dir / f"{safe_filename_host}_running-config.txt"]
    raw_candidate = host_dir / f"{normalized}_running-config.txt"
    if raw_candidate != candidates[0]:
        candidates.append(raw_candidate)
    return tuple(candidates)
