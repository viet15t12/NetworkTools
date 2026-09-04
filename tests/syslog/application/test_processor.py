import unittest

from features.syslog.application.processor import SyslogProcessor


class _Lookup:
    def resolve_device_host(self, source_ip: str) -> str | None:
        return "router-1" if source_ip == "192.0.2.1" else None


class SyslogProcessorTests(unittest.TestCase):
    def test_parses_and_resolves_device(self) -> None:
        row = SyslogProcessor(_Lookup()).process(
            b"%OSPF-5-ADJCHG: Neighbor up", "192.0.2.1", "udp"
        )
        self.assertEqual(row.device_host, "router-1")
        self.assertEqual(row.cisco_facility, "OSPF")


if __name__ == "__main__":
    unittest.main()
