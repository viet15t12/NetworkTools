"""Single Netmiko construction policy for direct and Nornir connections."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from netmiko import ConnectHandler
from netmiko.cisco.cisco_ios import CiscoIosSSH

from features.devices.ssh_algorithm_repository import get_ssh_algorithm_override
from .ssh_algorithms import SshAlgorithmOverride, make_transport_factory


class CAMSCiscoIosSSH(CiscoIosSSH):
    def __init__(
        self,
        *args: Any,
        ssh_algorithm_override: SshAlgorithmOverride | None = None,
        **kwargs: Any,
    ) -> None:
        self._ssh_algorithm_override = ssh_algorithm_override
        super().__init__(*args, **kwargs)

    def _connect_params_dict(self) -> dict[str, Any]:
        params = super()._connect_params_dict()
        if self._ssh_algorithm_override:
            params["transport_factory"] = make_transport_factory(
                self._ssh_algorithm_override
            )
        return params


def connect_device(
    device_params: dict[str, Any],
    db_path: str | Path | None = None,
):
    params = dict(device_params)
    method = str(params.pop("method", "") or "").lower()
    device_type = str(params.get("device_type") or "cisco_ios")
    is_telnet = method == "telnet" or device_type.endswith("_telnet")
    if is_telnet or not db_path:
        return ConnectHandler(**params)

    override = get_ssh_algorithm_override(db_path, str(params.get("host") or ""))
    if not override:
        return ConnectHandler(**params)
    if device_type != "cisco_ios":
        raise ValueError(
            "SSH algorithm overrides currently support only cisco_ios; "
            f"got {device_type!r}."
        )
    return CAMSCiscoIosSSH(
        **params,
        ssh_algorithm_override=override,
    )
