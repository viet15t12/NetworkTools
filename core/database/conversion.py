"""Pure QVariant and display-text conversion helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

def _variant_list(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows


def _clean_display_text(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isprintable()).strip().strip("\"'`#> ")


class ConversionMixin:
    """Provide dependency-free payload conversion to QML slot mixins."""

    def _as_list(self, value: Any) -> list[Any]:
        if hasattr(value, "toVariant"):
            value = value.toVariant()
        if value is None:
            return []
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return []
            return self._as_list(decoded)
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return list(value)
        return []

    def _as_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "toVariant"):
            value = value.toVariant()
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return self._as_dict(decoded)
        if isinstance(value, dict):
            return value
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def _int_or_none(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        try:
            text = str(value).strip()
            return int(text)
        except (TypeError, ValueError):
            try:
                number = float(str(value).strip())
            except (TypeError, ValueError):
                return None
            return int(number) if number.is_integer() else None

    def _int_or_zero(self, value: Any) -> int:
        return self._int_or_none(value) or 0

    def _bool_int(self, value: Any) -> int:
        if isinstance(value, str):
            return 1 if value.strip().lower() in {"1", "true", "yes", "on"} else 0
        return 1 if bool(value) else 0

    def _str_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _dict_rows(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [{k: ("" if v is None else v) for k, v in dict(row).items()} for row in rows]

__all__ = ["ConversionMixin", "_clean_display_text", "_variant_list"]
