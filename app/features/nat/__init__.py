"""NAT persistence helpers.

Mirrors the structure of features/dhcp/ and features/acl/.
All public functions receive the DatabaseManager instance (``db``) as the
first argument so they can call ``db._connect()`` and ``db._dict_rows()``.
"""

from .nat_db import (
    add_nat_acl,
    add_nat_dynamic_pool,
    add_nat_interface,
    add_nat_pat_rule,
    add_nat_route_map_entry,
    add_nat_static_entry,
    delete_nat_acl,
    delete_nat_dynamic_pool,
    delete_nat_interface,
    delete_nat_pat_rule,
    delete_nat_route_map_entry,
    delete_nat_static_entry,
    get_nat_acls,
    get_nat_acl_names,
    get_nat_dynamic_pools,
    get_nat_interfaces,
    get_nat_pat_rules,
    get_nat_route_map_entries,
    get_nat_route_map_names,
    get_nat_static_entries,
)

__all__ = [
    "add_nat_acl",
    "add_nat_dynamic_pool",
    "add_nat_interface",
    "add_nat_pat_rule",
    "add_nat_route_map_entry",
    "add_nat_static_entry",
    "delete_nat_acl",
    "delete_nat_dynamic_pool",
    "delete_nat_interface",
    "delete_nat_pat_rule",
    "delete_nat_route_map_entry",
    "delete_nat_static_entry",
    "get_nat_acls",
    "get_nat_acl_names",
    "get_nat_dynamic_pools",
    "get_nat_interfaces",
    "get_nat_pat_rules",
    "get_nat_route_map_entries",
    "get_nat_route_map_names",
    "get_nat_static_entries",
]
