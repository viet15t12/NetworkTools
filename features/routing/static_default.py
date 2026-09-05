from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
import ipaddress
from typing import Any

from .common import log_db_error, normalize_host


def fetch_default_route(conn: sqlite3.Connection, host: str) -> sqlite3.Row | None:
    """Đọc default static route hiện hành của một thiết bị."""
    return conn.execute(
        """
        SELECT id, next_hop_ip, sync_status
        FROM t04_static_default_routes
        WHERE host = ? AND sync_status != 'pending_delete'
        ORDER BY id DESC
        LIMIT 1;
        """,
        (host,),
    ).fetchone()


def fetch_default_routes(conn: sqlite3.Connection, host: str) -> list[sqlite3.Row]:
    """Return every active default route for a device."""
    return conn.execute(
        """
        SELECT id, next_hop_ip, sync_status
        FROM t04_static_default_routes
        WHERE host = ? AND sync_status != 'pending_delete'
        ORDER BY id ASC;
        """,
        (host,),
    ).fetchall()


def replace_default_route(conn: sqlite3.Connection, host: str, default_value: str) -> None:
    """Mark default route cũ cần xóa và thêm default route mới nếu có."""
    default_text = (default_value or "").strip()
    current = fetch_default_route(conn, host)

    # Saving the static-route form must not recreate an unchanged default
    # route.  Doing so produced one pending_apply and one pending_delete row,
    # rendering contradictory `ip route` / `no ip route` commands.
    if current is None and not default_text:
        return
    if current is not None and str(current["next_hop_ip"] or "").strip() == default_text:
        duplicate_delete = conn.execute(
            """
            SELECT id
            FROM t04_static_default_routes
            WHERE host = ? AND next_hop_ip = ? AND sync_status = 'pending_delete'
            ORDER BY id DESC
            LIMIT 1;
            """,
            (host, default_text),
        ).fetchone()
        if duplicate_delete is not None:
            # Repair rows created by the former unconditional replacement:
            # the old synchronized row became pending_delete while an equal
            # pending_apply row was inserted.
            if current["sync_status"] == "pending_apply":
                conn.execute(
                    "DELETE FROM t04_static_default_routes WHERE id = ?;",
                    (current["id"],),
                )
                conn.execute(
                    """
                    UPDATE t04_static_default_routes
                    SET sync_status = 'synchronized'
                    WHERE id = ?;
                    """,
                    (duplicate_delete["id"],),
                )
            else:
                conn.execute(
                    "DELETE FROM t04_static_default_routes WHERE id = ?;",
                    (duplicate_delete["id"],),
                )
        return

    conn.execute(
        """
        UPDATE t04_static_default_routes
        SET sync_status = 'pending_delete'
        WHERE host = ? AND sync_status != 'pending_delete';
        """,
        (host,),
    )
    if default_text:
        conn.execute(
            """
            INSERT INTO t04_static_default_routes (host, next_hop_ip, sync_status)
            VALUES (?, ?, 'pending_apply');
            """,
            (host, default_text),
        )


def default_route_payload(default_row: sqlite3.Row | None) -> dict[str, Any]:
    """Chuyển row default route thành payload trả về cho QML."""
    return {
        "default_route_id": default_row["id"] if default_row else 0,
        "default_route": default_row["next_hop_ip"] if default_row else "",
        "default_route_success": default_row["sync_status"] if default_row else 0,
    }


def get_default_routes(db: Any, host: str) -> dict[str, Any]:
    host = normalize_host(host)
    if not host:
        return {"ok": False, "message": "Host is empty", "routes": []}
    try:
        with db._connect() as conn:
            rows = fetch_default_routes(conn, host)
        return {
            "ok": True,
            "message": "Loaded default routes",
            "routes": [
                {
                    "id": row["id"],
                    "nexthop": row["next_hop_ip"],
                    "sync_status": row["sync_status"],
                }
                for row in rows
            ],
        }
    except sqlite3.Error as exc:
        log_db_error("getDefaultRoutes", exc)
        return {"ok": False, "message": str(exc), "routes": []}


def save_default_routes(db: Any, host: str, routes: Any) -> bool:
    """Reconcile a host's independent list of IPv4 default routes."""
    host = normalize_host(host)
    if not host:
        return False
    try:
        submitted: list[tuple[int, str]] = []
        seen: set[str] = set()
        for value in db._as_list(routes):
            route = db._as_dict(value)
            route_id = db._int_or_none(route.get("id")) or 0
            next_hop = str(route.get("nexthop") or route.get("next_hop_ip") or "").strip()
            if not next_hop:
                continue
            next_hop = str(ipaddress.IPv4Address(next_hop))
            if next_hop in seen:
                raise ValueError("Duplicate default-route next-hop")
            seen.add(next_hop)
            submitted.append((route_id, next_hop))

        with db._connect() as conn:
            # Heal contradictory pairs produced by older versions that always
            # replaced an unchanged default route on every form save.
            repaired_ids: dict[int, int] = {}
            duplicate_pairs = conn.execute(
                """
                SELECT applied.id AS applied_id, deleted.id AS deleted_id
                FROM t04_static_default_routes AS applied
                JOIN t04_static_default_routes AS deleted
                  ON deleted.host = applied.host
                 AND deleted.next_hop_ip = applied.next_hop_ip
                 AND deleted.sync_status = 'pending_delete'
                WHERE applied.host = ? AND applied.sync_status = 'pending_apply'
                """,
                (host,),
            ).fetchall()
            for pair in duplicate_pairs:
                applied_id = int(pair["applied_id"])
                deleted_id = int(pair["deleted_id"])
                repaired_ids[applied_id] = deleted_id
                conn.execute("DELETE FROM t04_static_default_routes WHERE id=?", (applied_id,))
                conn.execute(
                    "UPDATE t04_static_default_routes SET sync_status='synchronized' WHERE id=?",
                    (deleted_id,),
                )

            existing = {
                int(row["id"]): str(row["next_hop_ip"])
                for row in fetch_default_routes(conn, host)
            }
            kept: set[int] = set()
            for route_id, next_hop in submitted:
                route_id = repaired_ids.get(route_id, route_id)
                if route_id in existing and existing[route_id] == next_hop:
                    kept.add(route_id)
                    continue
                if route_id in existing:
                    conn.execute(
                        "UPDATE t04_static_default_routes SET sync_status='pending_delete' WHERE id=? AND host=?",
                        (route_id, host),
                    )
                    kept.add(route_id)
                conn.execute(
                    """
                    INSERT INTO t04_static_default_routes (host, next_hop_ip, sync_status)
                    VALUES (?, ?, 'pending_apply')
                    """,
                    (host, next_hop),
                )

            deleted = set(existing) - kept
            if deleted:
                placeholders = ",".join("?" for _ in deleted)
                conn.execute(
                    f"UPDATE t04_static_default_routes SET sync_status='pending_delete' WHERE host=? AND id IN ({placeholders})",
                    (host, *deleted),
                )
            conn.commit()
        return True
    except (sqlite3.Error, ValueError, ipaddress.AddressValueError) as exc:
        log_db_error("saveDefaultRoutes", exc)
        return False
