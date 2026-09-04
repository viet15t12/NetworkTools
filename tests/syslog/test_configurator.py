from __future__ import annotations

import unittest

from features.syslog.configurator import SyslogConfigurator, _contains_cli_error


HOST = "192.0.2.1"
SERVER = "192.0.2.100"
PORT = 5514
INTERFACE = "GigabitEthernet0/0"
DESTINATION = f"logging host {SERVER} transport udp port {PORT}"
SOURCE = f"logging source-interface {INTERFACE}"


class _RepositoryStub:
    def __init__(self) -> None:
        self.saved_states: list[tuple] = []
        self.attempts: list[tuple] = []

    def is_connected(self, host: str) -> bool:
        return True

    def device_os(self, host: str) -> str:
        return "cisco_ios"

    def source_interface(self, host: str):
        return None

    def save_device_state(self, *args) -> None:
        self.saved_states.append(args)

    def save_device_attempt(self, *args) -> None:
        self.attempts.append(args)


class _FailingRepository(_RepositoryStub):
    def save_device_state(self, *args) -> None:
        raise OSError("database is locked")


class _Connection:
    def __init__(self) -> None:
        self.interface_output = (
            "Interface IP-Address OK? Method Status Protocol\n"
            f"{INTERFACE} {HOST} YES manual up up"
        )
        self.config_output = ""
        self.running_logging = f"{DESTINATION}\n{SOURCE}"
        self.startup_logging = self.running_logging
        self.save_output: object = "Copy complete."
        self.config_calls: list[tuple[list[str], dict]] = []
        self.show_calls: list[str] = []
        self.save_calls: list[dict] = []

    def send_config_set(self, commands, **kwargs):
        self.config_calls.append((list(commands), kwargs))
        return self.config_output

    def send_command(self, command):
        self.show_calls.append(command)
        if command == "show ip interface brief":
            return self.interface_output
        if command == "show running-config | include logging":
            return self.running_logging
        if command == "show startup-config | include logging":
            return self.startup_logging
        raise AssertionError(f"Unexpected show command: {command}")

    def save_config(self, **kwargs):
        self.save_calls.append(kwargs)
        if isinstance(self.save_output, Exception):
            raise self.save_output
        return self.save_output


class _Connector:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection


class _Registry:
    def __init__(self, connection: _Connection) -> None:
        self.connector = _Connector(connection)
        self.ensure_open = None

    def execute(self, host, operation, *, ensure_open=True):
        self.ensure_open = ensure_open
        return {"ok": True, "value": operation(self.connector)}


