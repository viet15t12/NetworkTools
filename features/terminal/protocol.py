"""NTTP/1 JSON Lines validation and framing."""

from __future__ import annotations

import json
import unicodedata
from datetime import UTC, datetime
from typing import Any, Mapping


PROTOCOL_VERSION = "nttp/1"
MAX_MESSAGE_BYTES = 64 * 1024
EVENTS = frozenset(
    {
        "terminal.started",
        "terminal.ready",
        "child.started",
        "child.exited",
        "terminal.closed",
        "terminal.error",
    }
)
COMMANDS = frozenset(
    {
        "window.focus",
        "window.close",
        "window.set_title",
        "session.ping",
        "session.get_info",
    }
)
MESSAGE_TYPES = frozenset({"event", "command", "response"})


class NttpProtocolError(ValueError):
    """A stable protocol error suitable for safe diagnostics."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def utc_timestamp() -> str:
    """Return a timezone-aware timestamp for an NTTP envelope."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def validate_envelope(
    payload: Mapping[str, Any], *, allowed_types: set[str] | frozenset[str] | None = None
) -> dict[str, Any]:
    """Validate one decoded NTTP envelope and return a plain dictionary."""
    if not isinstance(payload, Mapping):
        raise NttpProtocolError("INVALID_ENVELOPE", "NTTP messages must be JSON objects.")
    message = dict(payload)
    if message.get("protocol") != PROTOCOL_VERSION:
        raise NttpProtocolError("UNSUPPORTED_PROTOCOL", "Unsupported NTTP protocol version.")
    message_type = message.get("type")
    valid_types = frozenset(allowed_types) if allowed_types is not None else MESSAGE_TYPES
    if message_type not in valid_types:
        raise NttpProtocolError("INVALID_TYPE", "Unsupported NTTP message type.")
    session_id = message.get("session_id")
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise NttpProtocolError("INVALID_SESSION", "NTTP session_id is missing or invalid.")
    device_id = message.get("device_id")
    if device_id is not None and (not isinstance(device_id, str) or len(device_id) > 253):
        raise NttpProtocolError("INVALID_DEVICE", "NTTP device_id is invalid.")
    data = message.get("data", {})
    if not isinstance(data, dict):
        raise NttpProtocolError("INVALID_DATA", "NTTP data must be a JSON object.")
    message["data"] = data

    if message_type == "event" and message.get("event") not in EVENTS:
        raise NttpProtocolError("UNKNOWN_EVENT", "Unsupported NTTP event.")
    if message_type == "command":
        if message.get("command") not in COMMANDS:
            raise NttpProtocolError("UNKNOWN_COMMAND", "Unsupported NTTP command.")
        _validate_request_id(message)
        if message.get("command") == "window.set_title":
            title = data.get("title")
            if (
                not isinstance(title, str)
                or not title
                or len(title) > 128
                or any(unicodedata.category(character).startswith("C") for character in title)
            ):
                raise NttpProtocolError("INVALID_TITLE", "NTTP window title is invalid.")
    if message_type == "response":
        _validate_request_id(message)
        if not isinstance(message.get("ok"), bool):
            raise NttpProtocolError("INVALID_RESPONSE", "NTTP response ok must be boolean.")
    return message


def _validate_request_id(message: Mapping[str, Any]) -> None:
    request_id = message.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
        raise NttpProtocolError("INVALID_REQUEST", "NTTP request_id is missing or invalid.")


def decode_line(line: bytes) -> dict[str, Any]:
    """Decode and validate one bounded UTF-8 JSON line."""
    if len(line) > MAX_MESSAGE_BYTES:
        raise NttpProtocolError("MESSAGE_TOO_LARGE", "NTTP message exceeds 64 KiB.")
    try:
        text = line.rstrip(b"\r\n").decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NttpProtocolError("INVALID_ENCODING", "NTTP messages must use UTF-8.") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NttpProtocolError("INVALID_JSON", "NTTP message is not valid JSON.") from exc
    return validate_envelope(payload, allowed_types={"event", "response"})


def encode_message(payload: Mapping[str, Any]) -> bytes:
    """Validate and serialize one outbound envelope as compact JSON Lines."""
    message = validate_envelope(payload)
    encoded = json.dumps(
        message,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8") + b"\n"
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise NttpProtocolError("MESSAGE_TOO_LARGE", "NTTP message exceeds 64 KiB.")
    return encoded
