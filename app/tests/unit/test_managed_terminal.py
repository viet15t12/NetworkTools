"""CAMS-side contracts for the external Alacritty terminal fork."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QObject, QProcess, pyqtSignal
from PyQt6.QtNetwork import QLocalSocket

from features.terminal.ipc_server import NttpServer
from features.terminal.launcher import TerminalLauncher
from features.terminal.managed_manager import ManagedTerminalManager
from features.terminal.protocol import (
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    NttpProtocolError,
    decode_line,
    encode_message,
)
from features.terminal.ssh import (
    TerminalLaunchError,
    build_openssh_command,
    build_terminal_command,
)


class _FakeProcess(QObject):
    started = pyqtSignal()
    finished = pyqtSignal(int, object)
    errorOccurred = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.program = ""
        self.arguments: list[str] = []
        self.terminate_calls = 0
        self.kill_calls = 0

    def start(self, program: str, arguments: list[str]) -> None:
        self.program = program
        self.arguments = list(arguments)
        self.started.emit()

    def processId(self) -> int:
        return 4242

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1

    def waitForFinished(self, _timeout: int) -> bool:
        return False


class _FakeIpc(QObject):
    eventReceived = pyqtSignal(object)
    responseReceived = pyqtSignal(object)
    sessionConnected = pyqtSignal(str)
    sessionDisconnected = pyqtSignal(str)
    requestTimedOut = pyqtSignal(str, str, str)
    protocolError = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.registered: set[str] = set()
        self.connected: set[str] = set()
        self.commands: list[tuple[str, str, dict[str, object]]] = []
        self.stopped = False

    def start(self) -> str:
        return "/run/user/1000/networktools/manager.sock"

    def stop(self) -> None:
        self.stopped = True

    def register_session(self, session_id: str) -> None:
        self.registered.add(session_id)

    def unregister_session(self, session_id: str) -> None:
        self.registered.discard(session_id)
        self.connected.discard(session_id)

    def send_command(
        self,
        session_id: str,
        command: str,
        data: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> str | None:
        if session_id not in self.connected:
            return None
        self.commands.append((session_id, command, dict(data or {})))
        return f"req-{len(self.commands)}"

    def connect_session(self, session_id: str) -> None:
        self.connected.add(session_id)
        self.sessionConnected.emit(session_id)


class ManagedTerminalManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.processes: list[_FakeProcess] = []

        def process_factory(parent: QObject | None) -> _FakeProcess:
            process = _FakeProcess(parent)
            self.processes.append(process)
            return process

        self.ipc = _FakeIpc()
        self.launcher = TerminalLauncher(
            "/bin/true",
            process_factory=process_factory,
        )
        self.device = {
            "host": "192.0.2.10",
            "device_id": "192.0.2.10",
            "device_name": "R1\n\x1b]2;unsafe",
            "method": "ssh",
            "port": 2222,
            "username": "admin",
            "password": "must-not-leak",
            "dev": 0,
        }
        self.manager = ManagedTerminalManager(
            lambda host: dict(self.device) if host == self.device["host"] else None,
            launcher=self.launcher,
            ipc_server=self.ipc,
        )

    def test_launch_uses_uuid_metadata_openssh_and_no_password(self) -> None:
        states: list[tuple[str, str]] = []
        self.manager.terminalStateChanged.connect(
            lambda host, state: states.append((host, state))
        )

        result = self.manager.open("192.0.2.10")

        self.assertTrue(result["ok"])
        self.assertEqual(len(self.processes), 1)
        process = self.processes[0]
        self.assertEqual(process.program, "/usr/bin/true")
        self.assertIn("--nt-managed", process.arguments)
        self.assertIn("--nt-session-id", process.arguments)
        self.assertIn("--nt-device-id", process.arguments)
        self.assertEqual(process.arguments[-5:], ["-e", "ssh", "-p", "2222", "admin@192.0.2.10"])
        serialized = " ".join(process.arguments)
        self.assertNotIn("must-not-leak", serialized)
        self.assertNotIn("\n", serialized)
        self.assertNotIn("\x1b", serialized)
        session = self.manager.session_for_device("192.0.2.10")
        self.assertIsNotNone(session)
        self.assertEqual(session.pid, 4242)
        self.assertEqual(states[0], ("192.0.2.10", "starting"))

    def test_cisco_ios_terminal_uses_device_scoped_legacy_algorithms(self) -> None:
        command = build_openssh_command({
            **self.device,
            "device_type": "cisco_ios",
        })

        serialized = " ".join(command.arguments)
        self.assertIn("KexAlgorithms=diffie-hellman-group14-sha1", serialized)
        self.assertIn("HostKeyAlgorithms=ssh-rsa", serialized)
        self.assertIn("PubkeyAcceptedAlgorithms=ssh-rsa", serialized)
        self.assertNotIn("must-not-leak", serialized)

    def test_saved_ssh_algorithms_override_cisco_fallback(self) -> None:
        command = build_openssh_command({
            **self.device,
            "device_type": "cisco_ios",
            "ssh_algorithms": {
                "kex": ["diffie-hellman-group14-sha256"],
                "key_types": ["rsa-sha2-256"],
            },
        })

        serialized = " ".join(command.arguments)
        self.assertIn("KexAlgorithms=diffie-hellman-group14-sha256", serialized)
        self.assertIn("HostKeyAlgorithms=rsa-sha2-256", serialized)
        self.assertNotIn("diffie-hellman-group14-sha1", serialized)

    def test_ready_then_duplicate_open_focuses_without_new_process(self) -> None:
        first = self.manager.open("192.0.2.10")
        session_id = first["sessionId"]
        self.ipc.connect_session(session_id)
        self.ipc.eventReceived.emit(
            {
                "protocol": PROTOCOL_VERSION,
                "type": "event",
                "event": "terminal.ready",
                "session_id": session_id,
                "data": {"window_id": "window-1"},
            }
        )

        second = self.manager.open("192.0.2.10")

        self.assertTrue(second["ok"])
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(self.ipc.commands[-1][1], "window.focus")
        self.assertEqual(self.manager.state_for_device("192.0.2.10"), "open")

    def test_duplicate_open_does_not_destroy_live_terminal_during_ipc_outage(self) -> None:
        opened = self.manager.open("192.0.2.10")
        self.ipc.eventReceived.emit(
            {
                "protocol": PROTOCOL_VERSION,
                "type": "event",
                "event": "terminal.ready",
                "session_id": opened["sessionId"],
                "data": {},
            }
        )
        self.ipc.connected.discard(opened["sessionId"])

        duplicate = self.manager.open("192.0.2.10")

        self.assertFalse(duplicate["ok"])
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(self.processes[0].terminate_calls, 0)
        self.assertIsNotNone(self.manager.session_for_device("192.0.2.10"))

    def test_child_exit_is_disconnected_while_window_remains_open(self) -> None:
        opened = self.manager.open("192.0.2.10")
        session_id = opened["sessionId"]
        self.ipc.connect_session(session_id)
        for event, data in (
            ("terminal.ready", {}),
            ("child.started", {"pid": 8000}),
            ("child.exited", {"exit_code": 255}),
        ):
            self.ipc.eventReceived.emit(
                {
                    "protocol": PROTOCOL_VERSION,
                    "type": "event",
                    "event": event,
                    "session_id": session_id,
                    "data": data,
                }
            )

        self.assertEqual(self.manager.state_for_device("192.0.2.10"), "disconnected")

    def test_control_commands_are_allowlisted_and_title_is_sanitized(self) -> None:
        opened = self.manager.open("192.0.2.10")
        session_id = opened["sessionId"]
        self.ipc.connect_session(session_id)
        self.ipc.eventReceived.emit(
            {
                "protocol": PROTOCOL_VERSION,
                "type": "event",
                "event": "terminal.ready",
                "session_id": session_id,
                "data": {},
            }
        )

        self.assertTrue(self.manager.ping("192.0.2.10")["ok"])
        self.assertTrue(self.manager.get_info("192.0.2.10")["ok"])
        self.assertTrue(self.manager.set_title("192.0.2.10", "R1\n\x1btitle")["ok"])

        self.assertEqual(
            [command for _session, command, _data in self.ipc.commands[-3:]],
            ["session.ping", "session.get_info", "window.set_title"],
        )
        self.assertNotIn("\n", str(self.ipc.commands[-1][2]["title"]))
        self.assertNotIn("\x1b", str(self.ipc.commands[-1][2]["title"]))

    def test_process_exit_without_closed_event_is_error_and_cleans_registry(self) -> None:
        errors: list[tuple[str, str]] = []
        self.manager.terminalError.connect(
            lambda host, message: errors.append((host, message))
        )
        opened = self.manager.open("192.0.2.10")

        self.processes[0].finished.emit(9, QProcess.ExitStatus.CrashExit)

        self.assertEqual(self.manager.state_for_device("192.0.2.10"), "error")
        self.assertIsNone(self.manager.session_for_device("192.0.2.10"))
        self.assertNotIn(opened["sessionId"], self.ipc.registered)
        self.assertIn("unexpectedly", errors[-1][1])

    def test_normal_exit_does_not_race_terminal_closed_event(self) -> None:
        errors: list[tuple[str, str]] = []
        self.manager.terminalError.connect(
            lambda host, message: errors.append((host, message))
        )
        self.manager.open("192.0.2.10")

        self.processes[0].finished.emit(0, QProcess.ExitStatus.NormalExit)

        self.assertEqual(self.manager.state_for_device("192.0.2.10"), "closed")
        self.assertIsNone(self.manager.session_for_device("192.0.2.10"))
        self.assertEqual(errors, [])

    def test_failed_process_start_is_error_and_cleans_registry(self) -> None:
        opened = self.manager.open("192.0.2.10")

        self.processes[0].errorOccurred.emit(QProcess.ProcessError.FailedToStart)

        self.assertEqual(self.manager.state_for_device("192.0.2.10"), "error")
        self.assertIsNone(self.manager.session_for_device("192.0.2.10"))
        self.assertNotIn(opened["sessionId"], self.ipc.registered)

    def test_dev_mode_and_telnet_fail_closed_without_process(self) -> None:
        self.device["dev"] = 1
        blocked = self.manager.open("192.0.2.10")
        self.assertFalse(blocked["ok"])
        self.assertEqual(self.processes, [])

        self.device["dev"] = 0
        self.device["method"] = "telnet"
        unsupported = self.manager.open("192.0.2.10")
        self.assertFalse(unsupported["ok"])
        self.assertIn("OpenSSH", unsupported["message"])
        self.assertEqual(self.processes, [])


class OpenSshBuilderTests(unittest.TestCase):
    def test_cisco_ios_uses_credential_free_legacy_adapter_argv(self) -> None:
        with tempfile.NamedTemporaryFile() as database:
            command = build_terminal_command({
                "method": "ssh",
                "host": "192.0.2.10",
                "port": 22,
                "username": "admin",
                "password": "must-not-leak",
                "device_type": "cisco_ios",
                "db_path": database.name,
            })

        serialized = " ".join((command.program, *command.arguments))
        self.assertEqual(command.program, sys.executable)
        self.assertIn("interactive_ssh.py", serialized)
        self.assertIn("--host 192.0.2.10", serialized)
        self.assertNotIn("must-not-leak", serialized)

    def test_builder_rejects_injection_fields(self) -> None:
        with self.assertRaises(TerminalLaunchError):
            build_openssh_command(
                {"method": "ssh", "host": "router;touch /tmp/x", "port": 22, "username": "admin"}
            )
        with self.assertRaises(TerminalLaunchError):
            build_openssh_command(
                {
                    "method": "ssh",
                    "host": "router.example",
                    "port": 22,
                    "username": "root -oProxyCommand",
                }
            )
        with self.assertRaises(TerminalLaunchError):
            build_openssh_command(
                {"method": "ssh", "host": "router.example", "port": 70000, "username": "admin"}
            )


class NttpProtocolTests(unittest.TestCase):
    def test_json_line_round_trip_and_protocol_rejection(self) -> None:
        message = {
            "protocol": PROTOCOL_VERSION,
            "type": "event",
            "event": "terminal.ready",
            "session_id": "session-1",
            "device_id": "device-1",
            "data": {},
        }
        encoded = encode_message(message)
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertEqual(decode_line(encoded)["event"], "terminal.ready")

        invalid = json.dumps({**message, "protocol": "nttp/2"}).encode()
        with self.assertRaisesRegex(NttpProtocolError, "Unsupported"):
            decode_line(invalid)

    def test_invalid_json_unknown_event_and_size_are_rejected(self) -> None:
        with self.assertRaises(NttpProtocolError) as malformed:
            decode_line(b"not-json")
        self.assertEqual(malformed.exception.code, "INVALID_JSON")

        unknown = json.dumps(
            {
                "protocol": PROTOCOL_VERSION,
                "type": "event",
                "event": "terminal.output",
                "session_id": "session-1",
                "data": {},
            }
        ).encode()
        with self.assertRaises(NttpProtocolError) as event:
            decode_line(unknown)
        self.assertEqual(event.exception.code, "UNKNOWN_EVENT")

        with self.assertRaises(NttpProtocolError) as large:
            decode_line(b"x" * (MAX_MESSAGE_BYTES + 1))
        self.assertEqual(large.exception.code, "MESSAGE_TOO_LARGE")

    def test_set_title_rejects_control_characters(self) -> None:
        with self.assertRaises(NttpProtocolError) as invalid:
            encode_message(
                {
                    "protocol": PROTOCOL_VERSION,
                    "type": "command",
                    "command": "window.set_title",
                    "request_id": "req-1",
                    "session_id": "session-1",
                    "data": {"title": "R1\nunsafe"},
                }
            )
        self.assertEqual(invalid.exception.code, "INVALID_TITLE")


class NttpServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.socket_path = Path(self.tempdir.name) / "networktools" / "manager.sock"
        self.server = NttpServer(socket_path=self.socket_path)
        self.server.start()

    def tearDown(self) -> None:
        self.server.stop()
        self.app.processEvents()
        self.tempdir.cleanup()

    def _wait_until(self, condition: object, timeout: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if callable(condition) and condition():
                return True
            time.sleep(0.002)
        return False

    def test_private_socket_accepts_fragmented_registered_event(self) -> None:
        self.assertEqual(stat.S_IMODE(self.socket_path.stat().st_mode), 0o600)
        self.server.register_session("session-1")
        events: list[dict[str, object]] = []
        self.server.eventReceived.connect(events.append)
        client = QLocalSocket()
        client.connectToServer(str(self.socket_path))
        self.assertTrue(client.waitForConnected(1000))
        encoded = encode_message(
            {
                "protocol": PROTOCOL_VERSION,
                "type": "event",
                "event": "terminal.ready",
                "session_id": "session-1",
                "data": {"window_id": "w1"},
            }
        )

        split = len(encoded) // 2
        client.write(encoded[:split])
        client.flush()
        self.app.processEvents()
        self.assertEqual(events, [])
        client.write(encoded[split:])
        client.flush()

        self.assertTrue(self._wait_until(lambda: len(events) == 1))
        self.assertEqual(events[0]["event"], "terminal.ready")
        self.assertTrue(self.server.is_connected("session-1"))
        client.abort()
        client.deleteLater()

    def test_unknown_session_is_rejected(self) -> None:
        errors: list[tuple[str, str]] = []
        self.server.protocolError.connect(
            lambda code, message: errors.append((code, message))
        )
        client = QLocalSocket()
        client.connectToServer(str(self.socket_path))
        self.assertTrue(client.waitForConnected(1000))
        client.write(
            encode_message(
                {
                    "protocol": PROTOCOL_VERSION,
                    "type": "event",
                    "event": "terminal.started",
                    "session_id": "unregistered",
                    "data": {"pid": 1},
                }
            )
        )
        client.flush()

        self.assertTrue(self._wait_until(lambda: bool(errors)))
        self.assertEqual(errors[0][0], "UNKNOWN_SESSION")
        client.deleteLater()

    def test_command_response_and_timeout_are_correlated(self) -> None:
        self.server.register_session("session-1")
        client = QLocalSocket()
        client.connectToServer(str(self.socket_path))
        self.assertTrue(client.waitForConnected(1000))
        client.write(
            encode_message(
                {
                    "protocol": PROTOCOL_VERSION,
                    "type": "event",
                    "event": "terminal.ready",
                    "session_id": "session-1",
                    "data": {},
                }
            )
        )
        client.flush()
        self.assertTrue(self._wait_until(lambda: self.server.is_connected("session-1")))

        responses: list[dict[str, object]] = []
        timeouts: list[tuple[str, str, str]] = []
        self.server.responseReceived.connect(responses.append)
        self.server.requestTimedOut.connect(
            lambda session, request, command: timeouts.append(
                (session, request, command)
            )
        )
        request_id = self.server.send_command("session-1", "session.ping")
        self.assertIsNotNone(request_id)
        self.assertTrue(self._wait_until(lambda: client.bytesAvailable() > 0))
        command = json.loads(bytes(client.readAll()).decode("utf-8"))
        self.assertEqual(command["request_id"], request_id)
        client.write(
            encode_message(
                {
                    "protocol": PROTOCOL_VERSION,
                    "type": "response",
                    "request_id": request_id,
                    "session_id": "session-1",
                    "ok": True,
                    "data": {},
                }
            )
        )
        client.flush()
        self.assertTrue(self._wait_until(lambda: len(responses) == 1))

        timed_request = self.server.send_command(
            "session-1", "session.get_info", timeout_ms=5
        )
        self.assertTrue(self._wait_until(lambda: len(timeouts) == 1))
        self.assertEqual(timeouts[0], ("session-1", timed_request, "session.get_info"))
        client.abort()
        client.deleteLater()


if __name__ == "__main__":
    unittest.main()
