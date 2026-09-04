from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSlot

# Imports use the canonical feature package; no sys.path mutation is required.
from features.switching import (
    add_l2_trust_port,
    delete_etherchannel,
    delete_l2_trust_port,
    delete_l2_vlan_security,
    delete_svi,
    delete_static_mac,
    delete_stp_config,
    delete_vlan,
    get_etherchannels,
    get_ip_routing,
    get_mac_table,
    get_l2_security,
    get_port_counters,
    get_svis,
    get_switch_interfaces,
    get_stp_configs,
    get_vlans,
    navigation_for_role,
    save_etherchannel,
    save_ip_routing,
    save_l2_vlan_security,
    save_svi,
    save_switch_interface,
    save_static_mac,
    save_stp_config,
    save_vlan,
    VtpGroupService,
)


class SwitchSlotsMixin:
    """QML bridge for local switch workspace operations."""

    @pyqtSlot(str, result="QVariant")
    def getSwitchNavigation(self, role: str) -> list[dict[str, Any]]:
        return navigation_for_role(role)

    @pyqtSlot(str, result="QVariant")
    def getSwitchVlans(self, host: str) -> list[dict[str, Any]]:
        return get_vlans(self, host)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSwitchVlan(self, host: str, payload: Any) -> dict[str, Any]:
        return save_vlan(self, host, self._as_dict(payload))

    @pyqtSlot(str, int, result="QVariant")
    def deleteSwitchVlan(self, host: str, row_id: int) -> dict[str, Any]:
        return delete_vlan(self, host, row_id)

    @pyqtSlot(str, result="QVariant")
    def getSwitchInterfaces(self, host: str) -> list[dict[str, Any]]:
        return get_switch_interfaces(self, host)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSwitchInterface(self, host: str, payload: Any) -> dict[str, Any]:
        return save_switch_interface(self, host, self._as_dict(payload))

    @pyqtSlot(str, result="QVariant")
    def getSwitchEtherChannels(self, host: str) -> list[dict[str, Any]]:
        return get_etherchannels(self, host)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSwitchEtherChannel(self, host: str, payload: Any) -> dict[str, Any]:
        return save_etherchannel(self, host, self._as_dict(payload))

    @pyqtSlot(str, int, result="QVariant")
    def deleteSwitchEtherChannel(self, host: str, row_id: int) -> dict[str, Any]:
        return delete_etherchannel(self, host, row_id)

    @pyqtSlot(str, result="QVariant")
    def getSwitchStpConfigs(self, host: str) -> list[dict[str, Any]]:
        return get_stp_configs(self, host)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSwitchStpConfig(self, host: str, payload: Any) -> dict[str, Any]:
        return save_stp_config(self, host, self._as_dict(payload))

    @pyqtSlot(str, int, result="QVariant")
    def deleteSwitchStpConfig(self, host: str, row_id: int) -> dict[str, Any]:
        """Stage deletion of one STP VLAN policy for the selected switch."""
        return delete_stp_config(self, host, row_id)

    @pyqtSlot(str, result="QVariant")
    def getSwitchL2Security(self, host: str) -> dict[str, Any]:
        return get_l2_security(self, host)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSwitchL2VlanSecurity(self, host: str, payload: Any) -> dict[str, Any]:
        return save_l2_vlan_security(self, host, self._as_dict(payload))

    @pyqtSlot(str, int, result="QVariant")
    def deleteSwitchL2VlanSecurity(self, host: str, row_id: int) -> dict[str, Any]:
        """Stage removal of DHCP Snooping/DAI policy from one VLAN."""
        return delete_l2_vlan_security(self, host, row_id)

    @pyqtSlot(str, str, result="QVariant")
    def addSwitchL2TrustPort(self, host: str, if_name: str) -> dict[str, Any]:
        return add_l2_trust_port(self, host, if_name)

    @pyqtSlot(str, int, result="QVariant")
    def deleteSwitchL2TrustPort(self, host: str, row_id: int) -> dict[str, Any]:
        """Stage removal of DHCP/ARP trust from one switch interface."""
        return delete_l2_trust_port(self, host, row_id)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSwitchStaticMac(self, host: str, payload: Any) -> dict[str, Any]:
        return save_static_mac(self, host, self._as_dict(payload))

    @pyqtSlot(str, int, result="QVariant")
    def deleteSwitchStaticMac(self, host: str, row_id: int) -> dict[str, Any]:
        """Stage deletion of one static MAC forwarding binding."""
        return delete_static_mac(self, host, row_id)

    @pyqtSlot(str, result="QVariant")
    def getSwitchSvis(self, host: str) -> list[dict[str, Any]]:
        return get_svis(self, host)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSwitchSvi(self, host: str, payload: Any) -> dict[str, Any]:
        return save_svi(self, host, self._as_dict(payload))

    @pyqtSlot(str, int, result="QVariant")
    def deleteSwitchSvi(self, host: str, row_id: int) -> dict[str, Any]:
        return delete_svi(self, host, row_id)

    @pyqtSlot(str, result="QVariant")
    def getSwitchIpRouting(self, host: str) -> dict[str, Any]:
        return get_ip_routing(self, host)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSwitchIpRouting(self, host: str, enabled: Any) -> dict[str, Any]:
        return save_ip_routing(self, host, enabled)

    @pyqtSlot(result="QVariant")
    def getVtpGroupOptions(self) -> dict[str, Any]:
        """Return connected switches eligible for a VTP group."""
        return VtpGroupService(self).options()

    @pyqtSlot(result="QVariant")
    def getVtpGroups(self) -> dict[str, Any]:
        """Return locally stored VTP domains and their switch members."""
        return VtpGroupService(self).groups()

    @pyqtSlot("QVariant", result="QVariant")
    def saveVtpGroup(self, payload: Any) -> dict[str, Any]:
        """Stage one VTP domain for several switches."""
        return VtpGroupService(self).save(self._as_dict(payload))

    @pyqtSlot(str, result="QVariant")
    def getSwitchPortCounters(self, host: str) -> list[dict[str, Any]]:
        return get_port_counters(self, host)

    @pyqtSlot(str, result="QVariant")
    def getSwitchMacTable(self, host: str) -> list[dict[str, Any]]:
        return get_mac_table(self, host)
