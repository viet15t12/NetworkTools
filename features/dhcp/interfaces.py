"""Compatibility shim for the former DHCP-owned interface repository."""

from features.interfaces.repository import (
    delete_router_interface,
    get_router_interface_by_name,
    get_router_interfaces,
    save_router_interface,
)

__all__ = [
    "delete_router_interface",
    "get_router_interface_by_name",
    "get_router_interfaces",
    "save_router_interface",
]
