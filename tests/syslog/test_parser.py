import unittest

from features.syslog.parser import parse_message


class SyslogParserTests(unittest.TestCase):
    def test_cisco_message(self) -> None:
        row = parse_message(
            b"<189>%SYS-5-CONFIG_I: Configured from console",
            "192.168.1.1",
            "udp",
        )
        self.assertEqual(row.facility, "SYS")
        self.assertEqual(row.severity, 5)
        self.assertEqual(row.mnemonic, "CONFIG_I")
        self.assertEqual(row.message, "Configured from console")
        self.assertEqual(row.parse_status, "parsed")

    def test_malformed_message_is_retained(self) -> None:
        row = parse_message(
            b"not a formatted syslog message", "192.168.1.2", "tcp"
        )
        self.assertEqual(row.message, "not a formatted syslog message")
        self.assertEqual(row.raw_message, row.message)
        self.assertEqual(row.parse_status, "raw")


if __name__ == "__main__":
    unittest.main()
