"""UI-level contract for the vendored qtpyTerminal external transport."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from qtpyTerminal import qtpyTerminal


class QtpyTerminalExternalAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.writes: list[bytes] = []
        self.console = qtpyTerminal(cols=80)
        self.console.attach_external(self.writes.append)

    def tearDown(self) -> None:
        self.console.stop()
        self.console.deleteLater()
        self.app.processEvents()

    def test_external_feed_renders_rows_and_tracks_remote_cursor(self) -> None:
        self.console.feed_external(
            "R1#\r\nshow clock\r\n12:00:00\r\nR1#"
        )

        self.assertEqual(
            self.console.term.toPlainText().splitlines()[:4],
            ["R1#", "show clock", "12:00:00", "R1#"],
        )
        cursor = self.console.term.textCursor()
        self.assertEqual((cursor.blockNumber(), cursor.positionInBlock()), (3, 3))

    def test_tab_and_navigation_are_written_to_external_transport(self) -> None:
        for key, text in (
            (Qt.Key.Key_Tab, "\t"),
            (Qt.Key.Key_Left, ""),
            (Qt.Key.Key_Right, ""),
        ):
            event = QKeyEvent(
                QEvent.Type.KeyPress,
                key,
                Qt.KeyboardModifier.NoModifier,
                text,
            )
            QApplication.sendEvent(self.console.term, event)

        self.assertEqual(self.writes, [b"\t", b"\x1b[D", b"\x1b[C"])

    def test_clear_recreates_external_screen_without_starting_local_process(self) -> None:
        self.console.feed_external("Router#")
        self.console.clear_external()

        self.assertEqual(self.console.term.toPlainText().strip(), "")
        self.assertIsNone(self.console.term.pid)
        self.assertEqual(
            type(self.console.term.backend).__name__,
            "_ExternalBackend",
        )


if __name__ == "__main__":
    unittest.main()
