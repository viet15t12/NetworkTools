"""Cisco IOS configuration-output validation used by Switching pushes."""

from __future__ import annotations

import re


ERROR_MARKERS = (
    "% invalid input",
    "% incomplete command",
    "% ambiguous command",
    "% authorization failed",
    "command rejected",
)


def _nearest_command(lines: list[str], error_index: int) -> str:
    """Find the echoed command directly associated with one IOS error line."""
    for line in reversed(lines[max(0, error_index - 4) : error_index]):
        stripped = line.strip()
        if not stripped or re.fullmatch(r"[\s^]+", line):
            continue
        if any(marker in stripped.lower() for marker in ERROR_MARKERS):
            break
        return stripped.lower()
    return ""


def has_rejected_command(output: str) -> bool:
    """Detect rejected IOS commands with one narrow fixed-dot1q exception.

    Fixed-encapsulation switches may reject the explicit dot1q command while
    still accepting the following trunk command.  Only the error immediately
    associated with that exact command is ignored; later errors remain fatal.
    """
    lines = str(output or "").splitlines()
    for index, line in enumerate(lines):
        normalized = line.lower()
        if not any(marker in normalized for marker in ERROR_MARKERS):
            continue
        command = _nearest_command(lines, index)
        if (
            "% invalid input" in normalized
            and "switchport trunk encapsulation dot1q" in command
        ):
            continue
        return True
    return False


__all__ = ["has_rejected_command"]
