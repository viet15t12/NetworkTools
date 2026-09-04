from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSlot

from features.interfaces import (
    delete_router_interface,
    get_router_interface_by_name,
    get_router_interfaces,
)
from features.interfaces.service import InterfaceService


class InterfaceSlotsMixin:
    """Expose router-interface persistence without coupling it to DHCP."""

    @pyqtSlot(str, result="QVariant")
    def getRouterInterfaces(self, host: str) -> list[dict[str, Any]]:
        return get_router_interfaces(self, host)

    @pyqtSlot(str, str, result="QVariant")
    def getRouterInterfaceByName(self, host: str, name: str) -> dict[str, Any]:
        return get_router_interface_by_name(self, host, name)

    @pyqtSlot("QVariant", result=bool)
    def saveRouterInterface(self, payload: Any) -> bool:
        return bool(InterfaceService(self).save(payload).get("ok"))

    @pyqtSlot("QVariant", result="QVariant")
    def saveRouterInterfaceResult(self, payload: Any) -> dict[str, Any]:
        """Validate and save one interface with a structured QML result."""
        return InterfaceService(self).save(payload)

    @pyqtSlot(str, result="QVariant")
    def getRouterInterfaceCapabilities(self, host: str) -> dict[str, Any]:
        """Return backend-owned create/delete/L1 capability metadata."""
        return InterfaceService(self).capabilities(host)

    @pyqtSlot(str, str, "QVariant", result="QVariant")
    def createRouterVirtualInterface(
        self, host: str, interface_type: str, payload: Any
    ) -> dict[str, Any]:
        """Create a deterministically named Loopback, Tunnel or Subinterface."""
        return InterfaceService(self).create_virtual(host, interface_type, payload)

    @pyqtSlot(str, "QVariant", result="QVariant")
    def buildRouterVirtualInterfaceName(
        self, interface_type: str, payload: Any
    ) -> dict[str, Any]:
        """Build a canonical virtual name before the user completes its form."""
        return InterfaceService(self).build_virtual_name(interface_type, payload)

    @pyqtSlot(int, result=bool)
    def deleteRouterInterface(self, iface_id: int) -> bool:
        return delete_router_interface(self, iface_id)
