from __future__ import annotations

import threading
import time
import unittest

from core.view_push_batch import ViewPushBatchService


class _Controller:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.maximum = 0
        self.apply_only_calls: list[tuple[str, str]] = []
        self.reconcile_calls: list[tuple[str, str]] = []

    def push(self, host: str, module: str) -> dict[str, object]:
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        time.sleep(0.02)
        with self.lock:
            self.active -= 1
        if host == "r2":
            return {"ok": False, "message": "r2 rejected configuration"}
        return {"ok": True, "message": f"{module} pushed to {host}"}

    def push_apply_only(self, host: str, module: str) -> dict[str, object]:
        self.apply_only_calls.append((host, module))
        result = self.push(host, module)
        if result.get("ok"):
            result["postPushPending"] = True
        return result

    def reconcile_after_push(self, host: str, module: str) -> dict[str, object]:
        self.reconcile_calls.append((host, module))
        return {
            "ok": host != "r3",
            "message": f"{module} synchronized for {host}",
            "reconciliation": {"ok": host != "r3", "snapshotUpdated": host != "r3"},
        }


class _Factory:
    def __init__(self, controller: _Controller) -> None:
        self.controller = controller

    def get(self, name: str) -> _Controller:
        if name != "routing":
            raise ValueError(name)
        return self.controller


class ViewPushBatchServiceTests(unittest.TestCase):
    def test_pushes_concurrently_and_isolates_host_failure(self) -> None:
        controller = _Controller()
        service = ViewPushBatchService(_Factory(controller), max_concurrent_hosts=2)
        final_hosts: list[str] = []

        result = service.run(
            "routing",
            "ospf",
            ["r1", "r2", "r1", "r3"],
            on_host=lambda host, state, *_: (
                final_hosts.append(host)
                if state in {"success", "error", "cancelled"}
                else None
            ),
            on_progress=lambda *_: None,
        )

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["success"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertTrue(result["partial"])
        self.assertGreater(controller.maximum, 1)
        self.assertLessEqual(controller.maximum, 2)
        self.assertCountEqual(final_hosts, ["r1", "r2", "r3"])
        self.assertCountEqual(
            controller.apply_only_calls,
            [("r1", "ospf"), ("r2", "ospf"), ("r3", "ospf")],
        )

    def test_reconciles_in_a_separate_bounded_pass(self) -> None:
        controller = _Controller()
        service = ViewPushBatchService(_Factory(controller), max_concurrent_hosts=2)

        result = service.reconcile(
            "routing",
            "ospf",
            ["r1", "r3"],
            on_host=lambda *_: None,
            on_progress=lambda *_: None,
        )

        self.assertEqual(result["success"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertTrue(result["partial"])
        self.assertCountEqual(
            controller.reconcile_calls, [("r1", "ospf"), ("r3", "ospf")]
        )

    def test_pushes_up_to_five_hosts_at_the_same_time(self) -> None:
        controller = _Controller()
        service = ViewPushBatchService(
            _Factory(controller), max_concurrent_hosts=99
        )

        result = service.run(
            "routing",
            "ospf",
            [f"r{index}" for index in range(1, 7)],
            on_host=lambda *_: None,
            on_progress=lambda *_: None,
        )

        self.assertEqual(result["total"], 6)
        self.assertEqual(controller.maximum, 5)

    def test_cancelled_batch_does_not_start_queued_hosts(self) -> None:
        controller = _Controller()
        service = ViewPushBatchService(_Factory(controller), max_concurrent_hosts=2)
        cancellation = threading.Event()
        cancellation.set()

        result = service.run(
            "routing",
            "eigrp",
            ["r1", "r2", "r3"],
            on_host=lambda *_: None,
            on_progress=lambda *_: None,
            cancel_event=cancellation,
        )

        self.assertEqual(result["cancelled"], 3)
        self.assertEqual(result["success"], 0)
        self.assertEqual(controller.maximum, 0)


if __name__ == "__main__":
    unittest.main()
