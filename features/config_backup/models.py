"""Typed payload models shared by the config-backup repository and service."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ConfigCommit:
    """Describe one immutable Git commit exposed to the QML history selector."""

    commitId: str
    shortCommitId: str
    message: str
    timestamp: int
    dateTime: str
    author: str
    host: str
    changed: bool

    def to_dict(self) -> dict[str, object]:
        """Convert this model to a Qt-friendly dictionary."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    """Contain configuration text and metadata read from a Git commit."""

    host: str
    commitId: str
    content: str
    path: str
    dateTime: str

    def to_dict(self) -> dict[str, object]:
        """Convert this snapshot to the public success payload."""
        return {"ok": True, **asdict(self)}
