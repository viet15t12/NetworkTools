from __future__ import annotations

import sys
from typing import Any


def normalize_host(value: Any) -> str:
    return text(value)


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def int_or_zero_value(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else 0
    try:
        text_value = str(value).strip()
        return int(text_value)
    except (TypeError, ValueError):
        try:
            number = float(str(value).strip())
        except (TypeError, ValueError):
            return 0
        return int(number) if number.is_integer() else 0


def int_or_none_value(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    try:
        text_value = str(value).strip()
        return int(text_value)
    except (TypeError, ValueError):
        try:
            number = float(str(value).strip())
        except (TypeError, ValueError):
            return None
        return int(number) if number.is_integer() else None


def bool_int_value(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "on"} else 0
    return 1 if bool(value) else 0


def as_list(db: Any, value: Any) -> list[Any]:
    return db._as_list(value)


def as_dict(db: Any, value: Any) -> dict[str, Any]:
    return db._as_dict(value)


def log_db_error(operation: str, exc: BaseException) -> None:
    print(f"[db] {operation} failed: {exc}", file=sys.stderr)
