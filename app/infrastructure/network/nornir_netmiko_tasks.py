"""Nornir tasks bound to the CAMS Netmiko connection plugin."""

from __future__ import annotations

from typing import Any

from nornir.core.task import Result, Task


CONNECTION_NAME = "networktools_netmiko"


def netmiko_send_config(
    task: Task,
    config_commands=None,
    config_file=None,
    enable: bool = True,
    dry_run=None,
    **kwargs: Any,
) -> Result:
    connection = task.host.get_connection(CONNECTION_NAME, task.nornir.config)
    if task.is_dry_run(dry_run):
        raise ValueError("netmiko_send_config does not support dry_run")
    if enable:
        connection.enable()
    if config_commands:
        output = connection.send_config_set(config_commands=config_commands, **kwargs)
    elif config_file:
        output = connection.send_config_from_file(config_file, **kwargs)
    else:
        raise ValueError("Must specify either config_commands or config_file")
    return Result(host=task.host, result=output, changed=True)


def netmiko_send_command(
    task: Task,
    command_string: str,
    use_timing: bool = False,
    enable: bool = False,
    **kwargs: Any,
) -> Result:
    connection = task.host.get_connection(CONNECTION_NAME, task.nornir.config)
    if enable:
        connection.enable()
    sender = connection.send_command_timing if use_timing else connection.send_command
    return Result(host=task.host, result=sender(command_string, **kwargs))
