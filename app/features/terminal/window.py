"""Independent app window embedding the adapted qtpyTerminal widget."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qtpyTerminal import qtpyTerminal


class InternalTerminalWindow(QMainWindow):
    """Host one callback-driven qtpyTerminal for a Netmiko session."""

    inputGenerated = pyqtSignal(str)
    closeRequested = pyqtSignal()
    reconnectRequested = pyqtSignal()

    def __init__(self, host: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.host = host
        self._pending_output: list[str] = []

        self.setWindowTitle(f"CAMS CLI — {host}")
        self.resize(980, 620)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        # qtpyTerminal-main is adapted with an external callback backend, so it
        # never forks a local shell for CAMS device sessions.
        self._terminal = qtpyTerminal(self, cols=120)
        self._terminal.set_bgcolor(QColor("#1e1e1e"))
        self._terminal.set_fgcolor(QColor("#cccccc"))
        font = QFont("Cascadia Mono")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)
        self._terminal.term.setFont(font)
        self._terminal.attach_external(self._forward_input)

        self._status = QLabel(f"Connecting to {host}…")
        self._status.setStyleSheet("color: #dcdcaa;")
        reconnect = QPushButton("Reconnect")
        reconnect.clicked.connect(self.reconnectRequested)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear_screen)
        copy = QPushButton("Copy selection")
        copy.clicked.connect(self._terminal.term.copy)

        controls = QHBoxLayout()
        controls.addWidget(self._status, 1)
        controls.addWidget(copy)
        controls.addWidget(clear)
        controls.addWidget(reconnect)
        body = QVBoxLayout()
        body.setContentsMargins(8, 8, 8, 8)
        body.addLayout(controls)
        body.addWidget(self._terminal, 1)
        container = QWidget(self)
        container.setLayout(body)
        self.setCentralWidget(container)

        # Keep socket and paint rates independent: one VT update per short frame.
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(20)
        self._render_timer.timeout.connect(self._flush_output)
        self._render_timer.start()

    @property
    def terminal_widget(self) -> qtpyTerminal:
        """Expose the embedded widget for focused UI tests and diagnostics."""
        return self._terminal

    def enqueue_output(self, text: str) -> None:
        """Queue normalized channel output for the next render batch."""
        if text:
            self._pending_output.append(str(text))

    def set_connection_state(self, state: str, message: str) -> None:
        """Display worker state without mixing it into device output."""
        colors = {
            "connecting": "#dcdcaa",
            "connected": "#23d18b",
            "warning": "#dcdcaa",
            "error": "#f14c4c",
            "closed": "#9d9d9d",
        }
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {colors.get(state, '#cccccc')};")
        if state == "connected":
            self._terminal.term.setFocus(Qt.FocusReason.OtherFocusReason)

    def clear_screen(self) -> None:
        """Clear queued data, VT viewport and qtpyTerminal scrollback."""
        self._pending_output.clear()
        self._terminal.clear_external()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.closeRequested.emit()
        event.accept()

    def _forward_input(self, data: bytes) -> None:
        self.inputGenerated.emit(bytes(data).decode("utf-8", errors="replace"))

    def _flush_output(self) -> None:
        if not self._pending_output:
            return
        text = "".join(self._pending_output)
        self._pending_output.clear()
        self._terminal.feed_external(text)
