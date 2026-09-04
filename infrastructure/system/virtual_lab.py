"""Best-effort discovery and API monitoring for local virtual lab servers."""

from __future__ import annotations

import os
import re
import shutil
import socket
import sys
import threading
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_interface
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

from .network_info import _lab_interface_label, _lab_platform_for_interface, _run_text_command


@dataclass(frozen=True)
class VirtualLabInfo:
    state: str = "offline"
    platform: str = ""
    server_ip: str = ""
    server_url: str = ""
    lab_name: str = ""
    running_node_count: int = 0
    adapter_name: str = ""
    detail: str = "No running virtual lab was detected."

    @property
    def is_active(self) -> bool:
        return self.state == "active"

    def as_qml_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "platform": self.platform,
            "serverIp": self.server_ip,
            "serverUrl": self.server_url,
            "labName": self.lab_name,
            "runningNodeCount": self.running_node_count,
            "adapterName": self.adapter_name,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class VirtualMachineEvidence:
    engine: str
    platform: str = ""
    vm_path: str = ""
    name: str = ""
    server_hints: tuple[str, ...] = ()


def _platform_from_text(value: str) -> str:
    normalized = value.casefold()
    if any(
        marker in normalized
        for marker in (
            "pnetlab",
            "pnet lab",
            "pnet_",
            "/store/public/admin/main/view",
            "/store/public/auth/login/license",
        )
    ):
        return "PNETLab"
    if any(
        marker in normalized
        for marker in (
            "eve-ng",
            "eve_ng",
            "unetlab",
            "unlmainapp",
            "'eve | '",
            '"eve | "',
        )
    ):
        return "EVE-NG"
    if "gns3" in normalized:
        return "GNS3"
    if any(marker in normalized for marker in ("cisco modeling labs", "cml2", "virl")):
        return "Cisco CML"
    if "containerlab" in normalized:
        return "Containerlab"
    if "ensp" in normalized:
        return "Huawei eNSP"
    return ""


def _normalize_server_url(value: str) -> str:
    text = (value or "").strip().rstrip("/")
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{parsed.scheme}://{host}{port}"


def _server_ip_from_url(server_url: str) -> str:
    hostname = urlparse(server_url).hostname or ""
    try:
        return str(ip_address(hostname))
    except ValueError:
        try:
            return socket.gethostbyname(hostname)
        except OSError:
            return hostname


def _node_is_running(raw_status: Any) -> bool:
    if isinstance(raw_status, bool):
        return raw_status
    if isinstance(raw_status, (int, float)):
        return raw_status > 0
    return str(raw_status or "").strip().casefold() in {
        "1", "2", "running", "started", "starting", "on",
    }


def _lab_path_and_name(raw_lab: Any) -> tuple[str, str]:
    if isinstance(raw_lab, dict):
        path = unquote(str(raw_lab.get("path") or raw_lab.get("file") or raw_lab.get("filename") or ""))
        name = str(raw_lab.get("name") or "")
        return path, name
    path = unquote(str(raw_lab or "").strip())
    return path, Path(path).stem if path else ""


def _process_evidence(name: str, command: list[str]) -> VirtualMachineEvidence | None:
    """Classify one Windows/Linux/macOS process without OS-specific APIs."""
    normalized_name = (name or "").casefold()
    engine_names = {
        "vmware-vmx",
        "vmware-vmx.exe",
        "virtualboxvm",
        "virtualboxvm.exe",
        "vboxheadless",
        "vboxheadless.exe",
        "prl_vm_app",
    }
    gns3_names = {"gns3", "gns3.exe", "gns3server", "gns3server.exe"}
    is_vm_engine = normalized_name in engine_names or normalized_name.startswith(
        ("qemu-system", "qemu-kvm")
    )
    is_gns3 = normalized_name in gns3_names
    if not is_vm_engine and not is_gns3:
        return None

    joined = " ".join(command)
    platform = "GNS3" if is_gns3 else _platform_from_text(joined)
    vm_path = next(
        (
            part
            for part in command
            if part.casefold().endswith((".vmx", ".vbox", ".xml"))
        ),
        "",
    )
    if not platform and vm_path:
        try:
            platform = _platform_from_text(
                Path(vm_path).read_text(encoding="utf-8", errors="ignore")
            )
        except OSError:
            pass
    engine = (
        "VMware"
        if normalized_name in {"vmware-vmx", "vmware-vmx.exe"}
        else "VirtualBox"
        if normalized_name in {
            "virtualboxvm",
            "virtualboxvm.exe",
            "vboxheadless",
            "vboxheadless.exe",
        }
        else "Parallels"
        if normalized_name == "prl_vm_app"
        else "GNS3"
        if is_gns3
        else "QEMU/KVM"
    )
    hints: tuple[str, ...] = ()
    if is_gns3:
        host = "127.0.0.1"
        port = "3080"
        for option, default in (("--host", host), ("--port", port)):
            try:
                value = command[command.index(option) + 1]
            except (ValueError, IndexError):
                value = default
            if option == "--host":
                host = "127.0.0.1" if value in {"0.0.0.0", "::"} else value
            else:
                port = value
        hints = (f"http://{host}:{port}/v2/version",)
    display_name = Path(vm_path).stem if vm_path else platform or engine
    if engine == "VirtualBox":
        for option in ("--comment", "--startvm"):
            try:
                display_name = command[command.index(option) + 1]
                break
            except (ValueError, IndexError):
                continue
    return VirtualMachineEvidence(
        engine=engine,
        platform=platform,
        vm_path=vm_path,
        name=display_name,
        server_hints=hints,
    )


