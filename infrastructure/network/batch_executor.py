"""Bounded multi-host execution with isolated per-host results."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Any, Callable

HostWorker = Callable[[str], dict[str, Any]]
HostCallback = Callable[[str, str, str, int], None]
ProgressCallback = Callable[[int, int, int, int], None]


class BatchExecutor:
    def __init__(self, max_concurrent_hosts: int = 5) -> None:
        self.max_concurrent_hosts = min(20, max(1, int(max_concurrent_hosts)))

    def run(
        self,
        hosts: list[str],
        worker: HostWorker,
        *,
        cancel_event: threading.Event,
        on_host: HostCallback,
        on_progress: ProgressCallback,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        counters = {"completed": 0, "success": 0, "failed": 0}
        queued = list(hosts)

        def invoke(host: str) -> dict[str, Any]:
            if cancel_event.is_set():
                return {
                    "host": host, "ok": False, "severity": "cancelled",
                    "state": "cancelled", "message": "Cancelled before start.",
                }
            on_host(host, "running", f"Running operation for {host}.", 10)
            try:
                result = dict(worker(host) or {})
            except Exception as exc:
                result = {
                    "ok": False, "severity": "error",
                    "message": f"Operation failed for {host}: {exc}",
                }
            result["host"] = host
            result.setdefault("severity", "success" if result.get("ok") else "error")
            result.setdefault("message", f"Operation finished for {host}.")
            result["state"] = (
                "cancelled" if result["severity"] == "cancelled"
                else "success" if result.get("ok")
                else "error"
            )
            return result

        for host in queued:
            on_host(host, "queued", f"Queued {host}.", 0)
        on_progress(0, 0, 0, len(queued))

        with ThreadPoolExecutor(
            max_workers=self.max_concurrent_hosts,
            thread_name_prefix="device-batch",
        ) as pool:
            futures = {pool.submit(invoke, host): host for host in queued}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                state = str(result["state"])
                on_host(
                    str(result["host"]), state, str(result["message"]),
                    100 if state != "cancelled" else 0,
                )
                counters["completed"] += 1
                if result.get("ok"):
                    counters["success"] += 1
                elif state != "cancelled":
                    counters["failed"] += 1
                on_progress(
                    counters["completed"], counters["success"],
                    counters["failed"], len(queued),
                )
        order = {host: index for index, host in enumerate(queued)}
        return sorted(results, key=lambda item: order[str(item["host"])])
