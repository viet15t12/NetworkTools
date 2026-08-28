"""NAT CRUD operations for all NAT tables.

Schema references (from main_numbered_tables.sql):
  t05_NAT_DB                   — parent NAT entry
  t05_nat_static_mappings      — Static NAT
  t05_nat_interfaces           — NAT interface roles (inside/outside)
  t05_nat_pools                — NAT pools (used by Dynamic rules)
  t05_nat_dynamic_rules        — Dynamic NAT rules (pool-based)
  t05_nat_overload_interface_rules — PAT (overload via interface)
  t05_NAT_ACL_DB               — NAT ACL (standard/extended)
  t05_nat_standard_acl_rules   — NAT ACL standard rules
  t05_nat_extended_acl_rules   — NAT ACL extended rules
  t05_route_map_db             — Route Map
  t05_route_map_entries        — Route Map entries

Design note:
  The QML forms use flat slot APIs without exposing the numeric nat_id. The
  repository still returns nat_name with child rows so the UI can distinguish
  the NAT parent name from ACL and route-map names.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from ipaddress import IPv4Address, IPv4Network
from typing import Any

from .common import (
    bool_to_int,
    int_or_none,
    log_db_error,
    normalize_host,
    soft_delete,
    text_or_default,
    text_or_none,
)


# ── Internal helper: get-or-create NAT_DB entry ───────────────────────────────

def _is_ipv4(value: Any) -> bool:
    try:
        IPv4Address(str(value).strip())
        return True
    except ValueError:
        return False


def _is_netmask(value: Any) -> bool:
    try:
        IPv4Network(f"0.0.0.0/{str(value).strip()}")
        return True
    except ValueError:
        return False


def _get_or_create_nat_id(conn: sqlite3.Connection, host: str, nat_type: str, nat_name: str) -> int:
    """Return, reactivate, or create the named NAT parent."""
    row = conn.execute(
        """
        SELECT nat_id, nat_type, sync_status FROM t05_NAT_DB
        WHERE host = ? AND nat_name = ?
        LIMIT 1;
        """,
        (host, nat_name),
    ).fetchone()
    if row:
        if str(row[1]) != nat_type:
            raise sqlite3.IntegrityError(
                f"NAT name {nat_name!r} already belongs to type {row[1]!r}"
            )
        nat_id = int(row[0])
        if row[2] == "pending_delete":
            conn.execute(
                """
                UPDATE t05_NAT_DB
                SET sync_status = 'pending_apply', action_Cfg = 1
                WHERE nat_id = ?;
                """,
                (nat_id,),
            )
        return nat_id
    cursor = conn.execute(
        """
        INSERT INTO t05_NAT_DB (nat_name, nat_type, host, sync_status, action_Cfg)
        VALUES (?, ?, ?, 'pending_apply', 1);
        """,
        (nat_name, nat_type, host),
    )
    return cursor.lastrowid  # type: ignore[return-value]


# ── Static NAT ────────────────────────────────────────────────────────────────

def get_nat_static_entries(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with closing(db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT m.id AS nat_static_id, m.nat_id,
                       m.inside_local_ip AS inside_local,
                       m.inside_global_ip AS inside_global,
                       UPPER(COALESCE(m.protocol, '')) AS protocol,
                       COALESCE(m.local_port, 0) AS local_port,
                       COALESCE(m.global_port, 0) AS global_port,
                       m.is_extendable, COALESCE(m.description, '') AS description,
                       m.sync_status
                FROM t05_nat_static_mappings m
                JOIN t05_NAT_DB n ON n.nat_id = m.nat_id
                WHERE n.host = ? AND n.nat_type = 'static'
                  AND n.sync_status != 'pending_delete' AND m.sync_status != 'pending_delete'
                ORDER BY m.id ASC;
                """,
                (host,),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        log_db_error("getNatStaticEntries", exc)
        return []


