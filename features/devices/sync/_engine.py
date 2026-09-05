from __future__ import annotations

import re
from infrastructure.database import sqlcipher as sqlite3
from dataclasses import dataclass, field
from ipaddress import IPv4Address
from typing import Any


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class ParsedRouterConfig:
    hostname: str = ""
    interfaces: list[dict[str, Any]] = field(default_factory=list)
    static_routes: list[dict[str, Any]] = field(default_factory=list)
    default_routes: list[dict[str, Any]] = field(default_factory=list)
    ospf_processes: dict[int, dict[str, Any]] = field(default_factory=dict)
    eigrp_processes: dict[int, dict[str, Any]] = field(default_factory=dict)
    fhrp_members: list[dict[str, Any]] = field(default_factory=list)
    dhcp_helpers: list[dict[str, str]] = field(default_factory=list)
    unsupported_routes: list[dict[str, str]] = field(default_factory=list)
    unsupported_routing: list[dict[str, str]] = field(default_factory=list)


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = ANSI_RE.sub("", text)
    text = CONTROL_RE.sub("", text)
    return text.strip()


def clean_label(value: Any) -> str:
    return clean_text(value).strip("\"'`#> ")


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def bool_int(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "on"} else 0
    return 1 if bool(value) else 0


def area_to_int(value: Any) -> int:
    text = clean_text(value)
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        try:
            return int(IPv4Address(text))
        except ValueError:
            return 0


def parse_static_route_line(line: str) -> tuple[str, dict[str, Any]]:
    """Parse the simple IPv4 route forms represented by the current schema."""
    normalized = clean_text(line)
    parts = normalized.split()
    if len(parts) not in {5, 6} or parts[:2] != ["ip", "route"]:
        return "unsupported", {
            "line": normalized,
            "code": "ROUTE_FORM_UNSUPPORTED",
        }
    network, mask, next_hop = parts[2:5]
    try:
        IPv4Address(network)
        IPv4Address(mask)
        IPv4Address(next_hop)
    except ValueError:
        return "unsupported", {
            "line": normalized,
            "code": "NON_IPV4_ROUTE_UNSUPPORTED",
        }
    ad = int_or_none(parts[5]) if len(parts) == 6 else 1
    if ad is None or not 1 <= ad <= 255:
        return "unsupported", {
            "line": normalized,
            "code": "INVALID_ADMINISTRATIVE_DISTANCE",
        }
    if network == "0.0.0.0" and mask == "0.0.0.0":
        if len(parts) == 6:
            return "unsupported", {
                "line": normalized,
                "code": "DEFAULT_ROUTE_AD_UNSUPPORTED",
            }
        return "default", {"next_hop_ip": next_hop}
    return "static", {
        "network": network,
        "subnet_mask": mask,
        "next_hop": next_hop,
        "ad": ad,
    }


def parse_running_config_sections(config_text: str) -> ParsedRouterConfig:
    text = ANSI_RE.sub("", config_text or "").replace("\r\n", "\n").replace("\r", "\n")
    hostname = ""
    interfaces: list[dict[str, Any]] = []
    static_routes: list[dict[str, Any]] = []
    default_routes: list[dict[str, Any]] = []
    unsupported_routes: list[dict[str, str]] = []
    unsupported_routing: list[dict[str, str]] = []
    ospf_processes: dict[int, dict[str, Any]] = {}
    eigrp_processes: dict[int, dict[str, Any]] = {}
    current_kind = ""
    current_name = ""
    current_body: list[str] = []

    def flush_current() -> None:
        nonlocal current_kind, current_name, current_body
        if current_kind == "interface":
            interfaces.append(parse_interface_block(current_name, current_body))
        elif current_kind == "ospf":
            process = parse_ospf_block(current_name, current_body)
            if process:
                ospf_processes[process["process_id"]] = process
        elif current_kind == "eigrp":
            process = parse_eigrp_block(current_name, current_body)
            if process:
                eigrp_processes[process["as_number"]] = process
            else:
                unsupported_routing.append(
                    {
                        "line": current_name,
                        "code": "NAMED_EIGRP_UNSUPPORTED",
                    }
                )
        current_kind = ""
        current_name = ""
        current_body = []

    for raw in text.splitlines():
        line = CONTROL_RE.sub("", raw.rstrip())
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "!":
            flush_current()
            continue

        if stripped.startswith("hostname "):
            hostname = clean_label(stripped.split(None, 1)[1])

        is_top_level = not line.startswith((" ", "\t"))
        if is_top_level and stripped.startswith("ip route "):
            flush_current()
            route_kind, route = parse_static_route_line(stripped)
            if route_kind == "static":
                static_routes.append(route)
            elif route_kind == "default":
                default_routes.append(route)
            else:
                unsupported_routes.append(route)
            continue
        if is_top_level and stripped.startswith("interface "):
            flush_current()
            current_kind = "interface"
            current_name = clean_text(stripped.split(None, 1)[1])
            current_body = []
            continue
        if is_top_level and stripped.startswith("router ospf "):
            flush_current()
            current_kind = "ospf"
            current_name = stripped
            current_body = []
            continue
        if is_top_level and stripped.startswith("router eigrp "):
            flush_current()
            current_kind = "eigrp"
            current_name = stripped
            current_body = []
            continue
        if is_top_level:
            flush_current()
            continue
        if current_kind:
            current_body.append(stripped)

    flush_current()
    merge_interface_ospf_settings(ospf_processes, interfaces)
    fhrp_members = [
        dict(member, interface_name=interface["name"])
        for interface in interfaces
        for member in interface.get("fhrp_members", [])
        if member.get("virtual_ip")
    ]
    dhcp_helpers = [
        {"interface_name": interface["name"], "helper_ip": helper_ip}
        for interface in interfaces
        for helper_ip in interface.get("helper_addresses", [])
    ]
    return ParsedRouterConfig(
        hostname=hostname,
        interfaces=interfaces,
        static_routes=static_routes,
        default_routes=default_routes,
        ospf_processes=ospf_processes,
        eigrp_processes=eigrp_processes,
        fhrp_members=fhrp_members,
        dhcp_helpers=dhcp_helpers,
        unsupported_routes=unsupported_routes,
        unsupported_routing=unsupported_routing,
    )


def parse_interface_brief(brief_text: str) -> dict[str, dict[str, Any]]:
    interfaces: dict[str, dict[str, Any]] = {}
    for raw in (brief_text or "").splitlines():
        line = clean_text(raw)
        if not line or line.lower().startswith("interface "):
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        name = parts[0]
        ip_addr = parts[1]
        status_text = " ".join(parts[4:-1]).lower()
        interfaces[name] = {
            "name": name,
            "ip_address": "" if ip_addr.lower() == "unassigned" else ip_addr,
            "shutdown": 1 if "administratively down" in status_text else 0,
        }
    return interfaces


def merge_interface_brief(interfaces: list[dict[str, Any]], brief_text: str) -> list[dict[str, Any]]:
    brief_rows = parse_interface_brief(brief_text)
    by_name = {row["name"]: row for row in interfaces}
    for name, brief in brief_rows.items():
        if name in by_name:
            if not by_name[name].get("ip_address") and brief.get("ip_address"):
                by_name[name]["ip_address"] = brief["ip_address"]
            if brief.get("shutdown"):
                by_name[name]["shutdown"] = 1
            continue
        row = default_interface(name)
        row["ip_address"] = brief.get("ip_address") or ""
        row["shutdown"] = brief.get("shutdown") or 0
        interfaces.append(row)
    return interfaces


def default_interface(name: str) -> dict[str, Any]:
    return {
        "name": clean_text(name),
        "ip_address": "",
        "subnet_mask": "",
        "description": "",
        "shutdown": 0,
        "secondary_ip": "",
        "secondary_mask": "",
        "mtu": 1500,
        "bandwidth": None,
        "delay": None,
        "speed": "auto",
        "duplex": "auto",
        "negotiation": 1,
        "proxy_arp": 1,
        "unreachables": 1,
        "directed_broadcast": 0,
        "tunnel_mode": "gre",
        "tunnel_src": "",
        "tunnel_dst": "",
        "tunnel_key": None,
        "keepalive_sec": None,
        "keepalive_retry": None,
        "ipsec_profile": "",
        "encap_type": "none",
        "pppoe_dialer_pool": None,
        "ppp_auth": "",
        "ppp_username": "",
        "ppp_password": "",
        "clock_rate": None,
        "lmi_type": "",
        "subif_encapsulation": "",
        "subif_vlan_id": None,
        "subif_native": 0,
        "ospf_settings": [],
        "fhrp_members": [],
        "helper_addresses": [],
    }


