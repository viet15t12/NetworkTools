"""Compatibility facade over the focused Syslog SQLite repositories."""

from __future__ import annotations

from pathlib import Path

from .persistence.device_lookup_repository import DeviceLookupRepository
from .persistence.device_state_repository import DeviceStateRepository
from .persistence.message_repository import MessageRepository


class SyslogRepository:
    """Preserve the historical API while delegating to focused repositories."""

    def __init__(self, info_db: Path, device_db: Path) -> None:
        self.info_db = Path(info_db)
        self.device_db = Path(device_db)
        self.messages = MessageRepository(self.info_db)
        self.device_states = DeviceStateRepository(self.device_db, self.info_db)
        self.device_lookup = DeviceLookupRepository(self.device_db)

    def ensure_schema(self) -> None:
        self.messages = MessageRepository(self.info_db)

    def __getattr__(self, name: str):
        for repository in (self.messages, self.device_states, self.device_lookup):
            value = getattr(repository, name, None)
            if value is not None:
                return value
        raise AttributeError(name)


__all__ = ["SyslogRepository"]