class SyslogConfiguratorTests(unittest.TestCase):
    def _configurator(self):
        repository = _RepositoryStub()
        connection = _Connection()
        registry = _Registry(connection)
        return SyslogConfigurator(repository, registry), repository, connection, registry

    def test_cli_error_patterns_include_required_cisco_failures(self) -> None:
        for output in (
            "% Invalid input detected at '^' marker.",
            "% Incomplete command.",
            "% Ambiguous command:  logging h",
            "% Unknown command or computer name",
            "% Error opening nvram:",
        ):
            with self.subTest(output=output):
                self.assertTrue(_contains_cli_error(output))
        self.assertFalse(_contains_cli_error("Building configuration...\n[OK]"))

    def test_missing_database_interface_requests_manual_input(self) -> None:
        configurator, _repository, _connection, _registry = self._configurator()

        result = configurator.configure(HOST, SERVER, "udp", PORT)

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "source_interface_required")

    def test_configure_success_verifies_saves_then_records_configured(self) -> None:
        configurator, repository, connection, registry = self._configurator()

        result = configurator.configure(HOST, SERVER, "udp", PORT, "Gi0/0")

        self.assertTrue(result["ok"], result)
        self.assertTrue(registry.ensure_open)
        commands, kwargs = connection.config_calls[0]
        self.assertIn(DESTINATION, commands)
        self.assertIn("logging source-interface Gi0/0", commands)
        self.assertIn("error_pattern", kwargs)
        self.assertEqual(
            connection.save_calls,
            [{"cmd": "copy running-config startup-config", "confirm": True}],
        )
        self.assertEqual(
            connection.show_calls,
            [
                "show ip interface brief",
                "show running-config | include logging",
                "show startup-config | include logging",
            ],
        )
        self.assertTrue(repository.saved_states[-1][5])

    def test_invalid_command_output_is_failure_and_never_saved(self) -> None:
        configurator, repository, connection, _registry = self._configurator()
        connection.config_output = "% Invalid input detected at '^' marker."

        result = configurator.configure(HOST, SERVER, "udp", PORT, INTERFACE)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "apply")
        self.assertIn("Invalid input", result["message"])
        self.assertFalse(repository.saved_states[-1][5])
        self.assertEqual(connection.save_calls, [])

    def test_incomplete_command_output_is_failure(self) -> None:
        configurator, repository, connection, _registry = self._configurator()
        connection.config_output = "% Incomplete command."

        result = configurator.configure(HOST, SERVER, "udp", PORT, INTERFACE)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "apply")
        self.assertIn("Incomplete command", result["message"])
        self.assertFalse(repository.saved_states[-1][5])

    def test_nonexistent_source_interface_is_rejected_before_apply(self) -> None:
        configurator, repository, connection, _registry = self._configurator()

        result = configurator.configure(
            HOST, SERVER, "udp", PORT, "GigabitEthernet99/99"
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "interface")
        self.assertEqual(connection.config_calls, [])
        self.assertFalse(repository.saved_states[-1][5])

    def test_missing_destination_after_apply_is_not_configured_or_saved(self) -> None:
        configurator, repository, connection, _registry = self._configurator()
        connection.running_logging = SOURCE

        result = configurator.configure(HOST, SERVER, "udp", PORT, INTERFACE)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "verify_running")
        self.assertFalse(repository.saved_states[-1][5])
        self.assertEqual(connection.save_calls, [])

    def test_save_failure_is_not_reported_as_complete_success(self) -> None:
        configurator, repository, connection, _registry = self._configurator()
        connection.save_output = OSError("NVRAM is unavailable")

        result = configurator.configure(HOST, SERVER, "udp", PORT, INTERFACE)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "save")
        self.assertIn("NVRAM is unavailable", result["message"])
        self.assertFalse(repository.saved_states[-1][5])

    def test_startup_verification_failure_is_not_configured(self) -> None:
        configurator, repository, connection, _registry = self._configurator()
        connection.startup_logging = SOURCE

        result = configurator.configure(HOST, SERVER, "udp", PORT, INTERFACE)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "verify_startup")
        self.assertFalse(repository.saved_states[-1][5])

    def test_database_failure_is_reported_separately_after_device_success(self) -> None:
        repository = _FailingRepository()
        connection = _Connection()
        configurator = SyslogConfigurator(repository, _Registry(connection))

        result = configurator.configure(HOST, SERVER, "udp", PORT, INTERFACE)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "database")
        self.assertIn("database is locked", result["message"])

    def test_cancel_success_verifies_removal_and_records_unconfigured(self) -> None:
        configurator, repository, connection, _registry = self._configurator()
        connection.running_logging = "logging trap warnings"
        connection.startup_logging = "logging trap warnings"

        result = configurator.cancel(HOST, SERVER, "udp", PORT)

        self.assertTrue(result["ok"], result)
        self.assertEqual(
            connection.config_calls[0][0],
            [f"no {DESTINATION}"],
        )
        self.assertFalse(repository.saved_states[-1][5])
        self.assertEqual(repository.attempts, [])

    def test_cancel_false_positive_keeps_state_and_does_not_save(self) -> None:
        configurator, repository, connection, _registry = self._configurator()

        result = configurator.cancel(HOST, SERVER, "udp", PORT)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "verify_running")
        self.assertEqual(repository.saved_states, [])
        self.assertEqual(len(repository.attempts), 1)
        self.assertEqual(connection.save_calls, [])


if __name__ == "__main__":
    unittest.main()
