"""Validation and orchestration for multi-device FHRP configuration."""

from __future__ import annotations

import ipaddress
import re
import sqlite3
from typing import Any

from .repository import FhrpRepository


LIMITS = {"hsrp": (0, 4095), "vrrp": (1, 255), "glbp": (0, 1023)}
_TRACK_OBJECT_RE = re.compile(r"^(?:[1-9][0-9]{0,3}|[A-Za-z][A-Za-z0-9./:_-]*)$")


class FhrpService:
    """Expose a compact frontend contract without leaking schema details."""

    MAX_HOSTS = 5

    def __init__(self, db: Any) -> None:
        self.db = db
        self.repository = FhrpRepository(db)

    def options(self) -> dict[str, Any]:
        return {"ok": True, "hosts": self.repository.connected_hosts()}

    def matching_interfaces(self, hosts: list[Any], gateway_text: str) -> dict[str, Any]:
        normalized_hosts = list(dict.fromkeys(str(host or "").strip() for host in hosts))
        normalized_hosts = [host for host in normalized_hosts if host]
        try:
            gateway = ipaddress.IPv4Address(str(gateway_text or "").strip())
        except ValueError:
            return {"ok": False, "message": "Default Gateway must be a valid IPv4 address.", "interfaces": []}
        interfaces = self.repository.matching_interfaces(normalized_hosts, gateway)
        return {
            "ok": True,
            "message": f"Found {len(interfaces)} matching interface(s).",
            "interfaces": interfaces,
        }

    def groups(self, host: str = "") -> dict[str, Any]:
        return {"ok": True, "groups": self.repository.list_groups(str(host or "").strip())}

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = self._normalize(payload)
            fhrp_id = self.repository.save_group(normalized)
            hosts = [member["host"] for member in normalized["members"]]
            return {
                "ok": True,
                "fhrp_id": fhrp_id,
                "hosts": hosts,
                "message": f"Saved {normalized['protocol'].upper()} group for {len(hosts)} devices.",
            }
        except (ValueError, sqlite3.Error) as exc:
            return {"ok": False, "fhrp_id": 0, "hosts": [], "message": str(exc)}

    def delete(self, fhrp_id: int) -> dict[str, Any]:
        if fhrp_id <= 0:
            return {"ok": False, "hosts": [], "message": "Invalid FHRP group ID."}
        hosts = self.repository.mark_group_for_delete(fhrp_id)
        return {
            "ok": bool(hosts),
            "hosts": hosts,
            "message": f"Marked FHRP group for removal on {len(hosts)} devices.",
        }

    def cancel_delete(self, fhrp_id: int) -> dict[str, Any]:
        if fhrp_id <= 0:
            return {"ok": False, "hosts": [], "message": "Invalid FHRP group ID."}
        hosts = self.repository.cancel_group_delete(fhrp_id)
        return {
            "ok": bool(hosts),
            "hosts": hosts,
            "message": (
                f"Cancelled FHRP group removal on {len(hosts)} devices."
                if hosts
                else "FHRP group is not waiting for removal."
            ),
        }

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        protocol = str(payload.get("protocol") or "").strip().lower()
        if protocol not in LIMITS:
            raise ValueError("Protocol must be HSRP, VRRP or GLBP.")
        group_number = self.db._int_or_none(payload.get("group_number"))
        low, high = LIMITS[protocol]
        if group_number is None or not low <= group_number <= high:
            raise ValueError(f"{protocol.upper()} group must be between {low} and {high}.")
        gateway_text = str(
            payload.get("default_gateway") or payload.get("virtual_ip") or ""
        ).strip()
        try:
            gateway = ipaddress.IPv4Address(gateway_text)
        except ValueError as exc:
            raise ValueError("Default Gateway must be a valid IPv4 address.") from exc

        raw_members = [
            self.db._as_dict(item)
            for item in self.db._as_list(payload.get("members"))
        ]
        if len(raw_members) < 2:
            raise ValueError("FHRP requires at least two selected hosts.")
        if len(raw_members) > self.MAX_HOSTS:
            raise ValueError(
                f"FHRP supports at most {self.MAX_HOSTS} selected hosts."
            )
        hosts: set[str] = set()
        selected_endpoints: set[tuple[str, str, int]] = set()
        members: list[dict[str, Any]] = []
        candidates = self.repository.matching_interfaces(
            [str(item.get("host") or "").strip() for item in raw_members],
            gateway,
        )
        for raw in raw_members:
            host = str(raw.get("host") or "").strip()
            iface_id = self.db._int_or_none(raw.get("iface_id"))
            if not host or host in hosts:
                raise ValueError("Every FHRP member must use a unique host.")
            requested_kind = str(raw.get("interface_kind") or "").strip().lower()
            endpoint_matches = [
                row
                for row in candidates
                if row["host"] == host
                and int(row["iface_id"]) == iface_id
                and (
                    not requested_kind
                    or str(row["interface_kind"]) == requested_kind
                )
            ]
            if iface_id is None or len(endpoint_matches) != 1:
                raise ValueError(f"Selected interface on {host} does not reach {gateway}.")
            endpoint = endpoint_matches[0]
            interface_kind = str(endpoint["interface_kind"])
            endpoint_key = (host, interface_kind, iface_id)
            if endpoint_key in selected_endpoints:
                raise ValueError("An interface can only be selected once.")
            priority = self.db._int_or_none(raw.get("priority"))
            if priority is None:
                priority = 100
            priority_high = 254 if protocol == "vrrp" else 255
            if not 1 <= priority <= priority_high:
                suffix = (
                    " Priority 255 is reserved for VRRP address-owner mode, "
                    "which is not supported by this form."
                    if protocol == "vrrp"
                    else ""
                )
                raise ValueError(
                    f"Priority on {host} must be between 1 and {priority_high}.{suffix}"
                )
            options = self._protocol_options(protocol, raw, host)
            if protocol == "hsrp" and options["version"] == 1 and group_number > 255:
                raise ValueError(f"HSRP version 1 group on {host} must be between 0 and 255.")
            member = dict(raw)
            member.update(
                {
                    "host": host,
                    "iface_id": iface_id,
                    "interface_kind": interface_kind,
                    "interface_name": str(endpoint["interface_name"]),
                    "subnet_mask": str(endpoint["subnet_mask"]),
                    "network": str(endpoint["network"]),
                    "priority": priority,
                    "preempt": self._boolean(raw.get("preempt")),
                    "shutdown": self._boolean(raw.get("shutdown")),
                    **options,
                    "tracks": self._tracks(raw.get("tracks")),
                }
            )
            hosts.add(host)
            selected_endpoints.add(endpoint_key)
            members.append(member)
        if len({member["network"] for member in members}) != 1:
            raise ValueError(
                "All FHRP member interfaces must use the same IPv4 subnet and prefix."
            )
        self._validate_shared_policy(protocol, members)
        return {
            "protocol": protocol,
            "group_number": group_number,
            "virtual_ip": str(gateway),
            "description": str(payload.get("description") or "").strip(),
            "members": members,
        }

    def _protocol_options(
        self, protocol: str, raw: dict[str, Any], host: str
    ) -> dict[str, Any]:
        auth_type = str(raw.get("auth_type") or "none").strip().lower()
        auth_secret = str(raw.get("auth_secret") or "").strip()
        allowed_auth = (
            {"none", "plain"}
            if protocol == "vrrp"
            else {"none", "plain", "md5-key", "md5-keychain"}
        )
        if auth_type not in allowed_auth:
            raise ValueError(f"Unsupported {protocol.upper()} authentication on {host}.")
        if auth_type != "none" and not auth_secret:
            raise ValueError(f"Authentication secret is required on {host}.")
        if auth_type == "none":
            auth_secret = ""
        elif any(character.isspace() for character in auth_secret):
            raise ValueError(
                f"Authentication value on {host} cannot contain whitespace."
            )
        secret_limit = 8 if auth_type == "plain" else (100 if protocol == "glbp" else 64)
        if len(auth_secret) > secret_limit:
            raise ValueError(
                f"Authentication value on {host} exceeds {secret_limit} characters."
            )

        if protocol == "hsrp":
            version = self._integer(raw, "version", 2, 1, 2, host)
            if version == 1 and auth_type.startswith("md5"):
                raise ValueError(f"HSRP MD5 authentication on {host} requires version 2.")
            hello = self._integer(raw, "hello_ms", 3000, 1, 255000, host)
            hold = self._integer(raw, "hold_ms", 10000, 2, 255000, host)
            if hold <= hello:
                raise ValueError(f"HSRP hold timer on {host} must exceed hello timer.")
            return {
                "version": version,
                "hello_ms": hello,
                "hold_ms": hold,
                "preempt_delay_min_sec": self._integer(
                    raw, "preempt_delay_min_sec", 0, 0, 3600, host
                ),
                "preempt_delay_reload_sec": self._integer(
                    raw, "preempt_delay_reload_sec", 0, 0, 3600, host
                ),
                "auth_type": auth_type,
                "auth_secret": auth_secret,
            }
        if protocol == "vrrp":
            version = self._integer(raw, "version", 2, 2, 3, host)
            if version != 2:
                raise ValueError(
                    "This Cisco IOS workflow supports VRRPv2 only; VRRPv3 "
                    "requires a device-wide mode change."
                )
            if self._boolean(raw.get("accept_mode")):
                raise ValueError("VRRP accept mode requires VRRPv3 and is not supported.")
            return {
                "version": 2,
                "advertisement_ms": self._integer(
                    raw, "advertisement_ms", 1000, 1, 60000, host
                ),
                "accept_mode": False,
                "auth_type": auth_type,
                "auth_secret": auth_secret,
            }

        hello = self._integer(raw, "hello_ms", 3000, 1, 255000, host)
        hold = self._integer(raw, "hold_ms", 10000, 2, 255000, host)
        if hold <= hello:
            raise ValueError(f"GLBP hold timer on {host} must exceed hello timer.")
        load_balancing = str(raw.get("load_balancing") or "round-robin").strip().lower()
        if load_balancing not in {"round-robin", "weighted", "host-dependent"}:
            raise ValueError(f"Unsupported GLBP load-balancing mode on {host}.")
        maximum = self._integer(raw, "weighting_max", 100, 1, 254, host)
        lower = self._optional_integer(raw, "weighting_lower", 1, 254, host)
        upper = self._optional_integer(raw, "weighting_upper", 1, 254, host)
        if lower is not None and lower > maximum:
            raise ValueError(f"GLBP lower weighting on {host} cannot exceed maximum.")
        if upper is not None and upper > maximum:
            raise ValueError(f"GLBP upper weighting on {host} cannot exceed maximum.")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"GLBP lower weighting on {host} cannot exceed upper.")
        return {
            "hello_ms": hello,
            "hold_ms": hold,
            "load_balancing": load_balancing,
            "weighting_max": maximum,
            "weighting_lower": lower,
            "weighting_upper": upper,
            "forwarder_preempt": self._boolean(
                raw.get("forwarder_preempt"), default=True
            ),
            "forwarder_preempt_delay_sec": self._integer(
                raw, "forwarder_preempt_delay_sec", 30, 0, 3600, host
            ),
            "auth_type": auth_type,
            "auth_secret": auth_secret,
        }

    def _validate_shared_policy(
        self, protocol: str, members: list[dict[str, Any]]
    ) -> None:
        fields = {
            "hsrp": ("version", "hello_ms", "hold_ms", "auth_type", "auth_secret"),
            "vrrp": ("version", "advertisement_ms", "auth_type", "auth_secret"),
            "glbp": (
                "hello_ms",
                "hold_ms",
                "load_balancing",
                "auth_type",
                "auth_secret",
            ),
        }[protocol]
        baseline = tuple(members[0][field] for field in fields)
        if any(tuple(member[field] for field in fields) != baseline for member in members[1:]):
            raise ValueError(
                f"All {protocol.upper()} members must use the same version, timers, "
                "authentication and group-wide policy."
            )

    def _integer(
        self,
        raw: dict[str, Any],
        field: str,
        default: int,
        low: int,
        high: int,
        host: str,
    ) -> int:
        value = self.db._int_or_none(raw.get(field))
        if value is None and raw.get(field) not in (None, ""):
            raise ValueError(f"{field} on {host} must be an integer.")
        value = default if value is None else value
        if not low <= value <= high:
            raise ValueError(f"{field} on {host} must be between {low} and {high}.")
        return value

    def _boolean(self, value: Any, *, default: bool = False) -> bool:
        if value is None:
            return default
        converter = getattr(self.db, "_bool_int", None)
        return bool(converter(value)) if callable(converter) else bool(value)

    def _optional_integer(
        self, raw: dict[str, Any], field: str, low: int, high: int, host: str
    ) -> int | None:
        if raw.get(field) in (None, ""):
            return None
        return self._integer(raw, field, low, low, high, host)

    def _tracks(self, value: Any) -> list[dict[str, Any]]:
        tracks: list[dict[str, Any]] = []
        for item in self.db._as_list(value):
            row = self.db._as_dict(item)
            track_object = str(row.get("track_object") or "").strip()
            if not track_object:
                continue
            if not _TRACK_OBJECT_RE.fullmatch(track_object):
                raise ValueError(
                    "Track object must be an object ID or a valid interface name."
                )
            decrement = self.db._int_or_none(row.get("decrement_value")) or 10
            if not 1 <= decrement <= 254:
                raise ValueError("Track decrement must be between 1 and 254.")
            tracks.append(
                {"track_object": track_object, "decrement_value": decrement}
            )
        if len({track["track_object"] for track in tracks}) != len(tracks):
            raise ValueError("Track objects must be unique per FHRP member.")
        return tracks
