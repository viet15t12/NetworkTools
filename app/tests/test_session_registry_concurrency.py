from __future__ import annotations

import threading
import time
import unittest

from infrastructure.network.session_registry import DeviceSessionRegistry


class _Connection:
    def __init__(self) -> None:
        self.in_config_mode = False
        self.exit_calls = 0

    def is_alive(self) -> bool:
        return True

    def check_enable_mode(self) -> bool:
        return True

    def check_config_mode(self) -> bool:
        return self.in_config_mode

    def exit_config_mode(self) -> None:
        self.exit_calls += 1
        self.in_config_mode = False


class _Connector:
    def __init__(self) -> None:
        self.connected = False
        self.connection = _Connection()

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False


class SessionRegistryConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = DeviceSessionRegistry(
            lambda host: {
                "host": host, "method": "ssh", "port": 22,
                "username": "user", "password": "secret",
                "device_type": "cisco_ios", "dev": 0,
            },
            connector_factory=lambda _device: _Connector(),
        )

    def test_same_host_operations_are_serialized(self) -> None:
        active = 0
        maximum = 0
        lock = threading.Lock()

        def operation(_connector) -> None:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.025)
            with lock:
                active -= 1

        workers = [
            threading.Thread(target=lambda: self.registry.execute("r1", operation))
            for _ in range(3)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(maximum, 1)
        self.assertTrue(self.registry.has_session("r1"))

    def test_different_hosts_can_overlap_and_keep_sessions(self) -> None:
        barrier = threading.Barrier(2)
        completed: list[str] = []

        def run(host: str) -> None:
            result = self.registry.execute(host, lambda _connector: barrier.wait(timeout=1))
            if result["ok"]:
                completed.append(host)

        workers = [threading.Thread(target=run, args=(host,)) for host in ("r1", "r2")]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertCountEqual(completed, ["r1", "r2"])
        self.assertTrue(self.registry.has_session("r1"))
        self.assertTrue(self.registry.has_session("r2"))

    def test_bounded_wait_returns_busy_instead_of_blocking_forever(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def hold_session(_connector) -> None:
            entered.set()
            release.wait(timeout=1)

        worker = threading.Thread(
            target=lambda: self.registry.execute("r1", hold_session)
        )
        worker.start()
        self.assertTrue(entered.wait(timeout=1))

        started = time.monotonic()
        result = self.registry.execute(
            "r1",
            lambda _connector: self.fail("busy operation must not run"),
            lock_timeout=0.01,
        )
        elapsed = time.monotonic() - started
        release.set()
        worker.join(timeout=1)

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "session_busy")
        self.assertLess(elapsed, 0.2)

    def test_dev_host_is_rejected_before_connector_or_operation_is_used(self) -> None:
        factory_called = False
        operation_called = False

        def factory(_device):
            nonlocal factory_called
            factory_called = True
            return _Connector()

        registry = DeviceSessionRegistry(
            lambda host: {
                "host": host,
                "method": "ssh",
                "port": 22,
                "username": "user",
                "password": "secret",
                "device_type": "cisco_ios",
                "dev": 1,
            },
            connector_factory=factory,
        )

        def operation(_connector):
            nonlocal operation_called
            operation_called = True

        result = registry.execute("dev-r1", operation)

        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertIn("Switch to Live Connection", result["message"])
        self.assertFalse(factory_called)
        self.assertFalse(operation_called)

    def test_each_operation_normalizes_a_reused_config_prompt(self) -> None:
        first = self.registry.execute(
            "r1",
            lambda connector: setattr(connector.connection, "in_config_mode", True),
        )

        observed = self.registry.execute(
            "r1",
            lambda connector: connector.connection.check_config_mode(),
        )

        self.assertTrue(first["ok"])
        self.assertTrue(observed["ok"])
        self.assertFalse(observed["value"])
        connector = self.registry.get_connector("r1")
        self.assertEqual(connector.connection.exit_calls, 1)

    def test_unbounded_close_waits_for_every_disconnect(self) -> None:
        release = threading.Event()
        disconnected = threading.Event()

        class SlowConnector(_Connector):
            def disconnect(self) -> None:
                release.wait(timeout=1)
                super().disconnect()
                disconnected.set()

        registry = DeviceSessionRegistry(
            lambda host: {
                "host": host, "method": "ssh", "port": 22,
                "username": "user", "password": "secret",
                "device_type": "cisco_ios", "dev": 0,
            },
            connector_factory=lambda _device: SlowConnector(),
        )
        self.assertTrue(registry.open("r1")["ok"])
        closer = threading.Thread(target=lambda: registry.close_all(timeout=None))
        closer.start()
        time.sleep(0.02)
        self.assertTrue(closer.is_alive())
        release.set()
        closer.join(timeout=1)

        self.assertFalse(closer.is_alive())
        self.assertTrue(disconnected.is_set())


if __name__ == "__main__":
    unittest.main()
