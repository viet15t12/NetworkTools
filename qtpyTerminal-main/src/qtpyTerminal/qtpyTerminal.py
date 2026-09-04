"""
qtpyTerminal is a Qt widget that runs a Bash shell.

qtpyTerminal VT100 emulation is powered by Pyte,
(https://github.com/selectel/pyte).

Windows support uses pywinpty (pip install pywinpty).
Unix support uses pty (built-in).
"""

import collections
import functools
import html
import os
import signal
import sys

import pyte
from pyte.screens import History
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Property as pyqtProperty
from qtpy.QtCore import QSize, Qt, QTimer
from qtpy.QtCore import Signal as pyqtSignal, Slot as pyqtSlot
from qtpy.QtGui import (
    QClipboard,
    QColor,
    QFont,
    QPalette,
    QTextCharFormat,
    QTextCursor,
)
from qtpy.QtWidgets import QApplication, QHBoxLayout, QScrollBar, QSizePolicy

IS_WINDOWS = sys.platform == "win32"

try:
    import fcntl
    import pty
    from qtpy.QtCore import QSocketNotifier

    _HAVE_PTY = True
except ImportError:
    _HAVE_PTY = False

if not _HAVE_PTY:
    import threading
    from winpty import PtyProcess  # pip install pywinpty  (imports as 'winpty')


def SafeSlot(*slot_args, **slot_kwargs):  # pylint: disable=invalid-name
    """Function with args, acting like a decorator, to display errors instead of raising an exception"""

    def error_managed(method):
        @pyqtSlot(*slot_args, **slot_kwargs)
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except Exception:
                sys.excepthook(*sys.exc_info())

        return wrapper

    return error_managed


ansi_colors = {
    "black": "#000000",
    "red": "#CD0000",
    "green": "#00CD00",
    "brown": "#996633",  # Brown, replacing the yellow
    "blue": "#0000EE",
    "magenta": "#CD00CD",
    "cyan": "#00CDCD",
    "white": "#E5E5E5",
    "brightblack": "#7F7F7F",
    "brightred": "#FF0000",
    "brightgreen": "#00FF00",
    "brightyellow": "#FFFF00",
    "brightblue": "#5C5CFF",
    "brightmagenta": "#FF00FF",
    "brightcyan": "#00FFFF",
    "brightwhite": "#FFFFFF",
}

control_keys_mapping = {
    QtCore.Qt.Key_A: b"\x01",  # Ctrl-A
    QtCore.Qt.Key_B: b"\x02",  # Ctrl-B
    QtCore.Qt.Key_C: b"\x03",  # Ctrl-C
    QtCore.Qt.Key_D: b"\x04",  # Ctrl-D
    QtCore.Qt.Key_E: b"\x05",  # Ctrl-E
    QtCore.Qt.Key_F: b"\x06",  # Ctrl-F
    QtCore.Qt.Key_G: b"\x07",  # Ctrl-G (Bell)
    QtCore.Qt.Key_H: b"\x08",  # Ctrl-H (Backspace)
    QtCore.Qt.Key_I: b"\x09",  # Ctrl-I (Tab)
    QtCore.Qt.Key_J: b"\x0a",  # Ctrl-J (Line Feed)
    QtCore.Qt.Key_K: b"\x0b",  # Ctrl-K (Vertical Tab)
    QtCore.Qt.Key_L: b"\x0c",  # Ctrl-L (Form Feed)
    QtCore.Qt.Key_M: b"\x0d",  # Ctrl-M (Carriage Return)
    QtCore.Qt.Key_N: b"\x0e",  # Ctrl-N
    QtCore.Qt.Key_O: b"\x0f",  # Ctrl-O
    QtCore.Qt.Key_P: b"\x10",  # Ctrl-P
    QtCore.Qt.Key_Q: b"\x11",  # Ctrl-Q
    QtCore.Qt.Key_R: b"\x12",  # Ctrl-R
    QtCore.Qt.Key_S: b"\x13",  # Ctrl-S
    QtCore.Qt.Key_T: b"\x14",  # Ctrl-T
    QtCore.Qt.Key_U: b"\x15",  # Ctrl-U
    QtCore.Qt.Key_V: b"\x16",  # Ctrl-V
    QtCore.Qt.Key_W: b"\x17",  # Ctrl-W
    QtCore.Qt.Key_X: b"\x18",  # Ctrl-X
    QtCore.Qt.Key_Y: b"\x19",  # Ctrl-Y
    QtCore.Qt.Key_Z: b"\x1a",  # Ctrl-Z
    QtCore.Qt.Key_Escape: b"\x1b",  # Ctrl-Escape
    QtCore.Qt.Key_Backslash: b"\x1c",  # Ctrl-\
    QtCore.Qt.Key_Underscore: b"\x1f",  # Ctrl-_
}

