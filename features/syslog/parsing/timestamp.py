"""Parse common Cisco sequence-number and timestamp prefixes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re


SEQUENCE_RE = re.compile(r"^(?P<sequence>\d+):\s*")
RFC3164_RE = re.compile(
    r"^(?P<unsynced>\*)?(?P<stamp>[A-Z][a-z]{2}\s+\d{1,2}\s+"
    r"\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)(?:\s+[A-Z][A-Z0-9+-]*)?"
    r"\s*:?\s*(?P<body>.*)$",
    re.DOTALL,
)
ISO_RE = re.compile(
    r"^(?P<unsynced>\*)?(?P<stamp>\d{4}-\d{2}-\d{2}T\S+?)\s+(?P<body>.*)$",
    re.DOTALL,
)


@dataclass(slots=True, frozen=True)
class TimestampResult:
    sequence_number: int | None
    device_time: str | None
    clock_unsynchronized: bool
    remainder: str


def parse_timestamp(text: str, *, now: datetime | None = None) -> TimestampResult:
    sequence_number: int | None = None
    sequence = SEQUENCE_RE.match(text)
    if sequence:
        sequence_number = int(sequence.group("sequence"))
        text = text[sequence.end():]

    iso = ISO_RE.match(text)
    if iso:
        stamp = iso.group("stamp")
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return TimestampResult(sequence_number, None, bool(iso.group("unsynced")), text)
        return TimestampResult(
            sequence_number, parsed, bool(iso.group("unsynced")), iso.group("body")
        )

    match = RFC3164_RE.match(text)
    if not match:
        return TimestampResult(sequence_number, None, False, text)
    year = (now or datetime.now()).year
    stamp = match.group("stamp")
    for fmt in ("%Y %b %d %H:%M:%S.%f", "%Y %b %d %H:%M:%S"):
        try:
            parsed = datetime.strptime(f"{year} {stamp}", fmt).isoformat()
            return TimestampResult(
                sequence_number,
                parsed,
                bool(match.group("unsynced")),
                match.group("body"),
            )
        except ValueError:
            continue
    return TimestampResult(sequence_number, None, bool(match.group("unsynced")), text)


__all__ = ["TimestampResult", "parse_timestamp"]