def parse_interface_block(name: str, body: list[str]) -> dict[str, Any]:
    row = default_interface(name)
    ospf_bindings: list[dict[str, Any]] = []
    ospf_options: dict[str, Any] = {}

    for line in body:
        if line.startswith("description "):
            row["description"] = clean_text(line.split(None, 1)[1])
        elif line == "shutdown":
            row["shutdown"] = 1
        elif line == "no shutdown":
            row["shutdown"] = 0
        elif line.startswith("ip address "):
            parts = line.split()
            if len(parts) >= 4 and parts[2].lower() != "dhcp":
                if len(parts) >= 5 and parts[4].lower() == "secondary":
                    row["secondary_ip"] = parts[2]
                    row["secondary_mask"] = parts[3]
                else:
                    row["ip_address"] = parts[2]
                    row["subnet_mask"] = parts[3]
        elif line.startswith("mtu "):
            row["mtu"] = int_or_none(line.split(None, 1)[1]) or 1500
        elif line.startswith("bandwidth "):
            row["bandwidth"] = int_or_none(line.split(None, 1)[1])
        elif line.startswith("delay "):
            row["delay"] = int_or_none(line.split(None, 1)[1])
        elif line.startswith("speed "):
            speed = line.split(None, 1)[1].lower()
            row["speed"] = speed if speed in {"auto", "10", "100", "1000", "10000"} else "auto"
        elif line.startswith("duplex "):
            duplex = line.split(None, 1)[1].lower()
            row["duplex"] = duplex if duplex in {"auto", "full", "half"} else "auto"
        elif line in {"no negotiation auto", "nonegotiate"}:
            row["negotiation"] = 0
        elif line == "negotiation auto":
            row["negotiation"] = 1
        elif line == "no ip proxy-arp":
            row["proxy_arp"] = 0
        elif line == "ip proxy-arp":
            row["proxy_arp"] = 1
        elif line == "no ip unreachables":
            row["unreachables"] = 0
        elif line == "ip unreachables":
            row["unreachables"] = 1
        elif line == "ip directed-broadcast":
            row["directed_broadcast"] = 1
        elif line == "no ip directed-broadcast":
            row["directed_broadcast"] = 0
        elif line.startswith("tunnel mode "):
            mode_text = line.split(None, 2)[2].lower()
            row["tunnel_mode"] = "ipsec" if "ipsec" in mode_text else "ipip" if "ipip" in mode_text else "gre"
        elif line.startswith("tunnel source "):
            row["tunnel_src"] = clean_text(line.split(None, 2)[2])
        elif line.startswith("tunnel destination "):
            row["tunnel_dst"] = clean_text(line.split(None, 2)[2])
        elif line.startswith("tunnel key "):
            row["tunnel_key"] = int_or_none(line.split(None, 2)[2])
        elif line.startswith("keepalive "):
            parts = line.split()
            row["keepalive_sec"] = int_or_none(parts[1]) if len(parts) > 1 else None
            row["keepalive_retry"] = int_or_none(parts[2]) if len(parts) > 2 else None
        elif line.startswith("tunnel protection ipsec profile "):
            row["ipsec_profile"] = clean_text(line.rsplit(" ", 1)[1])
        elif line.startswith("encapsulation "):
            parts = line.split()
            encap = parts[1].lower() if len(parts) > 1 else ""
            if encap in {"dot1q", "isl"} and len(parts) > 2:
                row["subif_encapsulation"] = encap
                row["subif_vlan_id"] = int_or_none(parts[2])
                row["subif_native"] = 1 if any(
                    value.lower() == "native" for value in parts[3:]
                ) else 0
            else:
                row["encap_type"] = (
                    encap if encap in {"hdlc", "ppp", "frame-relay"} else "none"
                )
        elif line.startswith("pppoe-client dial-pool-number "):
            row["encap_type"] = "pppoe"
            row["pppoe_dialer_pool"] = int_or_none(line.rsplit(" ", 1)[1])
        elif line.startswith("ppp authentication "):
            auth = line.split()[2].lower()
            row["ppp_auth"] = auth if auth in {"pap", "chap"} else ""
        elif line.startswith("clock rate "):
            row["clock_rate"] = int_or_none(line.rsplit(" ", 1)[1])
        elif line.startswith("frame-relay lmi-type "):
            lmi = line.rsplit(" ", 1)[1].lower()
            row["lmi_type"] = lmi if lmi in {"cisco", "ansi", "q933a"} else ""
        elif line.startswith("ip ospf "):
            parse_interface_ospf_line(line, ospf_bindings, ospf_options)
        elif line.startswith("ip helper-address "):
            parts = line.split()
            # The current database and renderer model only the non-VRF IPv4
            # form. Do not silently flatten qualified commands.
            if len(parts) == 3:
                try:
                    IPv4Address(parts[2])
                except ValueError:
                    continue
                if parts[2] not in row["helper_addresses"]:
                    row["helper_addresses"].append(parts[2])

    for binding in ospf_bindings:
        merged = dict(ospf_options)
        merged.update(binding)
        row["ospf_settings"].append(merged)

    row["fhrp_members"] = parse_interface_fhrp_lines(body)

    lowered_name = row["name"].lower()
    if "." in row["name"]:
        row["interface_kind"] = "Subinterface"
    elif lowered_name.startswith("tunnel"):
        row["interface_kind"] = "Tunnel"
    elif lowered_name.startswith("serial") or row["encap_type"] != "none":
        row["interface_kind"] = "WAN"
    else:
        row["interface_kind"] = "L3"
    return row


def _default_fhrp_member(protocol: str, group_number: int) -> dict[str, Any]:
    options: dict[str, Any]
    if protocol == "hsrp":
        options = {
            # Cisco IOS defaults to HSRPv1 when no interface-level version
            # command is present.
            "version": 1,
            "hello_ms": 3000,
            "hold_ms": 10000,
            "preempt_delay_min_sec": 0,
            "preempt_delay_reload_sec": 0,
            "auth_type": "none",
            "auth_secret": None,
        }
    elif protocol == "vrrp":
        options = {
            "version": 2,
            "advertisement_ms": 1000,
            "accept_mode": 0,
            "auth_type": "none",
            "auth_secret": None,
        }
    else:
        options = {
            "hello_ms": 3000,
            "hold_ms": 10000,
            "load_balancing": "round-robin",
            "weighting_max": 100,
            "weighting_lower": None,
            "weighting_upper": None,
            "forwarder_preempt": 1,
            "forwarder_preempt_delay_sec": 30,
            "auth_type": "none",
            "auth_secret": None,
        }
    return {
        "protocol": protocol,
        "group_number": group_number,
        "virtual_ip": "",
        "priority": 100,
        # VRRP preemption is enabled by default; HSRP and GLBP require it
        # explicitly. A persisted ``no vrrp ... preempt`` overrides this.
        "preempt": 1 if protocol == "vrrp" else 0,
        "shutdown": 0,
        "tracks": [],
        "options": options,
    }


