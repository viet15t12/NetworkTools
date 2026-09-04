import unittest

from features.syslog.device_config.verifier import (
    interface_exists, verify_destination, verify_source_interface,
)


class SyslogVerifierTests(unittest.TestCase):
    def test_interface_alias_and_destination(self) -> None:
        self.assertTrue(interface_exists("GigabitEthernet0/0 192.0.2.1 up up", "Gi0/0"))
        output = (
            "logging host 192.0.2.100 transport udp port 5514\n"
            "logging source-interface GigabitEthernet0/0"
        )
        self.assertIsNone(verify_destination(
            output, "192.0.2.100", "udp", 5514, expected=True
        ))
        self.assertTrue(verify_source_interface(output, "Gi0/0"))


if __name__ == "__main__":
    unittest.main()