def _active_vm_evidences() -> list[VirtualMachineEvidence]:
    """Return every recognizable lab VM/server process on the local host."""
    try:
        import psutil  # type: ignore
    except Exception:
        return []

    evidences: list[VirtualMachineEvidence] = []
    for process in psutil.process_iter(("name", "cmdline")):
        try:
            name = str(process.info.get("name") or "")
            command = [str(part) for part in (process.info.get("cmdline") or [])]
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        evidence = _process_evidence(name, command)
        if evidence is None:
            continue
        if evidence not in evidences:
            evidences.append(evidence)

    if os.name == "nt":
        hyper_v_output = _run_text_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Get-VM | Where-Object State -eq 'Running' | ForEach-Object { \"$($_.Name)|$($_.State)\" }",
            ],
            timeout=2.0,
        )
        for line in hyper_v_output.splitlines():
            vm_name = line.split("|", 1)[0].strip()
            platform = _platform_from_text(vm_name)
            if platform:
                evidence = VirtualMachineEvidence("Hyper-V", platform, name=vm_name)
                if evidence not in evidences:
                    evidences.append(evidence)
    elif sys.platform.startswith("linux"):
        for vm_name in _run_text_command(["virsh", "list", "--name"], timeout=2.0).splitlines():
            vm_name = vm_name.strip()
            platform = _platform_from_text(vm_name)
            if platform:
                evidence = VirtualMachineEvidence("KVM/libvirt", platform, name=vm_name)
                if evidence not in evidences:
                    evidences.append(evidence)
    return evidences


def _active_vm_evidence() -> tuple[bool, str, str]:
    """Compatibility wrapper returning the first detected VM evidence."""
    evidences = _active_vm_evidences()
    if not evidences:
        return False, "", ""
    first = evidences[0]
    return True, first.platform, first.vm_path


def _lab_adapters() -> list[tuple[str, str, list[IPv4Network]]]:
    try:
        import psutil  # type: ignore
    except Exception:
        return []
    try:
        stats = psutil.net_if_stats()
        addresses = psutil.net_if_addrs()
    except Exception:
        return []

    found: list[tuple[str, str, list[IPv4Network]]] = []
    for name, entries in addresses.items():
        platform = _lab_platform_for_interface(name)
        if not platform or not stats.get(name) or not stats[name].isup:
            continue
        networks: list[IPv4Network] = []
        for entry in entries:
            if entry.family != socket.AF_INET or not entry.netmask:
                continue
            try:
                networks.append(ip_interface(f"{entry.address}/{entry.netmask}").network)
            except ValueError:
                continue
        found.append((name, platform, networks))
    return found


def _neighbor_candidates(networks: list[IPv4Network]) -> list[str]:
    if not networks:
        return []
    candidates: set[IPv4Address] = set()

    try:
        import psutil  # type: ignore

        for connection in psutil.net_connections(kind="inet"):
            remote = connection.raddr
            if not remote:
                continue
            raw_ip = remote.ip if hasattr(remote, "ip") else remote[0]
            try:
                candidate = ip_address(raw_ip)
            except ValueError:
                continue
            if isinstance(candidate, IPv4Address) and any(candidate in network for network in networks):
                candidates.add(candidate)
    except Exception:
        pass

    arp_output = _run_text_command(["arp", "-a"], timeout=1.0)
    if os.name != "nt":
        arp_output += "\n" + _run_text_command(["ip", "neigh", "show"], timeout=1.0)

    local_addresses: set[IPv4Address] = set()
    try:
        import psutil  # type: ignore

        for entries in psutil.net_if_addrs().values():
            for entry in entries:
                if entry.family == socket.AF_INET:
                    local_addresses.add(IPv4Address(entry.address))
    except Exception:
        pass

    for raw_ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", arp_output):
        try:
            candidate = ip_address(raw_ip)
        except ValueError:
            continue
        if (
            isinstance(candidate, IPv4Address)
            and candidate not in local_addresses
            and any(
                candidate in network
                and candidate not in {network.network_address, network.broadcast_address}
                for network in networks
            )
        ):
            candidates.add(candidate)

    return [str(candidate) for candidate in sorted(candidates) if not candidate.is_multicast][:8]