def parse_interface_fhrp_lines(body: list[str]) -> list[dict[str, Any]]:
    """Parse the Cisco IOS FHRP forms emitted by the application's renderer."""
    members: dict[tuple[str, int], dict[str, Any]] = {}
    hsrp_version = 1

    def member(protocol: str, group_text: str) -> dict[str, Any] | None:
        group_number = int_or_none(group_text)
        if group_number is None:
            return None
        key = (protocol, group_number)
        if key not in members:
            members[key] = _default_fhrp_member(protocol, group_number)
            if protocol == "hsrp":
                members[key]["options"]["version"] = hsrp_version
        return members[key]

    for raw_line in body:
        line = clean_text(raw_line)
        negated = line.startswith("no ")
        command = line[3:] if negated else line
        parts = command.split()
        if len(parts) == 3 and parts[:2] == ["standby", "version"]:
            version = int_or_none(parts[2])
            if version in {1, 2}:
                hsrp_version = version
                for (protocol, _group), item in members.items():
                    if protocol == "hsrp":
                        item["options"]["version"] = version
            continue
        if len(parts) < 3 or parts[0] not in {"standby", "vrrp", "glbp"}:
            continue
        protocol = {"standby": "hsrp", "vrrp": "vrrp", "glbp": "glbp"}[parts[0]]
        item = member(protocol, parts[1])
        if item is None:
            continue
        option = parts[2].lower()
        options = item["options"]

        if option == "ip" and len(parts) >= 4 and not negated:
            try:
                IPv4Address(parts[3])
            except ValueError:
                continue
            item["virtual_ip"] = parts[3]
        elif option == "priority" and len(parts) >= 4 and not negated:
            priority = int_or_none(parts[3])
            if priority is not None:
                item["priority"] = priority
        elif option == "preempt":
            item["preempt"] = 0 if negated else 1
            if not negated and protocol == "hsrp" and "delay" in parts:
                for key, field_name in (
                    ("minimum", "preempt_delay_min_sec"),
                    ("reload", "preempt_delay_reload_sec"),
                ):
                    if key in parts and parts.index(key) + 1 < len(parts):
                        options[field_name] = int_or_none(parts[parts.index(key) + 1]) or 0
        elif option == "shutdown":
            item["shutdown"] = 0 if negated else 1
        elif option == "timers" and not negated:
            values = parts[3:]
            if protocol == "vrrp" and values[:1] == ["advertise"]:
                values = values[1:]
                if values[:1] == ["msec"]:
                    values = values[1:]
                if values:
                    options["advertisement_ms"] = int_or_none(values[0]) or 1000
            elif protocol in {"hsrp", "glbp"}:
                milliseconds = "msec" in values
                numeric = [int(value) for value in values if value.isdigit()]
                if len(numeric) >= 2:
                    options["hello_ms"] = numeric[0] if milliseconds else numeric[0] * 1000
                    options["hold_ms"] = numeric[1] if milliseconds else numeric[1] * 1000
        elif option == "authentication" and not negated:
            auth = parts[3:]
            if auth[:2] == ["md5", "key-string"] and len(auth) >= 3:
                options.update(auth_type="md5-key", auth_secret=" ".join(auth[2:]))
            elif auth[:2] == ["md5", "key-chain"] and len(auth) >= 3:
                options.update(auth_type="md5-keychain", auth_secret=" ".join(auth[2:]))
            elif auth[:1] == ["text"] and len(auth) >= 2:
                options.update(auth_type="plain", auth_secret=" ".join(auth[1:]))
            elif auth:
                options.update(auth_type="plain", auth_secret=" ".join(auth))
        elif option == "track" and not negated and protocol in {"hsrp", "vrrp"}:
            if len(parts) >= 4:
                decrement = 10
                if "decrement" in parts and parts.index("decrement") + 1 < len(parts):
                    decrement = int_or_none(parts[parts.index("decrement") + 1]) or 10
                elif protocol == "hsrp" and len(parts) >= 5:
                    decrement = int_or_none(parts[4]) or 10
                item["tracks"].append(
                    {"track_object": parts[3], "decrement_value": decrement}
                )
        elif protocol == "glbp" and option == "load-balancing" and len(parts) >= 4:
            options["load_balancing"] = parts[3]
        elif protocol == "glbp" and option == "weighting" and not negated:
            if len(parts) >= 5 and parts[3] == "track":
                decrement = 10
                if "decrement" in parts and parts.index("decrement") + 1 < len(parts):
                    decrement = int_or_none(parts[parts.index("decrement") + 1]) or 10
                item["tracks"].append(
                    {"track_object": parts[4], "decrement_value": decrement}
                )
            elif len(parts) >= 4:
                options["weighting_max"] = int_or_none(parts[3]) or 100
                for key, field_name in (("lower", "weighting_lower"), ("upper", "weighting_upper")):
                    if key in parts and parts.index(key) + 1 < len(parts):
                        options[field_name] = int_or_none(parts[parts.index(key) + 1])
        elif protocol == "glbp" and option == "forwarder" and len(parts) >= 4 and parts[3] == "preempt":
            options["forwarder_preempt"] = 0 if negated else 1
            if not negated and "minimum" in parts and parts.index("minimum") + 1 < len(parts):
                options["forwarder_preempt_delay_sec"] = (
                    int_or_none(parts[parts.index("minimum") + 1]) or 0
                )

    return list(members.values())


def parse_interface_ospf_line(line: str, bindings: list[dict[str, Any]], options: dict[str, Any]) -> None:
    parts = line.split()
    if len(parts) >= 5 and parts[2].isdigit() and parts[3] == "area":
        bindings.append({"process_id": int(parts[2]), "area": area_to_int(parts[4])})
    elif len(parts) >= 4 and parts[2] == "cost":
        options["cost"] = int_or_none(parts[3])
    elif len(parts) >= 4 and parts[2] == "hello-interval":
        options["hello_interval"] = int_or_none(parts[3])
    elif len(parts) >= 4 and parts[2] == "dead-interval":
        options["dead_interval"] = int_or_none(parts[3])
    elif len(parts) >= 3 and parts[2] == "mtu-ignore":
        options["mtu_ignore"] = 1
    elif len(parts) >= 3 and parts[2] == "bfd":
        options["bfd"] = 1
    elif len(parts) >= 4 and parts[2] == "network":
        net_type = parts[3]
        options["network_type"] = net_type if net_type in {"broadcast", "non-broadcast", "point-to-point", "point-to-multipoint"} else ""
    elif len(parts) >= 3 and parts[2] == "authentication":
        options["auth_type"] = "message-digest" if "message-digest" in parts[3:] else "plain"


def default_eigrp_process(as_number: int) -> dict[str, Any]:
    return {
        "as_number": as_number,
        "router_id": "",
        "timers_active_time": None,
        "bfd_all_interfaces": 0,
        "auto_summary": 0,
        "passive_default": 0,
        "metric_weights": "0 1 0 1 0 0",
        "distance_internal": None,
        "distance_external": None,
        "variance": None,
        "maximum_paths": None,
        "stub_enabled": 0,
        "stub_options": "",
        "stub_leak_map": "",
        "networks": [],
        "interface_settings": [],
        "passive_interfaces": [],
        "distribute_lists": [],
        "offset_lists": [],
        "redistribute": [],
    }


def parse_eigrp_block(
    header: str, body: list[str]
) -> dict[str, Any] | None:
    """Parse classic-mode EIGRP fields represented by the current schema."""
    match = re.fullmatch(r"router\s+eigrp\s+(\d+)", header.strip())
    if not match:
        return None
    process = default_eigrp_process(int(match.group(1)))
    for line in body:
        parts = line.split()
        if line.startswith("eigrp router-id ") and len(parts) >= 3:
            process["router_id"] = clean_text(parts[2])
        elif line == "passive-interface default":
            process["passive_default"] = 1
        elif line == "no passive-interface default":
            process["passive_default"] = 0
        elif line.startswith("passive-interface ") and len(parts) >= 2:
            process["passive_interfaces"].append(
                {"interface_name": parts[1], "mode": "passive"}
            )
        elif line.startswith("no passive-interface ") and len(parts) >= 3:
            process["passive_interfaces"].append(
                {"interface_name": parts[2], "mode": "no-passive"}
            )
        elif line.startswith("network ") and len(parts) in {2, 3}:
            process["networks"].append(
                {
                    "network": parts[1],
                    "wildcard": parts[2] if len(parts) == 3 else None,
                    "interface_name": None,
                }
            )
        elif line == "auto-summary":
            process["auto_summary"] = 1
        elif line == "no auto-summary":
            process["auto_summary"] = 0
        elif line.startswith("variance ") and len(parts) == 2:
            process["variance"] = int_or_none(parts[1])
        elif line.startswith("maximum-paths ") and len(parts) == 2:
            process["maximum_paths"] = int_or_none(parts[1])
        elif line.startswith("distance eigrp ") and len(parts) >= 4:
            process["distance_internal"] = int_or_none(parts[2])
            process["distance_external"] = int_or_none(parts[3])
        elif line.startswith("timers active-time ") and len(parts) >= 3:
            process["timers_active_time"] = int_or_none(parts[2])
        elif line == "bfd all-interfaces":
            process["bfd_all_interfaces"] = 1
        elif line.startswith("metric weights ") and len(parts) >= 8:
            process["metric_weights"] = " ".join(parts[2:8])
        elif line.startswith("eigrp stub"):
            process["stub_enabled"] = 1
            options = parts[2:]
            if "leak-map" in options:
                index = options.index("leak-map")
                if index + 1 < len(options):
                    process["stub_leak_map"] = options[index + 1]
                    del options[index : index + 2]
            process["stub_options"] = " ".join(options)
        elif line.startswith("redistribute ") and len(parts) >= 2:
            protocol = parts[1].lower()
            if protocol not in {"static", "connected", "ospf", "bgp", "rip", "isis"}:
                continue
            row: dict[str, Any] = {
                "protocol": protocol,
                "route_map": None,
                "metric_bw": None,
                "metric_delay": None,
                "metric_reliability": None,
                "metric_load": None,
                "metric_mtu": None,
            }
            if "route-map" in parts:
                index = parts.index("route-map")
                if index + 1 < len(parts):
                    row["route_map"] = parts[index + 1]
            if "metric" in parts:
                index = parts.index("metric")
                metrics = parts[index + 1 : index + 6]
                if len(metrics) == 5:
                    for key, value in zip(
                        (
                            "metric_bw",
                            "metric_delay",
                            "metric_reliability",
                            "metric_load",
                            "metric_mtu",
                        ),
                        metrics,
                    ):
                        row[key] = int_or_none(value)
            process["redistribute"].append(row)
    return process


