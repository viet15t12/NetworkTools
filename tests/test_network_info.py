from __future__ import annotations

import unittest

from infrastructure.system.network_info import (
    _connection_type_for_interface,
    _lab_interface_label,
    _lab_platform_for_interface,
)


class NetworkInfoClassificationTests(unittest.TestCase):
    def test_virtual_lab_adapters_are_identified_by_platform(self) -> None:
        cases = {
            "VMware Network Adapter VMnet8": "VMware",
            "pnet0": "PNETLab",
            "virl-management": "Cisco CML",
            "eNSP Host Adapter": "Huawei eNSP",
            "gns3-ubridge0": "GNS3",
            "vboxnet0": "VirtualBox",
            "vEthernet (Lab)": "Hyper-V",
            "virbr0": "KVM/libvirt",
        }
        for interface_name, platform in cases.items():
            with self.subTest(interface=interface_name):
                self.assertEqual(_lab_platform_for_interface(interface_name), platform)
                self.assertEqual(_connection_type_for_interface(interface_name), "lab")

    def test_linux_predictable_interface_names_are_classified(self) -> None:
        self.assertEqual(_connection_type_for_interface("wlp2s0"), "wifi")
        self.assertEqual(_connection_type_for_interface("enx001122334455"), "ethernet")

    def test_vendor_adapter_names_are_compact_for_the_status_bar(self) -> None:
        self.assertEqual(_lab_interface_label("VMware Network Adapter VMnet8"), "VMnet8")
        self.assertEqual(_lab_interface_label("pnet0"), "pnet0")

    def test_vpn_keeps_priority_over_virtual_lab_markers(self) -> None:
        self.assertEqual(_connection_type_for_interface("vmware-wireguard-vpn"), "vpn")


if __name__ == "__main__":
    unittest.main()
