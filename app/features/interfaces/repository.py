from __future__ import annotations

import sqlite3
from typing import Any

from .action_bits import (
    FULL_ACTION_CFG,
    action_cfg_for,
    has_dirty_fields,
    merge_action_cfg,
)
from .common import db_connection, log_db_error, normalize_host, text_or_none
from .models import InterfaceType, infer_interface_type, qml_metadata


def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def _int_or_none(db: Any, value: Any) -> int | None:
    return db._int_or_none(value)


def _bool_int(db: Any, value: Any) -> int:
    return db._bool_int(value)


def _interface_select_sql(where_clause: str) -> str:
    return f"""
        SELECT
            i.iface_id,
            i.host,
            i.interface_name,
            i.ip_address,
            i.subnet_mask,
            i.description,
            i.shutdown,
            i.sync_status,
            i.action_Cfg,
            CASE
                WHEN s.id IS NOT NULL THEN 'Subinterface'
                WHEN t.iface_id IS NOT NULL THEN 'Tunnel'
                WHEN w.iface_id IS NOT NULL THEN 'WAN'
                ELSE 'L3'
            END AS interface_kind,
            CASE WHEN l.iface_id IS NOT NULL THEN 1 ELSE 0 END AS has_l3,
            CASE WHEN t.iface_id IS NOT NULL THEN 1 ELSE 0 END AS has_tunnel,
            CASE WHEN w.iface_id IS NOT NULL THEN 1 ELSE 0 END AS has_wan,
            l.secondary_ip,
            l.secondary_mask,
            l.mtu,
            l.bandwidth,
            l.delay,
            l.speed,
            l.duplex,
            l.negotiation,
            l.proxy_arp,
            l.unreachables,
            l.directed_broadcast,
            l.action_Cfg AS l3_action_Cfg,
            t.tunnel_mode,
            t.tunnel_src,
            t.tunnel_dst,
            t.tunnel_key,
            t.keepalive_sec,
            t.keepalive_retry,
            t.ipsec_profile,
            w.encap_type,
            w.pppoe_dialer_pool,
            w.ppp_auth,
            w.ppp_username,
            w.ppp_password,
            w.clock_rate,
            w.lmi_type,
            s.parent_iface_id,
            p.interface_name AS parent_interface,
            s.encapsulation AS subif_encapsulation,
            s.vlan_id AS subif_vlan_id,
            s.native AS subif_native
        FROM t02_interface_name AS i
        LEFT JOIN t02_router_iface_l3 AS l
            ON l.iface_id = i.iface_id AND COALESCE(l.sync_status, 'pending_apply') != 'pending_delete'
        LEFT JOIN t02_router_iface_tunnel AS t
            ON t.iface_id = i.iface_id AND COALESCE(t.sync_status, 'pending_apply') != 'pending_delete'
        LEFT JOIN t02_router_iface_wan AS w
            ON w.iface_id = i.iface_id AND COALESCE(w.sync_status, 'pending_apply') != 'pending_delete'
        LEFT JOIN t02_router_iface_subif AS s
            ON s.host = i.host AND s.subif_name = i.interface_name
           AND COALESCE(s.sync_status, 'pending_apply') != 'pending_delete'
        LEFT JOIN t02_interface_name AS p
            ON p.iface_id = s.parent_iface_id
        WHERE {where_clause}
    """


