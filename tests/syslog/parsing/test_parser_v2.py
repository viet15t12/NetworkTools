from datetime import datetime
import unittest

from features.syslog.parsing.cisco import parse_cisco
from features.syslog.parsing.parser import parse_message
from features.syslog.parsing.pri import parse_pri
from features.syslog.parsing.timestamp import parse_timestamp


class SyslogParserV2Tests(unittest.TestCase):
    def test_pri_is_not_overwritten_by_cisco_facility(self) -> None:
        row = parse_message(
            b"<189>000013: Aug 22 19:32:10.039: %LINK-3-UPDOWN: Interface Gi0/1 down",
            "192.0.2.1", "udp",
        )
        self.assertEqual(row.syslog_pri, 189)
        self.assertEqual(row.syslog_facility, 23)
        self.assertEqual(row.cisco_facility, "LINK")
        self.assertEqual(row.sequence_number, 13)
        self.assertEqual(row.severity, 3)
        self.assertEqual(row.mnemonic, "UPDOWN")
        self.assertEqual(row.parse_status, "parsed")

    def test_unsynchronized_clock_and_milliseconds(self) -> None:
        result = parse_timestamp(
            "42: *Aug 22 19:32:10.039: %SYS-5-CONFIG_I: changed",
            now=datetime(2026, 1, 1),
        )
        self.assertEqual(result.sequence_number, 42)
        self.assertEqual(result.device_time, "2026-08-22T19:32:10.039000")
        self.assertTrue(result.clock_unsynchronized)

    def test_cisco_subfacility_is_separate(self) -> None:
        result = parse_cisco("%FACILITY-SUBFACILITY-4-MNEMONIC: details")
        self.assertIsNotNone(result)
        self.assertEqual(result.facility, "FACILITY")
        self.assertEqual(result.subfacility, "SUBFACILITY")
        self.assertEqual(result.message, "details")

    def test_common_cisco_facilities(self) -> None:
        facilities = (
            "LINK", "LINEPROTO", "SYS", "SEC_LOGIN", "SSH", "OSPF", "EIGRP",
            "BGP", "DHCP", "SPANTREE", "EC", "VLAN", "PORT_SECURITY",
        )
        for facility in facilities:
            with self.subTest(facility=facility):
                row = parse_message(
                    f"%{facility}-5-EVENT: test".encode(), "192.0.2.1", "udp"
                )
                self.assertEqual(row.cisco_facility, facility)
                self.assertEqual(row.message, "test")

    def test_invalid_pri_is_left_raw(self) -> None:
        result = parse_pri("<999>%SYS-5-CONFIG_I: value")
        self.assertIsNone(result.pri)
        self.assertTrue(result.remainder.startswith("<999>"))


if __name__ == "__main__":
    unittest.main()