normal_keys_mapping_unix = {
    QtCore.Qt.Key_Return: b"\r",
    QtCore.Qt.Key_Space: b" ",
    QtCore.Qt.Key_Enter: b"\r",
    QtCore.Qt.Key_Tab: b"\t",
    QtCore.Qt.Key_Backspace: b"\x7f",
    QtCore.Qt.Key_Delete: b"\x1b[3~",
    QtCore.Qt.Key_Home: b"\x1b[H",
    QtCore.Qt.Key_End: b"\x1b[F",
    QtCore.Qt.Key_Left: b"\x1b[D",
    QtCore.Qt.Key_Up: b"\x1b[A",
    QtCore.Qt.Key_Right: b"\x1b[C",
    QtCore.Qt.Key_Down: b"\x1b[B",
    QtCore.Qt.Key_PageUp: b"\x1b[5~",
    QtCore.Qt.Key_PageDown: b"\x1b[6~",
    QtCore.Qt.Key_F1: b"\x1bOP",
    QtCore.Qt.Key_F2: b"\x1bOQ",
    QtCore.Qt.Key_F3: b"\x1bOR",
    QtCore.Qt.Key_F4: b"\x1bOS",
    QtCore.Qt.Key_F5: b"\x1b[15~",
    QtCore.Qt.Key_F6: b"\x1b[17~",
    QtCore.Qt.Key_F7: b"\x1b[18~",
    QtCore.Qt.Key_F8: b"\x1b[19~",
    QtCore.Qt.Key_F9: b"\x1b[20~",
    QtCore.Qt.Key_F10: b"\x1b[21~",
    QtCore.Qt.Key_F11: b"\x1b[23~",
    QtCore.Qt.Key_F12: b"\x1b[24~",
}

# Windows cmd.exe / ConPTY expects CR for Enter, standard VT sequences for navigation
normal_keys_mapping_windows = {
    QtCore.Qt.Key_Return: b"\r",
    QtCore.Qt.Key_Space: b" ",
    QtCore.Qt.Key_Enter: b"\r",
    QtCore.Qt.Key_Tab: b"\t",
    QtCore.Qt.Key_Backspace: b"\x08",
    QtCore.Qt.Key_Delete: b"\x1b[3~",
    QtCore.Qt.Key_Home: b"\x1b[H",
    QtCore.Qt.Key_End: b"\x1b[F",
    QtCore.Qt.Key_Left: b"\x1b[D",
    QtCore.Qt.Key_Up: b"\x1b[A",
    QtCore.Qt.Key_Right: b"\x1b[C",
    QtCore.Qt.Key_Down: b"\x1b[B",
    QtCore.Qt.Key_PageUp: b"\x1b[5~",
    QtCore.Qt.Key_PageDown: b"\x1b[6~",
    QtCore.Qt.Key_F1: b"\x1bOP",
    QtCore.Qt.Key_F2: b"\x1bOQ",
    QtCore.Qt.Key_F3: b"\x1bOR",
    QtCore.Qt.Key_F4: b"\x1bOS",
    QtCore.Qt.Key_F5: b"\x1b[15~",
    QtCore.Qt.Key_F6: b"\x1b[17~",
    QtCore.Qt.Key_F7: b"\x1b[18~",
    QtCore.Qt.Key_F8: b"\x1b[19~",
    QtCore.Qt.Key_F9: b"\x1b[20~",
    QtCore.Qt.Key_F10: b"\x1b[21~",
    QtCore.Qt.Key_F11: b"\x1b[23~",
    QtCore.Qt.Key_F12: b"\x1b[24~",
}


