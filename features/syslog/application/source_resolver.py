"""TTL-cached mapping from packet source addresses to managed devices."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Protocol


class DeviceLookup(Protocol):
    def resolve_device_host(self, source_ip: str) -> str | None: ...


class DeviceHostResolver:
    def __init__(
        self, repository: DeviceLookup, *, ttl_seconds: float = 30.0,
        max_entries: int = 1_024,
    ) -> None:
        self.repository = repository
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self.max_entries = max(16, int(max_entries))
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def resolve(self, source_ip: str) -> str:
        now = time.monotonic()
        cached = self._cache.get(source_ip)
        if cached is not None and cached[0] > now:
            self._cache.move_to_end(source_ip)
            return cached[1]
        host = self.repository.resolve_device_host(source_ip) or source_ip
        self._cache[source_ip] = (now + self.ttl_seconds, host)
        self._cache.move_to_end(source_ip)
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)
        return host

    def set_repository(self, repository: DeviceLookup) -> None:
        self.repository = repository
        self._cache.clear()


__all__ = ["DeviceHostResolver"]
