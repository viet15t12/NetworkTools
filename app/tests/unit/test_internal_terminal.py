"""Focused tests for ANSI dirty rows and interactive channel ownership."""

from __future__ import annotations

import threading
import time
import unittest

import pyte
from PyQt6.QtCore import Qt

from features.terminal.manager import InternalTerminalManager
from features.terminal.stream import TerminalOutputNormalizer
from features.terminal.worker import TerminalStreamWorker
from qtpyTerminal.qtpyTerminal import Screen


class _InteractiveConnection:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.reads = ["Router#^@\nshow clock\x00\n12:00", ""]
        self.disable_lf_normalization = False
        self.config_mode = True
        self.buffer_cleared = False

    def write_channel(self, text: str) -> None:
        self.writes.append(text)

    def read_channel(self) -> str:
        return self.reads.pop(0) if self.reads else ""

    def check_enable_mode(self) -> bool:
        return True

    def check_config_mode(self) -> bool:
        return self.config_mode

    def exit_config_mode(self) -> None:
        self.config_mode = False

    def clear_buffer(self) -> None:
        self.buffer_cleared = True


class _Connector:
    def __init__(self) -> None:
        self.connection = _InteractiveConnection()


class _Registry:
    def __init__(self) -> None:
        self.connector = _Connector()
        self.ensure_open: bool | None = None

    def execute(self, _host, operation, *, ensure_open=True):
        self.ensure_open = ensure_open
        try:
            operation(self.connector)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}


class TerminalScreenTests(unittest.TestCase):
    def test_ansi_parser_reports_only_rows_changed_after_last_render(self) -> None:
        screen = Screen(lambda _data: None, 20, 5, 2000)
        stream = pyte.Stream(screen)
        self.assertEqual(set(screen.dirty), set(range(5)))
        screen.dirty.clear()

        stream.feed("\x1b[31mERROR\x1b[0m\r\nRouter#")
        self.assertEqual(set(screen.dirty), {0, 1})
        self.assertEqual(
            "".join(screen.buffer[0][column].data for column in range(5)),
            "ERROR",
        )
        self.assertEqual(screen.buffer[0][0].fg, "red")
        self.assertEqual(
            "".join(screen.buffer[1][column].data for column in range(7)),
            "Router#",
        )
        self.assertEqual((screen.cursor.y, screen.cursor.x), (1, 7))


class TerminalOutputNormalizerTests(unittest.TestCase):
    def test_restores_crlf_and_filters_split_cisco_nul_noise(self) -> None:
        normalizer = TerminalOutputNormalizer()

        first = normalizer.feed("line-one\nline-two\r")
        second = normalizer.feed("\nR1#^")
        third = normalizer.feed("@")

        self.assertEqual(first, "line-one\r\nline-two")
        self.assertEqual(second, "\r\nR1#")
        self.assertEqual(third, "")
        self.assertEqual(normalizer.flush(), "")


class TerminalManagerPreflightTests(unittest.TestCase):
    def test_dev_host_explains_how_to_enable_real_cli_without_opening_window(self) -> None:
        manager = InternalTerminalManager(
            object(),
            device_loader=lambda host: {
                "host": host,
                "method": "ssh",
                "dev": 1,
            },
        )

        result = manager.open("192.0.2.10")

        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertIn("Switch to Live Connection", result["message"])
        self.assertEqual(manager._terminals, {})


class TerminalStreamWorkerTests(unittest.TestCase):
    def test_worker_batches_input_through_registry_owned_channel(self) -> None:
        registry = _Registry()
        worker = TerminalStreamWorker("192.0.2.1", registry)
        outputs: list[str] = []
        worker.outputReady.connect(
            outputs.append,
            Qt.ConnectionType.DirectConnection,
        )
        worker.send("show ip int brief")
        worker.send("\r")

        thread = threading.Thread(target=worker.run)
        thread.start()
        deadline = time.monotonic() + 1.0
        while not outputs and time.monotonic() < deadline:
            time.sleep(0.005)
        worker.stop()
        thread.join(1.0)

        self.assertFalse(thread.is_alive())
        self.assertTrue(registry.ensure_open)
        self.assertTrue(registry.connector.connection.buffer_cleared)
        self.assertFalse(registry.connector.connection.config_mode)
        self.assertFalse(registry.connector.connection.disable_lf_normalization)
        self.assertEqual(
            registry.connector.connection.writes[:2],
            ["\r", "show ip int brief\r"],
        )
        self.assertEqual(outputs, ["Router#\r\nshow clock\r\n12:00"])


if __name__ == "__main__":
    unittest.main()