def QtKeyToAscii(event):
    """
    Convert the Qt key event to the corresponding ASCII sequence for
    the terminal. This works fine for standard alphanumerical characters, but
    most other characters require terminal specific control sequences.
    """
    normal_keys_mapping = normal_keys_mapping_unix if _HAVE_PTY else normal_keys_mapping_windows

    if sys.platform == "darwin":
        # special case for MacOS
        # /!\ Qt maps ControlModifier to CMD
        # CMD-C, CMD-V for copy/paste
        # CTRL-C and other modifiers -> key mapping
        if event.modifiers() == QtCore.Qt.MetaModifier:
            if event.key() == Qt.Key_Backspace:
                return control_keys_mapping.get(Qt.Key_W)
            return control_keys_mapping.get(event.key())
        elif event.modifiers() == QtCore.Qt.ControlModifier:
            if event.key() == Qt.Key_C:
                # copy
                return "copy"
            elif event.key() == Qt.Key_V:
                # paste
                return "paste"
            return None
        else:
            return normal_keys_mapping.get(event.key(), event.text().encode("utf8"))
    modifiers = event.modifiers()
    if (
        modifiers
        == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier)
        and event.key() == Qt.Key_C
    ):
        return "copy"
    if (
        modifiers
        == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier)
        and event.key() == Qt.Key_V
    ):
        return "paste"
    if modifiers == QtCore.Qt.ControlModifier:
        return control_keys_mapping.get(event.key())
    else:
        return normal_keys_mapping.get(event.key(), event.text().encode("utf8"))


class Screen(pyte.HistoryScreen):
    def __init__(self, write_fn, cols, rows, historyLength):
        """
        Args:
            write_fn: callable(data: str) used to respond to CPR/device requests.
        """
        super().__init__(cols, rows, historyLength, ratio=1 / rows)
        self._write_fn = write_fn

    def write_process_input(self, data):
        """Response to CPR request (for example)."""
        try:
            self._write_fn(data.encode("utf-8"))
        except (IOError, OSError):
            pass

    def resize(self, lines, columns):
        lines = lines or self.lines
        columns = columns or self.columns

        if lines == self.lines and columns == self.columns:
            return  # No changes.

        self.dirty.clear()
        self.dirty.update(range(lines))

        self.save_cursor()
        if lines < self.lines:
            if lines <= self.cursor.y:
                nlines_to_move_up = self.lines - lines
                for i in range(nlines_to_move_up):
                    line = self.buffer[i]
                    self.history.top.append(line)
                self.cursor_position(0, 0)
                self.delete_lines(nlines_to_move_up)
                self.restore_cursor()
                self.cursor.y -= nlines_to_move_up
        else:
            self.restore_cursor()

        self.lines, self.columns = lines, columns
        self.history = History(
            self.history.top,
            self.history.bottom,
            1 / self.lines,
            self.history.size,
            self.history.position,
        )
        self.set_margins()


# ---------------------------------------------------------------------------
# Platform-specific backends
# ---------------------------------------------------------------------------

if _HAVE_PTY:

    class _UnixBackend(QtCore.QObject):
        """Backend for Unix/macOS using pty + QSocketNotifier."""

        dataReady = pyqtSignal(object)
        processExited = pyqtSignal()

        def __init__(self, fd, cols, rows):
            super().__init__()
            self.fd = fd
            self.screen = Screen(lambda data: os.write(fd, data), cols, rows, 10000)
            self.stream = pyte.ByteStream()
            self.stream.attach(self.screen)

            self.notifier = QSocketNotifier(fd, QSocketNotifier.Read)
            self.notifier.activated.connect(self._fd_readable)

        def _fd_readable(self):
            try:
                out = os.read(self.fd, 2**16)
            except OSError:
                self.processExited.emit()
                self.notifier.setEnabled(False)
                return
            self.stream.feed(out)
            self.dataReady.emit(self.screen)

        def write(self, data: bytes):
            os.write(self.fd, data)

        def resize(self, rows, cols):
            self.screen.resize(rows, cols)

        def close(self):
            self.notifier.setEnabled(False)


