"""AclSlotsMixin — PyQt6 slots for ACL CRUD.

Mirrors DhcpSlotsMixin in dhcp_slots.py.

MRO note: DatabaseManager must list AclSlotsMixin *before* StubSlotsMixin
so that these real implementations shadow the stubs:

    class DatabaseManager(DhcpSlotsMixin, AclSlotsMixin, StubSlotsMixin, QObject): ...
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSlot

from features.acl import delete_acl, delete_acls, get_acl_binding_catalog, get_acls, save_acl, save_acl_bindings


class AclSlotsMixin:
    @pyqtSlot(str, str, result="QVariant")
    def getAcls(self, host: str, acl_type: str) -> list[dict[str, Any]]:
        """Return all non-deleted ACLs for host+type, including rules and bindings."""
        return get_acls(self, host, acl_type)

    @pyqtSlot(str, result="QVariant")
    def getAclBindingCatalog(self, host: str) -> list[dict[str, Any]]:
        return get_acl_binding_catalog(self, host)

    @pyqtSlot("QVariant", result=bool)
    def saveAcl(self, payload: Any) -> bool:
        """Create or update an ACL.

        *payload* is the JS object from AclForm.saveAcl():
        {
          acl_id, host, acl_name, acl_type, description,
          description_only, rules, binding: {iface_id, direction}
        }
        Returns True on success, False on validation or DB error.
        """
        # A JavaScript object passed through a QVariant slot can arrive as
        # QJSValue. DatabaseManager._as_dict() uses toVariant() first and also
        # handles normal dictionaries/mappings safely.
        data = self._as_dict(payload)
        return save_acl(self, data)

    @pyqtSlot(int, "QVariant", result=bool)
    def saveAclBindings(self, acl_id: int, payload: Any) -> bool:
        return save_acl_bindings(self, acl_id, self._as_list(payload))

    @pyqtSlot(int, result=bool)
    def deleteAcl(self, acl_id: int) -> bool:
        """Mark an ACL pending_delete and clean up its interface bindings."""
        return delete_acl(self, acl_id)

    @pyqtSlot("QVariant", result=bool)
    def deleteAcls(self, payload: Any) -> bool:
        return delete_acls(self, self._as_list(payload))
