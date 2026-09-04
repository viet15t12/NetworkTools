from __future__ import annotations

import threading
import time
import unittest

from features.devices.batch_service import DeviceBatchService


class MultiDeviceBatchTests(unittest.TestCase):
    def test_deduplicates_hosts_limits_concurrency_and_isolates_failure(self) -> None:
        service = DeviceBatchService(max_concurrent_hosts=2)
        batch_id = service.create_batch()
        lock = threading.Lock()
        active = 0
        maximum = 0

        def worker(host: str) -> dict:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            if host == "r2":
                raise RuntimeError("unreachable")
            return {"ok": True, "message": f"done {host}"}

        hosts = service.normalize_hosts(["r1", "r2", "r1", "r3", ""])
        payload = service.run(
            batch_id, "connect", hosts, worker,
            lambda *_args: None, lambda *_args: None,
        )

        self.assertEqual(hosts, ["r1", "r2", "r3"])
        self.assertLessEqual(maximum, 2)
        self.assertEqual(payload["success"], 2)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual([row["host"] for row in payload["results"]], hosts)


if __name__ == "__main__":
    unittest.main()