def get_router_interfaces(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with db_connection(db) as conn:
            rows = conn.execute(
                _interface_select_sql("i.host = ? AND COALESCE(i.sync_status, 'pending_apply') != 'pending_delete'")
                + " ORDER BY i.interface_name COLLATE NOCASE;",
                (host,),
            ).fetchall()
        values = db._dict_rows(rows)
        for row in values:
            row.update(qml_metadata(row.get("interface_name"), row.get("interface_kind")))
        return values
    except sqlite3.Error as exc:
        log_db_error("getRouterInterfaces", exc)
        return []


def get_router_interface_by_name(db: Any, host: str, name: str) -> dict[str, Any]:
    host = normalize_host(host)
    name = (name or "").strip()
    if not host or not name:
        return {}
    try:
        with db_connection(db) as conn:
            row = conn.execute(
                _interface_select_sql(
                    "i.host = ? AND i.interface_name = ? AND COALESCE(i.sync_status, 'pending_apply') != 'pending_delete'"
                )
                + " ORDER BY i.iface_id DESC LIMIT 1;",
                (host, name),
            ).fetchone()
        if not row:
            return {}
        value = dict(row)
        value.update(qml_metadata(value.get("interface_name"), value.get("interface_kind")))
        return value
    except sqlite3.Error as exc:
        log_db_error("getRouterInterfaceByName", exc)
        return {}


def get_router_interface_by_id(db: Any, iface_id: int) -> dict[str, Any]:
    if iface_id <= 0:
        return {}
    try:
        with db_connection(db) as conn:
            row = conn.execute(
                _interface_select_sql("i.iface_id = ?")
                + " ORDER BY i.iface_id DESC LIMIT 1;",
                (iface_id,),
            ).fetchone()
        if not row:
            return {}
        value = dict(row)
        value.update(qml_metadata(value.get("interface_name"), value.get("interface_kind")))
        return value
    except sqlite3.Error as exc:
        log_db_error("getRouterInterfaceById", exc)
        return {}


def _l3_values(db: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "secondary_ip": text_or_none(payload.get("secondary_ip")),
        "secondary_mask": text_or_none(payload.get("secondary_mask")),
        "mtu": _int_or_none(db, payload.get("mtu")) or 1500,
        "bandwidth": _int_or_none(db, payload.get("bandwidth")),
        "delay": _int_or_none(db, payload.get("delay")),
        "speed": _choice(payload.get("speed"), {"auto", "10", "100", "1000", "10000"}, "auto"),
        "duplex": _choice(payload.get("duplex"), {"auto", "full", "half"}, "auto"),
        "negotiation": _bool_int(db, payload.get("negotiation", True)),
        "proxy_arp": _bool_int(db, payload.get("proxy_arp", True)),
        "unreachables": _bool_int(db, payload.get("unreachables", True)),
        "directed_broadcast": _bool_int(db, payload.get("directed_broadcast")),
    }


def _upsert_l3(
    conn: sqlite3.Connection,
    db: Any,
    iface_id: int,
    payload: dict[str, Any],
    sync_status: str = "pending_apply",
) -> None:
    values = _l3_values(db, payload)
    conn.execute(
        """
        INSERT INTO t02_router_iface_l3 (
            iface_id, secondary_ip, secondary_mask, mtu, bandwidth, delay,
            speed, duplex, negotiation, proxy_arp, unreachables,
            directed_broadcast, sync_status, action_Cfg
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '00000')
        ON CONFLICT(iface_id) DO UPDATE SET
            secondary_ip = excluded.secondary_ip,
            secondary_mask = excluded.secondary_mask,
            mtu = excluded.mtu,
            bandwidth = excluded.bandwidth,
            delay = excluded.delay,
            speed = excluded.speed,
            duplex = excluded.duplex,
            negotiation = excluded.negotiation,
            proxy_arp = excluded.proxy_arp,
            unreachables = excluded.unreachables,
            directed_broadcast = excluded.directed_broadcast,
            sync_status = excluded.sync_status,
            action_Cfg = '00000';
        """,
        (
            iface_id,
            values["secondary_ip"],
            values["secondary_mask"],
            values["mtu"],
            values["bandwidth"],
            values["delay"],
            values["speed"],
            values["duplex"],
            values["negotiation"],
            values["proxy_arp"],
            values["unreachables"],
            values["directed_broadcast"],
            sync_status,
        ),
    )


def _changed_l3_fields(current: sqlite3.Row | None, desired: dict[str, Any]) -> set[str]:
    if current is None:
        return {
            "secondary_ip",
            "mtu",
            "bandwidth",
            "delay",
            "speed",
            "duplex",
            "negotiation",
            "proxy_arp",
            "unreachables",
            "directed_broadcast",
        }
    groups = {
        "secondary_ip": ("secondary_ip", "secondary_mask"),
        "mtu": ("mtu",),
        "bandwidth": ("bandwidth",),
        "delay": ("delay",),
        "speed": ("speed",),
        "duplex": ("duplex",),
        "negotiation": ("negotiation",),
        "proxy_arp": ("proxy_arp",),
        "unreachables": ("unreachables",),
        "directed_broadcast": ("directed_broadcast",),
    }
    return {
        field
        for field, columns in groups.items()
        if any(current[column] != desired[column] for column in columns)
    }


def _upsert_tunnel(conn: sqlite3.Connection, db: Any, iface_id: int, payload: dict[str, Any], sync_status: str = "pending_apply") -> bool:
    tunnel_src = text_or_none(payload.get("tunnel_src"))
    tunnel_dst = text_or_none(payload.get("tunnel_dst"))
    if not tunnel_src or not tunnel_dst:
        return False
    tunnel_mode = _choice(payload.get("tunnel_mode"), {"gre", "ipip", "ipsec", "gre-ipsec"}, "gre")
    conn.execute(
        """
        INSERT INTO t02_router_iface_tunnel (
            iface_id, tunnel_mode, tunnel_src, tunnel_dst, tunnel_key,
            keepalive_sec, keepalive_retry, ipsec_profile, sync_status, action_Cfg
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '111')
        ON CONFLICT(iface_id) DO UPDATE SET
            tunnel_mode = excluded.tunnel_mode,
            tunnel_src = excluded.tunnel_src,
            tunnel_dst = excluded.tunnel_dst,
            tunnel_key = excluded.tunnel_key,
            keepalive_sec = excluded.keepalive_sec,
            keepalive_retry = excluded.keepalive_retry,
            ipsec_profile = excluded.ipsec_profile,
            sync_status = excluded.sync_status,
            action_Cfg = '111';
        """,
        (
            iface_id,
            tunnel_mode,
            tunnel_src,
            tunnel_dst,
            _int_or_none(db, payload.get("tunnel_key")),
            _int_or_none(db, payload.get("keepalive_sec")),
            _int_or_none(db, payload.get("keepalive_retry")),
            text_or_none(payload.get("ipsec_profile")),
            sync_status,
        ),
    )
    return True


def _upsert_wan(conn: sqlite3.Connection, db: Any, iface_id: int, payload: dict[str, Any], sync_status: str = "pending_apply") -> None:
    encap_type = _choice(payload.get("encap_type"), {"none", "pppoe", "hdlc", "ppp", "frame-relay"}, "none")
    ppp_auth = _choice(payload.get("ppp_auth"), {"pap", "chap"}, "")
    lmi_type = _choice(payload.get("lmi_type"), {"cisco", "ansi", "q933a"}, "")
    conn.execute(
        """
        INSERT INTO t02_router_iface_wan (
            iface_id, encap_type, pppoe_dialer_pool, ppp_auth,
            ppp_username, ppp_password, clock_rate, lmi_type,
            sync_status, action_Cfg
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '11')
        ON CONFLICT(iface_id) DO UPDATE SET
            encap_type = excluded.encap_type,
            pppoe_dialer_pool = excluded.pppoe_dialer_pool,
            ppp_auth = excluded.ppp_auth,
            ppp_username = excluded.ppp_username,
            ppp_password = excluded.ppp_password,
            clock_rate = excluded.clock_rate,
            lmi_type = excluded.lmi_type,
            sync_status = excluded.sync_status,
            action_Cfg = '11';
        """,
        (
            iface_id,
            encap_type,
            _int_or_none(db, payload.get("pppoe_dialer_pool")),
            ppp_auth or None,
            text_or_none(payload.get("ppp_username")),
            text_or_none(payload.get("ppp_password")),
            _int_or_none(db, payload.get("clock_rate")),
            lmi_type or None,
            sync_status,
        ),
    )


def save_router_interface(db: Any, payload_value: Any) -> bool:
    payload = db._as_dict(payload_value)
    host = normalize_host(payload.get("host"))
    name = text_or_none(payload.get("interface_name"))
    if not host or not name:
        return False

    kind = str(payload.get("interface_kind") or "L3").strip()
    if kind not in {"L3", "WAN", "Tunnel", "Subinterface"}:
        kind = "L3"
    if kind == "Tunnel" and (
        not text_or_none(payload.get("tunnel_src")) or not text_or_none(payload.get("tunnel_dst"))
    ):
        return False

    try:
        with db_connection(db) as conn:
            requested_iface_id = _int_or_none(db, payload.get("iface_id"))
            row = None
            if requested_iface_id is not None and requested_iface_id > 0:
                row = conn.execute(
                    """
                    SELECT iface_id, interface_name, sync_status
                    FROM t02_interface_name
                    WHERE iface_id = ? AND host = ?
                    LIMIT 1;
                    """,
                    (requested_iface_id, host),
                ).fetchone()
                if row and row["interface_name"] != name:
                    if row["sync_status"] != "pending_apply":
                        return False
                    conn.execute(
                        "UPDATE t02_interface_name SET interface_name = ? WHERE iface_id = ?",
                        (name, requested_iface_id),
                    )
                    conn.execute(
                        "UPDATE t02_router_iface_subif SET subif_name = ? "
                        "WHERE host = ? AND subif_name = ?",
                        (name, host, row["interface_name"]),
                    )
            if row is None:
                row = conn.execute(
                    """
                    SELECT iface_id
                    FROM t02_interface_name
                    WHERE host = ? AND interface_name = ?
                    ORDER BY CASE WHEN COALESCE(sync_status, 'pending_apply') != 'pending_delete' THEN 0 ELSE 1 END, iface_id DESC
                    LIMIT 1;
                    """,
                    (host, name),
                ).fetchone()
            if row:
                iface_id = int(row["iface_id"])
                current = conn.execute(
                    "SELECT * FROM t02_interface_name WHERE iface_id = ?",
                    (iface_id,),
                ).fetchone()
                current_l3 = conn.execute(
                    "SELECT * FROM t02_router_iface_l3 WHERE iface_id = ?",
                    (iface_id,),
                ).fetchone()
                desired_l3 = _l3_values(db, payload)
                changed_fields: set[str] = set()
                if text_or_none(current["description"]) != text_or_none(payload.get("description")):
                    changed_fields.add("description")
                if (
                    text_or_none(current["ip_address"]),
                    text_or_none(current["subnet_mask"]),
                ) != (
                    text_or_none(payload.get("ip_address")),
                    text_or_none(payload.get("subnet_mask")),
                ):
                    changed_fields.add("primary_ip")
                if int(current["shutdown"] or 0) != _bool_int(db, payload.get("shutdown")):
                    changed_fields.add("shutdown")

                existing_kinds = {
                    "L3": current_l3 is not None
                    and current_l3["sync_status"] != "pending_delete",
                    "Tunnel": conn.execute(
                        "SELECT 1 FROM t02_router_iface_tunnel WHERE iface_id = ? "
                        "AND sync_status != 'pending_delete'",
                        (iface_id,),
                    ).fetchone() is not None,
                    "WAN": conn.execute(
                        "SELECT 1 FROM t02_router_iface_wan WHERE iface_id = ? "
                        "AND sync_status != 'pending_delete'",
                        (iface_id,),
                    ).fetchone() is not None,
                    "Subinterface": conn.execute(
                        "SELECT 1 FROM t02_router_iface_subif WHERE host = ? AND subif_name = ? "
                        "AND sync_status != 'pending_delete'",
                        (host, current["interface_name"]),
                    ).fetchone() is not None,
                }
                current_kind = next(
                    (key for key, present in existing_kinds.items() if present), None
                )
                profile_changed = current_kind is not None and current_kind != kind
                if kind == "L3":
                    changed_fields.update(_changed_l3_fields(current_l3, desired_l3))
                    profile_changed = profile_changed or current_l3 is None

                changed_mask = action_cfg_for(changed_fields)
                previous_mask = current["action_Cfg"]
                # Upgrade an already-pending task made by an older app version:
                # its five-bit L3 mask meant that the whole interface was dirty.
                if (
                    current_l3 is not None
                    and current_l3["sync_status"] == "pending_apply"
                    and "1" in str(current_l3["action_Cfg"] or "")
                    and not has_dirty_fields(previous_mask)
                ):
                    previous_mask = FULL_ACTION_CFG
                action_cfg = (
                    FULL_ACTION_CFG
                    if profile_changed
                    else merge_action_cfg(previous_mask, changed_mask)
                )
                base_status = (
                    "pending_apply"
                    if has_dirty_fields(action_cfg) or current["sync_status"] == "pending_apply"
                    else str(current["sync_status"] or "synchronized")
                )
                conn.execute(
                    """
                    UPDATE t02_interface_name
                    SET ip_address = ?, subnet_mask = ?, description = ?, shutdown = ?,
                        sync_status = ?, action_Cfg = ?
                    WHERE iface_id = ?;
                    """,
                    (
                        text_or_none(payload.get("ip_address")),
                        text_or_none(payload.get("subnet_mask")),
                        text_or_none(payload.get("description")),
                        _bool_int(db, payload.get("shutdown")),
                        base_status,
                        action_cfg,
                        iface_id,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO t02_interface_name (
                        host, interface_name, ip_address, subnet_mask,
                        description, shutdown, sync_status, action_Cfg
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'pending_apply', ?);
                    """,
                    (
                        host,
                        name,
                        text_or_none(payload.get("ip_address")),
                        text_or_none(payload.get("subnet_mask")),
                        text_or_none(payload.get("description")),
                        _bool_int(db, payload.get("shutdown")),
                        FULL_ACTION_CFG,
                    ),
                )
                iface_id = int(cursor.lastrowid)
                current_l3 = None
                changed_fields = set()
                profile_changed = True

            if kind == "L3":
                l3_changed = bool(
                    changed_fields
                    & {
                        "secondary_ip",
                        "mtu",
                        "bandwidth",
                        "delay",
                        "speed",
                        "duplex",
                        "negotiation",
                        "proxy_arp",
                        "unreachables",
                        "directed_broadcast",
                    }
                )
                l3_status = (
                    "pending_apply"
                    if current_l3 is None
                    or profile_changed
                    or l3_changed
                    or current_l3["sync_status"] == "pending_apply"
                    else str(current_l3["sync_status"] or "synchronized")
                )
                _upsert_l3(conn, db, iface_id, payload, l3_status)
                conn.execute("UPDATE t02_router_iface_tunnel SET sync_status = 'pending_delete' WHERE iface_id = ?;", (iface_id,))
                conn.execute("UPDATE t02_router_iface_wan SET sync_status = 'pending_delete' WHERE iface_id = ?;", (iface_id,))
            elif kind == "Tunnel":
                _upsert_tunnel(conn, db, iface_id, payload)
                conn.execute("UPDATE t02_router_iface_l3 SET sync_status = 'pending_delete' WHERE iface_id = ?;", (iface_id,))
                conn.execute("UPDATE t02_router_iface_wan SET sync_status = 'pending_delete' WHERE iface_id = ?;", (iface_id,))
            elif kind == "WAN":
                _upsert_wan(conn, db, iface_id, payload)
                conn.execute("UPDATE t02_router_iface_l3 SET sync_status = 'pending_delete' WHERE iface_id = ?;", (iface_id,))
                conn.execute("UPDATE t02_router_iface_tunnel SET sync_status = 'pending_delete' WHERE iface_id = ?;", (iface_id,))
            else:
                parent_name = str(payload.get("parent_interface") or name.rsplit(".", 1)[0]).strip()
                parent = conn.execute(
                    "SELECT iface_id FROM t02_interface_name WHERE host = ? AND interface_name = ? "
                    "AND COALESCE(sync_status, 'pending_apply') != 'pending_delete'",
                    (host, parent_name),
                ).fetchone()
                if parent is None:
                    raise sqlite3.IntegrityError("Subinterface parent does not exist")
                vlan_id = int(payload.get("vlan_id") or name.rsplit(".", 1)[1])
                conn.execute(
                    """
                    INSERT INTO t02_router_iface_subif(
                        parent_iface_id, host, subif_name, encapsulation, vlan_id,
                        native, ip_address, subnet_mask, shutdown, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_apply')
                    ON CONFLICT(host, subif_name) DO UPDATE SET
                        parent_iface_id = excluded.parent_iface_id,
                        encapsulation = excluded.encapsulation,
                        vlan_id = excluded.vlan_id,
                        native = excluded.native,
                        ip_address = excluded.ip_address,
                        subnet_mask = excluded.subnet_mask,
                        shutdown = excluded.shutdown,
                        sync_status = 'pending_apply'
                    """,
                    (
                        int(parent["iface_id"]), host, name,
                        _choice(payload.get("encapsulation"), {"dot1q", "isl"}, "dot1q"),
                        vlan_id, _bool_int(db, payload.get("native")),
                        text_or_none(payload.get("ip_address")),
                        text_or_none(payload.get("subnet_mask")),
                        _bool_int(db, payload.get("shutdown")),
                    ),
                )
                for table in (
                    "t02_router_iface_l3", "t02_router_iface_tunnel", "t02_router_iface_wan"
                ):
                    conn.execute(
                        f"UPDATE {table} SET sync_status = 'pending_delete' WHERE iface_id = ?",
                        (iface_id,),
                    )

            if kind != "Subinterface":
                conn.execute(
                    "UPDATE t02_router_iface_subif SET sync_status = 'pending_delete' "
                    "WHERE host = ? AND subif_name = ?",
                    (host, name),
                )

            conn.commit()
        return True
    except (sqlite3.Error, ValueError) as exc:
        log_db_error("saveRouterInterface", exc)
        return False


def delete_router_interface(db: Any, iface_id: int) -> bool:
    try:
        with db_connection(db) as conn:
            row = conn.execute(
                "SELECT host, interface_name, sync_status "
                "FROM t02_interface_name WHERE iface_id = ?",
                (iface_id,),
            ).fetchone()
            if row is None or infer_interface_type(row["interface_name"]) is InterfaceType.PHYSICAL:
                return False
            if row["sync_status"] == "pending_apply":
                # The device has never seen this virtual interface, so a
                # local delete must discard the draft instead of staging a
                # misleading `no interface` push task.
                conn.execute(
                    "DELETE FROM t02_router_iface_subif "
                    "WHERE host = ? AND subif_name = ?",
                    (row["host"], row["interface_name"]),
                )
                cursor = conn.execute(
                    "DELETE FROM t02_interface_name WHERE iface_id = ?",
                    (iface_id,),
                )
                conn.commit()
                return cursor.rowcount > 0
            cursor = conn.execute("UPDATE t02_interface_name SET sync_status = 'pending_delete' WHERE iface_id = ?;", (iface_id,))
            for table in (
                "t02_router_iface_l3",
                "t02_router_iface_tunnel",
                "t02_router_iface_wan",
            ):
                conn.execute(f"UPDATE {table} SET sync_status = 'pending_delete' WHERE iface_id = ?;", (iface_id,))
            conn.execute(
                "UPDATE t02_router_iface_subif SET sync_status = 'pending_delete' "
                "WHERE host = (SELECT host FROM t02_interface_name WHERE iface_id = ?) "
                "AND subif_name = (SELECT interface_name FROM t02_interface_name WHERE iface_id = ?)",
                (iface_id, iface_id),
            )
            conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as exc:
        log_db_error("deleteRouterInterface", exc)
        return False