def _host_private_networks() -> list[IPv4Network]:
    """Include physical subnets so Bridged VMs can be found on every OS."""
    try:
        import psutil  # type: ignore
    except Exception:
        return []
    networks: list[IPv4Network] = []
    try:
        address_groups = psutil.net_if_addrs().values()
    except Exception:
        return []
    for entries in address_groups:
        for entry in entries:
            if entry.family != socket.AF_INET or not entry.netmask:
                continue
            try:
                interface = ip_interface(f"{entry.address}/{entry.netmask}")
            except ValueError:
                continue
            if interface.ip.is_private and not interface.ip.is_loopback and interface.network not in networks:
                networks.append(interface.network)
    return networks


def _vbox_guest_ip(vm_name: str) -> str:
    executable = shutil.which("VBoxManage") or shutil.which("VBoxManage.exe")
    if not executable or not vm_name:
        return ""
    output = _run_text_command(
        [executable, "guestproperty", "get", vm_name, "/VirtualBox/GuestInfo/Net/0/V4/IP"],
        timeout=2.0,
    )
    for raw_ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", output):
        try:
            candidate = ip_address(raw_ip)
        except ValueError:
            continue
        if isinstance(candidate, IPv4Address) and not candidate.is_loopback:
            return str(candidate)
    return ""


def _vmrun_guest_ip(vm_path: str) -> str:
    if not vm_path:
        return ""
    executable = shutil.which("vmrun")
    if not executable and os.name == "nt":
        install_roots = (
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramFiles(x86)", ""),
        )
        for root in install_roots:
            candidate = Path(root) / "VMware" / "VMware Workstation" / "vmrun.exe"
            if root and candidate.is_file():
                executable = str(candidate)
                break
    if not executable:
        return ""
    output = _run_text_command(
        [executable, "getGuestIPAddress", vm_path, "-wait"],
        timeout=3.0,
    )
    for raw_ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", output):
        try:
            candidate = ip_address(raw_ip)
        except ValueError:
            continue
        if isinstance(candidate, IPv4Address) and not candidate.is_loopback:
            return str(candidate)
    return ""


def _guest_server_hints(server_ip: str, platform: str) -> tuple[str, str]:
    """Return root URLs for a guest IP obtained from its owning hypervisor."""
    primary, secondary = (
        ("https", "http") if platform == "Cisco CML" else ("http", "https")
    )
    return f"{primary}://{server_ip}", f"{secondary}://{server_ip}"


