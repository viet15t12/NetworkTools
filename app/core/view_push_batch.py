"""Bounded orchestration for View & Push operations across many devices."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from infrastructure.network.batch_executor import BatchExecutor


HostCallback = Callable[[str, str, str, int], None]
ProgressCallback = Callable[[int, int, int, int], None]


class ViewPushBatchService:
    """Run one controller independently per host with bounded concurrency."""

    MAX_CONCURRENT_HOSTS = 5

    def __init__(self, controller_factory: Any, max_concurrent_hosts: int = 5) -> None:
        self._controllers = controller_factory
        concurrency = min(
            self.MAX_CONCURRENT_HOSTS,
            max(1, int(max_concurrent_hosts)),
        )
        self._executor = BatchExecutor(concurrency)
        self._lock = threading.RLock()
        self._active_cancellations: set[threading.Event] = set()

    def cancel_all(self) -> None:
        """Prevent queued hosts from starting during application shutdown."""
        with self._lock:
            events = tuple(self._active_cancellations)
        for event in events:
            event.set()

    @staticmethod
    def normalize_hosts(hosts: Any) -> list[str]:
        if hasattr(hosts, "toVariant"):
            hosts = hosts.toVariant()
        if not isinstance(hosts, (list, tuple)):
            return []
        return list(
            dict.fromkeys(
                str(host or "").strip()
                for host in hosts
                if str(host or "").strip()
            )
        )

    def run(
        self,
        controller_name: str,
        module_name: str,
        hosts: Any,
        *,
        on_host: HostCallback,
        on_progress: ProgressCallback,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        controller_key = str(controller_name or "").strip().lower()
        module = str(module_name or "all").strip().lower() or "all"
        targets = self.normalize_hosts(hosts)
        if not controller_key:
            return self._invalid("View & Push controller is required.")
        if not targets:
            return self._invalid("Select at least one target device.")

        # Resolve before starting threads so an unsupported controller fails as
        # one validation error rather than being repeated for every host.
        controller = self._controllers.get(controller_key)
        cancellation = cancel_event or threading.Event()
        with self._lock:
            self._active_cancellations.add(cancellation)
        try:
            results = self._executor.run(
                targets,
                lambda host: (
                    controller.push_apply_only(host, module)
                    if callable(getattr(controller, "push_apply_only", None))
                    else controller.push(host, module)
                ),
                cancel_event=cancellation,
                on_host=on_host,
                on_progress=on_progress,
            )
        finally:
            with self._lock:
                self._active_cancellations.discard(cancellation)
        succeeded = sum(1 for item in results if item.get("ok"))
        cancelled = sum(1 for item in results if item.get("state") == "cancelled")
        failed = len(results) - succeeded - cancelled
        return {
            "ok": failed == 0 and cancelled == 0,
            "partial": succeeded > 0 and (failed > 0 or cancelled > 0),
            "total": len(results),
            "success": succeeded,
            "failed": failed,
            "cancelled": cancelled,
            "results": results,
            "message": (
                f"Push completed: {succeeded} succeeded, {failed} failed"
                f"{f', {cancelled} cancelled' if cancelled else ''}."
            ),
        }

    def reconcile(
        self,
        controller_name: str,
        module_name: str,
        hosts: Any,
        *,
        on_host: HostCallback,
        on_progress: ProgressCallback,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        """Run deferred post-push show/save/synchronization per successful host."""
        controller_key = str(controller_name or "").strip().lower()
        module = str(module_name or "all").strip().lower() or "all"
        targets = self.normalize_hosts(hosts)
        if not controller_key or not targets:
            return self._invalid("No devices require background synchronization.")
        controller = self._controllers.get(controller_key)
        cancellation = cancel_event or threading.Event()
        with self._lock:
            self._active_cancellations.add(cancellation)
        try:
            results = self._executor.run(
                targets,
                lambda host: controller.reconcile_after_push(host, module),
                cancel_event=cancellation,
                on_host=on_host,
                on_progress=on_progress,
            )
        finally:
            with self._lock:
                self._active_cancellations.discard(cancellation)
        succeeded = sum(1 for item in results if item.get("ok"))
        cancelled = sum(1 for item in results if item.get("state") == "cancelled")
        failed = len(results) - succeeded - cancelled
        return {
            "ok": failed == 0 and cancelled == 0,
            "partial": succeeded > 0 and (failed > 0 or cancelled > 0),
            "total": len(results),
            "success": succeeded,
            "failed": failed,
            "cancelled": cancelled,
            "results": results,
            "message": (
                f"Background device synchronization completed: {succeeded} succeeded, "
                f"{failed} failed{f', {cancelled} cancelled' if cancelled else ''}."
            ),
        }

    @staticmethod
    def _invalid(message: str) -> dict[str, Any]:
        return {
            "ok": False,
            "partial": False,
            "total": 0,
            "success": 0,
            "failed": 0,
            "cancelled": 0,
            "results": [],
            "message": message,
        }