def add_nat_static_entry(
    db: Any,
    host: str,
    local_ip: str,
    global_ip: str,
    protocol: str,
    local_port: str,
    global_port: str,
) -> bool:
    host = normalize_host(host)
    local_ip = text_or_default(local_ip, "")
    global_ip = text_or_default(global_ip, "")
    if not host or not _is_ipv4(local_ip) or not _is_ipv4(global_ip):
        return False

    protocol_val = text_or_none(protocol)
    if protocol_val is not None:
        protocol_val = protocol_val.lower()
        if protocol_val not in ("tcp", "udp"):
            return False
    local_port_val = int_or_none(local_port)
    global_port_val = int_or_none(global_port)
    if protocol_val is None:
        local_port_val = None
        global_port_val = None
    elif (
        local_port_val is None or global_port_val is None
        or not 1 <= local_port_val <= 65535
        or not 1 <= global_port_val <= 65535
    ):
        return False

    try:
        with closing(db._connect()) as conn:
            nat_id = _get_or_create_nat_id(conn, host, "static", f"static_{host}")
            conn.execute(
                """
                INSERT INTO t05_nat_static_mappings
                    (nat_id, inside_local_ip, inside_global_ip, protocol,
                     local_port, global_port, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending_apply');
                """,
                (nat_id, local_ip, global_ip, protocol_val, local_port_val, global_port_val),
            )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addNatStaticEntry", exc)
        return False


