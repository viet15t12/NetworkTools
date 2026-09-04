"""Render Cisco IOS CLI for router-interface desired state."""

from __future__ import annotations

import re
from typing import Any

from .action_bits import ACTION_WIDTH, field_is_dirty, normalize_action_cfg
from .models import InterfaceType, infer_interface_type


def _enabled(value: Any) -> bool:
    return bool(int(value or 0))


def _append_toggle(commands: list[str], enabled: Any, command: str) -> None:
    commands.append(command if _enabled(enabled) else f"no {command}")


def _cleanup_l3(profile: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    if profile.get("secondary_ip") and profile.get("secondary_mask"):
        commands.append(
            f"no ip address {profile['secondary_ip']} {profile['secondary_mask']} secondary"
        )
    commands.extend(
        [
            "default mtu",
            "default bandwidth",
            "default delay",
            "default speed",
            "default duplex",
            "ip proxy-arp",
            "ip unreachables",
            "no ip directed-broadcast",
        ]
    )
    return commands


def _cleanup_tunnel(_profile: dict[str, Any]) -> list[str]:
    return [
        "no tunnel protection ipsec profile",
        "no keepalive",
        "no tunnel key",
        "no tunnel destination",
        "no tunnel source",
    ]


def _cleanup_wan(_profile: dict[str, Any]) -> list[str]:
    return [
        "default encapsulation",
        "no ppp authentication",
        "no ppp pap sent-username",
        "no ppp chap hostname",
        "no ppp chap password",
        "no pppoe enable group global",
        "no pppoe-client dial-pool-number",
        "no clock rate",
        "no frame-relay lmi-type",
    ]


def _cleanup_subinterface(_profile: dict[str, Any]) -> list[str]:
    return ["no encapsulation dot1Q"]


def _render_l3(
    profile: dict[str, Any], action_cfg: Any = None, *, selective: bool = False
) -> list[str]:
    commands: list[str] = []
    dirty = lambda field: not selective or field_is_dirty(action_cfg, field)
    if dirty("secondary_ip"):
        if profile.get("secondary_ip") and profile.get("secondary_mask"):
            commands.append(
                f"ip address {profile['secondary_ip']} {profile['secondary_mask']} secondary"
            )
    if dirty("mtu"):
        commands.append(f"mtu {profile['mtu']}" if profile.get("mtu") else "default mtu")
    if dirty("bandwidth") and profile.get("bandwidth"):
        commands.append(f"bandwidth {profile['bandwidth']}")
    if dirty("delay") and profile.get("delay"):
        commands.append(f"delay {profile['delay']}")
    if dirty("speed"):
        speed = str(profile.get("speed") or "auto")
        commands.append("speed auto" if speed == "auto" else f"speed {speed}")
    if dirty("duplex"):
        duplex = str(profile.get("duplex") or "auto")
        commands.append("duplex auto" if duplex == "auto" else f"duplex {duplex}")
    if dirty("negotiation"):
        # Full/legacy renders omit the IOS default. A selective change back to
        # the enabled state must explicitly undo a prior `no negotiation auto`.
        if not _enabled(profile.get("negotiation")):
            commands.append("no negotiation auto")
        elif selective:
            commands.append("negotiation auto")
    if dirty("proxy_arp"):
        _append_toggle(commands, profile.get("proxy_arp"), "ip proxy-arp")
    if dirty("unreachables"):
        _append_toggle(commands, profile.get("unreachables"), "ip unreachables")
    if dirty("directed_broadcast"):
        _append_toggle(
            commands, profile.get("directed_broadcast"), "ip directed-broadcast"
        )
    return commands


def _render_virtual_l3(
    profile: dict[str, Any], action_cfg: Any = None, *, selective: bool = False
) -> list[str]:
    """Render only L3-safe options for Loopback and other virtual L3 types."""
    commands: list[str] = []
    dirty = lambda field: not selective or field_is_dirty(action_cfg, field)
    if (
        dirty("secondary_ip")
        and profile.get("secondary_ip")
        and profile.get("secondary_mask")
    ):
        commands.append(
            f"ip address {profile['secondary_ip']} {profile['secondary_mask']} secondary"
        )
    if dirty("bandwidth") and profile.get("bandwidth"):
        commands.append(f"bandwidth {profile['bandwidth']}")
    if dirty("delay") and profile.get("delay"):
        commands.append(f"delay {profile['delay']}")
    return commands


def _render_tunnel(profile: dict[str, Any]) -> list[str]:
    mode_commands = {
        "gre": "tunnel mode gre ip",
        "ipip": "tunnel mode ipip",
        "ipsec": "tunnel mode ipsec ipv4",
        "gre-ipsec": "tunnel mode gre ip",
    }
    commands = [
        mode_commands.get(str(profile.get("tunnel_mode") or "gre"), "tunnel mode gre ip"),
        f"tunnel source {profile['tunnel_src']}",
        f"tunnel destination {profile['tunnel_dst']}",
    ]
    if profile.get("tunnel_key") is not None:
        commands.append(f"tunnel key {profile['tunnel_key']}")
    if profile.get("keepalive_sec"):
        retry = profile.get("keepalive_retry")
        commands.append(
            f"keepalive {profile['keepalive_sec']}"
            + (f" {retry}" if retry else "")
        )
    if profile.get("ipsec_profile"):
        commands.append(f"tunnel protection ipsec profile {profile['ipsec_profile']}")
    return commands


def _render_wan(profile: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    encapsulation = str(profile.get("encap_type") or "none")
    if encapsulation in {"hdlc", "ppp", "frame-relay"}:
        commands.append(f"encapsulation {encapsulation}")
    if encapsulation == "pppoe":
        commands.append("pppoe enable group global")
        if profile.get("pppoe_dialer_pool"):
            commands.append(
                f"pppoe-client dial-pool-number {profile['pppoe_dialer_pool']}"
            )
    if profile.get("ppp_auth"):
        commands.append(f"ppp authentication {profile['ppp_auth']}")
    if profile.get("ppp_username") and profile.get("ppp_password"):
        if str(profile.get("ppp_auth") or "") == "pap":
            commands.append(
                "ppp pap sent-username "
                f"{profile['ppp_username']} password 0 {profile['ppp_password']}"
            )
        else:
            commands.extend(
                [
                    f"ppp chap hostname {profile['ppp_username']}",
                    f"ppp chap password 0 {profile['ppp_password']}",
                ]
            )
    if profile.get("clock_rate"):
        commands.append(f"clock rate {profile['clock_rate']}")
    if profile.get("lmi_type"):
        commands.append(f"frame-relay lmi-type {profile['lmi_type']}")
    return commands


def _render_subinterface(profile: dict[str, Any]) -> list[str]:
    encapsulation = "dot1Q" if profile.get("encapsulation") == "dot1q" else "isl"
    command = f"encapsulation {encapsulation} {profile['vlan_id']}"
    if int(profile.get("native") or 0):
        command += " native"
    return [command]


_CLEANUP_RENDERERS = {
    "l3": _cleanup_l3,
    "tunnel": _cleanup_tunnel,
    "wan": _cleanup_wan,
    "subinterface": _cleanup_subinterface,
}
_PROFILE_RENDERERS = {
    "l3": _render_l3,
    "tunnel": _render_tunnel,
    "wan": _render_wan,
    "subinterface": _render_subinterface,
}


def render_interface_commands(task: dict[str, Any]) -> list[str]:
    """Render one interface task without transport or database side effects."""
    interface = task["interface"]
    name = str(interface.get("interface_name") or "").strip()
    if not name:
        return []
    commands = [f"interface {name}"]
    if task.get("action") == "remove":
        if infer_interface_type(name) is not InterfaceType.PHYSICAL:
            return [f"no interface {name}"]
        commands.extend(["no ip address", "no description", "shutdown", "exit"])
        return commands

    interface_type = infer_interface_type(name)
    tracking = task.get("tracking", {})
    profile_states = tracking.get("profile_states", {})
    removed_profiles = task.get("removed_profiles", {})
    effective_profile_pending = any(
        state in {"pending_apply", "pending_delete"}
        and not (
            kind == "l3"
            and kind in removed_profiles
            and interface_type is not InterfaceType.PHYSICAL
        )
        for kind, state in profile_states.items()
    )
    if not tracking.get("base_pending") and not effective_profile_pending:
        return []

    for kind, profile in removed_profiles.items():
        # Older sync snapshots could misclassify a Subinterface as L3.  Never
        # translate that stale profile into physical-only cleanup commands
        # such as `default speed` or `default duplex` on a virtual interface.
        if kind == "l3" and interface_type is not InterfaceType.PHYSICAL:
            continue
        cleanup = _CLEANUP_RENDERERS.get(kind)
        if cleanup:
            commands.extend(cleanup(profile))

    kind = task.get("profile_kind")
    profile = task.get("profile")
    raw_action_cfg = str(interface.get("action_Cfg") or "")
    valid_action_cfg = (
        len(raw_action_cfg) == ACTION_WIDTH
        and all(bit in "01" for bit in raw_action_cfg)
    )
    legacy_l3_pending = (
        kind == "l3"
        and isinstance(profile, dict)
        and str(profile.get("sync_status") or "pending_apply") == "pending_apply"
        and "1" in str(profile.get("action_Cfg") or "")
        and "1" not in normalize_action_cfg(raw_action_cfg)
    )
    selective_l3 = kind == "l3" and valid_action_cfg and not legacy_l3_pending
    action_cfg = normalize_action_cfg(raw_action_cfg)

    description = str(interface.get("description") or "").strip()
    if not selective_l3 or field_is_dirty(action_cfg, "description"):
        commands.append(
            f"description {description}" if description else "no description"
        )
    if not selective_l3 or field_is_dirty(action_cfg, "primary_ip"):
        if interface.get("ip_address") and interface.get("subnet_mask"):
            commands.append(
                f"ip address {interface['ip_address']} {interface['subnet_mask']}"
            )
        else:
            commands.append("no ip address")

    renderer = _PROFILE_RENDERERS.get(str(kind))
    if renderer and isinstance(profile, dict):
        if kind == "l3" and interface_type is not InterfaceType.PHYSICAL:
            commands.extend(
                _render_virtual_l3(profile, action_cfg, selective=selective_l3)
            )
        elif kind == "l3":
            commands.extend(_render_l3(profile, action_cfg, selective=selective_l3))
        else:
            commands.extend(renderer(profile))
    if not selective_l3 or field_is_dirty(action_cfg, "shutdown"):
        commands.append(
            "shutdown" if _enabled(interface.get("shutdown")) else "no shutdown"
        )
    if len(commands) == 1:
        return []
    commands.append("exit")
    return commands


def redact_interface_commands(commands: list[str]) -> list[str]:
    """Hide PPP secrets while retaining a useful preview."""
    redacted: list[str] = []
    for command in commands:
        if command.startswith("ppp pap sent-username ") and " password " in command:
            redacted.append(command.split(" password ", 1)[0] + " password <redacted>")
        elif command.startswith("ppp chap password "):
            redacted.append("ppp chap password <redacted>")
        else:
            redacted.append(command)
    return redacted


def redact_interface_output(output: str) -> str:
    """Remove PPP passwords that a CLI server may echo in transport output."""
    text = re.sub(
        r"(?im)(ppp\s+pap\s+sent-username\s+\S+\s+password)(?:\s+\d+)?\s+\S+",
        r"\1 <redacted>",
        str(output or ""),
    )
    return re.sub(
        r"(?im)(ppp\s+chap\s+password)(?:\s+\d+)?\s+\S+",
        r"\1 <redacted>",
        text,
    )


__all__ = [
    "redact_interface_commands",
    "redact_interface_output",
    "render_interface_commands",
]
