"""Single adapter for creating device connectors."""

from __future__ import annotations

from typing import Any, Protocol


class ConnectorFactory(Protocol):
    def __call__(self, device: dict[str, Any]) -> Any: ...


def create_connector(device: dict[str, Any]) -> Any:
    from .device_connector import DeviceConnector

    return DeviceConnector(
        device["host"],
        device["method"],
        device["port"],
        device["username"],
        device["password"],
        device_type=device["device_type"],
        start_config_mode=False,
        db_path=device.get("db_path"),
        timeout=int(device.get("timeout", 15)),
    )