class _WindowsBackend(QtCore.QObject):
    """Backend for Windows using pywinpty.

    pywinpty exposes a WinPTY/ConPTY handle.  Since Windows has no
    select()-able file descriptor for the PTY output pipe, we read from a
    background thread and post the data back to the Qt main thread via a
    queued signal.
    """

    dataReady = pyqtSignal(object)
    processExited = pyqtSignal()

    def __init__(self, pty_process, cols, rows):
        super().__init__()
        self._pty = pty_process  # winpty.PtyProcess instance

        self.screen = Screen(self._write_raw, cols, rows, 10000)
        self.stream = pyte.ByteStream()
        self.stream.attach(self.screen)

        self._running = True
        self._thread = threading.Thread(target=self._reader_thread, daemon=True)
        self._thread.start()

    def _write_raw(self, data: bytes):
        try:
            self._pty.write(data.decode("utf-8", errors="replace"))
        except Exception:
            pass

    def _reader_thread(self):
        """Run in background thread: read PTY output and emit signal."""
        while self._running:
            try:
                # winpty returns str; encode back to bytes for pyte
                chunk = self._pty.read(65536)
                if chunk:
                    self._on_data(chunk.encode("utf-8", errors="replace"))
                elif not self._pty.isalive():
                    self.processExited.emit()
                    break
            except Exception:
                self.processExited.emit()
                break

    def _on_data(self, data: bytes):
        """Called from background thread — post to main thread via signal."""
        # We need to feed pyte and emit from the main thread.
        # Use a QTimer with 0 delay to bounce back to the Qt event loop.
        QtCore.QMetaObject.invokeMethod(
            self, "_process_data", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(object, data)
        )

    @pyqtSlot(object)
    def _process_data(self, data: bytes):
        self.stream.feed(data)
        self.dataReady.emit(self.screen)

    def write(self, data: bytes):
        try:
            self._pty.write(data.decode("utf-8", errors="replace"))
        except Exception:
            pass

    def resize(self, rows, cols):
        self.screen.resize(rows, cols)
        try:
            self._pty.setwinsize(rows, cols)
        except Exception:
            pass

    def close(self):
        self._running = False
        try:
            self._pty.close()
        except Exception:
            pass


class _ExternalBackend(QtCore.QObject):
    """VT screen backed by callbacks instead of a local PTY process."""

    dataReady = pyqtSignal(object)

    def __init__(self, write_fn, cols, rows):
        super().__init__()
        self._write_fn = write_fn
        self.screen = Screen(self.write, cols, rows, 10000)
        self.stream = pyte.Stream(self.screen)

    def feed(self, data):
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        self.stream.feed(str(data or ""))
        self.dataReady.emit(self.screen)

    def write(self, data: bytes):
        self._write_fn(bytes(data))

    def resize(self, rows, cols):
        self.screen.resize(rows, cols)
        self.dataReady.emit(self.screen)

    def reset(self):
        cols, rows = self.screen.columns, self.screen.lines
        self.screen = Screen(self.write, cols, rows, 10000)
        self.stream = pyte.Stream(self.screen)
        self.dataReady.emit(self.screen)

    def close(self):
        return None


# ---------------------------------------------------------------------------
# Public container widget
# ---------------------------------------------------------------------------


