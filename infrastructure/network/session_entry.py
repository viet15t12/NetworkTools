"""State owned by the persistent session registry for one device host."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any


@dataclass(slots=True)
class SessionEntry:
    host: str
    connector: Any | None = None
    state: str = "closed"
    operation_lock: threading.RLock = field(default_factory=threading.RLock)
    opened_at: float = 0.0
    last_used_at: float = 0.0
    last_error: str = ""
    generation: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "state": self.state,
            "openedAt": self.opened_at,
            "lastUsedAt": self.last_used_at,
            "lastError": self.last_error,
            "generation": self.generation,
        }

    def touch(self) -> None:
        self.last_used_at = time.time()
