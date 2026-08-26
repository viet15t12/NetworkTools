"""QML slots for the FHRP feature boundary."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSlot

from features.fhrp import FhrpService


class FhrpSlotsMixin:
    """Expose FHRP services without embedding feature SQL in the facade."""

    @pyqtSlot(result="QVariant")
    def getFhrpOptions(self) -> dict[str, Any]:
        """Return connected router/L3-switch hosts for multi-device selection."""
        return FhrpService(self).options()

    @pyqtSlot("QVariant", str, result="QVariant")
    def getFhrpMatchingInterfaces(
        self, hosts: Any, default_gateway: str
    ) -> dict[str, Any]:
        """Filter interfaces whose configured subnet contains the gateway IP."""
        return FhrpService(self).matching_interfaces(
            self._as_list(hosts),
            default_gateway,
        )

    @pyqtSlot(str, result="QVariant")
    @pyqtSlot(result="QVariant")
    def getFhrpGroups(self, host: str = "") -> dict[str, Any]:
        """Load saved FHRP groups, optionally scoped to one member host."""
        return FhrpService(self).groups(host)

    @pyqtSlot("QVariant", result="QVariant")
    def saveFhrpGroup(self, payload: Any) -> dict[str, Any]:
        """Validate and persist one HSRP/VRRP/GLBP group for multiple hosts."""
        return FhrpService(self).save(self._as_dict(payload))

    @pyqtSlot(int, result="QVariant")
    def deleteFhrpGroup(self, fhrp_id: int) -> dict[str, Any]:
        """Stage one logical FHRP group for removal from all member hosts."""
        return FhrpService(self).delete(fhrp_id)

    @pyqtSlot(int, result="QVariant")
    def cancelFhrpGroupDelete(self, fhrp_id: int) -> dict[str, Any]:
        """Cancel a staged group removal before it is pushed to devices."""
        return FhrpService(self).cancel_delete(fhrp_id)
