from __future__ import annotations

import unittest
from ipaddress import IPv4Network
from unittest.mock import Mock, patch

from infrastructure.system.virtual_lab import (
    VirtualLabInfo,
    VirtualLabProbe,
    VirtualMachineEvidence,
    _lab_path_and_name,
    _node_is_running,
    _normalize_server_url,
    _platform_from_text,
    _process_evidence,
)


class _Response:
    def __init__(
        self,
        payload: dict,
        ok: bool = True,
        *,
        url: str = "",
        text: str = "",
        status_code: int = 200,
        headers: dict | None = None,
    ) -> None:
        self._payload = payload
        self.ok = ok
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError("request failed")


class _Session:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def post(self, url: str, **_kwargs) -> _Response:
        self.urls.append(url)
        return _Response({"status": "success"})

    def get(self, url: str, **_kwargs) -> _Response:
        self.urls.append(url)
        if url.endswith("/api/auth"):
            return _Response({"data": {"lab": "/Training/OSPF.unl"}})
        if url.endswith("/nodes"):
            return _Response(
                {
                    "data": {
                        "1": {"name": "R1", "status": 2},
                        "2": {"name": "R2", "status": 0},
                    }
                }
            )
        return _Response({"data": {"name": "OSPF Practice"}})


class _DiscoverySession:
    def get(self, url: str, **_kwargs) -> _Response:
        if url == "http://192.168.56.10":
            return _Response({}, url=url, text='<html data-ng-app="unlMainApp">')
        if url == "http://192.168.56.11":
            return _Response(
                {},
                url=url,
                status_code=301,
                headers={"Location": "/store/public/admin/main/view"},
            )
        raise OSError("unreachable")


class _UnbrandedDiscoverySession:
    def get(self, url: str, **_kwargs) -> _Response:
        return _Response(
            {},
            url=url,
            status_code=302,
            headers={"Location": "/login"},
        )