def default_ospf_process(process_id: int) -> dict[str, Any]:
    return {
        "process_id": process_id,
        "router_id": "",
        "reference_bandwidth": None,
        "passive_default": 0,
        "default_originate": 0,
        "default_originate_always": 0,
        "networks": [],
        "distance": {},
        "areas": {},
        "redistribute": [],
        "passive_interfaces": [],
        "tuning": {},
        "interface_settings": [],
    }


def parse_ospf_block(header: str, body: list[str]) -> dict[str, Any] | None:
    match = re.match(r"router\s+ospf\s+(\d+)", header)
    if not match:
        return None
    process = default_ospf_process(int(match.group(1)))

    for line in body:
        if line.startswith("router-id "):
            process["router_id"] = clean_text(line.split(None, 1)[1])
        elif line.startswith("auto-cost reference-bandwidth "):
            process["reference_bandwidth"] = int_or_none(line.rsplit(" ", 1)[1])
        elif line == "passive-interface default":
            process["passive_default"] = 1
        elif line == "no passive-interface default":
            process["passive_default"] = 0
        elif line.startswith("passive-interface "):
            process["passive_interfaces"].append(
                {"interface_name": clean_text(line.split(None, 1)[1]), "passive": 1}
            )
        elif line.startswith("no passive-interface "):
            process["passive_interfaces"].append(
                {"interface_name": clean_text(line.split(None, 2)[2]), "passive": 0}
            )
        elif line.startswith("default-information originate"):
            process["default_originate"] = 1
            if " always" in f" {line} ":
                process["default_originate_always"] = 1
        elif line.startswith("network "):
            parts = line.split()
            if len(parts) >= 5 and parts[3] == "area":
                process["networks"].append(
                    {"network": parts[1], "wildcard": parts[2], "area": area_to_int(parts[4])}
                )
        elif line.startswith("distance ospf"):
            process["distance"] = parse_ospf_distance(line)
        elif line.startswith("maximum-paths "):
            process["tuning"]["maximum_paths"] = int_or_none(line.rsplit(" ", 1)[1])
        elif line.startswith("max-lsa "):
            process["tuning"]["max_lsa"] = int_or_none(line.split()[1])
        elif line.startswith("timers throttle spf "):
            parts = line.split()
            if len(parts) >= 6:
                process["tuning"].update(
                    {
                        "spf_delay": int_or_none(parts[3]),
                        "spf_min_delay": int_or_none(parts[4]),
                        "spf_max_delay": int_or_none(parts[5]),
                    }
                )
        elif line.startswith("timers throttle lsa all "):
            parts = line.split()
            if len(parts) >= 6:
                process["tuning"].update(
                    {
                        "lsa_delay": int_or_none(parts[4]),
                        "lsa_min_delay": int_or_none(parts[5]),
                        "lsa_max_delay": int_or_none(parts[6]) if len(parts) > 6 else None,
                    }
                )
        elif line.startswith("area "):
            parse_ospf_area_line(process, line)
        elif line.startswith("redistribute "):
            redist = parse_ospf_redistribute(line)
            if redist:
                process["redistribute"].append(redist)

    return process


def parse_ospf_distance(line: str) -> dict[str, int | None]:
    parts = line.split()
    distance = {"external": None, "intra_area": None, "inter_area": None}
    index = 2
    while index < len(parts) - 1:
        key = parts[index]
        value = int_or_none(parts[index + 1])
        if key == "external":
            distance["external"] = value
        elif key == "intra-area":
            distance["intra_area"] = value
        elif key == "inter-area":
            distance["inter_area"] = value
        index += 2
    return distance


def area_row(process: dict[str, Any], area_id: int) -> dict[str, Any]:
    areas = process["areas"]
    if area_id not in areas:
        areas[area_id] = {
            "area_id": area_id,
            "area_type": "normal",
            "no_summary": 0,
            "authentication": "",
            "ranges": [],
        }
    return areas[area_id]


def parse_ospf_area_line(process: dict[str, Any], line: str) -> None:
    parts = line.split()
    if len(parts) < 3:
        return
    area_id = area_to_int(parts[1])
    area = area_row(process, area_id)
    if parts[2] in {"stub", "nssa"}:
        area["area_type"] = parts[2]
        area["no_summary"] = 1 if "no-summary" in parts[3:] else 0
    elif parts[2] == "authentication":
        area["authentication"] = "message-digest" if "message-digest" in parts[3:] else "plain"
    elif parts[2] == "range" and len(parts) >= 5:
        range_row = {
            "ip": parts[3],
            "mask": parts[4],
            "advertise": 0 if "not-advertise" in parts[5:] else 1,
            "cost": None,
        }
        if "cost" in parts[5:]:
            cost_index = parts.index("cost")
            if cost_index + 1 < len(parts):
                range_row["cost"] = int_or_none(parts[cost_index + 1])
        area["ranges"].append(range_row)


def parse_ospf_redistribute(line: str) -> dict[str, Any] | None:
    parts = line.split()
    if len(parts) < 2:
        return None
    protocol = parts[1]
    allowed = {"static", "connected", "eigrp", "bgp", "rip", "isis"}
    if protocol not in allowed:
        return None
    redist: dict[str, Any] = {
        "protocol": protocol,
        "process_id": None,
        "subnets": 1 if "subnets" in parts[2:] else 0,
        "metric": None,
        "metric_type": None,
        "route_map": "",
    }
    index = 2
    if index < len(parts) and parts[index].isdigit() and protocol in {"eigrp", "bgp"}:
        redist["process_id"] = int(parts[index])
        index += 1
    while index < len(parts):
        token = parts[index]
        if token == "metric" and index + 1 < len(parts):
            redist["metric"] = int_or_none(parts[index + 1])
            index += 2
        elif token == "metric-type" and index + 1 < len(parts):
            redist["metric_type"] = int_or_none(parts[index + 1])
            index += 2
        elif token == "route-map" and index + 1 < len(parts):
            redist["route_map"] = parts[index + 1]
            index += 2
        else:
            index += 1
    return redist


def merge_interface_ospf_settings(processes: dict[int, dict[str, Any]], interfaces: list[dict[str, Any]]) -> None:
    for interface in interfaces:
        for setting in interface.get("ospf_settings", []):
            process_id = int_or_none(setting.get("process_id"))
            if process_id is None:
                continue
            process = processes.setdefault(process_id, default_ospf_process(process_id))
            area = area_to_int(setting.get("area"))
            area_row(process, area)
            process["interface_settings"].append(
                {
                    "interface_name": interface["name"],
                    "area": area,
                    "cost": setting.get("cost"),
                    "hello_interval": setting.get("hello_interval"),
                    "dead_interval": setting.get("dead_interval"),
                    "mtu_ignore": bool_int(setting.get("mtu_ignore")),
                    "bfd": bool_int(setting.get("bfd")),
                    "network_type": clean_text(setting.get("network_type")),
                    "auth_type": clean_text(setting.get("auth_type")),
                }
            )


