"""Fast, responsibility-oriented device state synchronization API."""

from .common import area_to_int, bool_int, clean_label, clean_text, int_or_none
from .interfaces import (
    sync_interfaces,
    sync_l3,
    sync_subinterface,
    sync_tunnel,
    sync_wan,
)
from .fhrp import clear_fhrp_members, insert_fhrp_members
from .dhcp import sync_dhcp_helpers
from .parser import (
    ParsedRouterConfig,
    default_eigrp_process,
    default_interface,
    default_ospf_process,
    merge_interface_brief,
    merge_interface_ospf_settings,
    parse_eigrp_block,
    parse_interface_block,
    parse_interface_brief,
    parse_interface_fhrp_lines,
    parse_interface_ospf_line,
    parse_ospf_area_line,
    parse_ospf_block,
    parse_ospf_distance,
    parse_ospf_redistribute,
    parse_running_config_sections,
    parse_static_route_line,
)
from .routing import (
    sync_default_routes,
    sync_eigrp_processes,
    sync_ospf_processes,
    sync_static_routes,
)
from .service import sync_device_state

__all__ = [
    "ParsedRouterConfig",
    "area_to_int",
    "bool_int",
    "clean_label",
    "clean_text",
    "clear_fhrp_members",
    "default_eigrp_process",
    "default_interface",
    "default_ospf_process",
    "int_or_none",
    "insert_fhrp_members",
    "merge_interface_brief",
    "merge_interface_ospf_settings",
    "parse_eigrp_block",
    "parse_interface_block",
    "parse_interface_brief",
    "parse_interface_fhrp_lines",
    "parse_interface_ospf_line",
    "parse_ospf_area_line",
    "parse_ospf_block",
    "parse_ospf_distance",
    "parse_ospf_redistribute",
    "parse_running_config_sections",
    "parse_static_route_line",
    "sync_default_routes",
    "sync_dhcp_helpers",
    "sync_device_state",
    "sync_eigrp_processes",
    "sync_interfaces",
    "sync_l3",
    "sync_ospf_processes",
    "sync_subinterface",
    "sync_static_routes",
    "sync_tunnel",
    "sync_wan",
]
