"""Bounded queue and batch writer for processed Syslog events."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol

from ..domain.models import SyslogMessage
from .processor import SyslogProcessor


class MessageStore(Protocol):
    def insert_messages(self, messages: list[SyslogMessage]) -> list[dict[str, Any]]: ...
    def resolve_device_host(self, source_ip: str) -> str | None: ...


class SyslogWriter:
    def __init__(
        self,
        repository: MessageStore,
        on_inserted: Callable[[list[dict[str, Any]]], None],
        on_error: Callable[[str], None],
        max_queue: int = 10_000,
        *,
        processor: SyslogProcessor | None = None,
        batch_size: int = 100,
        flush_interval: float = 0.1,
    ) -> None:
        self.repository = repository
        self.on_inserted = on_inserted
        self.on_error = on_error
        self.queue: queue.Queue[tuple[bytes, str, str]] = queue.Queue(maxsize=max_queue)
        self.batch_size = max(1, int(batch_size))
        self.flush_interval = max(0.01, float(flush_interval))
        self._dropped = 0
        self._metrics_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.processor = processor or SyslogProcessor(repository)

    @property
    def dropped(self) -> int:
        with self._metrics_lock:
            return self._dropped

    def _add_dropped(self, count: int = 1) -> None:
        with self._metrics_lock:
            self._dropped += max(0, int(count))

    def set_repository(self, repository: MessageStore) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Stop the Syslog writer before changing its repository")
        self.repository = repository
        self.processor.set_repository(repository)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="syslog-writer", daemon=True)
        self._thread.start()

    def submit(self, data: bytes, source_ip: str, protocol: str) -> None:
        try:
            self.queue.put_nowait((data, source_ip, protocol))
        except queue.Full:
            self._add_dropped()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout)

    def _run(self) -> None:
        batch: list[SyslogMessage] = []
        deadline = time.monotonic() + self.flush_interval
        while not self._stop.is_set() or not self.queue.empty() or batch:
            timeout = max(0.0, deadline - time.monotonic()) if batch else self.flush_interval
            try:
                event = self.queue.get(timeout=min(timeout, self.flush_interval))
            except queue.Empty:
                event = None
            if event is not None:
                try:
                    batch.append(self.processor.process(*event))
                except Exception as exc:
                    self._add_dropped()
                    self.on_error(f"Could not process a syslog message: {exc}")
            if len(batch) >= self.batch_size or (batch and time.monotonic() >= deadline):
                self._flush(batch)
                batch = []
                deadline = time.monotonic() + self.flush_interval

    def _flush(self, batch: list[SyslogMessage]) -> None:
        try:
            inserted = self.repository.insert_messages(batch)
        except Exception as exc:
            self._add_dropped(len(batch))
            self.on_error(f"Could not store syslog messages: {exc}")
            return
        try:
            self.on_inserted(inserted)
        except Exception as exc:
            self.on_error(f"Could not publish stored syslog messages: {exc}")


__all__ = ["SyslogWriter"]
