"""NatSlotsMixin — PyQt6 slots for NAT CRUD.

Mirrors DhcpSlotsMixin and AclSlotsMixin patterns.

MRO note: DatabaseManager must list NatSlotsMixin *before* StubSlotsMixin
so that these real implementations shadow the stubs.
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSlot

from features.nat import (
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


class NatSlotsMixin:
    # ── Static NAT ────────────────────────────────────────────────────────────

    @pyqtSlot(str, result="QVariant")
    def getNatStaticEntries(self, host: str) -> list[dict[str, Any]]:
        return get_nat_static_entries(self, host)

    @pyqtSlot(str, str, str, str, str, str, result=bool)
    def addNatStaticEntry(
        self,
        host: str,
        local_ip: str,
        global_ip: str,
        protocol: str,
        local_port: str,
        global_port: str,
    ) -> bool:
        return add_nat_static_entry(self, host, local_ip, global_ip, protocol, local_port, global_port)

    @pyqtSlot(int, result=bool)
    def deleteNatStaticEntry(self, nat_static_id: int) -> bool:
        return delete_nat_static_entry(self, nat_static_id)

    # ── NAT Interfaces ────────────────────────────────────────────────────────

    @pyqtSlot(str, result="QVariant")
    def getNatInterfaces(self, host: str) -> list[dict[str, Any]]:
        return get_nat_interfaces(self, host)

    @pyqtSlot(str, str, str, result=bool)
    def addNatInterface(self, host: str, interface_name: str, nat_role: str) -> bool:
        return add_nat_interface(self, host, interface_name, nat_role)

    @pyqtSlot(int, result=bool)
    def deleteNatInterface(self, nat_intf_id: int) -> bool:
        return delete_nat_interface(self, nat_intf_id)

    # ── Dynamic NAT ───────────────────────────────────────────────────────────

    @pyqtSlot(str, result="QVariant")
    def getNatDynamicPools(self, host: str) -> list[dict[str, Any]]:
        return get_nat_dynamic_pools(self, host)

    @pyqtSlot(str, str, str, str, str, str, result=bool)
    def addNatDynamicPool(
        self,
        host: str,
        pool_name: str,
        start_ip: str,
        end_ip: str,
        netmask: str,
        acl_name: str,
    ) -> bool:
        return add_nat_dynamic_pool(self, host, pool_name, start_ip, end_ip, netmask, acl_name)

    @pyqtSlot(int, result=bool)
    def deleteNatDynamicPool(self, nat_dynamic_id: int) -> bool:
        return delete_nat_dynamic_pool(self, nat_dynamic_id)

    # ── PAT (overload) ────────────────────────────────────────────────────────

    @pyqtSlot(str, result="QVariant")
    def getNatPatRules(self, host: str) -> list[dict[str, Any]]:
        return get_nat_pat_rules(self, host)

    @pyqtSlot(str, str, str, str, bool, result=bool)
    def addNatPatRule(
        self,
        host: str,
        acl_name: str,
        source_type: str,
        source_value: str,
        overload: bool,
    ) -> bool:
        return add_nat_pat_rule(self, host, acl_name, source_type, source_value, overload)

    @pyqtSlot(int, result=bool)
    def deleteNatPatRule(self, nat_pat_id: int) -> bool:
        return delete_nat_pat_rule(self, nat_pat_id)

    # ── NAT ACL ───────────────────────────────────────────────────────────────

    @pyqtSlot(str, result="QVariant")
    def getNatAclNames(self, host: str) -> list[str]:
        return get_nat_acl_names(self, host)

    @pyqtSlot(str, result="QVariant")
    def getNatAcls(self, host: str) -> list[dict[str, Any]]:
        return get_nat_acls(self, host)

    @pyqtSlot(str, str, str, str, str, result=bool)
    def addNatAcl(self, host: str, acl_name: str, action: str, source_network: str, wildcard: str) -> bool:
        return add_nat_acl(self, host, acl_name, action, source_network, wildcard)

    @pyqtSlot(int, result=bool)
    def deleteNatAcl(self, nat_acl_rule_id: int) -> bool:
        return delete_nat_acl(self, nat_acl_rule_id)

    # ── Route Map ─────────────────────────────────────────────────────────────

    @pyqtSlot(str, result="QVariant")
    def getNatRouteMapEntries(self, host: str) -> list[dict[str, Any]]:
        return get_nat_route_map_entries(self, host)

    @pyqtSlot(str, result="QVariant")
    def getNatRouteMapNames(self, host: str) -> list[str]:
        return get_nat_route_map_names(self, host)

    @pyqtSlot(str, str, str, int, str, str, result=bool)
    def addNatRouteMapEntry(
        self,
        host: str,
        route_map_name: str,
        description: str,
        sequence: int,
        action: str,
        acl_name: str,
    ) -> bool:
        return add_nat_route_map_entry(self, host, route_map_name, description, sequence, action, acl_name)

    @pyqtSlot(int, result=bool)
    def deleteNatRouteMapEntry(self, route_map_entry_id: int) -> bool:
        return delete_nat_route_map_entry(self, route_map_entry_id)
