"""Parse the compact, user-facing Syslog smart-filter syntax."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import re
import shlex
from typing import Any


_SEVERITIES = {
    "0": 0, "emergency": 0, "emergencies": 0, "emerg": 0,
    "1": 1, "alert": 1, "alerts": 1,
    "2": 2, "critical": 2, "crit": 2,
    "3": 3, "error": 3, "errors": 3, "err": 3,
    "4": 4, "warning": 4, "warnings": 4, "warn": 4,
    "5": 5, "notice": 5, "notifications": 5,
    "6": 6, "info": 6, "informational": 6,
    "7": 7, "debug": 7, "debugging": 7,
}
_KEY_ALIASES = {
    "host": "host",
    "from": "from_time",
    "to": "to_time",
    "since": "since",
    "last": "per_host",
    "perhost": "per_host",
    "severity": "severities",
    "sev": "severities",
    "protocol": "protocols",
    "proto": "protocols",
    "facility": "facility",
    "fac": "facility",
    "mnemonic": "mnemonic",
    "mn": "mnemonic",
    "text": "text",
    "message": "text",
}
_DURATION_RE = re.compile(r"^(\d+)([mhdw])$", re.IGNORECASE)
_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class SmartFilterError(ValueError):
    """Raised when a smart-filter expression cannot be interpreted safely."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _parse_time(value: Any, field: str, *, end_of_day: bool = False) -> str:
    text_value = str(value or "").strip()
    if not text_value:
        return ""
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text_value):
            parsed_date = datetime.fromisoformat(text_value).date()
            parsed = datetime.combine(
                parsed_date,
                time.max if end_of_day else time.min,
                tzinfo=timezone.utc,
            )
        else:
            parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat(timespec="milliseconds")
    except ValueError as exc:
        raise SmartFilterError(
            f"Invalid {field} time '{text_value}'. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM."
        ) from exc


def _parse_severities(values: Any) -> list[int]:
    result: list[int] = []
    for raw in _as_list(values):
        for item in str(raw or "").split(","):
            key = item.strip().lower()
            if not key:
                continue
            if key not in _SEVERITIES:
                raise SmartFilterError(f"Unknown severity '{item.strip()}'.")
            severity = _SEVERITIES[key]
            if severity not in result:
                result.append(severity)
    return result


def _parse_protocols(values: Any) -> list[str]:
    result: list[str] = []
    for raw in _as_list(values):
        for item in str(raw or "").split(","):
            protocol = item.strip().lower()
            if not protocol:
                continue
            if protocol not in {"udp", "tcp"}:
                raise SmartFilterError(f"Unknown protocol '{item.strip()}'. Use UDP or TCP.")
            if protocol not in result:
                result.append(protocol)
    return result


def _parse_per_host(value: Any, *, allow_zero: bool = False) -> int:
    try:
        count = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise SmartFilterError("last must be a whole number from 1 to 500.") from exc
    if allow_zero and count == 0:
        return 0
    if not 1 <= count <= 500:
        raise SmartFilterError("last must be from 1 to 500 logs per host.")
    return count


def build_log_filters(
    base_filters: dict[str, Any] | None,
    expression: str = "",
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Merge structured controls with a compact smart-filter expression.

    Smart-filter keys override the corresponding structured control. Unkeyed
    terms remain a case-insensitive message/mnemonic/facility search.
    """

    base = dict(base_filters or {})
    filters: dict[str, Any] = {
        "host": str(base.get("host") or "").strip(),
        "search": str(base.get("search") or "").strip(),
        "severities": _parse_severities(base.get("severities", [])),
        "protocols": _parse_protocols(base.get("protocols", [])),
        "from_time": _parse_time(base.get("from_time"), "from"),
        "to_time": _parse_time(base.get("to_time"), "to", end_of_day=True),
        "per_host": _parse_per_host(base.get("per_host"), allow_zero=True),
        "facility": str(base.get("facility") or "").strip(),
        "mnemonic": str(base.get("mnemonic") or "").strip(),
    }

    try:
        tokens = shlex.split(str(expression or ""), posix=True)
    except ValueError as exc:
        raise SmartFilterError(f"Invalid quotes in smart filter: {exc}") from exc

    plain_terms: list[str] = []
    explicit_text: list[str] = []
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    for token in tokens:
        if ":" not in token:
            plain_terms.append(token)
            continue
        raw_key, value = token.split(":", 1)
        key = raw_key.strip().lower()
        if key not in _KEY_ALIASES:
            if _KEY_RE.fullmatch(raw_key):
                raise SmartFilterError(
                    f"Unknown filter '{raw_key}'. Open Smart filter help to see supported keys."
                )
            plain_terms.append(token)
            continue
        if not value.strip():
            raise SmartFilterError(f"Filter '{raw_key}' requires a value.")

        target = _KEY_ALIASES[key]
        if target == "host":
            filters["host"] = value.strip()
        elif target == "from_time":
            filters["from_time"] = _parse_time(value, "from")
        elif target == "to_time":
            filters["to_time"] = _parse_time(value, "to", end_of_day=True)
        elif target == "since":
            duration = _DURATION_RE.fullmatch(value.strip())
            if duration is None:
                raise SmartFilterError("since must use m, h, d, or w, for example since:30m.")
            amount = int(duration.group(1))
            if amount < 1:
                raise SmartFilterError("since duration must be greater than zero.")
            unit = duration.group(2).lower()
            seconds = amount * {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
            filters["from_time"] = (current_time - timedelta(seconds=seconds)).isoformat(
                timespec="milliseconds"
            )
        elif target == "per_host":
            filters["per_host"] = _parse_per_host(value)
        elif target == "severities":
            filters["severities"] = _parse_severities(value)
        elif target == "protocols":
            filters["protocols"] = _parse_protocols(value)
        elif target == "facility":
            filters["facility"] = value.strip()
        elif target == "mnemonic":
            filters["mnemonic"] = value.strip()
        elif target == "text":
            explicit_text.append(value.strip())

    search_parts = [filters["search"], *plain_terms, *explicit_text]
    filters["search"] = " ".join(part for part in search_parts if part).strip()
    filters["smart_query"] = str(expression or "").strip()

    if filters["from_time"] and filters["to_time"]:
        start = datetime.fromisoformat(filters["from_time"])
        end = datetime.fromisoformat(filters["to_time"])
        if start > end:
            raise SmartFilterError("The from time must be earlier than or equal to the to time.")
    return filters


__all__ = ["SmartFilterError", "build_log_filters"]
