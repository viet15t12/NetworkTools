"""Incremental cleanup for device output before ANSI parsing."""

from __future__ import annotations

import re


LONE_LINE_FEED_RE = re.compile(r"(?<!\r)\n")


class TerminalOutputNormalizer:
    """Preserve terminal rows while removing known Cisco console noise."""

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, chunk: str) -> str:
        """Normalize one channel chunk without breaking split CRLF or ``^@``."""
        text = self._pending + str(chunk or "")
        self._pending = ""
        if text.endswith(("\r", "^")):
            self._pending = text[-1]
            text = text[:-1]

        # Some virtual IOS consoles expose NUL as either the control byte or
        # the two printable characters "^@". Neither belongs on the screen.
        text = text.replace("\x00", "").replace("^@", "")
        # Netmiko normally folds CRLF into LF. A VT screen treats LF as
        # vertical movement only, so restore carriage return for lone LF.
        return LONE_LINE_FEED_RE.sub("\r\n", text)

    def flush(self) -> str:
        """Return a deferred final character when the channel stops."""
        pending = self._pending
        self._pending = ""
        return pending.replace("\x00", "")
