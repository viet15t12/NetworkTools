"""Parse the RFC Syslog PRI prefix independently from vendor payloads."""

from __future__ import annotations

from dataclasses import dataclass
import re


PRI_RE = re.compile(r"^<(?P<pri>\d{1,3})>")


@dataclass(slots=True, frozen=True)
class PriResult:
    pri: int | None
    facility: int | None
    severity: int | None
    remainder: str


def parse_pri(text: str) -> PriResult:
    match = PRI_RE.match(text)
    if not match:
        return PriResult(None, None, None, text)
    pri = int(match.group("pri"))
    if pri > 191:
        return PriResult(None, None, None, text)
    return PriResult(pri, pri // 8, pri % 8, text[match.end():].lstrip())


__all__ = ["PriResult", "parse_pri"]
