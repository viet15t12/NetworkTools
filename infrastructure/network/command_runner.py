"""Normalize command execution against an active connector."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def run_show(connector: Any, command: str) -> str:
    connection = getattr(connector, "connection", connector)
    return str(connection.send_command(command))


def run_config(connector: Any, commands: Iterable[str]) -> str:
    connection = getattr(connector, "connection", connector)
    return str(connection.send_config_set(list(commands)))
