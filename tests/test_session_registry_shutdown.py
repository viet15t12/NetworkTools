from __future__ import annotations

import threading
import time
import unittest

from infrastructure.network.session_registry import DeviceSessionRegistry


class _SlowConnector:
    connected = True

    def __init__(self) -> None:
        self.started = threading.Event()

    def disconnect(self) -> None:
        self.started.set()
        time.sleep(1.0)


class SessionRegistryShutdownTests(unittest.TestCase):
    def test_close_all_uses_one_bounded_parallel_deadline(self) -> None:
        registry = DeviceSessionRegistry(lambda _host: None)
        connectors = [_SlowConnector(), _SlowConnector()]
        registry._sessions = {str(index): connector for index, connector in enumerate(connectors)}

        started = time.monotonic()
        registry.close_all(timeout=0.05)
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.25)
        self.assertTrue(all(connector.started.is_set() for connector in connectors))
        self.assertEqual(registry._sessions, {})


if __name__ == "__main__":
    unittest.main()
