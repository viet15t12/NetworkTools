import unittest
from datetime import datetime, timezone

from features.syslog.smart_filter import SmartFilterError, build_log_filters


class SmartFilterTests(unittest.TestCase):
    def test_combines_structured_controls_and_smart_keys(self) -> None:
        result = build_log_filters(
            {
                "host": "192.0.2.1",
                "severities": [5],
                "protocols": [],
                "from_time": "2026-08-26",
                "per_host": 0,
            },
            'host:192.0.2.10 last:20 severity:error,warning '
            'protocol:udp facility:LINK mnemonic:UPDOWN "Loopback 99"',
        )

        self.assertEqual(result["host"], "192.0.2.10")
        self.assertEqual(result["hosts"], ["192.0.2.10"])
        self.assertEqual(result["per_host"], 20)
        self.assertEqual(result["severities"], [3, 4])
        self.assertEqual(result["protocols"], ["udp"])
        self.assertEqual(result["facility"], "LINK")
        self.assertEqual(result["mnemonic"], "UPDOWN")
        self.assertEqual(result["search"], "Loopback 99")
        self.assertEqual(result["from_time"], "2026-08-26T00:00:00.000+00:00")

    def test_supports_relative_since_duration(self) -> None:
        result = build_log_filters(
            {}, "since:30m text:changed",
            now=datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["from_time"], "2026-08-26T17:30:00.000+00:00")
        self.assertEqual(result["search"], "changed")

    def test_supports_multiple_structured_and_smart_hosts(self) -> None:
        structured = build_log_filters(
            {"hosts": ["192.0.2.1", "192.0.2.2"]}, ""
        )
        smart = build_log_filters({}, "host:192.0.2.3,192.0.2.4")

        self.assertEqual(structured["hosts"], ["192.0.2.1", "192.0.2.2"])
        self.assertEqual(structured["host"], "")
        self.assertEqual(smart["hosts"], ["192.0.2.3", "192.0.2.4"])
        self.assertEqual(smart["host"], "")

    def test_rejects_unknown_keys_and_invalid_ranges(self) -> None:
        with self.assertRaisesRegex(SmartFilterError, "Unknown filter"):
            build_log_filters({}, "device:192.0.2.1")
        with self.assertRaisesRegex(SmartFilterError, "from time"):
            build_log_filters({}, "from:2026-08-27 to:2026-08-26")


if __name__ == "__main__":
    unittest.main()
