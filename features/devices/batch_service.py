"""Batch orchestration independent from QML and Qt."""

from __future__ import annotations

import threading
from typing import Any, Callable
from uuid import uuid4

from infrastructure.network.batch_executor import BatchExecutor


class DeviceBatchService:
    def __init__(self, max_concurrent_hosts: int = 5) -> None:
        self._executor = BatchExecutor(max_concurrent_hosts)
        self._lock = threading.RLock()
        self._cancellations: dict[str, threading.Event] = {}

    @staticmethod
    def normalize_hosts(hosts: Any) -> list[str]:
        if hasattr(hosts, "toVariant"):
            hosts = hosts.toVariant()
        if not isinstance(hosts, (list, tuple)):
            return []
        return list(dict.fromkeys(
            str(host or "").strip() for host in hosts if str(host or "").strip()
        ))

    def create_batch(self) -> str:
        batch_id = uuid4().hex
        with self._lock:
            self._cancellations[batch_id] = threading.Event()
        return batch_id

    def cancel(self, batch_id: str) -> bool:
        with self._lock:
            event = self._cancellations.get(batch_id)
        if event is None:
            return False
        event.set()
        return True

    def run(
        self,
        batch_id: str,
        operation: str,
        hosts: list[str],
        worker: Callable[[str], dict[str, Any]],
        on_host: Callable[[str, str, str, int], None],
        on_progress: Callable[[int, int, int, int], None],
    ) -> dict[str, Any]:
        with self._lock:
            event = self._cancellations.setdefault(batch_id, threading.Event())
        try:
            results = self._executor.run(
                hosts, worker, cancel_event=event,
                on_host=on_host, on_progress=on_progress,
            )
        finally:
            with self._lock:
                self._cancellations.pop(batch_id, None)
        success = sum(1 for item in results if item.get("ok"))
        cancelled = sum(1 for item in results if item.get("state") == "cancelled")
        failed = len(results) - success - cancelled
        warnings = sum(1 for item in results if item.get("severity") == "warning")
        return {
            "batchId": batch_id, "operation": operation, "total": len(hosts),
            "success": success, "warning": warnings, "failed": failed,
            "cancelled": cancelled, "results": results,
        }
