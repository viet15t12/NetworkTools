from __future__ import annotations

import sqlite3
from contextlib import closing
import re
from typing import Any

from infrastructure.network.config import DB_PATH, DB_TABLES


ACL = DB_TABLES["acl"]
RULE_COLUMNS = {
    "standard": "id, sequence, action, source, wildcard, sync_status",
    "extended": (
        "id, sequence, action, protocol, source, src_wildcard, src_port, "
        "destination, dst_wildcard, dst_port, sync_status"
    ),
    "dynamic": (
        "id, sequence, action, protocol, source, src_wildcard, src_port, "
        "destination, dst_wildcard, dst_port, dynamic_name, timeout_seconds, sync_status"
    ),
    "reflexive": (
        "id, sequence, action, protocol, source, src_wildcard, src_port, "
        "destination, dst_wildcard, dst_port, reflect_name, timeout_seconds, sync_status"
    ),
    "mac": "id, sequence, action, src_mac, src_mask, dst_mac, dst_mask, ethertype, sync_status",
}


def _pending(value: Any) -> bool:
    return value is None or value in ("pending_apply", "pending_delete")


def _rule_payload(acl_type: str, row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["seq"] = item.pop("sequence") or int(item["id"]) * 10
    if acl_type == "standard":
        item["src"] = item.pop("source")
        item["src_mask"] = item.pop("wildcard")
    elif acl_type in {"extended", "dynamic", "reflexive"}:
        item["src"] = item.pop("source")
        item["src_mask"] = item.pop("src_wildcard")
        item["dst"] = item.pop("destination")
        item["dst_mask"] = item.pop("dst_wildcard")
        if str(item.get("protocol") or "").strip().lower() == "icmp":
            # Older rows may contain the generic port form `eq echo`. IOS ICMP
            # ACL syntax expects the message type directly: `... echo`.
            item["src_port"] = None
            item["dst_port"] = re.sub(
                r"^eq\s+", "", str(item.get("dst_port") or "").strip(), flags=re.IGNORECASE
            ) or None
        if acl_type == "dynamic":
            item["dyn_name"] = item.pop("dynamic_name")
            item["timeout"] = item.pop("timeout_seconds")
        elif acl_type == "reflexive":
            item["timeout"] = item.pop("timeout_seconds")
    return item


def _collect_bindings(
    cursor: sqlite3.Cursor, acl_id: int, acl_host: str,
) -> tuple[list[dict[str, Any]], dict[str, list[int]]]:
    rows = cursor.execute(
        f"""
        SELECT b.id, i.interface_name, i.host AS interface_host,
               b.direction, b.sync_status
        FROM {ACL['bindings']} AS b
        JOIN t02_interface_name AS i ON i.iface_id = b.iface_id
        WHERE b.acl_id = ? AND (b.sync_status IN ('pending_apply', 'pending_delete') OR b.sync_status IS NULL)
        ORDER BY i.interface_name COLLATE NOCASE, b.direction;
        """,
        (acl_id,),
    ).fetchall()
    bindings: list[dict[str, Any]] = []
    tracking = {"add": [], "del": []}
    for row in rows:
        if str(row["interface_host"] or "") != str(acl_host or ""):
            raise ValueError(
                f"ACL {acl_id} belongs to {acl_host}, but binding {row['id']} "
                f"references an interface owned by {row['interface_host']}; Push was blocked"
            )
        state = "remove" if row["sync_status"] == "pending_delete" else "setup"
        bindings.append({
            "id": row["id"],
            "interface_name": row["interface_name"],
            "direction": row["direction"],
            "state": state,
        })
        tracking["del" if state == "remove" else "add"].append(int(row["id"]))
    return bindings, tracking


def _collect_acl(cursor: sqlite3.Cursor, row: sqlite3.Row) -> tuple[dict[str, Any], dict[str, Any]]:
    acl_id = int(row["Acl_id"])
    acl_type = str(row["acl_type"]).lower()
    parent_remove = row["sync_status"] == "pending_delete"
    rules = cursor.execute(
        f"SELECT {RULE_COLUMNS[acl_type]} FROM {ACL[acl_type]} "
        "WHERE acl_id = ? AND (sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL) "
        "ORDER BY COALESCE(sequence, id * 10), id;",
        (acl_id,),
    ).fetchall()
    rules_add: list[dict[str, Any]] = []
    rules_del: list[dict[str, Any]] = []
    rule_tracking = {"add": [], "del": []}
    rendered_delete_sequences: set[int] = set()
    for rule in rules:
        payload = _rule_payload(acl_type, rule)
        state = "remove" if parent_remove or rule["sync_status"] == "pending_delete" else "setup"
        payload.pop("sync_status", None)
        payload.pop("id", None)
        if state == "remove":
            # Failed/retried edits can leave several historical rows with the
            # same sequence pending deletion. Render one `no <seq>` command,
            # while tracking every row so a successful Push cleans them all.
            sequence = int(payload["seq"])
            if sequence not in rendered_delete_sequences:
                rules_del.append(payload)
                rendered_delete_sequences.add(sequence)
        else:
            rules_add.append(payload)
        rule_tracking["del" if state == "remove" else "add"].append(int(rule["id"]))

    bindings, binding_tracking = _collect_bindings(cursor, acl_id, str(row["host"] or ""))
    payload = {
        "acl_id": acl_id,
        "acl_name": row["acl_name"],
        "acl_type": acl_type,
        "description": row["description"],
        "push_desc": bool(int(row["action_Cfg"] or 0) & 1),
        "action": "delete" if parent_remove else ("set" if row["sync_status"] in (None, "pending_apply") else "change"),
        "rules_add": rules_add,
        "rules_del": rules_del,
        "bindings": bindings,
    }
    tracking = {
        "acl": {
            "add": [acl_id] if _pending(row["sync_status"]) and not parent_remove else [],
            "del": [acl_id] if parent_remove else [],
        },
        "rules": {acl_type: rule_tracking},
        "bindings": binding_tracking,
    }
    return payload, tracking


def collect_acl_tasks(target_ip: str = "all", db_path: str = DB_PATH) -> list[dict[str, Any]]:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        host_clause = "" if target_ip == "all" else "AND a.host = ?"
        parameters: tuple[Any, ...] = () if target_ip == "all" else (target_ip,)
        child_checks = " OR ".join(
            f"EXISTS (SELECT 1 FROM {ACL[kind]} r WHERE r.acl_id=a.Acl_id AND (r.sync_status IN ('pending_apply', 'pending_delete') OR r.sync_status IS NULL))"
            for kind in RULE_COLUMNS
        )
        rows = cursor.execute(
            f"""
            SELECT a.Acl_id, a.acl_name, a.acl_type, a.host, a.description,
                   a.sync_status, a.action_Cfg
            FROM {ACL['main']} AS a
            WHERE ({"a.sync_status IN ('pending_apply', 'pending_delete') OR a.sync_status IS NULL OR " + child_checks}
                   OR EXISTS (
                       SELECT 1 FROM {ACL['bindings']} b
                       WHERE b.acl_id=a.Acl_id AND (b.sync_status IN ('pending_apply', 'pending_delete') OR b.sync_status IS NULL)
                   ))
              {host_clause}
            ORDER BY a.host, a.Acl_id;
            """,
            parameters,
        ).fetchall()

        tasks: list[dict[str, Any]] = []
        for row in rows:
            payload, tracking = _collect_acl(cursor, row)
            tasks.append({
                "module": "acl",
                "target": {"ip": row["host"]},
                "action": "setup",
                "config": payload,
                "tracking": tracking,
            })
        return tasks
