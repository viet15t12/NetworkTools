"""Validation for OSPF payloads crossing the QML/Python boundary."""

from __future__ import annotations

from collections.abc import Mapping
from ipaddress import IPv4Address
import re
from typing import Any

from ..common import text


AREA_MAX = 0xFFFFFFFF
SQLITE_INTEGER_MAX = (1 << 63) - 1
REDISTRIBUTE_PROTOCOLS = {"static", "connected", "eigrp", "bgp", "rip", "isis"}
NETWORK_TYPES = {"", "broadcast", "non-broadcast", "point-to-point", "point-to-multipoint"}
AUTH_TYPES = {"", "plain", "message-digest"}


def _integer(value: Any, label: str, *, minimum: int, maximum: int | None = None,
             optional: bool = False) -> int | None:
    if value is None or str(value).strip() == "":
        if optional:
            return None
        raise ValueError(f"{label} is required")
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{label} must be an integer")
        number = int(value)
    else:
        candidate = str(value).strip()
        if not re.fullmatch(r"[+-]?\d+", candidate):
            raise ValueError(f"{label} must be an integer")
        number = int(candidate)
    if isinstance(number, bool):
        raise ValueError(f"{label} must be an integer")
    effective_maximum = SQLITE_INTEGER_MAX if maximum is None else maximum
    if number < minimum or number > effective_maximum:
        suffix = f" between {minimum} and {effective_maximum}"
        raise ValueError(f"{label} must be{suffix}")
    return number


def _ipv4(value: Any, label: str) -> str:
    candidate = text(value)
    try:
        return str(IPv4Address(candidate))
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid IPv4 address") from exc


def _row(db: Any, value: Any, label: str) -> dict[str, Any]:
    try:
        row = db._as_dict(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{label} could not be converted from the QML payload; reload and try again"
        ) from exc
    if not row and not isinstance(value, Mapping):
        raise ValueError(
            f"{label} could not be converted from the QML payload; reload and try again"
        )
    return row


def _validate_unique(key: object, seen: set[object], label: str) -> None:
    if key in seen:
        raise ValueError(f"Duplicate {label}")
    seen.add(key)


def validate_ospf_processes(db: Any, process_values: list[Any]) -> None:
    process_ids: set[object] = set()
    database_ids: set[object] = set()
    for process_index, process_value in enumerate(process_values, start=1):
        process = _row(db, process_value, f"OSPF process #{process_index}")
        if not process:
            continue
        prefix = f"OSPF process #{process_index}"
        process_id = _integer(
            process.get("process_id"), f"{prefix} Process ID", minimum=1, maximum=65535
        )
        _validate_unique(process_id, process_ids, f"OSPF Process ID {process_id}")
        raw_ospf_id = process.get("ospf_id")
        ospf_id = None if raw_ospf_id in (None, "", 0, 0.0, "0") else _integer(
            raw_ospf_id, f"{prefix} database ID", minimum=1, optional=True
        )
        if ospf_id is not None:
            _validate_unique(ospf_id, database_ids, f"OSPF database ID {ospf_id}")

        router_id = text(process.get("router_id"))
        if router_id:
            _ipv4(router_id, f"{prefix} Router ID")
        _integer(
            process.get("reference_bandwidth"), f"{prefix} reference bandwidth",
            minimum=0, optional=True,
        )
        if bool(process.get("default_originate_always")) and not bool(process.get("default_originate")):
            raise ValueError(f"{prefix} cannot use 'always' without default originate")

        _validate_networks(db, process, prefix)
        _validate_distance(db, process, prefix)
        _validate_areas(db, process, prefix)
        _validate_redistribute(db, process, prefix)
        _validate_passive_interfaces(db, process, prefix)
        _validate_tuning(db, process, prefix)
        _validate_interfaces(db, process, prefix)


def _validate_networks(db: Any, process: dict[str, Any], prefix: str) -> None:
    seen: set[object] = set()
    for index, value in enumerate(db._as_list(process.get("networks")), start=1):
        row = _row(db, value, f"{prefix} network #{index}")
        network = _ipv4(row.get("network"), f"{prefix} network #{index}")
        wildcard = _ipv4(row.get("wildcard"), f"{prefix} wildcard #{index}")
        area = _integer(row.get("area"), f"{prefix} network area #{index}", minimum=0, maximum=AREA_MAX)
        _validate_unique((network, wildcard, area), seen, f"network {network} {wildcard} area {area}")


def _validate_distance(db: Any, process: dict[str, Any], prefix: str) -> None:
    distance = db._as_dict(process.get("distance"))
    for key, label in (("external", "external"), ("intra_area", "intra-area"), ("inter_area", "inter-area")):
        _integer(distance.get(key), f"{prefix} {label} distance", minimum=1, maximum=255, optional=True)


