from __future__ import annotations

from typing import Any

from ..common import as_dict, as_list, bool_int_value, int_or_none_value, int_or_zero_value, text


def normalize_action_cfg(value: Any) -> str:
    text_value = text(value)
    return text_value if len(text_value) == 7 and all(ch in "01" for ch in text_value) else "1111111"


def normalize_process(db: Any, process: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_number": int_or_none_value(process.get("as_number")),
        "router_id": text(process.get("router_id")),
        "timers_active_time": int_or_zero_value(process.get("timers_active_time")),
        "bfd_all_interfaces": bool_int_value(process.get("bfd_all_interfaces")),
        "auto_summary": bool_int_value(process.get("auto_summary")),
        "passive_default": bool_int_value(process.get("passive_default")),
        "metric_weights": text(process.get("metric_weights")) or "0 1 0 1 0 0",
        "distance_internal": int_or_zero_value(process.get("distance_internal")),
        "distance_external": int_or_zero_value(process.get("distance_external")),
        "variance": int_or_zero_value(process.get("variance")),
        "maximum_paths": int_or_zero_value(process.get("maximum_paths")),
        "stub_enabled": bool_int_value(process.get("stub_enabled")),
        "stub_options": text(process.get("stub_options")),
        "stub_leak_map": text(process.get("stub_leak_map")),
        "action": int_or_none_value(process.get("action")) or 15,
        "action_Cfg": normalize_action_cfg(process.get("action_Cfg")),
        "networks": [
            {
                "network": text(row.get("network")),
                "wildcard": text(row.get("wildcard")),
                "interface_name": text(row.get("interface_name")),
            }
            for row in (as_dict(db, value) for value in as_list(db, process.get("networks")))
            if text(row.get("network"))
        ],
        "interface_settings": [
            {
                "interface_name": text(row.get("interface_name")),
                "bandwidth": int_or_zero_value(row.get("bandwidth")),
                "delay": int_or_zero_value(row.get("delay")),
                "hello_interval": int_or_zero_value(row.get("hello_interval")),
                "hold_time": int_or_zero_value(row.get("hold_time")),
                "auth_key_chain": text(row.get("auth_key_chain")),
                "summary_ip": text(row.get("summary_ip")),
                "summary_mask": text(row.get("summary_mask")),
                "split_horizon": bool_int_value(row.get("split_horizon")),
                "bandwidth_percent": int_or_zero_value(row.get("bandwidth_percent")),
                "next_hop_self": bool_int_value(row.get("next_hop_self")),
                "bfd": bool_int_value(row.get("bfd")),
                "bfd_tx": int_or_zero_value(row.get("bfd_tx")),
                "bfd_rx": int_or_zero_value(row.get("bfd_rx")),
                "bfd_multiplier": int_or_zero_value(row.get("bfd_multiplier")),
            }
            for row in (as_dict(db, value) for value in as_list(db, process.get("interface_settings")))
            if text(row.get("interface_name"))
        ],
        "passive_interfaces": [
            {
                "interface_name": text(row.get("interface_name")),
                "mode": text(row.get("mode")) or "passive",
            }
            for row in (as_dict(db, value) for value in as_list(db, process.get("passive_interfaces")))
            if text(row.get("interface_name"))
        ],
        "distribute_lists": [
            {
                "list_name": text(row.get("list_name")),
                "direction": text(row.get("direction")) or "in",
                "interface_name": text(row.get("interface_name")),
            }
            for row in (as_dict(db, value) for value in as_list(db, process.get("distribute_lists")))
            if text(row.get("list_name"))
        ],
        "offset_lists": [
            {
                "list_name": text(row.get("list_name")),
                "direction": text(row.get("direction")) or "in",
                "value": int_or_zero_value(row.get("value")),
                "interface_name": text(row.get("interface_name")),
            }
            for row in (as_dict(db, value) for value in as_list(db, process.get("offset_lists")))
            if text(row.get("list_name")) and int_or_zero_value(row.get("value")) > 0
        ],
        "redistribute": [
            {
                "protocol": text(row.get("protocol")),
                "route_map": text(row.get("route_map")),
                "metric_bw": int_or_zero_value(row.get("metric_bw")),
                "metric_delay": int_or_zero_value(row.get("metric_delay")),
                "metric_reliability": int_or_zero_value(row.get("metric_reliability")),
                "metric_load": int_or_zero_value(row.get("metric_load")),
                "metric_mtu": int_or_zero_value(row.get("metric_mtu")),
            }
            for row in (as_dict(db, value) for value in as_list(db, process.get("redistribute")))
            if text(row.get("protocol"))
        ],
    }