class VirtualLabHelperTests(unittest.TestCase):
    def test_platform_signatures_distinguish_eve_and_pnetlab(self) -> None:
        self.assertEqual(_platform_from_text("<title>EVE-NG</title>"), "EVE-NG")
        self.assertEqual(
            _platform_from_text('<html data-ng-app="unlMainApp"><title>EVE | Login</title>'),
            "EVE-NG",
        )
        self.assertEqual(_platform_from_text("Welcome to PNETLab"), "PNETLab")
        self.assertEqual(
            _platform_from_text("Redirecting to /store/public/admin/main/view"),
            "PNETLab",
        )

    def test_process_detection_covers_common_cross_platform_engines(self) -> None:
        cases = (
            (
                "vmware-vmx.exe",
                ["vmware-vmx.exe", "C:/VMs/EVE-NG/EVE-NG.vmx"],
                ("VMware", "EVE-NG"),
            ),
            (
                "VirtualBoxVM",
                ["VirtualBoxVM", "--comment", "PNETLab 4", "--startvm", "uuid"],
                ("VirtualBox", "PNETLab"),
            ),
            (
                "qemu-system-x86_64",
                ["qemu-system-x86_64", "-name", "Cisco Modeling Labs CML2"],
                ("QEMU/KVM", "Cisco CML"),
            ),
            (
                "gns3server",
                ["gns3server", "--host", "127.0.0.1", "--port", "3080"],
                ("GNS3", "GNS3"),
            ),
        )
        for process_name, command, expected in cases:
            with self.subTest(process=process_name):
                evidence = _process_evidence(process_name, command)
                self.assertIsNotNone(evidence)
                self.assertEqual((evidence.engine, evidence.platform), expected)

        self.assertIsNone(_process_evidence("notepad.exe", ["notepad.exe"]))

    def test_server_url_is_normalized_and_restricted_to_http(self) -> None:
        self.assertEqual(_normalize_server_url("192.168.56.128/"), "http://192.168.56.128")
        self.assertEqual(_normalize_server_url("https://eve.local/lab"), "https://eve.local")
        self.assertEqual(_normalize_server_url("file:///tmp/lab"), "")

    def test_node_status_requires_a_running_value(self) -> None:
        self.assertTrue(_node_is_running(2))
        self.assertTrue(_node_is_running("running"))
        self.assertFalse(_node_is_running(0))
        self.assertFalse(_node_is_running("stopped"))

    @patch("infrastructure.system.virtual_lab._active_vm_evidences")
    def test_cancelled_probe_returns_without_starting_discovery(self, active_evidences) -> None:
        probe = VirtualLabProbe()
        probe.cancel()

        self.assertEqual(probe.inspect_all(), ())
        active_evidences.assert_not_called()

    def test_lab_path_is_usable_for_api_and_display(self) -> None:
        self.assertEqual(_lab_path_and_name("/Training/OSPF.unl"), ("/Training/OSPF.unl", "OSPF"))
        self.assertEqual(
            _lab_path_and_name({"path": "/Training/BGP.unl", "name": "BGP Lab"}),
            ("/Training/BGP.unl", "BGP Lab"),
        )

    def test_authenticated_api_marks_only_running_nodes_active(self) -> None:
        probe = VirtualLabProbe()
        session = _Session()
        probe._session = session
        fallback = VirtualLabInfo(
            state="idle",
            platform="EVE-NG",
            server_ip="192.168.56.128",
            server_url="https://192.168.56.128",
        )

        result = probe._api_info(
            fallback.server_url,
            fallback.platform,
            "admin",
            "secret",
            fallback,
        )

        self.assertEqual(result.state, "active")
        self.assertTrue(result.is_active)
        self.assertEqual(result.lab_name, "OSPF Practice")
        self.assertEqual(result.running_node_count, 1)
        self.assertTrue(
            any(url.endswith("/api/labs/Training/OSPF.unl/nodes") for url in session.urls)
        )

    @patch("infrastructure.system.virtual_lab._neighbor_candidates")
    @patch("infrastructure.system.virtual_lab._host_private_networks")
    @patch("infrastructure.system.virtual_lab._lab_adapters")
    @patch("infrastructure.system.virtual_lab._active_vm_evidences")
    def test_inspect_all_keeps_eve_and_pnetlab_as_separate_servers(
        self,
        active_evidences,
        lab_adapters,
        private_networks,
        neighbor_candidates,
    ) -> None:
        active_evidences.return_value = [
            VirtualMachineEvidence("QEMU/KVM", "EVE-NG", "eve.xml", "EVE"),
            VirtualMachineEvidence("QEMU/KVM", "PNETLab", "pnet.xml", "PNET"),
        ]
        lab_adapters.return_value = []
        private_networks.return_value = [IPv4Network("192.168.56.0/24")]
        neighbor_candidates.return_value = ["192.168.56.10", "192.168.56.11"]

        probe = VirtualLabProbe()

        def reachable(_configured, _candidates, expected_platform="", **_kwargs):
            if expected_platform == "EVE-NG":
                return "http://192.168.56.10", "EVE-NG"
            if expected_platform == "PNETLab":
                return "http://192.168.56.11", "PNETLab"
            return "", ""

        probe._reachable_server = Mock(side_effect=reachable)
        results = probe.inspect_all()

        self.assertEqual([result.platform for result in results], ["EVE-NG", "PNETLab"])
        self.assertEqual(
            [result.server_ip for result in results],
            ["192.168.56.10", "192.168.56.11"],
        )
        self.assertTrue(all(result.state == "online" for result in results))

    @patch("infrastructure.system.virtual_lab._vmrun_guest_ip")
    @patch("infrastructure.system.virtual_lab._neighbor_candidates")
    @patch("infrastructure.system.virtual_lab._host_private_networks")
    @patch("infrastructure.system.virtual_lab._lab_adapters")
    @patch("infrastructure.system.virtual_lab._active_vm_evidences")
    def test_inspect_all_trusts_urls_for_the_hypervisor_reported_guest_ip(
        self,
        active_evidences,
        lab_adapters,
        private_networks,
        neighbor_candidates,
        vmrun_guest_ip,
    ) -> None:
        active_evidences.return_value = [
            VirtualMachineEvidence("VMware", "EVE-NG", "eve.vmx", "EVE-NG")
        ]
        lab_adapters.return_value = []
        private_networks.return_value = []
        neighbor_candidates.return_value = []
        vmrun_guest_ip.return_value = "192.168.56.128"
        probe = VirtualLabProbe()

        def reachable(_configured, _candidates, server_hints=(), **_kwargs):
            if server_hints:
                return "http://192.168.56.128", "EVE-NG"
            return "", ""

        probe._reachable_server = Mock(side_effect=reachable)
        results = probe.inspect_all()

        first_call = probe._reachable_server.call_args_list[0]
        self.assertEqual(
            first_call.kwargs["server_hints"][:2],
            ("http://192.168.56.128", "https://192.168.56.128"),
        )
        self.assertEqual(results[0].state, "online")

    def test_expected_platforms_do_not_claim_each_others_server(self) -> None:
        probe = VirtualLabProbe()
        probe._session = _DiscoverySession()
        candidates = ["192.168.56.10", "192.168.56.11"]

        eve_url, eve_platform = probe._reachable_server(
            "", candidates, expected_platform="EVE-NG"
        )
        pnet_url, pnet_platform = probe._reachable_server(
            "",
            candidates,
            expected_platform="PNETLab",
            excluded_urls={eve_url, "192.168.56.10"},
        )

        self.assertEqual((eve_url, eve_platform), ("http://192.168.56.10", "EVE-NG"))
        self.assertEqual(
            (pnet_url, pnet_platform),
            ("http://192.168.56.11", "PNETLab"),
        )

    def test_vm_guest_hint_accepts_ready_server_without_legacy_html_signature(self) -> None:
        probe = VirtualLabProbe()
        probe._session = _UnbrandedDiscoverySession()

        untrusted_url, _platform = probe._reachable_server(
            "",
            ["192.168.56.128"],
            expected_platform="EVE-NG",
        )
        trusted_url, platform = probe._reachable_server(
            "",
            [],
            expected_platform="EVE-NG",
            server_hints=("http://192.168.56.128",),
        )

        self.assertEqual(untrusted_url, "")
        self.assertEqual((trusted_url, platform), ("http://192.168.56.128", "EVE-NG"))


if __name__ == "__main__":
    unittest.main()