def delete_nat_static_entry(db: Any, nat_static_id: int) -> bool:
    if nat_static_id <= 0:
        return False
    try:
        with closing(db._connect()) as conn:
            deleted = soft_delete(conn, "t05_nat_static_mappings", "id", nat_static_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteNatStaticEntry", exc)
        return False


# ── NAT Interfaces ────────────────────────────────────────────────────────────

def get_nat_interfaces(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with closing(db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT i.id AS nat_intf_id, i.nat_id,
                       i.t02_interface_name AS interface_name,
                       i.nat_role AS direction, i.sync_status
                FROM t05_nat_interfaces i
                JOIN t05_NAT_DB n ON n.nat_id = i.nat_id
                WHERE n.host = ? AND n.sync_status != 'pending_delete' AND i.sync_status != 'pending_delete'
                ORDER BY i.id ASC;
                """,
                (host,),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        log_db_error("getNatInterfaces", exc)
        return []


def add_nat_interface(db: Any, host: str, interface_name: str, nat_role: str) -> bool:
    host = normalize_host(host)
    interface_name = text_or_default(interface_name, "")
    nat_role = text_or_default(nat_role, "inside")
    if not host or not interface_name:
        return False
    if nat_role not in ("inside", "outside"):
        nat_role = "inside"
    try:
        with closing(db._connect()) as conn:
            nat_id = _get_or_create_nat_id(conn, host, "static", f"nat_iface_{host}")
            conn.execute(
                """
                INSERT INTO t05_nat_interfaces (nat_id, t02_interface_name, nat_role, sync_status)
                VALUES (?, ?, ?, 'pending_apply')
                ON CONFLICT(nat_id, t02_interface_name)
                DO UPDATE SET nat_role = excluded.nat_role, sync_status = 'pending_apply';
                """,
                (nat_id, interface_name, nat_role),
            )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addNatInterface", exc)
        return False


def delete_nat_interface(db: Any, nat_intf_id: int) -> bool:
    if nat_intf_id <= 0:
        return False
    try:
        with closing(db._connect()) as conn:
            deleted = soft_delete(conn, "t05_nat_interfaces", "id", nat_intf_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteNatInterface", exc)
        return False


# ── Dynamic NAT (pool-based) ──────────────────────────────────────────────────

def get_nat_dynamic_pools(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with closing(db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT p.pool_id AS nat_dynamic_id, p.nat_id, n.nat_name, p.pool_name,
                       p.start_ip, p.end_ip, COALESCE(p.netmask, '') AS netmask,
                       COALESCE(p.prefix_length, 0) AS prefix_length,
                       COALESCE(a.acl_name, '') AS acl_name, p.sync_status
                FROM t05_nat_pools p
                JOIN t05_NAT_DB n ON n.nat_id = p.nat_id
                LEFT JOIN t05_nat_dynamic_rules r
                  ON r.pool_id = p.pool_id AND r.sync_status != 'pending_delete'
                LEFT JOIN t05_NAT_ACL_DB a
                  ON a.nat_acl_id = r.nat_acl_id AND a.sync_status != 'pending_delete'
                WHERE n.host = ? AND n.nat_type = 'dynamic'
                  AND n.sync_status != 'pending_delete' AND p.sync_status != 'pending_delete'
                ORDER BY p.pool_id ASC;
                """,
                (host,),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        log_db_error("getNatDynamicPools", exc)
        return []


def add_nat_dynamic_pool(
    db: Any,
    host: str,
    pool_name: str,
    start_ip: str,
    end_ip: str,
    netmask: str,
    acl_name: str,
) -> bool:
    host = normalize_host(host)
    pool_name = text_or_default(pool_name, "")
    start_ip = text_or_default(start_ip, "")
    end_ip = text_or_default(end_ip, "")
    if (
        not host or not pool_name or not _is_ipv4(start_ip)
        or not _is_ipv4(end_ip) or not _is_netmask(netmask)
        or int(IPv4Address(start_ip)) > int(IPv4Address(end_ip))
    ):
        return False
    try:
        with closing(db._connect()) as conn:
            nat_id = _get_or_create_nat_id(conn, host, "dynamic", f"dynamic_{host}")
            cursor = conn.execute(
                """
                INSERT INTO t05_nat_pools (nat_id, pool_name, start_ip, end_ip, netmask, sync_status)
                VALUES (?, ?, ?, ?, ?, 'pending_apply')
                ON CONFLICT(nat_id, pool_name)
                DO UPDATE SET start_ip = excluded.start_ip,
                              end_ip = excluded.end_ip,
                              netmask = excluded.netmask,
                              prefix_length = NULL,
                              sync_status = 'pending_apply'
                RETURNING pool_id;
                """,
                (nat_id, pool_name, start_ip, end_ip, text_or_none(netmask)),
            )
            pool_id = int(cursor.fetchone()[0])
            acl_name = text_or_default(acl_name, "")
            if acl_name:
                nat_acl_id = _get_or_create_nat_acl_id(conn, host, acl_name, create=True)
                conn.execute(
                    """
                    INSERT INTO t05_nat_dynamic_rules
                        (nat_id, nat_acl_id, pool_id, overload, sync_status)
                    VALUES (?, ?, ?, 0, 'pending_apply')
                    ON CONFLICT(nat_id, nat_acl_id, pool_id)
                    DO UPDATE SET overload = 0, sync_status = 'pending_apply';
                    """,
                    (nat_id, nat_acl_id, pool_id),
                )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addNatDynamicPool", exc)
        return False


def delete_nat_dynamic_pool(db: Any, nat_dynamic_id: int) -> bool:
    if nat_dynamic_id <= 0:
        return False
    try:
        with closing(db._connect()) as conn:
            conn.execute(
                "UPDATE t05_nat_dynamic_rules SET sync_status = 'pending_delete' WHERE pool_id = ? AND sync_status != 'pending_delete';",
                (nat_dynamic_id,),
            )
            deleted = soft_delete(conn, "t05_nat_pools", "pool_id", nat_dynamic_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteNatDynamicPool", exc)
        return False


# ── PAT (overload via interface) ──────────────────────────────────────────────

def get_nat_pat_rules(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with closing(db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT r.id AS nat_pat_id, r.nat_id, n.nat_name, r.nat_acl_id,
                       a.acl_name, 'Interface' AS source_type,
                       r.outside_interface AS source_value,
                       r.overload, COALESCE(r.description, '') AS description, r.sync_status
                FROM t05_nat_overload_interface_rules r
                JOIN t05_NAT_DB n ON n.nat_id = r.nat_id
                JOIN t05_NAT_ACL_DB a ON a.nat_acl_id = r.nat_acl_id
                WHERE n.host = ? AND n.nat_type = 'overload'
                  AND n.sync_status != 'pending_delete' AND a.sync_status != 'pending_delete' AND r.sync_status != 'pending_delete'
                UNION ALL
                SELECT -r.id AS nat_pat_id, r.nat_id, n.nat_name, r.nat_acl_id,
                       a.acl_name, 'Pool' AS source_type,
                       p.pool_name AS source_value,
                       r.overload, COALESCE(r.description, '') AS description, r.sync_status
                FROM t05_nat_dynamic_rules r
                JOIN t05_NAT_DB n ON n.nat_id = r.nat_id
                JOIN t05_NAT_ACL_DB a ON a.nat_acl_id = r.nat_acl_id
                JOIN t05_nat_pools p ON p.pool_id = r.pool_id
                WHERE n.host = ? AND n.nat_type = 'dynamic'
                  AND n.sync_status != 'pending_delete' AND a.sync_status != 'pending_delete'
                  AND p.sync_status != 'pending_delete' AND r.sync_status != 'pending_delete' AND r.overload = 1
                ORDER BY nat_pat_id;
                """,
                (host, host),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        log_db_error("getNatPatRules", exc)
        return []


def _get_or_create_nat_acl_id(
    conn: sqlite3.Connection,
    host: str,
    acl_name: str,
    *,
    create: bool = False,
) -> int | None:
    """Look up an ACL parent and optionally create/reactivate it."""
    row = conn.execute(
        """
        SELECT nat_acl_id, sync_status FROM t05_NAT_ACL_DB
        WHERE host = ? AND acl_name = ?
        LIMIT 1;
        """,
        (host, acl_name),
    ).fetchone()
    if row:
        acl_id = int(row[0])
        if create and row[1] == "pending_delete":
            conn.execute(
                "UPDATE t05_NAT_ACL_DB SET sync_status = 'pending_apply', action_Cfg = 1 WHERE nat_acl_id = ?;",
                (acl_id,),
            )
        return acl_id if create or row[1] != "pending_delete" else None
    if not create:
        return None
    cursor = conn.execute(
        """
        INSERT INTO t05_NAT_ACL_DB (acl_name, acl_type, host, sync_status, action_Cfg)
        VALUES (?, 'standard', ?, 'pending_apply', 1);
        """,
        (acl_name, host),
    )
    return int(cursor.lastrowid)


def add_nat_pat_rule(
    db: Any,
    host: str,
    acl_name: str,
    source_type: str,
    source_value: str,
    overload: bool,
) -> bool:
    host = normalize_host(host)
    source_type = text_or_default(source_type, "Interface").lower()
    source_value = text_or_default(source_value, "")
    if not host or not acl_name or not source_value or source_type not in ("interface", "pool"):
        return False
    try:
        with closing(db._connect()) as conn:
            nat_acl_id = _get_or_create_nat_acl_id(conn, host, acl_name, create=True)
            if source_type == "interface":
                nat_id = _get_or_create_nat_id(conn, host, "overload", f"pat_{host}")
                conn.execute(
                    """
                    INSERT INTO t05_nat_overload_interface_rules
                        (nat_id, nat_acl_id, outside_interface, overload, sync_status)
                    VALUES (?, ?, ?, ?, 'pending_apply')
                    ON CONFLICT(nat_id, nat_acl_id, outside_interface)
                    DO UPDATE SET overload = excluded.overload, sync_status = 'pending_apply';
                    """,
                    (nat_id, nat_acl_id, source_value, bool_to_int(overload)),
                )
            else:
                pool = conn.execute(
                    """
                    SELECT p.pool_id, p.nat_id
                    FROM t05_nat_pools p
                    JOIN t05_NAT_DB n ON n.nat_id = p.nat_id
                    WHERE n.host = ? AND p.pool_name = ?
                      AND n.sync_status != 'pending_delete' AND p.sync_status != 'pending_delete'
                    LIMIT 1;
                    """,
                    (host, source_value),
                ).fetchone()
                if pool is None:
                    return False
                conn.execute(
                    """
                    INSERT INTO t05_nat_dynamic_rules
                        (nat_id, nat_acl_id, pool_id, overload, sync_status)
                    VALUES (?, ?, ?, ?, 'pending_apply')
                    ON CONFLICT(nat_id, nat_acl_id, pool_id)
                    DO UPDATE SET overload = excluded.overload, sync_status = 'pending_apply';
                    """,
                    (int(pool[1]), nat_acl_id, int(pool[0]), bool_to_int(overload)),
                )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addNatPatRule", exc)
        return False


def delete_nat_pat_rule(db: Any, nat_pat_id: int) -> bool:
    if nat_pat_id == 0:
        return False
    try:
        with closing(db._connect()) as conn:
            if nat_pat_id < 0:
                deleted = soft_delete(conn, "t05_nat_dynamic_rules", "id", -nat_pat_id)
            else:
                deleted = soft_delete(conn, "t05_nat_overload_interface_rules", "id", nat_pat_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteNatPatRule", exc)
        return False


def apply_nat_pat_quick_setup(db: Any, host: str, payload: Any) -> dict[str, Any]:
    """Create the common inside/outside + ACL + interface PAT workflow atomically."""
    host = normalize_host(host)
    values = db._as_dict(payload) if hasattr(db, "_as_dict") else dict(payload or {})
    inside_interface = text_or_default(values.get("inside_interface"), "")
    outside_interface = text_or_default(values.get("outside_interface"), "")
    source_network = text_or_default(values.get("source_network"), "")
    wildcard = text_or_default(values.get("wildcard"), "")
    acl_name = text_or_default(values.get("acl_name"), "NAT_INSIDE")

    if not host:
        return {"ok": False, "message": "Select a device before using Quick PAT setup."}
    if not inside_interface or not outside_interface:
        return {"ok": False, "message": "Select both an inside and an outside interface."}
    if inside_interface == outside_interface:
        return {"ok": False, "message": "Inside and outside interfaces must be different."}
    if not _is_ipv4(source_network) or not _is_ipv4(wildcard):
        return {"ok": False, "message": "LAN network and wildcard must be valid IPv4 values."}
    if not acl_name:
        return {"ok": False, "message": "ACL name is required."}

    try:
        with closing(db._connect()) as conn:
            available = {
                str(row[0])
                for row in conn.execute(
                    "SELECT interface_name FROM t02_interface_name WHERE host = ?;",
                    (host,),
                ).fetchall()
            }
            missing = [
                name for name in (inside_interface, outside_interface)
                if name not in available
            ]
            if missing:
                return {
                    "ok": False,
                    "message": "Interface not found for this device: " + ", ".join(missing),
                }

            interface_nat_id = _get_or_create_nat_id(
                conn, host, "static", f"nat_iface_{host}"
            )
            for interface_name, role in (
                (inside_interface, "inside"),
                (outside_interface, "outside"),
            ):
                conn.execute(
                    """
                    INSERT INTO t05_nat_interfaces
                        (nat_id, t02_interface_name, nat_role, sync_status)
                    VALUES (?, ?, ?, 'pending_apply')
                    ON CONFLICT(nat_id, t02_interface_name) DO UPDATE SET
                        nat_role = excluded.nat_role,
                        sync_status = 'pending_apply'
                    WHERE t05_nat_interfaces.nat_role != excluded.nat_role
                       OR t05_nat_interfaces.sync_status = 'pending_delete';
                    """,
                    (interface_nat_id, interface_name, role),
                )

            nat_acl_id = _get_or_create_nat_acl_id(
                conn, host, acl_name, create=True
            )
            acl_rule = conn.execute(
                """
                SELECT id, sync_status
                FROM t05_nat_standard_acl_rules
                WHERE nat_acl_id = ? AND action = 'permit'
                  AND source = ? AND COALESCE(wildcard, '') = ?
                LIMIT 1;
                """,
                (nat_acl_id, source_network, wildcard),
            ).fetchone()
            if acl_rule is None:
                next_sequence = int(conn.execute(
                    """
                    SELECT COALESCE(MAX(COALESCE(sequence, id * 10)), 0) + 10
                    FROM t05_nat_standard_acl_rules WHERE nat_acl_id = ?;
                    """,
                    (nat_acl_id,),
                ).fetchone()[0])
                conn.execute(
                    """
                    INSERT INTO t05_nat_standard_acl_rules
                        (nat_acl_id, sequence, action, source, wildcard, sync_status)
                    VALUES (?, ?, 'permit', ?, ?, 'pending_apply');
                    """,
                    (nat_acl_id, next_sequence, source_network, wildcard),
                )
            elif acl_rule["sync_status"] == "pending_delete":
                conn.execute(
                    "UPDATE t05_nat_standard_acl_rules "
                    "SET sync_status = 'pending_apply' WHERE id = ?;",
                    (acl_rule["id"],),
                )

            pat_nat_id = _get_or_create_nat_id(conn, host, "overload", f"pat_{host}")
            conn.execute(
                """
                INSERT INTO t05_nat_overload_interface_rules
                    (nat_id, nat_acl_id, outside_interface, overload, sync_status)
                VALUES (?, ?, ?, 1, 'pending_apply')
                ON CONFLICT(nat_id, nat_acl_id, outside_interface) DO UPDATE SET
                    overload = 1,
                    sync_status = 'pending_apply'
                WHERE t05_nat_overload_interface_rules.overload != 1
                   OR t05_nat_overload_interface_rules.sync_status = 'pending_delete';
                """,
                (pat_nat_id, nat_acl_id, outside_interface),
            )
            conn.commit()
        return {
            "ok": True,
            "message": (
                f"Quick PAT setup saved: {source_network} via {outside_interface}. "
                "Review the preview before pushing."
            ),
        }
    except sqlite3.Error as exc:
        log_db_error("applyNatPatQuickSetup", exc)
        return {"ok": False, "message": f"Quick PAT setup failed: {exc}"}


# ── NAT ACL ───────────────────────────────────────────────────────────────────

def get_nat_acl_names(db: Any, host: str) -> list[str]:
    """Return active ACL parent names for NAT comboboxes."""
    host = normalize_host(host)
    if not host:
        return []
    try:
        with closing(db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT acl_name
                FROM t05_NAT_ACL_DB
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY acl_name COLLATE NOCASE;
                """,
                (host,),
            ).fetchall()
        return [str(row[0]) for row in rows]
    except sqlite3.Error as exc:
        log_db_error("getNatAclNames", exc)
        return []

def get_nat_acls(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with closing(db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT a.nat_acl_id, a.acl_name, a.acl_type, a.host,
                       COALESCE(a.description, '') AS description, r.action,
                       r.source AS source_network, COALESCE(r.wildcard, '') AS wildcard,
                       r.id AS rule_id, COALESCE(r.sequence, r.id * 10) AS sequence,
                       r.sync_status
                FROM t05_NAT_ACL_DB a
                JOIN t05_nat_standard_acl_rules r ON r.nat_acl_id = a.nat_acl_id
                WHERE a.host = ? AND a.sync_status != 'pending_delete' AND r.sync_status != 'pending_delete'
                ORDER BY a.nat_acl_id ASC, r.sequence ASC, r.id ASC;
                """,
                (host,),
            ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        log_db_error("getNatAcls", exc)
        return []


def add_nat_acl(
    db: Any,
    host: str,
    acl_name: str,
    action: str,
    source_network: str,
    wildcard: str,
) -> bool:
    host = normalize_host(host)
    acl_name = text_or_default(acl_name, "")
    source_network = text_or_default(source_network, "any")
    wildcard = text_or_default(wildcard, "")
    if (
        not host or not acl_name
        or (source_network.lower() != "any" and not _is_ipv4(source_network))
        or (wildcard and not _is_ipv4(wildcard))
    ):
        return False
    try:
        with closing(db._connect()) as conn:
            nat_acl_id = _get_or_create_nat_acl_id(conn, host, acl_name, create=True)
            next_sequence = int(conn.execute(
                """
                SELECT COALESCE(MAX(COALESCE(sequence, id * 10)), 0) + 10
                FROM t05_nat_standard_acl_rules
                WHERE nat_acl_id = ?;
                """,
                (nat_acl_id,),
            ).fetchone()[0])

            conn.execute(
                """
                INSERT INTO t05_nat_standard_acl_rules
                    (nat_acl_id, sequence, action, source, wildcard, sync_status)
                VALUES (?, ?, ?, ?, ?, 'pending_apply');
                """,
                (nat_acl_id, next_sequence,
                 "permit" if str(action).strip().lower() == "permit" else "deny",
                 source_network,
                 text_or_none(wildcard)),
            )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addNatAcl", exc)
        return False


def delete_nat_acl(db: Any, nat_acl_rule_id: int) -> bool:
    if nat_acl_rule_id <= 0:
        return False
    try:
        with closing(db._connect()) as conn:
            deleted = soft_delete(conn, "t05_nat_standard_acl_rules", "id", nat_acl_rule_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteNatAcl", exc)
        return False


# ── Route Map ─────────────────────────────────────────────────────────────────

def get_nat_route_map_names(db: Any, host: str) -> list[str]:
    """Return active route-map names for the current device."""
    host = normalize_host(host)
    if not host:
        return []
    try:
        with closing(db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT route_map_name
                FROM t05_route_map_db
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY route_map_name COLLATE NOCASE;
                """,
                (host,),
            ).fetchall()
        return [str(row[0]) for row in rows]
    except sqlite3.Error as exc:
        log_db_error("getNatRouteMapNames", exc)
        return []


def get_nat_route_map_entries(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with closing(db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT rm.route_map_id, rm.route_map_name, rm.host,
                       COALESCE(rm.description, '') AS description, rm.sync_status,
                       e.id AS route_map_entry_id, e.sequence, e.action,
                       COALESCE(e.nat_acl_id, 0) AS nat_acl_id,
                       COALESCE(a.acl_name, '') AS nat_acl_name
                FROM t05_route_map_db rm
                JOIN t05_route_map_entries e ON e.route_map_id = rm.route_map_id
                LEFT JOIN t05_NAT_ACL_DB a ON a.nat_acl_id = e.nat_acl_id
                WHERE rm.host = ? AND rm.sync_status != 'pending_delete' AND e.sync_status != 'pending_delete'
                ORDER BY rm.route_map_id ASC, e.sequence ASC;
                """,
                (host,),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        log_db_error("getNatRouteMapEntries", exc)
        return []


def add_nat_route_map_entry(
    db: Any,
    host: str,
    route_map_name: str,
    description: str,
    sequence: int,
    action: str,
    acl_name: str,
) -> bool:
    host = normalize_host(host)
    route_map_name = text_or_default(route_map_name, "")
    if not host or not route_map_name:
        return False
    try:
        sequence_value = int(sequence)
    except (TypeError, ValueError):
        return False
    if not 1 <= sequence_value <= 65535:
        return False
    try:
        with closing(db._connect()) as conn:
            # Get or create route_map_db entry
            rm_row = conn.execute(
                """
                SELECT route_map_id, sync_status, description FROM t05_route_map_db
                WHERE host = ? AND route_map_name = ?
                LIMIT 1;
                """,
                (host, route_map_name),
            ).fetchone()
            if rm_row:
                rm_id = int(rm_row[0])
                new_description = text_or_none(description)
                if rm_row[1] == "pending_delete" or rm_row[2] != new_description:
                    conn.execute(
                        "UPDATE t05_route_map_db SET description = ?, sync_status = 'pending_apply' WHERE route_map_id = ?;",
                        (new_description, rm_id),
                    )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO t05_route_map_db (route_map_name, host, description, sync_status)
                    VALUES (?, ?, ?, 'pending_apply');
                    """,
                    (route_map_name, host, text_or_none(description)),
                )
                rm_id = cursor.lastrowid

            # Resolve nat_acl_id if acl_name given
            nat_acl_id: int | None = None
            if acl_name:
                nat_acl_id = _get_or_create_nat_acl_id(conn, host, acl_name, create=True)

            action_val = "permit" if str(action or "permit").strip().lower() == "permit" else "deny"
            conn.execute(
                """
                INSERT INTO t05_route_map_entries (route_map_id, sequence, action, nat_acl_id, sync_status)
                VALUES (?, ?, ?, ?, 'pending_apply')
                ON CONFLICT(route_map_id, sequence)
                DO UPDATE SET action = excluded.action,
                              nat_acl_id = excluded.nat_acl_id,
                              sync_status = 'pending_apply';
                """,
                (rm_id, sequence_value, action_val, nat_acl_id),
            )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addNatRouteMapEntry", exc)
        return False


def delete_nat_route_map_entry(db: Any, route_map_entry_id: int) -> bool:
    if route_map_entry_id <= 0:
        return False
    try:
        with closing(db._connect()) as conn:
            deleted = soft_delete(conn, "t05_route_map_entries", "id", route_map_entry_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteNatRouteMapEntry", exc)
        return False