def _validate_areas(db: Any, process: dict[str, Any], prefix: str) -> None:
    seen: set[object] = set()
    for index, value in enumerate(db._as_list(process.get("areas")), start=1):
        row = _row(db, value, f"{prefix} area #{index}")
        area_id = _integer(row.get("area_id"), f"{prefix} area ID #{index}", minimum=0, maximum=AREA_MAX)
        _validate_unique(area_id, seen, f"area ID {area_id}")
        area_type = text(row.get("area_type")) or "normal"
        if area_type not in {"normal", "stub", "nssa"}:
            raise ValueError(f"{prefix} area {area_id} has an invalid type")
        if bool(row.get("no_summary")) and area_type == "normal":
            raise ValueError(f"{prefix} area {area_id}: no-summary requires stub or nssa")
        authentication = text(row.get("authentication"))
        if authentication not in AUTH_TYPES:
            raise ValueError(f"{prefix} area {area_id} has an invalid authentication type")
        range_seen: set[object] = set()
        for range_index, range_value in enumerate(db._as_list(row.get("ranges")), start=1):
            range_row = _row(db, range_value, f"{prefix} area {area_id} range #{range_index}")
            address = _ipv4(range_row.get("ip"), f"{prefix} area {area_id} range IP")
            mask = _ipv4(range_row.get("mask"), f"{prefix} area {area_id} range mask")
            _integer(range_row.get("cost"), f"{prefix} area {area_id} range cost", minimum=0, optional=True)
            _validate_unique((address, mask), range_seen, f"area {area_id} range {address} {mask}")


def _validate_redistribute(db: Any, process: dict[str, Any], prefix: str) -> None:
    seen: set[object] = set()
    for index, value in enumerate(db._as_list(process.get("redistribute")), start=1):
        row = _row(db, value, f"{prefix} redistribution #{index}")
        protocol = text(row.get("protocol"))
        if protocol not in REDISTRIBUTE_PROTOCOLS:
            raise ValueError(f"{prefix} redistribution #{index} has an invalid protocol")
        process_id = _integer(
            row.get("process_id"), f"{prefix} redistribution Process ID #{index}",
            minimum=1, maximum=65535, optional=True,
        )
        _integer(row.get("metric"), f"{prefix} redistribution metric #{index}", minimum=0, optional=True)
        metric_type = _integer(
            row.get("metric_type"), f"{prefix} redistribution metric type #{index}",
            minimum=1, maximum=2, optional=True,
        )
        _validate_unique((protocol, process_id), seen, f"redistribution {protocol} {process_id or ''}".strip())


def _validate_passive_interfaces(db: Any, process: dict[str, Any], prefix: str) -> None:
    seen: set[object] = set()
    for index, value in enumerate(db._as_list(process.get("passive_interfaces")), start=1):
        row = _row(db, value, f"{prefix} passive interface #{index}")
        name = text(row.get("interface_name"))
        if not name:
            raise ValueError(f"{prefix} passive interface #{index} is required")
        _validate_unique(name.casefold(), seen, f"passive interface {name}")


def _validate_tuning(db: Any, process: dict[str, Any], prefix: str) -> None:
    tuning = db._as_dict(process.get("tuning"))
    for key in (
        "maximum_paths", "max_lsa", "spf_delay", "spf_min_delay", "spf_max_delay",
        "lsa_delay", "lsa_min_delay", "lsa_max_delay",
    ):
        _integer(tuning.get(key), f"{prefix} {key.replace('_', ' ')}", minimum=0, optional=True)


def _validate_interfaces(db: Any, process: dict[str, Any], prefix: str) -> None:
    seen: set[object] = set()
    for index, value in enumerate(db._as_list(process.get("interface_settings")), start=1):
        row = _row(db, value, f"{prefix} interface setting #{index}")
        name = text(row.get("interface_name"))
        if not name:
            raise ValueError(f"{prefix} interface setting #{index} requires an interface")
        _validate_unique(name.casefold(), seen, f"interface setting {name}")
        _integer(row.get("area"), f"{prefix} interface {name} area", minimum=0, maximum=AREA_MAX)
        _integer(row.get("cost"), f"{prefix} interface {name} cost", minimum=1, maximum=65535, optional=True)
        _integer(row.get("priority"), f"{prefix} interface {name} priority", minimum=0, maximum=255, optional=True)
        hello = _integer(row.get("hello_interval"), f"{prefix} interface {name} hello interval", minimum=1, optional=True)
        dead = _integer(row.get("dead_interval"), f"{prefix} interface {name} dead interval", minimum=1, optional=True)
        if hello is not None and dead is not None and dead <= hello:
            raise ValueError(f"{prefix} interface {name} dead interval must exceed hello interval")
        if text(row.get("network_type")) not in NETWORK_TYPES:
            raise ValueError(f"{prefix} interface {name} has an invalid network type")
        if text(row.get("auth_type")) not in AUTH_TYPES:
            raise ValueError(f"{prefix} interface {name} has an invalid authentication type")


__all__ = ["validate_ospf_processes"]
