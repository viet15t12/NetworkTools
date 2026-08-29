"""Host-key replacement contracts for the legacy interactive SSH child."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import paramiko

from features.terminal.interactive_ssh import (
    _connect_with_host_key_confirmation,
    _fingerprint,
    _replace_changed_host_key,
)


class InteractiveSshHostKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected_key = paramiko.RSAKey.generate(1024)
        cls.received_key = paramiko.RSAKey.generate(1024)

    def _exception(self, hostname: str = "192.0.2.10") -> paramiko.BadHostKeyException:
        return paramiko.BadHostKeyException(
            hostname,
            self.received_key,
            self.expected_key,
        )

    def test_fingerprint_uses_sha256_display_format(self) -> None:
        fingerprint = _fingerprint(self.received_key)

        self.assertTrue(fingerprint.startswith("SHA256:"))
        self.assertNotIn("=", fingerprint)

    def test_confirmed_replacement_removes_old_key_and_saves_received_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            known_hosts = Path(directory) / "known_hosts"
            known_hosts.write_text(
                "# retained comment\n"
                f"192.0.2.10 {self.expected_key.get_name()} "
                f"{self.expected_key.get_base64()}\n",
                encoding="ascii",
            )

            _replace_changed_host_key(self._exception(), known_hosts)

            saved = paramiko.HostKeys(str(known_hosts)).lookup("192.0.2.10")
            self.assertIsNotNone(saved)
            self.assertEqual(
                saved[self.received_key.get_name()].asbytes(),
                self.received_key.asbytes(),
            )
            self.assertTrue(known_hosts.with_name("known_hosts.old").is_file())

    def test_replacement_stops_if_saved_key_changed_during_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            known_hosts = Path(directory) / "known_hosts"
            another_key = paramiko.RSAKey.generate(1024)
            original = (
                f"192.0.2.10 {another_key.get_name()} {another_key.get_base64()}\n"
            )
            known_hosts.write_text(original, encoding="ascii")

            with self.assertRaisesRegex(RuntimeError, "changed after the warning"):
                _replace_changed_host_key(self._exception(), known_hosts)

            self.assertEqual(known_hosts.read_text(encoding="ascii"), original)

    def test_cancel_does_not_replace_key_or_retry(self) -> None:
        mismatch = self._exception()
        with (
            patch(
                "features.terminal.interactive_ssh._connect",
                side_effect=mismatch,
            ) as connect,
            patch(
                "features.terminal.interactive_ssh._confirm_changed_host_key",
                return_value=False,
            ),
            patch("features.terminal.interactive_ssh._replace_changed_host_key") as replace,
        ):
            with self.assertRaisesRegex(RuntimeError, "cancelled"):
                _connect_with_host_key_confirmation(Path("workspace.db"), "192.0.2.10")

        connect.assert_called_once()
        replace.assert_not_called()

    def test_continue_replaces_key_and_retries_connection(self) -> None:
        mismatch = self._exception()
        connected = (object(), object())
        with (
            patch(
                "features.terminal.interactive_ssh._connect",
                side_effect=[mismatch, connected],
            ) as connect,
            patch(
                "features.terminal.interactive_ssh._confirm_changed_host_key",
                return_value=True,
            ),
            patch("features.terminal.interactive_ssh._replace_changed_host_key") as replace,
        ):
            result = _connect_with_host_key_confirmation(
                Path("workspace.db"), "192.0.2.10"
            )

        self.assertIs(result, connected)
        self.assertEqual(connect.call_count, 2)
        replace.assert_called_once_with(mismatch)


if __name__ == "__main__":
    unittest.main()
