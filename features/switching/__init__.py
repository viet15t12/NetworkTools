"""Switch SW2/SW3 desired-state persistence and Cisco IOS Layer 2 push support."""

from .etherchannel_repository import delete_etherchannel, get_etherchannels, save_etherchannel
from .interface_repository import get_switch_interfaces, save_switch_interface
from .l3_repository import delete_svi, get_ip_routing, get_svis, save_ip_routing, save_svi
from .monitoring_repository import get_mac_table, get_port_counters
from .navigation import navigation_for_role
from .policy_delete_repository import (
    delete_l2_trust_port,
    delete_l2_vlan_security,
    delete_static_mac,
    delete_stp_config,
)
from .schema import ensure_switch_schema
from .security_repository import (
    add_l2_trust_port,
    get_l2_security,
    save_l2_vlan_security,
    save_static_mac,
)
from .stp_repository import get_stp_configs, save_stp_config
from .vlan_repository import delete_vlan, get_vlans, save_vlan
from .vtp_group import VtpGroupService

__all__ = [
    "ensure_switch_schema",
    "add_l2_trust_port",
    "delete_etherchannel",
    "delete_l2_trust_port",
    "delete_l2_vlan_security",
    "delete_static_mac",
    "delete_stp_config",
    "delete_svi",
    "delete_vlan",
    "get_etherchannels",
    "get_ip_routing",
    "get_mac_table",
    "get_l2_security",
    "get_port_counters",
    "get_svis",
    "get_switch_interfaces",
    "get_stp_configs",
    "get_vlans",
    "navigation_for_role",
    "save_etherchannel",
    "save_ip_routing",
    "save_l2_vlan_security",
    "save_svi",
    "save_switch_interface",
    "save_static_mac",
    "save_stp_config",
    "save_vlan",
    "VtpGroupService",
]