class VirtualLabProbe:
    """Stateful probe that keeps one API session between polling rounds."""

    def __init__(self) -> None:
        self._session: Any = None
        self._authenticated_for: tuple[str, str, str] | None = None
        self._cancel_event = threading.Event()

    def reset_cancellation(self) -> None:
        """Prepare the reusable probe for another polling round."""
        self._cancel_event.clear()

    def cancel(self) -> None:
        """Stop discovery between bounded I/O calls during app shutdown."""
        self._cancel_event.set()
        if self._session is not None:
            close = getattr(self._session, "close", None)
            if callable(close):
                close()

    def _requests_session(self):
        if self._session is None:
            import requests
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self._session = requests.Session()
            self._session.headers.update({"Accept": "application/json", "User-Agent": "CAMS/VirtualLabMonitor"})
        return self._session

    def _reachable_server(
        self,
        configured_url: str,
        candidates: list[str],
        expected_platform: str = "",
        server_hints: tuple[str, ...] = (),
        excluded_urls: set[str] | None = None,
    ) -> tuple[str, str]:
        excluded = excluded_urls or set()
        if configured_url:
            urls = [configured_url]
        else:
            urls = list(server_hints)
            for candidate in candidates:
                if expected_platform == "GNS3":
                    urls.append(f"http://{candidate}:3080")
                protocols = ("https", "http") if expected_platform == "Cisco CML" else ("http", "https")
                urls.extend(f"{protocol}://{candidate}" for protocol in protocols)
        session = self._requests_session()
        for url in urls:
            if self._cancel_event.is_set():
                break
            normalized_candidate = _normalize_server_url(url)
            candidate_ip = _server_ip_from_url(normalized_candidate) if normalized_candidate else ""
            if normalized_candidate in excluded or candidate_ip in excluded:
                continue
            try:
                response = session.get(
                    url,
                    timeout=(
                        1.0
                        if configured_url or expected_platform == "Cisco CML" or url in server_hints
                        else 0.4
                    ),
                    verify=False,
                    # PNETLab first redirects to a local /store route and then
                    # to authen.pnetlab.com. Discovery only needs the local
                    # response and must retain the VM's address for Click to open.
                    allow_redirects=False,
                )
            except Exception:
                continue
            if response.status_code >= 500:
                continue
            sample = (
                f"{response.url}\n"
                f"{response.headers.get('Location', '')}\n"
                f"{response.text[:65536]}"
            )
            platform = _platform_from_text(sample)
            if expected_platform and platform and platform != expected_platform:
                continue
            trusted_hint = bool(expected_platform and url in server_hints)
            if configured_url or platform or trusted_hint:
                return normalized_candidate or url, platform or expected_platform
        return "", ""

    def _api_info(
        self,
        server_url: str,
        platform: str,
        username: str,
        password: str,
        fallback: VirtualLabInfo,
    ) -> VirtualLabInfo:
        if not username or not password:
            return fallback
        session = self._requests_session()
        signature = (server_url, username, password)
        try:
            if self._authenticated_for != signature:
                response = session.post(
                    f"{server_url}/api/auth/login",
                    json={"username": username, "password": password, "html5": "0"},
                    timeout=1.5,
                    verify=False,
                )
                if not response.ok or response.json().get("status") != "success":
                    return VirtualLabInfo(**{**fallback.__dict__, "detail": "Server is online, but API authentication failed."})
                self._authenticated_for = signature

            auth_response = session.get(f"{server_url}/api/auth", timeout=1.2, verify=False)
            auth_response.raise_for_status()
            auth_payload = auth_response.json()
            auth_data = auth_payload.get("data") or {}
            lab_path, lab_name = _lab_path_and_name(auth_data.get("lab"))
            if not lab_path:
                return VirtualLabInfo(
                    **{
                        **fallback.__dict__,
                        "state": "idle",
                        "detail": "API authenticated; no current lab or running node was detected.",
                    }
                )

            encoded_path = quote(lab_path.strip("/"), safe="/")
            lab_endpoint = f"{server_url}/api/labs/{encoded_path}"
            lab_response = session.get(lab_endpoint, timeout=1.2, verify=False)
            if lab_response.ok:
                lab_data = lab_response.json().get("data") or {}
                lab_name = str(lab_data.get("name") or lab_name)

            nodes_response = session.get(f"{lab_endpoint}/nodes", timeout=1.2, verify=False)
            nodes = (nodes_response.json().get("data") or {}) if nodes_response.ok else {}
            node_values = nodes.values() if isinstance(nodes, dict) else nodes
            running = sum(1 for node in node_values if isinstance(node, dict) and _node_is_running(node.get("status")))
            state = "active" if running else "idle"
            detail = f"{lab_name or 'Lab'}: {running} node(s) running."
            return VirtualLabInfo(
                state=state,
                platform=platform,
                server_ip=fallback.server_ip,
                server_url=server_url,
                lab_name=lab_name,
                running_node_count=running,
                adapter_name=fallback.adapter_name,
                detail=detail,
            )
        except Exception:
            self._authenticated_for = None
            return VirtualLabInfo(**{**fallback.__dict__, "detail": "Server is online, but its lab API did not respond."})

    def _online_info(
        self,
        reachable_url: str,
        platform: str,
        adapter_name: str,
        username: str = "",
        password: str = "",
    ) -> VirtualLabInfo:
        fallback = VirtualLabInfo(
            state="online",
            platform=platform or "Virtual Lab",
            server_ip=_server_ip_from_url(reachable_url),
            server_url=reachable_url,
            adapter_name=_lab_interface_label(adapter_name),
            detail="The lab server is online. Enter API credentials to detect the current lab and running nodes.",
        )
        if platform in {"EVE-NG", "PNETLab"}:
            return self._api_info(reachable_url, fallback.platform, username.strip(), password, fallback)
        return fallback

    def inspect_all(
        self,
        server_url: str = "",
        username: str = "",
        password: str = "",
    ) -> tuple[VirtualLabInfo, ...]:
        if self._cancel_event.is_set():
            return ()
        configured_url = _normalize_server_url(server_url)
        evidences = _active_vm_evidences()
        adapters = _lab_adapters()
        adapter_name = adapters[0][0] if adapters else ""
        networks = [network for _name, _platform, items in adapters for network in items]
        for network in _host_private_networks():
            if network not in networks:
                networks.append(network)
        shared_candidates = _neighbor_candidates(networks)
        claimed_urls: set[str] = set()
        results: list[VirtualLabInfo] = []
        configured_ip = _server_ip_from_url(configured_url) if configured_url else ""

        for evidence in evidences:
            if self._cancel_event.is_set():
                break
            candidates: list[str] = []
            evidence_hints = list(evidence.server_hints)
            if evidence.engine == "VMware":
                guest_ip = _vmrun_guest_ip(evidence.vm_path)
                if guest_ip:
                    candidates.append(guest_ip)
                    evidence_hints[0:0] = _guest_server_hints(
                        guest_ip, evidence.platform
                    )
            elif evidence.engine == "VirtualBox":
                guest_ip = _vbox_guest_ip(evidence.name)
                if guest_ip:
                    candidates.append(guest_ip)
                    evidence_hints[0:0] = _guest_server_hints(
                        guest_ip, evidence.platform
                    )
            candidates.extend(
                candidate for candidate in shared_candidates if candidate not in candidates
            )
            reachable_url, detected_platform = self._reachable_server(
                "",
                candidates,
                expected_platform=evidence.platform,
                server_hints=tuple(evidence_hints),
                excluded_urls=claimed_urls,
            )
            platform = detected_platform or evidence.platform
            if reachable_url:
                claimed_urls.add(reachable_url)
                claimed_urls.add(_server_ip_from_url(reachable_url))
                use_credentials = bool(
                    configured_url
                    and _server_ip_from_url(reachable_url) == configured_ip
                )
                results.append(
                    self._online_info(
                        reachable_url,
                        platform,
                        adapter_name,
                        username if use_credentials else "",
                        password if use_credentials else "",
                    )
                )
            elif platform:
                results.append(
                    VirtualLabInfo(
                        state="starting",
                        platform=platform,
                        adapter_name=_lab_interface_label(adapter_name),
                        detail=f"{evidence.name or platform} is running, but its web server is not reachable yet.",
                    )
                )

        # A server can be reachable even when its hypervisor is remote or the
        # process list is unavailable. Fingerprint every remaining neighbor and
        # retain up to four additional lab platforms.
        for _index in range(4):
            if self._cancel_event.is_set():
                break
            reachable_url, detected_platform = self._reachable_server(
                "",
                shared_candidates,
                excluded_urls=claimed_urls,
            )
            if not reachable_url or not detected_platform:
                break
            claimed_urls.add(reachable_url)
            claimed_urls.add(_server_ip_from_url(reachable_url))
            results.append(
                self._online_info(
                    reachable_url,
                    detected_platform,
                    adapter_name,
                    username if _server_ip_from_url(reachable_url) == configured_ip else "",
                    password if _server_ip_from_url(reachable_url) == configured_ip else "",
                )
            )

        claimed_ips = {info.server_ip for info in results if info.server_ip}
        if configured_url and configured_ip not in claimed_ips:
            reachable_url, detected_platform = self._reachable_server(
                configured_url,
                [],
                excluded_urls=claimed_urls,
            )
            if reachable_url:
                results.append(
                    self._online_info(
                        reachable_url,
                        detected_platform,
                        adapter_name,
                        username,
                        password,
                    )
                )

        unique: dict[str, VirtualLabInfo] = {}
        for index, info in enumerate(results):
            key = info.server_ip or info.server_url or f"{info.platform}|{index}"
            unique.setdefault(key, info)
        return tuple(unique.values())

    def inspect(self, server_url: str = "", username: str = "", password: str = "") -> VirtualLabInfo:
        """Compatibility view selecting the most useful item from inspect_all()."""
        results = self.inspect_all(server_url, username, password)
        if not results:
            return VirtualLabInfo()
        priority = {"active": 0, "idle": 1, "online": 2, "starting": 3}
        return min(results, key=lambda item: priority.get(item.state, 9))


__all__ = [
    "VirtualLabInfo",
    "VirtualLabProbe",
    "VirtualMachineEvidence",
    "_active_vm_evidences",
    "_lab_path_and_name",
    "_node_is_running",
    "_normalize_server_url",
    "_platform_from_text",
    "_process_evidence",
]
