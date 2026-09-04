"""Canonical persisted status values."""

from __future__ import annotations

from enum import StrEnum


class ConnectionStatus(StrEnum):
    DISCONNECTED = "disconnected"
    WAITING = "waiting"
    CONNECTED = "connected"


class SyncStatus(StrEnum):
    PENDING_APPLY = "pending_apply"
    PENDING_DELETE = "pending_delete"
    SYNCHRONIZED = "synchronized"
    SKIPPED = "skipped"


LEGACY_CONNECTION_STATUS = {
    -1: ConnectionStatus.DISCONNECTED,
    0: ConnectionStatus.WAITING,
    1: ConnectionStatus.CONNECTED,
}

LEGACY_SYNC_STATUS = {
    -1: SyncStatus.PENDING_DELETE,
    0: SyncStatus.PENDING_APPLY,
    1: SyncStatus.SYNCHRONIZED,
    3: SyncStatus.SKIPPED,
}


def connection_status(value: object) -> ConnectionStatus:
    """Normalize a persisted connection status and reject unknown values."""
    if isinstance(value, ConnectionStatus):
        return value
    if isinstance(value, int):
        try:
            return LEGACY_CONNECTION_STATUS[value]
        except KeyError as exc:
            raise ValueError(f"Unknown connection status: {value!r}") from exc
    try:
        return ConnectionStatus(str(value))
    except ValueError as exc:
        raise ValueError(f"Unknown connection status: {value!r}") from exc


def sync_status(value: object) -> SyncStatus:
    """Normalize a persisted synchronization status and reject unknown values."""
    if isinstance(value, SyncStatus):
        return value
    if isinstance(value, int):
        try:
            return LEGACY_SYNC_STATUS[value]
        except KeyError as exc:
            raise ValueError(f"Unknown sync status: {value!r}") from exc
    try:
        return SyncStatus(str(value))
    except ValueError as exc:
        raise ValueError(f"Unknown sync status: {value!r}") from exc
