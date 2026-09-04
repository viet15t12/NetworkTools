from __future__ import annotations

import importlib
import re
import sys
import types
import unittest
from unittest.mock import patch


def _load_device_connector():
    exceptions = types.ModuleType("netmiko.exceptions")
    exceptions.NetmikoTimeoutException = type("NetmikoTimeoutException", (Exception,), {})
    exceptions.NetmikoAuthenticationException = type(
        "NetmikoAuthenticationException", (Exception,), {}
    )
    exceptions.ConnectionException = type("ConnectionException", (Exception,), {})

    factory = types.ModuleType("infrastructure.network.netmiko_factory")
    factory.connect_device = lambda *args, **kwargs: None

    algorithms = types.ModuleType("infrastructure.network.ssh_algorithms")
    algorithms.classify_ssh_error = lambda _error: "connection error"

    module_name = "infrastructure.network.device_connector"
    sys.modules.pop(module_name, None)
    with patch.dict(
        sys.modules,
        {
            "netmiko.exceptions": exceptions,
            "infrastructure.network.netmiko_factory": factory,
            "infrastructure.network.ssh_algorithms": algorithms,
        },
    ):
        module = importlib.import_module(module_name)
    sys.modules.pop(module_name, None)
    return module.DeviceConnector


class _Connection:
    def __init__(self, prompt: str = "R3(config)#^@") -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.prompt = prompt

    def find_prompt(self) -> str:
        return self.prompt

    def send_command(self, command: str, **kwargs: object) -> str:
        self.calls.append((command, kwargs))
        return "GigabitEthernet0/0  192.0.2.1  YES manual up up"


class DeviceConnectorTests(unittest.TestCase):
    def test_connect_preserves_timeout_diagnostic_for_view_push(self) -> None:
        DeviceConnector = _load_device_connector()
        timeout_error = DeviceConnector.connect.__globals__["NetmikoTimeoutException"]
        connector = DeviceConnector(
            "192.0.2.10", "ssh", 22, "admin", "secret", db_path=":memory:"
        )

        with patch.dict(
            DeviceConnector.connect.__globals__,
            {"connect_device": lambda *_args, **_kwargs: (_ for _ in ()).throw(
                timeout_error("SSH banner timed out")
            )},
        ):
            self.assertFalse(connector.connect())

        self.assertEqual(
            connector.last_error,
            "CONNECTION_TIMEOUT: SSH banner timed out",
        )

    def test_send_command_does_not_require_command_echo(self) -> None:
        DeviceConnector = _load_device_connector()
        connector = DeviceConnector(
            "192.0.2.1",
            "ssh",
            22,
            "admin",
            "secret",
            db_path=":memory:",
            timeout=30,
        )
        connection = _Connection()
        connector.connection = connection
        connector.connected = True

        output = connector.send_command("do show ip interface brief")

        self.assertIn("GigabitEthernet0/0", output or "")
        self.assertEqual(len(connection.calls), 1)
        command, kwargs = connection.calls[0]
        self.assertEqual(command, "do show ip interface brief")
        self.assertEqual(kwargs["read_timeout"], 30)
        self.assertIs(kwargs["cmd_verify"], False)

        pattern = str(kwargs["expect_string"])
        self.assertIsNotNone(re.search(pattern, "R3(config)#"))
        self.assertIsNotNone(re.search(pattern, "R3(config)#\x00"))
        self.assertIsNotNone(re.search(pattern, "R3(config)#^@"))
        self.assertIsNotNone(re.search(pattern, "R3(config)#\r\n"))

    def test_send_command_rejects_partial_command_echo_as_prompt(self) -> None:
        DeviceConnector = _load_device_connector()
        connector = DeviceConnector(
            "192.0.2.1", "ssh", 22, "admin", "secret", db_path=":memory:"
        )
        connection = _Connection(prompt="o show running-")
        connector.connection = connection
        connector.connected = True

        connector.send_command("do show running-config")

        pattern = str(connection.calls[0][1]["expect_string"])
        self.assertIsNone(re.search(pattern, "o show running-"))
        self.assertIsNotNone(re.search(pattern, "R3(config)#"))
        self.assertIsNotNone(re.search(pattern, "R3(config)#^@"))

    def test_switch_collection_uses_bounded_non_secret_show_commands(self) -> None:
        DeviceConnector = _load_device_connector()
        connector = DeviceConnector(
            "192.0.2.2", "ssh", 22, "admin", "secret", db_path=":memory:"
        )
        connection = _Connection()
        connector.connection = connection
        connector.connected = True

        result = connector.collect_switch_state()

        self.assertTrue(result["ok"])
        commands = [call[0] for call in connection.calls]
        self.assertEqual(
            commands,
            [
                "show vlan brief",
                "show interfaces status",
                "show interfaces trunk",
                "show etherchannel summary",
                "show vtp status",
            ],
        )
        self.assertNotIn("show vtp password", commands)

    def test_switch_collection_can_be_scoped_to_the_pushed_module(self) -> None:
        DeviceConnector = _load_device_connector()
        connector = DeviceConnector(
            "192.0.2.2", "ssh", 22, "admin", "secret", db_path=":memory:"
        )
        connection = _Connection()
        connector.connection = connection
        connector.connected = True

        result = connector.collect_switch_state(
            ("interfaces_status", "interfaces_trunk")
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            [call[0] for call in connection.calls],
            ["show interfaces status", "show interfaces trunk"],
        )