def sync_device_state(
    db_path: str,
    host: str,
    running_config: str,
    interface_brief: str | None = None,
    mode: str = "safe",
) -> dict[str, Any]:
    mode = str(mode or "safe").strip().lower()
    if mode not in {"safe", "force_device_state", "preview"}:
        raise ValueError("Sync mode must be safe, force_device_state, or preview")
    parsed = parse_running_config_sections(running_config)
    interfaces = merge_interface_brief(parsed.interfaces, interface_brief or "")
    conflicts: list[str] = []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        pending = {
            "interfaces": _interfaces_have_pending(conn, host),
            "static_routes": _table_has_pending(conn, "t04_static_routes", host),
            "default_routes": _table_has_pending(conn, "t04_static_default_routes", host),
            "ospf": _ospf_has_pending(conn, host),
            "eigrp": _eigrp_has_pending(conn, host),
            "fhrp": _fhrp_has_pending(conn, host),
            "dhcp_helpers": _dhcp_helpers_have_pending(conn, host),
        }
        if mode == "safe":
            conflicts = [name for name, exists in pending.items() if exists]
        if mode == "preview":
            return {
                "hostname": parsed.hostname,
                "interfaces": len(interfaces),
                "static_routes": len(parsed.static_routes),
                "default_routes": len(parsed.default_routes),
                "ospf_processes": len(parsed.ospf_processes),
                "eigrp_processes": len(parsed.eigrp_processes),
                "fhrp_members": len(parsed.fhrp_members),
                "dhcp_helpers": len(parsed.dhcp_helpers),
                "conflicts": [name for name, exists in pending.items() if exists],
                "unsupported_routes": len(parsed.unsupported_routes),
                "unsupported_route_details": parsed.unsupported_routes,
                "unsupported_routing": len(parsed.unsupported_routing),
                "unsupported_routing_details": parsed.unsupported_routing,
                "mode": mode,
            }
        _ensure_sync_indexes(conn)
        with conn:
            if parsed.hostname:
                conn.execute(
                    "UPDATE t01_devices SET device_name = ? WHERE host = ?;",
                    (parsed.hostname, host),
                )
            sync_fhrp = mode == "force_device_state" or not pending["fhrp"]
            sync_interfaces_allowed = (
                mode == "force_device_state"
                or (
                    not pending["interfaces"]
                    and not pending["fhrp"]
                    and not pending["dhcp_helpers"]
                )
            )
            # Remove this host's old members before interface reconciliation;
            # FHRP deliberately guards referenced interfaces from deletion.
            if sync_fhrp:
                clear_fhrp_members(conn, host)
            if sync_interfaces_allowed:
                sync_interfaces(conn, host, interfaces)
            if sync_fhrp:
                insert_fhrp_members(conn, host, parsed.fhrp_members)
            if mode == "force_device_state" or not pending["dhcp_helpers"]:
                sync_dhcp_helpers(conn, host, parsed.dhcp_helpers)
            if mode == "force_device_state" or not pending["static_routes"]:
                sync_static_routes(conn, host, parsed.static_routes)
            if mode == "force_device_state" or not pending["default_routes"]:
                sync_default_routes(conn, host, parsed.default_routes)
            if mode == "force_device_state" or not pending["ospf"]:
                sync_ospf_processes(
                    conn, host, list(parsed.ospf_processes.values())
                )
            if mode == "force_device_state" or not pending["eigrp"]:
                sync_eigrp_processes(
                    conn, host, list(parsed.eigrp_processes.values())
                )
    finally:
        conn.close()

    return {
        "hostname": parsed.hostname,
        "interfaces": len(interfaces),
        "static_routes": len(parsed.static_routes),
        "default_routes": len(parsed.default_routes),
        "ospf_processes": len(parsed.ospf_processes),
        "eigrp_processes": len(parsed.eigrp_processes),
        "fhrp_members": len(parsed.fhrp_members),
        "dhcp_helpers": len(parsed.dhcp_helpers),
        "conflicts": conflicts,
        "unsupported_routes": len(parsed.unsupported_routes),
        "unsupported_route_details": parsed.unsupported_routes,
        "unsupported_routing": len(parsed.unsupported_routing),
        "unsupported_routing_details": parsed.unsupported_routing,
        "mode": mode,
    }


def _ensure_sync_indexes(conn: sqlite3.Connection) -> None:
    """Create the lookup indexes used by sync on databases from older releases."""
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_t02_interface_sync "
        "ON t02_interface_name(host, sync_status);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_t04_static_routes_sync "
        "ON t04_static_routes(host, sync_status);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_t04_default_routes_sync "
        "ON t04_static_default_routes(host, sync_status);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_t04_ospf_processes_sync "
        "ON t04_ospf_processes(host, sync_status);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_t04_eigrp_processes_sync "
        "ON t04_eigrp_processes(host, sync_status);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_t08_fhrp_members_sync "
        "ON t08_fhrp_members(host, sync_status);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_t03_router_iface_helper_sync "
        "ON t03_router_iface_helper(iface_id, sync_status);"
    )


def _table_has_pending(
    conn: sqlite3.Connection, table: str, host: str
) -> bool:
    return conn.execute(
        f"SELECT 1 FROM {table} WHERE host = ? AND sync_status IN ('pending_delete', 'pending_apply') LIMIT 1;",
        (host,),
    ).fetchone() is not None


def _interfaces_have_pending(conn: sqlite3.Connection, host: str) -> bool:
    if _table_has_pending(conn, "t02_interface_name", host):
        return True
    for table in (
        "t02_router_iface_l3",
        "t02_router_iface_tunnel",
        "t02_router_iface_wan",
    ):
        if conn.execute(
            f"""
            SELECT 1 FROM {table}
            WHERE sync_status IN ('pending_delete', 'pending_apply') AND iface_id IN (
                SELECT iface_id FROM t02_interface_name WHERE host = ?
            ) LIMIT 1;
            """,
            (host,),
        ).fetchone():
            return True
    return False


