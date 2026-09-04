from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from infrastructure.network.config import DB_PATH, DB_TABLES, NAT_OUTPUT
try:
    from .collector import collect_nat_tasks
except ImportError:
    from collector import collect_nat_tasks


TRACK_TABLES = {
    "acl": (DB_TABLES["nat_acl"]["main"], "nat_acl_id"),
    "acl_std": (DB_TABLES["nat_acl"]["standard"], "id"),
    "acl_ext": (DB_TABLES["nat_acl"]["extended"], "id"),
    "nat": (DB_TABLES["nat"]["main"], "nat_id"),
    "interface": (DB_TABLES["nat"]["interfaces"], "id"),
    "pool": (DB_TABLES["nat"]["pools"], "pool_id"),
    "static": (DB_TABLES["nat"]["static_mappings"], "id"),
    "dynamic": (DB_TABLES["nat"]["dynamic_rules"], "id"),
    "overload": (DB_TABLES["nat"]["overload_rules"], "id"),
    "exempt": (DB_TABLES["nat"]["exempt_rules"], "id"),
    "route_map": (DB_TABLES["route_map"]["main"], "route_map_id"),
    "route_map_entry": (DB_TABLES["route_map"]["entries"], "id"),
}


def _apply_tracking(cursor: sqlite3.Cursor, tracking: dict[str, Any]) -> int:
    changes = 0
    child_keys = ("acl_std", "acl_ext", "interface", "pool", "static", "dynamic", "overload", "exempt", "route_map_entry")
    parent_keys = ("acl", "nat", "route_map")
    for key in (*child_keys, *parent_keys):
        table, id_column = TRACK_TABLES[key]
        states = tracking.get(key, {})
        for row_id in states.get("del", []):
            cursor.execute(f"DELETE FROM {table} WHERE {id_column}=? AND sync_status='pending_delete'", (row_id,))
            changes += cursor.rowcount
    for key in (*parent_keys, *child_keys):
        table, id_column = TRACK_TABLES[key]
        states = tracking.get(key, {})
        for row_id in states.get("add", []):
            cursor.execute(f"UPDATE {table} SET sync_status='synchronized' WHERE {id_column}=? AND (sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL)", (row_id,))
            changes += cursor.rowcount
    return changes


def apply_nat_results(tasks: list[dict[str, Any]], results: list[dict[str, Any]], db_path: str = DB_PATH) -> list[dict[str, Any]]:
    tasks_by_ip = {task.get("target", {}).get("ip"): task for task in tasks}
    report: list[dict[str, Any]] = []
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        for result in results:
            ip = result.get("target") or result.get("ip") or result.get("host")
            succeeded = str(result.get("status", "")).lower() == "success"
            item = {"ip": ip, "status": "SUCCESS" if succeeded else "FAIL", "log": result.get("message", ""), "db_updated": False}
            task = tasks_by_ip.get(ip)
            if succeeded and task:
                changed = _apply_tracking(cursor, task.get("tracking", {}))
                item["db_updated"] = changed > 0
                if changed <= 0:
                    item["status"] = "FAIL"
                    item["log"] = (item["log"] + " " if item["log"] else "") + "Worker succeeded, but no NAT database rows were updated."
            report.append(item)
        conn.commit()
    return report


def nat_dispatcher(target_ip: str = "all", dry_run: bool = False, session_provider=None) -> list[dict[str, Any]]:
    tasks = collect_nat_tasks(target_ip, DB_PATH)
    if dry_run or not tasks:
        return tasks
    try:
        from .worker import run_nat_config
    except ImportError:
        from features.nat.worker import run_nat_config

    run_nat_config(tasks, DB_PATH, NAT_OUTPUT, session_provider=session_provider)
    output_path = Path(NAT_OUTPUT)
    results = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else []
    apply_nat_results(tasks, results, DB_PATH)
    return tasks


if __name__ == "__main__":
    nat_dispatcher()
