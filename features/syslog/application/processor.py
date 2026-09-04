"""Turn raw transport events into normalized, device-resolved messages."""

from __future__ import annotations

from collections.abc import Callable

from ..domain.models import SyslogMessage
from ..parsing.parser import parse_message
from .source_resolver import DeviceHostResolver, DeviceLookup


class SyslogProcessor:
    def __init__(
        self,
        repository: DeviceLookup,
        *,
        parser: Callable[[bytes, str, str], SyslogMessage] = parse_message,
    ) -> None:
        self._parser = parser
        self._resolver = DeviceHostResolver(repository)

    def process(self, data: bytes, source_ip: str, protocol: str) -> SyslogMessage:
        message = self._parser(data, source_ip, protocol)
        message.device_host = self._resolver.resolve(source_ip)
        return message

    def set_repository(self, repository: DeviceLookup) -> None:
        self._resolver.set_repository(repository)


__all__ = ["SyslogProcessor"]
