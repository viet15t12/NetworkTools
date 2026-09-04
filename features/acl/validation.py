from __future__ import annotations

import ipaddress
import re
from typing import Any

ACL_TYPES = {"standard", "extended", "dynamic", "reflexive", "mac"}
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_MAC_RE = re.compile(r"^(?:[0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}$")
_PORT_RE = re.compile(r"^(?:eq|neq|lt|gt)\s+[A-Za-z0-9_-]+$|^range\s+\S+\s+\S+$")


def canonical_type(value: Any) -> str:
    acl_type = str(value or "").strip().lower()
    if acl_type not in ACL_TYPES:
        raise ValueError("Unsupported ACL type")
    return acl_type


def validate_acl_name(value: Any) -> str:
    name = str(value or "").strip()
    if not _NAME_RE.fullmatch(name):
        raise ValueError("ACL name must use 1-64 letters, digits, '.', '_' or '-'")
    return name


def _ipv4(value: Any, field: str) -> str:
    text = str(value or "").strip()
    try:
        return str(ipaddress.IPv4Address(text))
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"Invalid {field}: {text}") from exc


def _endpoint(value: Any, wildcard: Any, field: str) -> None:
    text = str(value or "any").strip().lower()
    if text == "any":
        return
    if text.startswith("host "):
        _ipv4(text[5:].strip(), field)
        return
    _ipv4(text, field)
    if wildcard not in (None, ""):
        _ipv4(wildcard, f"{field} wildcard")


def _port(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if re.fullmatch(r"[A-Za-z0-9_-]+", text):
        return f"eq {text}"
    if text and not _PORT_RE.fullmatch(text):
        raise ValueError(f"{field} must use eq/neq/lt/gt/range Cisco syntax")
    return text


def _icmp_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("eq "):
        text = text[3:].strip()
    if text and not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise ValueError("ICMP type must be a Cisco name or number")
    return text


def _sequence(rule: dict[str, Any]) -> None:
    value = rule.get("sequence")
    if value in (None, ""):
        return
    sequence = int(value)
    if not 1 <= sequence <= 65535:
        raise ValueError("ACL sequence must be between 1 and 65535")


def _timeout_seconds(rule: dict[str, Any], acl_type: str) -> None:
    if acl_type not in {"dynamic", "reflexive"}:
        return
    value = rule.get("timeout_seconds")
    try:
        timeout = int(value) if value not in (None, "") else 300
    except (TypeError, ValueError) as exc:
        raise ValueError("ACL timeout must be an integer") from exc

    if acl_type == "dynamic" and not 60 <= timeout <= 9999 * 60:
        raise ValueError("Dynamic ACL timeout must be between 1 and 9999 minutes")
    if acl_type == "reflexive" and not 30 <= timeout <= 2147483:
        raise ValueError("Reflexive ACL timeout must be between 30 and 2147483 seconds")
    rule["timeout_seconds"] = timeout


def validate_rules(acl_type: str, rules: list[dict[str, Any]]) -> None:
    seen: set[int] = set()
    for rule in rules:
        _sequence(rule)
        sequence = int(rule.get("sequence") or 0)
        if sequence and sequence in seen:
            raise ValueError(f"Duplicate ACL sequence: {sequence}")
        seen.add(sequence)
        if str(rule.get("action") or "permit").lower() not in {"permit", "deny"}:
            raise ValueError("ACL action must be permit or deny")

        if acl_type == "mac":
            for key in ("src_mac", "dst_mac"):
                value = str(rule.get(key) or "any").strip()
                if value.lower() != "any" and not _MAC_RE.fullmatch(value):
                    raise ValueError(f"{key} must use Cisco xxxx.xxxx.xxxx format")
            for key in ("src_mask", "dst_mask"):
                value = str(rule.get(key) or "").strip()
                if value and not _MAC_RE.fullmatch(value):
                    raise ValueError(f"{key} must use Cisco xxxx.xxxx.xxxx format")
            continue

        _endpoint(rule.get("source"), rule.get("wildcard") or rule.get("src_wildcard"), "source")
        if acl_type != "standard":
            _endpoint(rule.get("destination"), rule.get("dst_wildcard"), "destination")
            protocol = str(rule.get("protocol") or "ip").strip().lower()
            if protocol in {"tcp", "udp"}:
                rule["src_port"] = _port(rule.get("src_port"), "Source port")
                rule["dst_port"] = _port(rule.get("dst_port"), "Destination port")
            elif protocol == "icmp":
                if str(rule.get("src_port") or "").strip():
                    raise ValueError("ICMP rules do not support a source port")
                rule["src_port"] = ""
                rule["dst_port"] = _icmp_type(rule.get("dst_port"))
            elif str(rule.get("src_port") or "").strip() or str(rule.get("dst_port") or "").strip():
                raise ValueError(f"Protocol {protocol} does not support TCP/UDP ports")
        if acl_type == "dynamic" and not str(rule.get("dynamic_name") or "").strip():
            raise ValueError("Dynamic ACL rule requires dynamic_name")
        _timeout_seconds(rule, acl_type)
