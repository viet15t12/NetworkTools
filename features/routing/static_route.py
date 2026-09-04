from __future__ import annotations

import sqlite3
from typing import Any

from .common import log_db_error, normalize_host
from .static_default import default_route_payload, fetch_default_route, fetch_default_routes, replace_default_route


def get_static_routing(db: Any, host: str) -> dict[str, Any]:
    host = normalize_host(host)
    if not host:
        return {"ok": False, "message": "Host is empty", "default_route": "", "routes": []}

    try:
        with db._connect() as conn:
            default_row = fetch_default_route(conn, host)
            default_rows = fetch_default_routes(conn, host)
            route_rows = conn.execute(
                """
                SELECT id, network, subnet_mask, next_hop, ad, sync_status
                FROM t04_static_routes
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY id ASC;
                """,
                (host,),
            ).fetchall()

        routes = [
            {
                "id": row["id"],
                "network": row["network"],
                "mask": row["subnet_mask"],
                "nexthop": row["next_hop"],
                "ad": row["ad"],
                "sync_status": row["sync_status"],
            }
            for row in route_rows
        ]
        return {
            "ok": True,
            "message": "Loaded static/default routes",
            **default_route_payload(default_row),
            "default_routes": [
                {"id": row["id"], "nexthop": row["next_hop_ip"], "sync_status": row["sync_status"]}
                for row in default_rows
            ],
            "routes": routes,
        }
    except sqlite3.Error as exc:
        log_db_error("getStaticRouting", exc)
        return {"ok": False, "message": str(exc), "default_route": "", "routes": []}


def save_static_routing(db: Any, host: str, default_value: str, routes: Any) -> bool:
    """Backward-compatible combined save used by older callers."""
    host = normalize_host(host)
    if not host:
        return False
    try:
        with db._connect() as conn:
            replace_default_route(conn, host, default_value)
            conn.commit()
    except (sqlite3.Error, ValueError) as exc:
        log_db_error("saveStaticRouting", exc)
        return False
    return save_static_routes(db, host, routes)


def save_static_routes(db: Any, host: str, routes: Any) -> bool:
    """Save static routes without touching the independently managed defaults."""
    host = normalize_host(host)
    if not host:
        return False
    try:
        with db._connect() as conn:
            existing_ids = {
                row["id"] for row in conn.execute(
                    "SELECT id FROM t04_static_routes WHERE host=? AND sync_status!='pending_delete'",
                    (host,),
                ).fetchall()
            }
            submitted_ids: set[int] = set()
            for value in db._as_list(routes):
                route = db._as_dict(value)
                route_id = db._int_or_none(route.get("id")) or db._int_or_none(route.get("routeId")) or 0
                network = db._str_or_none(route.get("network"))
                mask = db._str_or_none(route.get("mask"))
                nexthop = db._str_or_none(route.get("nexthop"))
                if not (network and mask and nexthop):
                    raise ValueError("Static route must include network, mask, and next-hop")
                ad = db._int_or_none(route.get("ad")) or 1
                if not 1 <= ad <= 255:
                    raise ValueError("Static route AD must be between 1 and 255")
                if route_id in existing_ids:
                    submitted_ids.add(route_id)
                    if bool(route.get("edited")):
                        conn.execute("UPDATE t04_static_routes SET sync_status='pending_delete' WHERE id=? AND host=?", (route_id, host))
                        conn.execute(
                            "INSERT INTO t04_static_routes(host,network,subnet_mask,next_hop,ad,sync_status) VALUES(?,?,?,?,?,'pending_apply')",
                            (host, network, mask, nexthop, ad),
                        )
                else:
                    conn.execute(
                        "INSERT INTO t04_static_routes(host,network,subnet_mask,next_hop,ad,sync_status) VALUES(?,?,?,?,?,'pending_apply')",
                        (host, network, mask, nexthop, ad),
                    )
            deleted = existing_ids - submitted_ids
            if deleted:
                placeholders = ",".join("?" for _ in deleted)
                conn.execute(f"UPDATE t04_static_routes SET sync_status='pending_delete' WHERE host=? AND id IN ({placeholders})", (host, *deleted))
            conn.commit()
        return True
    except (sqlite3.Error, ValueError) as exc:
        log_db_error("saveStaticRoutes", exc)
        return False
