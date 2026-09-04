"""Framing strategies for a stream-oriented Syslog transport."""

from __future__ import annotations

from abc import ABC, abstractmethod


class FrameTooLarge(ValueError):
    pass


class SyslogFramer(ABC):
    @abstractmethod
    def feed(self, data: bytes) -> list[bytes]:
        """Append bytes and return all complete frames."""

    @abstractmethod
    def finish(self) -> list[bytes]:
        """Return a final unterminated frame when the stream closes."""


class LineFramer(SyslogFramer):
    """Split TCP messages on LF while preserving a final unterminated frame."""

    def __init__(self, max_message_bytes: int) -> None:
        self.max_message_bytes = max(1, int(max_message_bytes))
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer.extend(data)
        frames: list[bytes] = []
        while b"\n" in self._buffer:
            frame, _, remainder = self._buffer.partition(b"\n")
            self._buffer[:] = remainder
            frame = frame.rstrip(b"\r")
            if len(frame) > self.max_message_bytes:
                raise FrameTooLarge("TCP Syslog frame exceeds the configured size limit")
            if frame.strip():
                frames.append(bytes(frame))
        if len(self._buffer) > self.max_message_bytes:
            raise FrameTooLarge("TCP Syslog frame exceeds the configured size limit")
        return frames

    def finish(self) -> list[bytes]:
        frame = bytes(self._buffer).rstrip(b"\r")
        self._buffer.clear()
        return [frame] if frame.strip() else []


__all__ = ["FrameTooLarge", "LineFramer", "SyslogFramer"]
