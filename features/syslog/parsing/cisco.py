"""Parse Cisco IOS/IOS-XE system-message headers."""

from __future__ import annotations

from dataclasses import dataclass
import re


CISCO_RE = re.compile(
    r"%(?P<prefix>[A-Z0-9_]+(?:-[A-Z0-9_]+)*)-"
    r"(?P<severity>[0-7])-(?P<mnemonic>[A-Z0-9_]+):\s*(?P<message>.*)",
    re.DOTALL,
)


@dataclass(slots=True, frozen=True)
class CiscoResult:
    facility: str
    subfacility: str | None
    severity: int
    mnemonic: str
    message: str


def parse_cisco(text: str) -> CiscoResult | None:
    match = CISCO_RE.search(text)
    if not match:
        return None
    prefix = match.group("prefix").split("-")
    return CiscoResult(
        facility=prefix[0],
        subfacility="-".join(prefix[1:]) or None,
        severity=int(match.group("severity")),
        mnemonic=match.group("mnemonic"),
        message=match.group("message").strip(),
    )


__all__ = ["CiscoResult", "parse_cisco"]
