from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from typing import Any

from .common import as_dict, as_list, int_or_none_value, text


def normalize_key_chain(row: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa một key-chain EIGRP trước khi so sánh/lưu DB."""
    return {
        "chain_name": text(row.get("chain_name")),
        "key_id": int_or_none_value(row.get("key_id")),
        "key_string": text(row.get("key_string")),
        "accept_lifetime": text(row.get("accept_lifetime")),
        "send_lifetime": text(row.get("send_lifetime")),
    }


def key_chain_identity(row: dict[str, Any]) -> tuple[str, int | None]:
    """Tạo khóa định danh cho key-chain EIGRP."""
    return (text(row.get("chain_name")), int_or_none_value(row.get("key_id")))


def collect_payload_key_chains(db: Any, payload: Any) -> list[dict[str, Any]]:
    """Thu thập và khử trùng lặp key-chain từ payload EIGRP."""
    deduped: dict[tuple[str, int | None], dict[str, Any]] = {}
    for process_value in as_list(db, payload):
        process = as_dict(db, process_value)
        for key_value in as_list(db, process.get("key_chains")):
            key_chain = normalize_key_chain(as_dict(db, key_value))
            key = key_chain_identity(key_chain)
            if key[0]:
                deduped[key] = key_chain
    return list(deduped.values())


def sync_eigrp_key_chains(conn: sqlite3.Connection, db: Any, host: str, payload: Any) -> None:
    """Đồng bộ bảng key-chain EIGRP theo payload mới."""
    submitted_rows = collect_payload_key_chains(db, payload)
    existing_rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT id, chain_name, key_id, key_string, accept_lifetime, send_lifetime
            FROM t04_eigrp_key_chains
            WHERE host = ? AND sync_status != 'pending_delete'
            ORDER BY id ASC;
            """,
            (host,),
        ).fetchall()
    ]
    existing_by_key = {key_chain_identity(row): row for row in existing_rows}
    submitted_by_key = {key_chain_identity(row): row for row in submitted_rows}

    for key, existing in existing_by_key.items():
        if key not in submitted_by_key:
            conn.execute("UPDATE t04_eigrp_key_chains SET sync_status = 'pending_delete' WHERE id = ?;", (existing["id"],))

    for key, submitted in submitted_by_key.items():
        existing = existing_by_key.get(key)
        if existing is None:
            conn.execute(
                """
                INSERT INTO t04_eigrp_key_chains (
                    host, chain_name, key_id, key_string, accept_lifetime, send_lifetime, sync_status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending_apply');
                """,
                (
                    host,
                    submitted["chain_name"],
                    submitted["key_id"],
                    submitted["key_string"] or None,
                    submitted["accept_lifetime"] or None,
                    submitted["send_lifetime"] or None,
                ),
            )
            continue

        current = normalize_key_chain(existing)
        if current != submitted:
            conn.execute(
                """
                UPDATE t04_eigrp_key_chains
                SET key_string = ?, accept_lifetime = ?, send_lifetime = ?, sync_status = 'pending_apply'
                WHERE id = ?;
                """,
                (
                    submitted["key_string"] or None,
                    submitted["accept_lifetime"] or None,
                    submitted["send_lifetime"] or None,
                    existing["id"],
                ),
            )
        else:
            conn.execute("UPDATE t04_eigrp_key_chains SET sync_status = 'pending_apply' WHERE id = ?;", (existing["id"],))
