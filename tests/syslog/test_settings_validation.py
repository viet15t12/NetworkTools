import unittest
import json
from pathlib import Path
import tempfile

from features.syslog.settings import SyslogSettings, _local_ipv4_addresses, _validate_ip


class SyslogSettingsValidationTests(unittest.TestCase):
    def test_listener_always_enables_udp_and_tcp(self) -> None:
        settings = SyslogSettings()
        self.assertEqual(settings.protocol, "both")
        self.assertEqual(settings.listener_config().protocol, "both")

    def test_empty_advertised_ip_has_friendly_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Advertised/server IP is required"):
            _validate_ip("", "Advertised/server IP", allow_unspecified=False)

    def test_unspecified_bind_ip_is_allowed_for_listener(self) -> None:
        _validate_ip("0.0.0.0", "Bind IP", allow_unspecified=True)

    def test_detected_advertised_addresses_are_usable_ipv4(self) -> None:
        for value in _local_ipv4_addresses():
            self.assertNotIn(":", value)
            self.assertNotEqual(value, "0.0.0.0")
            self.assertFalse(value.startswith("127."))

    def test_settings_are_persisted_in_json_for_native_collector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "syslog.json"
            settings = SyslogSettings(settings_path=path)
            settings.bindIp = "127.0.0.1"
            settings.port = 15514
            settings.maxMessageBytes = 32768
            settings.maxTcpClients = 128

            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored["bind_ip"], "127.0.0.1")
            self.assertEqual(stored["port"], 15514)
            self.assertEqual(stored["protocol"], "both")
            self.assertEqual(stored["max_message_bytes"], 32768)
            self.assertEqual(stored["max_tcp_clients"], 128)
            config = settings.listener_config()
            self.assertEqual(config.max_message_bytes, 32768)
            self.assertEqual(config.max_tcp_clients, 128)


if __name__ == "__main__":
    unittest.main()
