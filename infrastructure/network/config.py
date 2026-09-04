from __future__ import annotations

from pathlib import Path

from infrastructure.database.paths import APP_DIR, DEVICE_NETWORK_DB

DB_PATH = str(DEVICE_NETWORK_DB)
TMP_DIR = str(APP_DIR / "tmp")
BACKUP_DIR = str(APP_DIR / "backup")
ROUTE_OUTPUT = str(Path(TMP_DIR) / "routing_output.json")
DHCP_OUTPUT = str(Path(TMP_DIR) / "dhcp_output.json")
NAT_OUTPUT = str(Path(TMP_DIR) / "nat_output.json")
ACL_OUTPUT = str(Path(TMP_DIR) / "acl_output.json")
ROUTING_TEMPLATE_DIR = str(APP_DIR / "features" / "routing" / "templates")
NAT_TEMPLATE_DIR = str(APP_DIR / "features" / "nat" / "templates")
ACL_TEMPLATE_DIR = str(APP_DIR / "features" / "acl" / "templates")

DB_TABLES = {
    "device_info": {"main": "t01_devices"},
    "routing_static": {
        "default": "t04_static_default_routes",
        "routes": "t04_static_routes",
    },
    "routing_ospf": {
        "processes": "t04_ospf_processes",
        "networks": "t04_ospf_networks",
        "areas": "t04_ospf_areas",
        "area_ranges": "t04_ospf_area_ranges",
        "distance": "t04_ospf_distance",
        "tuning": "t04_ospf_tuning",
        "redistribute": "t04_ospf_redistribute",
        "passive_interfaces": "t04_ospf_passive_interfaces",
        "interface_settings": "t04_router_iface_ospf",
    },
    "routing_eigrp": {
        "processes": "t04_eigrp_processes",
        "networks": "t04_eigrp_networks",
        "interface_settings": "t04_router_iface_eigrp",
        "passive_interfaces": "t04_eigrp_passive_interfaces",
        "distribute_lists": "t04_eigrp_distribute_lists",
        "offset_lists": "t04_eigrp_offset_lists",
        "redistribute": "t04_eigrp_redistribute",
        "key_chains": "t04_eigrp_key_chains",
    },
    "dhcp": {
        "pools": "t03_dhcp_pool",
        "excluded": "t03_excluded_address",
        "helpers": "t03_router_iface_helper",
    },
    "acl": {
        "main": "t05_ACL_DB",
        "standard": "t05_standard_acl_rules",
        "extended": "t05_extended_acl_rules",
        "dynamic": "t05_dynamic_acl_rules",
        "reflexive": "t05_reflexive_acl_rules",
        "mac": "t05_mac_acl_rules",
        "bindings": "t05_router_iface_acl",
    },
    "nat_acl": {
        "main": "t05_NAT_ACL_DB",
        "standard": "t05_nat_standard_acl_rules",
        "extended": "t05_nat_extended_acl_rules",
    },
    "nat": {
        "main": "t05_NAT_DB",
        "interfaces": "t05_nat_interfaces",
        "pools": "t05_nat_pools",
        "static_mappings": "t05_nat_static_mappings",
        "dynamic_rules": "t05_nat_dynamic_rules",
        "overload_rules": "t05_nat_overload_interface_rules",
        "exempt_rules": "t05_nat_exempt_rules",
    },
    "route_map": {
        "main": "t05_route_map_db",
        "entries": "t05_route_map_entries",
    },
}