class qtpyTerminal(QtWidgets.QWidget):
    """Container widget for the terminal text area."""

    def __init__(self, parent=None, cols=132):
        super().__init__(parent)

        self.term = _TerminalWidget(self, cols, rows=25)
        self.scroll_bar = QScrollBar(Qt.Vertical, self)
        layout = QHBoxLayout(self)
        layout.addWidget(self.term)
        layout.addWidget(self.scroll_bar)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.MinimumExpanding)

        pal = QPalette()
        self.set_bgcolor(pal.window().color())
        self.set_fgcolor(pal.windowText().color())
        self.term.set_scroll_bar(self.scroll_bar)
        self.set_cmd("")  # will execute the default shell

    def minimumSizeHint(self):
        size = self.term.sizeHint()
        size.setWidth(size.width() + self.scroll_bar.width())
        return size

    def sizeHint(self):
        return self.minimumSizeHint()

    def get_rows(self):
        return self.term.rows

    def set_rows(self, rows):
        self.term.rows = rows
        self.adjustSize()
        self.updateGeometry()

    def get_cols(self):
        return self.term.cols

    def set_cols(self, cols):
        self.term.cols = cols
        self.adjustSize()
        self.updateGeometry()

    def get_bgcolor(self):
        return QColor.fromString(self.term.bg_color)

    def set_bgcolor(self, color):
        self.term.bg_color = color.name(QColor.HexRgb)

    def get_fgcolor(self):
        return QColor.fromString(self.term.fg_color)

    def set_fgcolor(self, color):
        self.term.fg_color = color.name(QColor.HexRgb)

    def get_cmd(self):
        return self.term._cmd

    def set_cmd(self, cmd):
        if not cmd:
            if _HAVE_PTY:
                cmd = os.environ.get("SHELL", "/bin/sh")
            else:
                cmd = os.environ.get("COMSPEC", "cmd.exe")
        self.term._cmd = cmd
        if self.term.backend is None:
            self.term.clear()
            self.term.appendHtml(f"<h2>qtpyTerminal - {repr(cmd)}</h2>")

    @SafeSlot(bool)
    def start(self, deactivate_ctrl_d=True):
        self.term.start(deactivate_ctrl_d=deactivate_ctrl_d)

    @SafeSlot()
    def stop(self):
        self.term.stop()

    @SafeSlot(str)
    def push(self, text):
        """Push some text to the terminal"""
        return self.term.push(text)

    def attach_external(self, write_fn):
        """Attach a callback-driven transport such as a Netmiko channel."""
        self.term.attach_external(write_fn)

    def feed_external(self, data):
        """Feed device output into the callback-driven VT screen."""
        self.term.feed_external(data)

    def clear_external(self):
        """Reset the external VT screen and its scrollback."""
        self.term.clear_external()

    cols = pyqtProperty(int, get_cols, set_cols)
    rows = pyqtProperty(int, get_rows, set_rows)
    bgcolor = pyqtProperty(QColor, get_bgcolor, set_bgcolor)
    fgcolor = pyqtProperty(QColor, get_fgcolor, set_fgcolor)
    cmd = pyqtProperty(str, get_cmd, set_cmd)


# ---------------------------------------------------------------------------
# Internal terminal widget
# ---------------------------------------------------------------------------


