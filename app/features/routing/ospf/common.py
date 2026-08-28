from __future__ import annotations

from typing import Any

from ..common import as_dict, as_list, bool_int_value, int_or_none_value, int_or_zero_value, text


OSPF_ACTION_BITS = 4


def normalize_action_cfg(value: Any, default: str = "1111") -> str:
    mask = text(value)
    return mask if len(mask) == OSPF_ACTION_BITS and all(bit in "01" for bit in mask) else default


def process_action_cfg(current: dict[str, Any] | None, submitted: dict[str, Any]) -> str:
    """Return a bit mask containing only changed process-level command groups."""
    if current is None:
        return "1111"
    before = normalize_process_core(current)
    after = normalize_process_core(submitted)
    return "".join(
        (
            "1" if before["router_id"] != after["router_id"] else "0",
            "1" if before["reference_bandwidth"] != after["reference_bandwidth"] else "0",
            "1" if before["passive_default"] != after["passive_default"] else "0",
            "1" if (
                before["default_originate"], before["default_originate_always"]
            ) != (
                after["default_originate"], after["default_originate_always"]
            ) else "0",
        )
    )


def normalize_priority(value: Any) -> int:
    priority = int_or_none_value(value)
    return 1 if priority is None else priority


def normalize_process(db: Any, process: dict[str, Any]) -> dict[str, Any]:
    distance = as_dict(db, process.get("distance"))
    tuning = as_dict(db, process.get("tuning"))

    return {
        "process_id": int_or_none_value(process.get("process_id")),
        "router_id": text(process.get("router_id")),
        "reference_bandwidth": int_or_zero_value(process.get("reference_bandwidth")),
        "passive_default": bool_int_value(process.get("passive_default")),
        "default_originate": bool_int_value(process.get("default_originate")),
        "default_originate_always": bool_int_value(process.get("default_originate_always")),
        "networks": [
            {
                "network": text(as_dict(db, row).get("network")),
                "wildcard": text(as_dict(db, row).get("wildcard")),
                "area": int_or_zero_value(as_dict(db, row).get("area")),
            }
            for row in as_list(db, process.get("networks"))
            if text(as_dict(db, row).get("network")) or text(as_dict(db, row).get("wildcard"))
        ],
        "distance": (
            {
                "external": int_or_none_value(distance.get("external")),
                "intra_area": int_or_none_value(distance.get("intra_area")),
                "inter_area": int_or_none_value(distance.get("inter_area")),
            }
            if distance
            else {}
        ),
        "areas": [
            {
                "area_id": int_or_zero_value(area.get("area_id")),
                "area_type": text(area.get("area_type")) or "normal",
                "no_summary": bool_int_value(area.get("no_summary")),
                "authentication": text(area.get("authentication")),
                "ranges": [
                    {
                        "ip": text(range_row.get("ip")),
                        "mask": text(range_row.get("mask")),
                        "advertise": bool_int_value(range_row.get("advertise", True)),
                        "cost": int_or_none_value(range_row.get("cost")),
                    }
                    for range_row in (as_dict(db, range_value) for range_value in as_list(db, area.get("ranges")))
                    if text(range_row.get("ip")) or text(range_row.get("mask"))
                ],
            }
            for area in (as_dict(db, area_value) for area_value in as_list(db, process.get("areas")))
        ],
        "redistribute": [
            {
                "protocol": text(redist.get("protocol")) or "static",
                "process_id": int_or_none_value(redist.get("process_id")),
                "subnets": bool_int_value(redist.get("subnets", True)),
                "metric": int_or_none_value(redist.get("metric")),
                "metric_type": int_or_none_value(redist.get("metric_type")),
                "route_map": text(redist.get("route_map")),
            }
            for redist in (as_dict(db, redist_value) for redist_value in as_list(db, process.get("redistribute")))
            if text(redist.get("protocol"))
        ],
        "passive_interfaces": [
            {
                "interface_name": text(passive.get("interface_name")),
                "passive": bool_int_value(passive.get("passive", True)),
            }
            for passive in (as_dict(db, passive_value) for passive_value in as_list(db, process.get("passive_interfaces")))
            if text(passive.get("interface_name"))
        ],
        "tuning": (
            {
                "maximum_paths": int_or_none_value(tuning.get("maximum_paths")),
                "max_lsa": int_or_none_value(tuning.get("max_lsa")),
                "spf_delay": int_or_none_value(tuning.get("spf_delay")),
                "spf_min_delay": int_or_none_value(tuning.get("spf_min_delay")),
                "spf_max_delay": int_or_none_value(tuning.get("spf_max_delay")),
                "lsa_delay": int_or_none_value(tuning.get("lsa_delay")),
                "lsa_min_delay": int_or_none_value(tuning.get("lsa_min_delay")),
                "lsa_max_delay": int_or_none_value(tuning.get("lsa_max_delay")),
            }
            if tuning
            else {}
        ),
        "interface_settings": [
            {
                "interface_name": text(iface.get("interface_name")),
                "area": int_or_zero_value(iface.get("area")),
                "cost": int_or_none_value(iface.get("cost")),
                "priority": normalize_priority(iface.get("priority")),
                "hello_interval": int_or_none_value(iface.get("hello_interval")),
                "dead_interval": int_or_none_value(iface.get("dead_interval")),
                "mtu_ignore": bool_int_value(iface.get("mtu_ignore")),
                "bfd": bool_int_value(iface.get("bfd")),
                "network_type": text(iface.get("network_type")),
                "auth_type": text(iface.get("auth_type")),
                "auth_key": text(iface.get("auth_key")),
            }
            for iface in (as_dict(db, iface_value) for iface_value in as_list(db, process.get("interface_settings")))
            if text(iface.get("interface_name"))
        ],
    }


def normalize_process_core(process: dict[str, Any]) -> dict[str, Any]:
    return {
        "process_id": int_or_none_value(process.get("process_id")),
        "router_id": text(process.get("router_id")),
        "reference_bandwidth": int_or_zero_value(process.get("reference_bandwidth")),
        "passive_default": bool_int_value(process.get("passive_default")),
        "default_originate": bool_int_value(process.get("default_originate")),
        "default_originate_always": bool_int_value(process.get("default_originate_always")),
    }


def normalize_without_networks(db: Any, process: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_process(db, process)
    normalized["networks"] = []
    return normalized


def network_key(row: dict[str, Any]) -> tuple[str, str, int]:
    return (
        text(row.get("network")),
        text(row.get("wildcard")),
        int_or_zero_value(row.get("area")),
    )


def payload_networks(db: Any, process: dict[str, Any]) -> dict[tuple[str, str, int], dict[str, Any]]:
    networks: dict[tuple[str, str, int], dict[str, Any]] = {}
    for network_value in db._as_list(process.get("networks")):
        network = db._as_dict(network_value)
        key = network_key(network)
        if key[0] and key[1]:
            networks[key] = network
    return networks
