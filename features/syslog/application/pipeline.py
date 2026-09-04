"""Atomic lifecycle for the Syslog receiver and writer."""

from __future__ import annotations

import threading
from collections.abc import Callable

from ..domain.models import ListenerConfig
from ..transport.receiver import SyslogReceiver
from .writer import SyslogWriter


ReceiverFactory = Callable[
    [ListenerConfig, Callable[[bytes, str, str], None], Callable[[str], None]],
    SyslogReceiver,
]


class SyslogPipeline:
    def __init__(
        self, writer: SyslogWriter, on_receiver_error: Callable[[str], None], *,
        receiver_factory: ReceiverFactory = SyslogReceiver,
    ) -> None:
        self.writer = writer
        self._on_receiver_error = on_receiver_error
        self._receiver_factory = receiver_factory
        self._receiver: SyslogReceiver | None = None
        self._lock = threading.RLock()

    @property
    def receiver(self) -> SyslogReceiver | None:
        with self._lock:
            return self._receiver

    def start(self, config: ListenerConfig) -> SyslogReceiver:
        with self._lock:
            if self._receiver is not None and self._receiver.is_running:
                return self._receiver
            if self._receiver is not None:
                self._receiver.stop(timeout=0.5)
                self._receiver = None
            self.writer.start()
            receiver = self._receiver_factory(config, self.writer.submit, self._on_receiver_error)
            try:
                receiver.start()
            except Exception:
                receiver.stop(timeout=0.5)
                self.writer.stop()
                raise
            self._receiver = receiver
            return receiver

    def stop(self, *, receiver_timeout: float = 3.0, writer_timeout: float = 5.0) -> None:
        with self._lock:
            receiver = self._receiver
            self._receiver = None
            if receiver is not None:
                receiver.stop(timeout=receiver_timeout)
            self.writer.stop(timeout=writer_timeout)


__all__ = ["SyslogPipeline"]
