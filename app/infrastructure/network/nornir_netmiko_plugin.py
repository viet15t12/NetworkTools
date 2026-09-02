"""Nornir Netmiko plugin using the application connection policy."""

from __future__ import annotations

from typing import Any

from nornir.core.plugins.connections import ConnectionPluginRegister
from nornir_netmiko.connections.netmiko import napalm_to_netmiko_map

from .netmiko_factory import connect_device


class CAMSNetmiko:
    def open(
        self,
        hostname,
        username,
        password,
        port,
        platform,
        extras=None,
        configuration=None,
    ) -> None:
        parameters: dict[str, Any] = {
            "host": hostname,
            "username": username,
            "password": password,
            "port": port,
        }
        extras = dict(extras or {})
        db_path = extras.pop("ssh_algorithm_db_path", None)
        try:
            parameters["ssh_config_file"] = configuration.ssh.config_file
        except AttributeError:
            pass
        if platform is not None:
            parameters["device_type"] = napalm_to_netmiko_map.get(platform, platform)
        parameters.update(extras)
        self.connection = connect_device(parameters, db_path)

    def close(self) -> None:
        self.connection.disconnect()


def register_cams_netmiko() -> None:
    """Register the application's isolated Nornir connection plugin once."""
    name = "cams_netmiko"
    if name not in ConnectionPluginRegister.available:
        ConnectionPluginRegister.register(name, CAMSNetmiko)