def _ospf_has_pending(conn: sqlite3.Connection, host: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM t04_ospf_processes
        WHERE host = ? AND sync_status IN ('pending_delete', 'pending_apply') LIMIT 1;
        """,
        (host,),
    ).fetchone()
    if row:
        return True
    child_tables = (
        ("t04_ospf_networks", "ospf_id"),
        ("t04_ospf_distance", "ospf_id"),
        ("t04_ospf_areas", "ospf_id"),
        ("t04_ospf_redistribute", "ospf_id"),
        ("t04_ospf_passive_interfaces", "ospf_id"),
        ("t04_ospf_tuning", "ospf_id"),
        ("t04_router_iface_ospf", "ospf_id"),
    )
    for table, column in child_tables:
        if conn.execute(
            f"""
            SELECT 1 FROM {table}
            WHERE sync_status IN ('pending_delete', 'pending_apply') AND {column} IN (
                SELECT ospf_id FROM t04_ospf_processes WHERE host = ?
            ) LIMIT 1;
            """,
            (host,),
        ).fetchone():
            return True
    return conn.execute(
        """
        SELECT 1 FROM t04_ospf_area_ranges
        WHERE sync_status IN ('pending_delete', 'pending_apply') AND area_db_id IN (
            SELECT a.id FROM t04_ospf_areas AS a
            JOIN t04_ospf_processes AS p ON p.ospf_id = a.ospf_id
            WHERE p.host = ?
        ) LIMIT 1;
        """,
        (host,),
    ).fetchone() is not None


def _eigrp_has_pending(conn: sqlite3.Connection, host: str) -> bool:
    if conn.execute(
        """
        SELECT 1 FROM t04_eigrp_key_chains
        WHERE host = ? AND sync_status IN ('pending_delete', 'pending_apply') LIMIT 1;
        """,
        (host,),
    ).fetchone():
        return True
    if conn.execute(
        """
        SELECT 1 FROM t04_eigrp_processes
        WHERE host = ? AND sync_status IN ('pending_delete', 'pending_apply') LIMIT 1;
        """,
        (host,),
    ).fetchone():
        return True
    for table in (
        "t04_eigrp_networks",
        "t04_router_iface_eigrp",
        "t04_eigrp_passive_interfaces",
        "t04_eigrp_distribute_lists",
        "t04_eigrp_offset_lists",
        "t04_eigrp_redistribute",
    ):
        if conn.execute(
            f"""
            SELECT 1 FROM {table}
            WHERE sync_status IN ('pending_delete', 'pending_apply') AND eigrp_id IN (
                SELECT eigrp_id FROM t04_eigrp_processes WHERE host = ?
            ) LIMIT 1;
            """,
            (host,),
        ).fetchone():
            return True
    return False


def _fhrp_has_pending(conn: sqlite3.Connection, host: str) -> bool:
    if conn.execute(
        """
        SELECT 1 FROM t08_fhrp_members
        WHERE host = ? AND sync_status IN ('pending_delete', 'pending_apply')
        LIMIT 1;
        """,
        (host,),
    ).fetchone():
        return True
    return conn.execute(
        """
        SELECT 1 FROM t08_fhrp_tracks
        WHERE sync_status IN ('pending_delete', 'pending_apply')
          AND member_id IN (
              SELECT member_id FROM t08_fhrp_members WHERE host = ?
          )
        LIMIT 1;
        """,
        (host,),
    ).fetchone() is not None


def _dhcp_helpers_have_pending(conn: sqlite3.Connection, host: str) -> bool:
    return conn.execute(
        """
        SELECT 1
        FROM t03_router_iface_helper AS h
        JOIN t02_interface_name AS i ON i.iface_id = h.iface_id
        WHERE i.host = ?
          AND h.sync_status IN ('pending_delete', 'pending_apply')
        LIMIT 1;
        """,
        (host,),
    ).fetchone() is not None


def sync_dhcp_helpers(
    conn: sqlite3.Connection,
    host: str,
    helpers: list[dict[str, str]],
) -> None:
    """Replace observed non-VRF IPv4 helper addresses for one router."""
    conn.execute(
        """
        DELETE FROM t03_router_iface_helper
        WHERE iface_id IN (
            SELECT iface_id FROM t02_interface_name WHERE host = ?
        );
        """,
        (host,),
    )
    interfaces = {
        str(row["interface_name"]): int(row["iface_id"])
        for row in conn.execute(
            "SELECT iface_id, interface_name FROM t02_interface_name WHERE host = ?;",
            (host,),
        )
    }
    rows: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()
    for helper in helpers:
        iface_id = interfaces.get(clean_text(helper.get("interface_name")))
        helper_ip = clean_text(helper.get("helper_ip"))
        if iface_id is None or not helper_ip:
            continue
        key = (iface_id, helper_ip)
        if key in seen:
            continue
        seen.add(key)
        rows.append(key)
    conn.executemany(
        """
        INSERT INTO t03_router_iface_helper(iface_id, helper_ip, sync_status)
        VALUES (?, ?, 'synchronized');
        """,
        rows,
    )


def clear_fhrp_members(conn: sqlite3.Connection, host: str) -> None:
    """Remove only one host's observed FHRP state and retain shared groups."""
    conn.execute("DELETE FROM t08_fhrp_members WHERE host = ?;", (host,))
    conn.execute(
        """
        DELETE FROM t08_fhrp_groups
        WHERE NOT EXISTS (
            SELECT 1 FROM t08_fhrp_members AS m
            WHERE m.fhrp_id = t08_fhrp_groups.fhrp_id
        );
        """
    )


def insert_fhrp_members(
    conn: sqlite3.Connection,
    host: str,
    members: list[dict[str, Any]],
) -> None:
    """Insert parsed HSRP/VRRP/GLBP members as synchronized device state."""
    interfaces = {
        str(row["interface_name"]): ("router", int(row["iface_id"]))
        for row in conn.execute(
            "SELECT iface_id, interface_name FROM t02_interface_name WHERE host = ?;",
            (host,),
        )
    }
    interfaces.update(
        {
            f"Vlan{int(row['vlan_id'])}": ("svi", int(row["id"]))
            for row in conn.execute(
                "SELECT id, vlan_id FROM t06_svi_interface WHERE host = ?;",
                (host,),
            )
        }
    )
    for item in members:
        interface_name = clean_text(item.get("interface_name"))
        endpoint = interfaces.get(interface_name)
        protocol = clean_text(item.get("protocol")).lower()
        group_number = int_or_none(item.get("group_number"))
        virtual_ip = clean_text(item.get("virtual_ip"))
        if endpoint is None or protocol not in {"hsrp", "vrrp", "glbp"}:
            continue
        interface_kind, iface_id = endpoint
        if group_number is None or not virtual_ip:
            continue
        group = conn.execute(
            """
            SELECT fhrp_id FROM t08_fhrp_groups
            WHERE protocol = ? AND group_number = ? AND virtual_ip = ?
              AND address_family = 'ipv4';
            """,
            (protocol, group_number, virtual_ip),
        ).fetchone()
        if group is None:
            cursor = conn.execute(
                """
                INSERT INTO t08_fhrp_groups(
                    protocol, group_number, virtual_ip, address_family
                ) VALUES (?, ?, ?, 'ipv4');
                """,
                (protocol, group_number, virtual_ip),
            )
            fhrp_id = int(cursor.lastrowid)
        else:
            fhrp_id = int(group["fhrp_id"])
        cursor = conn.execute(
            """
            INSERT INTO t08_fhrp_members(
                fhrp_id, host, iface_id, interface_kind,
                priority, preempt, shutdown, sync_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'synchronized');
            """,
            (
                fhrp_id,
                host,
                iface_id,
                interface_kind,
                int_or_none(item.get("priority")) or 100,
                bool_int(item.get("preempt")),
                bool_int(item.get("shutdown")),
            ),
        )
        member_id = int(cursor.lastrowid)
        options = dict(item.get("options") or {})
        if protocol == "hsrp":
            conn.execute(
                """
                INSERT INTO t08_hsrp_options(
                    member_id, version, hello_ms, hold_ms,
                    preempt_delay_min_sec, preempt_delay_reload_sec,
                    auth_type, auth_secret
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    member_id,
                    options.get("version", 2),
                    options.get("hello_ms", 3000),
                    options.get("hold_ms", 10000),
                    options.get("preempt_delay_min_sec", 0),
                    options.get("preempt_delay_reload_sec", 0),
                    options.get("auth_type", "none"),
                    options.get("auth_secret"),
                ),
            )
        elif protocol == "vrrp":
            conn.execute(
                """
                INSERT INTO t08_vrrp_options(
                    member_id, version, advertisement_ms, accept_mode,
                    auth_type, auth_secret
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    member_id,
                    options.get("version", 2),
                    options.get("advertisement_ms", 1000),
                    bool_int(options.get("accept_mode")),
                    options.get("auth_type", "none"),
                    options.get("auth_secret"),
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO t08_glbp_options(
                    member_id, hello_ms, hold_ms, load_balancing,
                    weighting_max, weighting_lower, weighting_upper,
                    forwarder_preempt, forwarder_preempt_delay_sec,
                    auth_type, auth_secret
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    member_id,
                    options.get("hello_ms", 3000),
                    options.get("hold_ms", 10000),
                    options.get("load_balancing", "round-robin"),
                    options.get("weighting_max", 100),
                    options.get("weighting_lower"),
                    options.get("weighting_upper"),
                    bool_int(options.get("forwarder_preempt", True)),
                    options.get("forwarder_preempt_delay_sec", 30),
                    options.get("auth_type", "none"),
                    options.get("auth_secret"),
                ),
            )
        for track in item.get("tracks") or []:
            conn.execute(
                """
                INSERT INTO t08_fhrp_tracks(
                    member_id, track_object, decrement_value, sync_status
                ) VALUES (?, ?, ?, 'synchronized');
                """,
                (
                    member_id,
                    clean_text(track.get("track_object")),
                    int_or_none(track.get("decrement_value")) or 10,
                ),
            )


def sync_static_routes(
    conn: sqlite3.Connection, host: str, routes: list[dict[str, Any]]
) -> None:
    conn.execute("DELETE FROM t04_static_routes WHERE host = ?;", (host,))
    conn.executemany(
        """
        INSERT INTO t04_static_routes
            (host, network, subnet_mask, next_hop, ad, sync_status)
        VALUES (?, ?, ?, ?, ?, 'synchronized');
        """,
        [
            (
                host,
                route["network"],
                route["subnet_mask"],
                route["next_hop"],
                int(route.get("ad") or 1),
            )
            for route in routes
        ],
    )


def sync_default_routes(
    conn: sqlite3.Connection, host: str, routes: list[dict[str, Any]]
) -> None:
    conn.execute("DELETE FROM t04_static_default_routes WHERE host = ?;", (host,))
    conn.executemany(
        """
        INSERT INTO t04_static_default_routes (host, next_hop_ip, sync_status)
        VALUES (?, ?, 'synchronized');
        """,
        [(host, route["next_hop_ip"]) for route in routes],
    )


class _EigrpSyncAdapter:
    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        return list(value or [])

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return dict(value or {})

    _int_or_none = staticmethod(int_or_none)
    _bool_int = staticmethod(bool_int)

    @staticmethod
    def _str_or_none(value: Any) -> str | None:
        text = clean_text(value)
        return text or None


def sync_eigrp_processes(
    conn: sqlite3.Connection,
    host: str,
    processes: list[dict[str, Any]],
) -> None:
    """Replace the observed classic EIGRP snapshot with sync_status='synchronized' rows."""
    from features.routing.eigrp.child_sync import CHILD_TABLES
    from features.routing.eigrp.process_store import insert_eigrp_process

    conn.execute("DELETE FROM t04_eigrp_processes WHERE host = ?;", (host,))
    adapter = _EigrpSyncAdapter()
    for process in processes:
        eigrp_id = insert_eigrp_process(conn, adapter, host, process)
        conn.execute(
            "UPDATE t04_eigrp_processes SET sync_status = 'synchronized' WHERE eigrp_id = ?;",
            (eigrp_id,),
        )
        for table in CHILD_TABLES:
            conn.execute(
                f"UPDATE {table} SET sync_status = 'synchronized' WHERE eigrp_id = ?;",
                (eigrp_id,),
            )


def sync_interfaces(conn: sqlite3.Connection, host: str, interfaces: list[dict[str, Any]]) -> None:
    existing_interfaces = {
        str(row["interface_name"]): int(row["iface_id"])
        for row in conn.execute(
            """
            SELECT interface_name, iface_id
            FROM t02_interface_name
            WHERE host = ?;
            """,
            (host,),
        )
    }
    for table in (
        "t02_router_iface_l3",
        "t02_router_iface_tunnel",
        "t02_router_iface_wan",
    ):
        conn.execute(
            f"""
            UPDATE {table}
            SET sync_status = 'pending_delete'
            WHERE iface_id IN (
                SELECT iface_id FROM t02_interface_name WHERE host = ?
            );
            """,
            (host,),
        )
    conn.execute(
        "UPDATE t02_router_iface_subif SET sync_status = 'pending_delete' WHERE host = ?;",
        (host,),
    )
    conn.execute("UPDATE t02_interface_name SET sync_status = 'pending_delete' WHERE host = ?;", (host,))

    # A subinterface profile references its physical parent.  Ensure that
    # parent exists before processing profiles even if the device returned the
    # subinterface block first or omitted the parent from running-config.
    for row in interfaces:
        name = clean_text(row.get("name"))
        if (row.get("interface_kind") or "") != "Subinterface" or "." not in name:
            continue
        parent_name = name.rsplit(".", 1)[0]
        if parent_name in existing_interfaces:
            conn.execute(
                "UPDATE t02_interface_name SET sync_status = 'synchronized', "
                "action_Cfg = '0000000000000' "
                "WHERE iface_id = ?;",
                (existing_interfaces[parent_name],),
            )
            continue
        cursor = conn.execute(
            "INSERT INTO t02_interface_name(host, interface_name, sync_status) "
            "VALUES (?, ?, 'synchronized');",
            (host, parent_name),
        )
        existing_interfaces[parent_name] = int(cursor.lastrowid)

    for row in interfaces:
        name = clean_text(row.get("name"))
        if not name:
            continue
        iface_id = existing_interfaces.get(name)
        if iface_id is not None:
            conn.execute(
                """
                UPDATE t02_interface_name
                SET ip_address = ?, subnet_mask = ?, description = ?, shutdown = ?,
                    sync_status = 'synchronized', action_Cfg = '0000000000000'
                WHERE iface_id = ?;
                """,
                (
                    clean_text(row.get("ip_address")) or None,
                    clean_text(row.get("subnet_mask")) or None,
                    clean_text(row.get("description")) or None,
                    bool_int(row.get("shutdown")),
                    iface_id,
                ),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO t02_interface_name (
                    host, interface_name, ip_address, subnet_mask, description, shutdown, sync_status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'synchronized');
                """,
                (
                    host,
                    name,
                    clean_text(row.get("ip_address")) or None,
                    clean_text(row.get("subnet_mask")) or None,
                    clean_text(row.get("description")) or None,
                    bool_int(row.get("shutdown")),
                ),
            )
            iface_id = int(cursor.lastrowid)
            existing_interfaces[name] = iface_id

        kind = row.get("interface_kind") or "L3"
        if kind == "Subinterface":
            if row.get("subif_vlan_id") is not None:
                sync_subinterface(conn, host, row)
        elif kind == "Tunnel" and row.get("tunnel_src") and row.get("tunnel_dst"):
            sync_tunnel(conn, iface_id, row)
        elif kind == "WAN":
            sync_wan(conn, iface_id, row)
        else:
            sync_l3(conn, iface_id, row)

    # This is an observed device-state replacement, not a desired-state delete.
    # Rows absent from both running-config and interface brief must disappear
    # from the database instead of becoming commands for a later View & Push.
    conn.execute(
        "DELETE FROM t02_interface_name WHERE host = ? AND sync_status = 'pending_delete';",
        (host,),
    )

    # A device snapshot replaces observed child state.  Profiles that were not
    # observed must be removed locally, not left as desired-state deletions for
    # a later View & Push operation.
    for table in (
        "t02_router_iface_l3",
        "t02_router_iface_tunnel",
        "t02_router_iface_wan",
    ):
        conn.execute(
            f"""
            DELETE FROM {table}
            WHERE sync_status = 'pending_delete'
              AND iface_id IN (
                  SELECT iface_id FROM t02_interface_name WHERE host = ?
              );
            """,
            (host,),
        )
    conn.execute(
        "DELETE FROM t02_router_iface_subif "
        "WHERE host = ? AND sync_status = 'pending_delete';",
        (host,),
    )


def sync_subinterface(
    conn: sqlite3.Connection,
    host: str,
    row: dict[str, Any],
) -> None:
    """Persist an observed 802.1Q/ISL subinterface without creating an L3 profile."""
    name = clean_text(row.get("name"))
    parent_name = name.rsplit(".", 1)[0]
    parent = conn.execute(
        "SELECT iface_id FROM t02_interface_name WHERE host = ? AND interface_name = ?;",
        (host, parent_name),
    ).fetchone()
    if parent is None:
        return
    conn.execute(
        """
        INSERT INTO t02_router_iface_subif(
            parent_iface_id, host, subif_name, encapsulation, vlan_id,
            native, ip_address, subnet_mask, shutdown, sync_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'synchronized')
        ON CONFLICT(host, subif_name) DO UPDATE SET
            parent_iface_id = excluded.parent_iface_id,
            encapsulation = excluded.encapsulation,
            vlan_id = excluded.vlan_id,
            native = excluded.native,
            ip_address = excluded.ip_address,
            subnet_mask = excluded.subnet_mask,
            shutdown = excluded.shutdown,
            sync_status = 'synchronized';
        """,
        (
            int(parent[0]),
            host,
            name,
            row.get("subif_encapsulation") or "dot1q",
            int(row["subif_vlan_id"]),
            bool_int(row.get("subif_native")),
            clean_text(row.get("ip_address")) or None,
            clean_text(row.get("subnet_mask")) or None,
            bool_int(row.get("shutdown")),
        ),
    )

def sync_l3(conn: sqlite3.Connection, iface_id: int, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO t02_router_iface_l3 (
            iface_id, secondary_ip, secondary_mask, mtu, bandwidth, delay,
            speed, duplex, negotiation, proxy_arp, unreachables,
            directed_broadcast, sync_status, action_Cfg
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synchronized', '00000')
        ON CONFLICT(iface_id) DO UPDATE SET
            secondary_ip = excluded.secondary_ip,
            secondary_mask = excluded.secondary_mask,
            mtu = excluded.mtu,
            bandwidth = excluded.bandwidth,
            delay = excluded.delay,
            speed = excluded.speed,
            duplex = excluded.duplex,
            negotiation = excluded.negotiation,
            proxy_arp = excluded.proxy_arp,
            unreachables = excluded.unreachables,
            directed_broadcast = excluded.directed_broadcast,
            sync_status = 'synchronized',
            action_Cfg = '00000';
        """,
        (
            iface_id,
            clean_text(row.get("secondary_ip")) or None,
            clean_text(row.get("secondary_mask")) or None,
            int_or_none(row.get("mtu")) or 1500,
            int_or_none(row.get("bandwidth")),
            int_or_none(row.get("delay")),
            row.get("speed") or "auto",
            row.get("duplex") or "auto",
            bool_int(row.get("negotiation")),
            bool_int(row.get("proxy_arp")),
            bool_int(row.get("unreachables")),
            bool_int(row.get("directed_broadcast")),
        ),
    )


def sync_tunnel(conn: sqlite3.Connection, iface_id: int, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO t02_router_iface_tunnel (
            iface_id, tunnel_mode, tunnel_src, tunnel_dst, tunnel_key,
            keepalive_sec, keepalive_retry, ipsec_profile, sync_status, action_Cfg
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synchronized', '111')
        ON CONFLICT(iface_id) DO UPDATE SET
            tunnel_mode = excluded.tunnel_mode,
            tunnel_src = excluded.tunnel_src,
            tunnel_dst = excluded.tunnel_dst,
            tunnel_key = excluded.tunnel_key,
            keepalive_sec = excluded.keepalive_sec,
            keepalive_retry = excluded.keepalive_retry,
            ipsec_profile = excluded.ipsec_profile,
            sync_status = 'synchronized',
            action_Cfg = '111';
        """,
        (
            iface_id,
            row.get("tunnel_mode") or "gre",
            clean_text(row.get("tunnel_src")),
            clean_text(row.get("tunnel_dst")),
            int_or_none(row.get("tunnel_key")),
            int_or_none(row.get("keepalive_sec")),
            int_or_none(row.get("keepalive_retry")),
            clean_text(row.get("ipsec_profile")) or None,
        ),
    )


def sync_wan(conn: sqlite3.Connection, iface_id: int, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO t02_router_iface_wan (
            iface_id, encap_type, pppoe_dialer_pool, ppp_auth,
            ppp_username, ppp_password, clock_rate, lmi_type, sync_status, action_Cfg
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synchronized', '11')
        ON CONFLICT(iface_id) DO UPDATE SET
            encap_type = excluded.encap_type,
            pppoe_dialer_pool = excluded.pppoe_dialer_pool,
            ppp_auth = excluded.ppp_auth,
            ppp_username = excluded.ppp_username,
            ppp_password = excluded.ppp_password,
            clock_rate = excluded.clock_rate,
            lmi_type = excluded.lmi_type,
            sync_status = 'synchronized',
            action_Cfg = '11';
        """,
        (
            iface_id,
            row.get("encap_type") or "none",
            int_or_none(row.get("pppoe_dialer_pool")),
            clean_text(row.get("ppp_auth")) or None,
            clean_text(row.get("ppp_username")) or None,
            clean_text(row.get("ppp_password")) or None,
            int_or_none(row.get("clock_rate")),
            clean_text(row.get("lmi_type")) or None,
        ),
    )


def sync_ospf_processes(conn: sqlite3.Connection, host: str, processes: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM t04_ospf_processes WHERE host = ?;", (host,))
    for process in processes:
        cursor = conn.execute(
            """
            INSERT INTO t04_ospf_processes (
                host, process_id, router_id, reference_bandwidth,
                passive_default, default_originate, default_originate_always, sync_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'synchronized');
            """,
            (
                host,
                process["process_id"],
                clean_text(process.get("router_id")) or None,
                int_or_none(process.get("reference_bandwidth")),
                bool_int(process.get("passive_default")),
                bool_int(process.get("default_originate")),
                bool_int(process.get("default_originate_always")),
            ),
        )
        ospf_id = int(cursor.lastrowid)
        for network in process.get("networks", []):
            if network.get("network") and network.get("wildcard"):
                conn.execute(
                    """
                    INSERT INTO t04_ospf_networks (ospf_id, network, wildcard, area, sync_status)
                    VALUES (?, ?, ?, ?, 'synchronized');
                    """,
                    (ospf_id, network["network"], network["wildcard"], area_to_int(network.get("area"))),
                )
        distance = process.get("distance") or {}
        if any(distance.get(key) is not None for key in ("external", "intra_area", "inter_area")):
            conn.execute(
                """
                INSERT INTO t04_ospf_distance (ospf_id, external, intra_area, inter_area, sync_status)
                VALUES (?, ?, ?, ?, 'synchronized');
                """,
                (ospf_id, distance.get("external"), distance.get("intra_area"), distance.get("inter_area")),
            )
        for area in process.get("areas", {}).values():
            area_cursor = conn.execute(
                """
                INSERT INTO t04_ospf_areas (
                    ospf_id, area_id, area_type, no_summary, authentication, sync_status
                )
                VALUES (?, ?, ?, ?, ?, 'synchronized');
                """,
                (
                    ospf_id,
                    area_to_int(area.get("area_id")),
                    area.get("area_type") or "normal",
                    bool_int(area.get("no_summary")),
                    clean_text(area.get("authentication")) or None,
                ),
            )
            area_db_id = int(area_cursor.lastrowid)
            for range_row in area.get("ranges", []):
                if range_row.get("ip") and range_row.get("mask"):
                    conn.execute(
                        """
                        INSERT INTO t04_ospf_area_ranges (area_db_id, ip, mask, advertise, cost, sync_status)
                        VALUES (?, ?, ?, ?, ?, 'synchronized');
                        """,
                        (
                            area_db_id,
                            range_row["ip"],
                            range_row["mask"],
                            bool_int(range_row.get("advertise", True)),
                            int_or_none(range_row.get("cost")),
                        ),
                    )
        for redist in process.get("redistribute", []):
            conn.execute(
                """
                INSERT INTO t04_ospf_redistribute (
                    ospf_id, protocol, process_id, subnets, metric, metric_type, route_map, sync_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'synchronized');
                """,
                (
                    ospf_id,
                    redist["protocol"],
                    int_or_none(redist.get("process_id")),
                    bool_int(redist.get("subnets")),
                    int_or_none(redist.get("metric")),
                    int_or_none(redist.get("metric_type")),
                    clean_text(redist.get("route_map")) or None,
                ),
            )
        for passive in process.get("passive_interfaces", []):
            if clean_text(passive.get("interface_name")):
                conn.execute(
                    """
                    INSERT INTO t04_ospf_passive_interfaces (
                        ospf_id, interface_name, passive, sync_status
                    )
                    VALUES (?, ?, ?, 'synchronized');
                    """,
                    (
                        ospf_id,
                        clean_text(passive.get("interface_name")),
                        bool_int(passive.get("passive", True)),
                    ),
                )
        tuning = process.get("tuning") or {}
        if tuning:
            conn.execute(
                """
                INSERT INTO t04_ospf_tuning (
                    ospf_id, maximum_paths, max_lsa, spf_delay, spf_min_delay, spf_max_delay,
                    lsa_delay, lsa_min_delay, lsa_max_delay, sync_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'synchronized');
                """,
                (
                    ospf_id,
                    int_or_none(tuning.get("maximum_paths")),
                    int_or_none(tuning.get("max_lsa")),
                    int_or_none(tuning.get("spf_delay")),
                    int_or_none(tuning.get("spf_min_delay")),
                    int_or_none(tuning.get("spf_max_delay")),
                    int_or_none(tuning.get("lsa_delay")),
                    int_or_none(tuning.get("lsa_min_delay")),
                    int_or_none(tuning.get("lsa_max_delay")),
                ),
            )
        for iface in process.get("interface_settings", []):
            if clean_text(iface.get("interface_name")):
                conn.execute(
                    """
                    INSERT INTO t04_router_iface_ospf (
                        ospf_id, iface_id, area, cost, hello_interval, dead_interval,
                        mtu_ignore, bfd, network_type, auth_type, sync_status
                    )
                    VALUES (?, (SELECT iface_id FROM t02_interface_name WHERE host = ? AND interface_name = ?),
                            ?, ?, ?, ?, ?, ?, ?, ?, 1);
                    """,
                    (
                        ospf_id,
                        host,
                        clean_text(iface.get("interface_name")),
                        area_to_int(iface.get("area")),
                        int_or_none(iface.get("cost")),
                        int_or_none(iface.get("hello_interval")),
                        int_or_none(iface.get("dead_interval")),
                        bool_int(iface.get("mtu_ignore")),
                        bool_int(iface.get("bfd")),
                        clean_text(iface.get("network_type")) or None,
                        clean_text(iface.get("auth_type")) or None,
                    ),
                )