class _TerminalWidget(QtWidgets.QPlainTextEdit):
    """Start the platform backend and render Pyte output as text."""

    def __init__(self, parent, cols=125, rows=50, **kwargs):
        self.fd = None  # Unix fd  (or truthy sentinel on Windows)
        self.pid = None  # Unix pid (None on Windows)
        self.backend = None
        # command to execute
        self._cmd = ""
        # should ctrl-d be deactivated ? (prevent Python exit)
        self._deactivate_ctrl_d = False

        # Default colors
        pal = QPalette()
        self._fg_color = pal.text().color().name()
        self._bg_color = pal.base().color().name()

        # Specify the terminal size in terms of lines and columns.
        self._rows = rows
        self._cols = cols
        self.output = collections.deque()
        self._document_lines = 0

        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        # Disable default scrollbars (we use our own, to be set via .set_scroll_bar())
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_bar = None

        # Use Monospace fonts and disable line wrapping.
        self.setFont(QtGui.QFont("Courier", 9))
        self.setFont(QtGui.QFont("Monospace"))
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        fmt = QtGui.QFontMetrics(self.font())
        char_width = fmt.horizontalAdvance("w")
        self.setCursorWidth(char_width)
        self.setTabChangesFocus(False)
        self.setFocusPolicy(Qt.StrongFocus)

        self.adjustSize()
        self.updateGeometry()
        self.update_stylesheet()

    # ------------------------------------------------------------------
    # Color properties
    # ------------------------------------------------------------------

    @property
    def bg_color(self):
        return self._bg_color

    @bg_color.setter
    def bg_color(self, hexcolor):
        self._bg_color = hexcolor
        self.update_stylesheet()

    @property
    def fg_color(self):
        return self._fg_color

    @fg_color.setter
    def fg_color(self, hexcolor):
        self._fg_color = hexcolor
        self.update_stylesheet()

    def update_stylesheet(self):
        self.setStyleSheet(
            f"QPlainTextEdit {{ border: 0; color: {self._fg_color}; background-color: {self._bg_color}; }} "
        )

    # ------------------------------------------------------------------
    # Size properties
    # ------------------------------------------------------------------

    @property
    def rows(self):
        return self._rows

    @rows.setter
    def rows(self, rows: int):
        if self.backend is None:
            # not initialized yet, ok to change
            self._rows = rows
            self.adjustSize()
            self.updateGeometry()
        else:
            raise RuntimeError("Cannot change rows after console is started.")

    @property
    def cols(self):
        return self._cols

    @cols.setter
    def cols(self, cols: int):
        if self.fd is None:
            # not initialized yet, ok to change
            self._cols = cols
            self.adjustSize()
            self.updateGeometry()
        else:
            raise RuntimeError("Cannot change cols after console is started.")

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def stop(self):
        if self.backend is None:
            return
        self.backend.close()
        if _HAVE_PTY and self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, os.WNOHANG)
            except OSError:
                pass

    def start(self, deactivate_ctrl_d: bool = False):
        self._deactivate_ctrl_d = deactivate_ctrl_d
        self.update_term_size()

        if _HAVE_PTY:
            self._start_unix()
        else:
            self._start_windows()

    def attach_external(self, write_fn):
        """Use an application-owned transport instead of starting a shell."""
        self.stop()
        self.update_term_size()
        self.fd = True
        self.pid = None
        self.backend = _ExternalBackend(write_fn, self.cols, self.rows)
        self.backend.dataReady.connect(self.data_ready)
        self._document_lines = 0
        self.data_ready(self.backend.screen)
        self.setReadOnly(True)
        self.setFocus(Qt.OtherFocusReason)

    def feed_external(self, data):
        if not isinstance(self.backend, _ExternalBackend):
            raise RuntimeError("No external terminal transport is attached.")
        self.backend.feed(data)

    def clear_external(self):
        if isinstance(self.backend, _ExternalBackend):
            self._document_lines = 0
            self.backend.reset()

    def _start_unix(self):
        self.fd, self.pid = self._fork_shell_unix()
        if self.fd:
            self.backend = _UnixBackend(self.fd, self.cols, self.rows)
            self.backend.dataReady.connect(self.data_ready)
            self.backend.processExited.connect(self.process_exited)
        else:
            self.process_exited()

    def _start_windows(self):
        cmd = self._cmd
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        try:
            pty_proc = PtyProcess.spawn(
                cmd, dimensions=(self.rows, self.cols), env=dict(os.environ, TERM="xterm-256color")
            )
        except Exception as exc:
            self.appendHtml(f"<br><h2>Failed to start {repr(cmd)}: {html.escape(str(exc))}</h2>")
            return
        # Use a truthy sentinel so the fd-is-None guard still works
        self.fd = True
        self.backend = _WindowsBackend(pty_proc, self.cols, self.rows)
        self.backend.dataReady.connect(self.data_ready)
        self.backend.processExited.connect(self.process_exited)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @SafeSlot()
    def process_exited(self):
        self.fd = None
        self.clear()
        self.appendHtml(f"<br><h2>{repr(self._cmd)} - Process exited.</h2>")
        self.setReadOnly(True)

    @SafeSlot(object)
    def data_ready(self, screen):
        """Handle new screen: redraw, set scroll bar max and slider, move cursor to its position

        This method is triggered via a signal from ``Backend``.
        """
        self.redraw_screen()
        self.adjust_scroll_bar()
        self.move_cursor()

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def minimumSizeHint(self):
        fmt = QtGui.QFontMetrics(self.font())
        char_width = fmt.horizontalAdvance("w")
        char_height = fmt.height()
        return QSize(char_width * self.cols, char_height * self.rows)

    def sizeHint(self):
        return self.minimumSizeHint()

    # ------------------------------------------------------------------
    # Scroll bar
    # ------------------------------------------------------------------

    def set_scroll_bar(self, scroll_bar):
        self.scroll_bar = scroll_bar
        self.scroll_bar.setMinimum(0)
        self.scroll_bar.valueChanged.connect(self.scroll_value_change)

    def scroll_value_change(self, value, old={"value": -1}):
        if self.backend is None:
            return
        if old["value"] == -1:
            old["value"] = self.scroll_bar.maximum()
        if value <= old["value"]:
            # scroll up
            # value is number of lines from the start
            nlines = old["value"] - value
            # history ratio gives prev_page == 1 line
            for i in range(nlines):
                self.backend.screen.prev_page()
        else:
            # scroll down
            nlines = value - old["value"]
            for i in range(nlines):
                self.backend.screen.next_page()
        old["value"] = value
        self.redraw_screen()

    def adjust_scroll_bar(self):
        sb = self.scroll_bar
        sb.valueChanged.disconnect(self.scroll_value_change)
        tmp = len(self.backend.screen.history.top) + len(self.backend.screen.history.bottom)
        sb.setMaximum(tmp if tmp > 0 else 0)
        sb.setSliderPosition(tmp if tmp > 0 else 0)
        sb.valueChanged.connect(self.scroll_value_change)

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def write(self, data: bytes):
        if self.backend is None:
            return
        try:
            self.backend.write(data)
        except (IOError, OSError):
            self.process_exited()

    @SafeSlot(object)
    def keyPressEvent(self, event):
        """
        Redirect all keystrokes to the terminal process.
        """
        if self.fd is None:
            # not started
            return
        # Convert the Qt key to the correct ASCII code.
        if (
            self._deactivate_ctrl_d
            and event.modifiers() == QtCore.Qt.ControlModifier
            and event.key() == QtCore.Qt.Key_D
        ):
            return None

        code = QtKeyToAscii(event)
        if code == "copy":
            # MacOS only: CMD-C handling
            self.copy()
        elif code == "paste":
            # MacOS only: CMD-V handling
            self._push_clipboard()
        elif code is not None:
            self.write(code)

    def event(self, event):
        # Qt consumes Tab for focus traversal before keyPressEvent. A terminal
        # must send it to the remote CLI for command completion.
        if event.type() == QtCore.QEvent.KeyPress and event.key() in (
            Qt.Key_Tab,
            Qt.Key_Backtab,
        ):
            self.write(b"\t")
            event.accept()
            return True
        if event.type() == QtCore.QEvent.ShortcutOverride and event.key() in (
            Qt.Key_Tab,
            Qt.Key_Backtab,
            Qt.Key_Left,
            Qt.Key_Right,
            Qt.Key_Up,
            Qt.Key_Down,
        ):
            event.accept()
            return True
        return super().event(event)

    def push(self, text: str):
        self.write(text.encode("utf-8"))

    # ------------------------------------------------------------------
    # Context menu / clipboard
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        if self.fd is None:
            return
        menu = self.createStandardContextMenu()
        for action in menu.actions():
            # remove all actions except copy and paste
            if "opy" in action.text():
                # redefine text without shortcut
                # since it probably clashes with control codes (like CTRL-C etc)
                action.setText("Copy")
                continue
            if "aste" in action.text():
                # redefine text without shortcut
                action.setText("Paste")
                # paste -> have to insert with self.push
                action.triggered.connect(self._push_clipboard)
                continue
            menu.removeAction(action)
        menu.exec_(event.globalPos())

    @SafeSlot()
    def _push_clipboard(self):
        clipboard = QApplication.instance().clipboard()
        text = clipboard.text().replace("\r\n", "\n").replace("\r", "\n")
        self.push(text.replace("\n", "\r"))

    # ------------------------------------------------------------------
    # Cursor / mouse
    # ------------------------------------------------------------------

    def move_cursor(self):
        if self.textCursor().hasSelection():
            return
        block = self.document().findBlockByNumber(self.backend.screen.cursor.y)
        if not block.isValid():
            return
        textCursor = QTextCursor(block)
        textCursor.movePosition(
            QTextCursor.Right,
            QTextCursor.MoveAnchor,
            min(self.backend.screen.cursor.x, max(0, block.length() - 1)),
        )
        self.setTextCursor(textCursor)
        self.ensureCursorVisible()

    def mouseReleaseEvent(self, event):
        if self.fd is None:
            return
        if event.button() == Qt.MiddleButton:
            # push primary selection buffer ("mouse clipboard") to terminal
            clipboard = QApplication.instance().clipboard()
            if clipboard.supportsSelection():
                self.push(clipboard.text(QClipboard.Selection))
            return None
        elif event.button() == Qt.LeftButton:
            # left button click
            textCursor = self.textCursor()
            if textCursor.selectedText():
                # mouse was used to select text -> nothing to do
                pass
            else:
                # a simple 'click', move scrollbar to end
                self.scroll_bar.setSliderPosition(self.scroll_bar.maximum())
                self.move_cursor()
                return None
        return super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Screen rendering
    # ------------------------------------------------------------------

    def redraw_screen(self):
        """
        Render only dirty Pyte rows into the QPlainTextEdit document.
        """
        screen = self.backend.screen
        if self._document_lines != screen.lines:
            self.setPlainText("\n".join("" for _ in range(screen.lines)))
            self._document_lines = screen.lines
            screen.dirty.update(range(screen.lines))

        for line_no in sorted(screen.dirty):
            if line_no < 0 or line_no >= screen.lines:
                continue
            block = self.document().findBlockByNumber(line_no)
            if not block.isValid():
                continue
            cursor = QTextCursor(block)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()

            run_text = []
            run_style = None
            for column in range(screen.columns):
                ch = screen.buffer[line_no][column]
                style = (
                    ch.fg,
                    ch.bg,
                    bool(ch.bold),
                    bool(ch.italics),
                    bool(ch.underscore),
                    bool(ch.reverse),
                )
                if run_style is not None and style != run_style:
                    cursor.insertText("".join(run_text), self._format(run_style))
                    run_text = []
                run_style = style
                run_text.append(ch.data or " ")
            if run_style is not None:
                cursor.insertText(
                    "".join(run_text).rstrip(),
                    self._format(run_style),
                )
        screen.dirty.clear()

    def _format(self, style):
        fg, bg, bold, italics, underscore, reverse = style
        foreground = ansi_colors.get(fg, self._fg_color)
        background = self._bg_color if bg == "default" else ansi_colors.get(bg, self._bg_color)
        if fg == "default":
            foreground = self._fg_color
        if reverse:
            foreground, background = background, foreground
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(foreground))
        fmt.setBackground(QColor(background))
        fmt.setFontWeight(QFont.Bold if bold else QFont.Normal)
        fmt.setFontItalic(italics)
        fmt.setFontUnderline(underscore)
        return fmt

    # ------------------------------------------------------------------
    # Terminal resize
    # ------------------------------------------------------------------

    def update_term_size(self):
        fmt = QtGui.QFontMetrics(self.font())
        char_width = fmt.width("w")
        char_height = fmt.height()
        self._cols = int(self.width() / char_width)
        self._rows = int(self.height() / char_height)

    def resizeEvent(self, event):
        self.update_term_size()
        if self.fd and self.backend:
            self.backend.resize(self._rows, self._cols)
            self.redraw_screen()
            self.adjust_scroll_bar()
            self.move_cursor()

    def wheelEvent(self, event):
        if not self.fd:
            return
        y = event.angleDelta().y()
        if y > 0:
            self.backend.screen.prev_page()
        else:
            self.backend.screen.next_page()
        self.redraw_screen()
        self.move_cursor()

    # ------------------------------------------------------------------
    # Unix-only: fork a shell
    # ------------------------------------------------------------------

    def _fork_shell_unix(self):
        try:
            pid, fd = pty.fork()
        except (IOError, OSError):
            return False, None
        if pid == 0:
            try:
                ls = os.environ["LANG"].split(".")
            except KeyError:
                ls = []
            if len(ls) < 2:
                ls = ["en_US", "UTF-8"]
            os.putenv("COLUMNS", str(self.cols))
            os.putenv("LINES", str(self.rows))
            os.putenv("TERM", "linux")
            os.putenv("LANG", ls[0] + ".UTF-8")
            if not self._cmd:
                self._cmd = os.environ.get("SHELL", "/bin/sh")
            cmd = self._cmd
            if isinstance(cmd, str):
                cmd = cmd.split()
            try:
                os.execvp(cmd[0], cmd)
            except (IOError, OSError):
                pass
            os._exit(0)
        else:
            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
            return fd, pid


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    mainwin = QtWidgets.QMainWindow()
    mainwin.setWindowTitle("qtpyTerminal")

    console = qtpyTerminal(mainwin)
    mainwin.setCentralWidget(console)
    console.start()

    mainwin.show()
    sys.exit(app.exec_())
