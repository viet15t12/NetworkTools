from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from typing import Any

from .bindings import mark_bindings_deleted, read_bindings, replace_bindings
from .common import db_connection, log_db_error, normalize_host, soft_delete, text_or_none
from .rules import mark_rules_deleted, read_rules, replace_rules
from .validation import canonical_type, validate_acl_name, validate_rules


def get_acls(db: Any, host: str, acl_type: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    try:
        kind = canonical_type(acl_type)
    except ValueError:
        return []
    if not host:
        return []
    try:
        with db_connection(db) as conn:
            rows = conn.execute(
                """SELECT Acl_id, acl_name, acl_type, host, description, sync_status, action_Cfg
                   FROM t05_ACL_DB WHERE host = ? AND lower(acl_type) = ? AND sync_status != 'pending_delete'
                   ORDER BY Acl_id""", (host, kind),
            ).fetchall()
            result = []
            for row in rows:
                acl = dict(row)
                acl["rules"] = read_rules(conn, kind, acl["Acl_id"])
                acl["bindings"] = read_bindings(conn, acl["Acl_id"])
                result.append(acl)
            return result
    except sqlite3.Error as exc:
        log_db_error("getAcls", exc)
        return []


def get_acl_binding_catalog(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with db_connection(db) as conn:
            rows = conn.execute(
                """SELECT Acl_id, acl_name, acl_type, description
                   FROM t05_ACL_DB WHERE host = ? AND sync_status != 'pending_delete'
                   ORDER BY acl_name COLLATE NOCASE""", (host,),
            ).fetchall()
            return [dict(row) | {"bindings": read_bindings(conn, row["Acl_id"])} for row in rows]
    except sqlite3.Error as exc:
        log_db_error("getAclBindingCatalog", exc)
        return []


def _existing_acl(conn: sqlite3.Connection, acl_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT Acl_id, host, acl_name, lower(acl_type) AS acl_type, description, action_Cfg
           FROM t05_ACL_DB WHERE Acl_id = ? AND sync_status != 'pending_delete'""", (acl_id,),
    ).fetchone()


def _insert_acl(
    conn: sqlite3.Connection, host: str, name: str, kind: str, description: str | None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO t05_ACL_DB
           (acl_name, acl_type, host, description, sync_status, action_Cfg)
           VALUES (?, ?, ?, ?, 'pending_apply', 1)""", (name, kind, host, description),
    )
    return int(cursor.lastrowid)


def _create_or_revive_acl(
    conn: sqlite3.Connection, host: str, name: str, kind: str, description: str | None,
) -> int:
    existing = conn.execute(
        """SELECT Acl_id, lower(acl_type) AS acl_type, sync_status
           FROM t05_ACL_DB WHERE host = ? AND acl_name = ?""", (host, name),
    ).fetchone()
    if existing is None:
        return _insert_acl(conn, host, name, kind, description)
    if existing["sync_status"] != "pending_delete":
        raise sqlite3.IntegrityError(f"ACL name already exists for host: {name}")

    acl_id = int(existing["Acl_id"])
    mark_rules_deleted(conn, existing["acl_type"], acl_id)
    mark_bindings_deleted(conn, acl_id)
    conn.execute(
        """UPDATE t05_ACL_DB
           SET acl_type = ?, description = ?, sync_status = 'pending_apply', action_Cfg = 1
           WHERE Acl_id = ?""", (kind, description, acl_id),
    )
    return acl_id


def save_acl(db: Any, payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    try:
        host = normalize_host(payload.get("host"))
        name = validate_acl_name(payload.get("acl_name"))
        kind = canonical_type(payload.get("acl_type"))
        description = text_or_none(payload.get("description"))
        acl_id = int(payload.get("acl_id") or 0)
        rules = [dict(rule) for rule in list(payload.get("rules") or [])]
        raw_bindings = payload.get("bindings")
        if raw_bindings is None and "binding" in payload:
            legacy = dict(payload.get("binding") or {})
            raw_bindings = [legacy] if legacy else []
        bindings = [dict(item) for item in list(raw_bindings or [])]
        description_only = bool(payload.get("description_only", False))
        rules_changed = bool(payload.get("rules_changed", True))
        binding_changed = bool(payload.get("binding_changed", raw_bindings is not None))
        if not host or not rules:
            return False
        validate_rules(kind, rules)
    except (TypeError, ValueError):
        return False

    try:
        with db_connection(db) as conn:
            current = _existing_acl(conn, acl_id) if acl_id > 0 else None
            if acl_id > 0 and current is None:
                return False
            if current and description_only:
                conn.execute(
                    "UPDATE t05_ACL_DB SET description = ?, action_Cfg = 1, sync_status = 'pending_apply' WHERE Acl_id = ?",
                    (description, acl_id),
                )
                conn.commit()
                return True
            identity_changed = bool(current) and (
                current["host"] != host or current["acl_name"] != name or current["acl_type"] != kind
            )
            if identity_changed:
                preserved_bindings = [
                    {"iface_id": item["iface_id"], "direction": item["direction"]}
                    for item in read_bindings(conn, acl_id)
                ]
                if current["host"] == host and current["acl_name"] == name:
                    mark_rules_deleted(conn, current["acl_type"], acl_id)
                    conn.execute(
                        """UPDATE t05_ACL_DB
                           SET acl_type = ?, description = ?, sync_status = 'pending_apply', action_Cfg = 1
                           WHERE Acl_id = ?""", (kind, description, acl_id),
                    )
                else:
                    mark_rules_deleted(conn, current["acl_type"], acl_id)
                    mark_bindings_deleted(conn, acl_id)
                    soft_delete(conn, "t05_ACL_DB", "Acl_id", acl_id)
                    acl_id = _create_or_revive_acl(conn, host, name, kind, description)
                rules_changed = True
                if raw_bindings is None:
                    bindings = preserved_bindings
                binding_changed = True
            elif current:
                action_cfg = 1 if (current["description"] or "") != (description or "") else current["action_Cfg"]
                conn.execute(
                    "UPDATE t05_ACL_DB SET description = ?, action_Cfg = ?, sync_status = 'pending_apply' WHERE Acl_id = ?",
                    (description, action_cfg, acl_id),
                )
            else:
                acl_id = _create_or_revive_acl(conn, host, name, kind, description)

            if rules_changed or current is None:
                replace_rules(conn, kind, acl_id, rules)
            if binding_changed:
                replace_bindings(conn, acl_id, host, bindings)
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("saveAcl", exc)
        return False


def save_acl_bindings(db: Any, acl_id: int, payload: Any) -> bool:
    if acl_id <= 0 or not isinstance(payload, list):
        return False
    try:
        bindings = [dict(item) for item in payload]
    except (TypeError, ValueError):
        return False
    try:
        with db_connection(db) as conn:
            current = _existing_acl(conn, acl_id)
            if current is None:
                return False
            replace_bindings(conn, acl_id, current["host"], bindings)
            conn.execute("UPDATE t05_ACL_DB SET sync_status = 'pending_apply' WHERE Acl_id = ?", (acl_id,))
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("saveAclBindings", exc)
        return False


def delete_acls(db: Any, payload: Any) -> bool:
    try:
        acl_ids = list(dict.fromkeys(int(value) for value in list(payload or []) if int(value) > 0))
    except (TypeError, ValueError):
        return False
    if not acl_ids:
        return False
    try:
        with db_connection(db) as conn:
            current_rows = [_existing_acl(conn, acl_id) for acl_id in acl_ids]
            if any(row is None for row in current_rows):
                return False
            for acl_id, current in zip(acl_ids, current_rows):
                mark_rules_deleted(conn, current["acl_type"], acl_id)
                mark_bindings_deleted(conn, acl_id)
                soft_delete(conn, "t05_ACL_DB", "Acl_id", acl_id)
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("deleteAcls", exc)
        return False


def delete_acl(db: Any, acl_id: int) -> bool:
    return delete_acls(db, [acl_id])
