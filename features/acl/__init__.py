"""ACL persistence helpers.

Mirrors the structure of features/dhcp/ for consistency.
All public functions receive the DatabaseManager instance (``db``) as the
first argument so they can call ``db._connect()`` and ``db._dict_rows()``.
"""

from .acl_db import (
    delete_acl,
    delete_acls,
    get_acl_binding_catalog,
    get_acls,
    save_acl,
    save_acl_bindings,
)

__all__ = [
    "delete_acl",
    "delete_acls",
    "get_acl_binding_catalog",
    "get_acls",
    "save_acl",
    "save_acl_bindings",
]
