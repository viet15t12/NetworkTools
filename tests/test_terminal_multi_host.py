"""Tests for concurrent multi-host connection task admission."""

from __future__ import annotations

import unittest

from core.terminal import TerminalHelper


class _TerminalAdmissionFake:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def connectHostAndSyncAsync(self, host: str) -> bool:
        self.seen.append(host)
        return host != "r2"


class _Signal:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def emit(self, *args) -> None:
        self.calls.append(args)


class _BatchService:
    @staticmethod
    def normalize_hosts(hosts):
        return list(hosts)

    @staticmethod
    def create_batch():
        return "batch-1"

    @staticmethod
    def run(_batch_id, _operation, hosts, _worker, on_host, on_progress):
        on_host(hosts[0], "running", "collecting", 10)
        on_host(hosts[0], "success", "committed", 100)
        on_progress(1, 1, 0, 1)
        return {"ok": True, "results": [{"host": hosts[0], "ok": True}]}


class _BatchTerminalFake:
    def __init__(self) -> None:
        self._batch_service = _BatchService()
        self.batchStarted = _Signal()
        self.hostOperationChanged = _Signal()
        self.runningConfigFinished = _Signal()
        self.batchProgress = _Signal()

    def saveRunningConfigBackup(self, _host):
        return {"ok": True}

    def connectHostAndSync(self, _host):
        return {"ok": True}

    def closeDeviceSession(self, _host):
        return {"ok": True}

    def _start_background_task(
        self, _task_key, _kind, _host, _message, callback, _metadata
    ):
        callback(lambda _message: None)
        return True


class TerminalMultiHostTests(unittest.TestCase):
    def test_batch_deduplicates_hosts_and_reports_per_host_admission(self) -> None:
        helper = _TerminalAdmissionFake()
        result = TerminalHelper.connectHostsAndSyncAsync(
            helper, ["r1", "r2", "r1", "", "  "]
        )
        self.assertEqual(helper.seen, ["r1", "r2"])
        self.assertEqual(result["accepted"], ["r1"])
        self.assertEqual(result["rejected"], ["r2"])
        self.assertFalse(result["ok"])

    def test_running_config_batch_publishes_each_committed_host(self) -> None:
        helper = _BatchTerminalFake()

        batch_id = TerminalHelper._start_device_batch(
            helper, "running-config", ["r1"]
        )

        self.assertEqual(batch_id, "batch-1")
        self.assertEqual(
            helper.runningConfigFinished.calls,
            [("r1", True, "committed")],
        )
        self.assertEqual(
            helper.hostOperationChanged.calls[-1],
            ("batch-1", "r1", "success", "committed", 100),
        )


if __name__ == "__main__":
    unittest.main()
