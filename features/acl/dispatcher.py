from __future__ import annotations

import json
from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from infrastructure.network.config import ACL_OUTPUT, DB_PATH, DB_TABLES

from .collector import collect_acl_tasks


ACL = DB_TABLES["acl"]


def _apply_tracking(cursor: sqlite3.Cursor, tracking: dict[str, Any]) -> int:
    changes = 0
    bindings = tracking.get("bindings", {})
    for row_id in bindings.get("del", []):
        cursor.execute(f"DELETE FROM {ACL['bindings']} WHERE id=? AND sync_status='pending_delete'", (row_id,))
        changes += cursor.rowcount
    for kind, states in tracking.get("rules", {}).items():
        for row_id in states.get("del", []):
            cursor.execute(f"DELETE FROM {ACL[kind]} WHERE id=? AND sync_status='pending_delete'", (row_id,))
            changes += cursor.rowcount
    for acl_id in tracking.get("acl", {}).get("del", []):
        cursor.execute(f"DELETE FROM {ACL['main']} WHERE Acl_id=? AND sync_status='pending_delete'", (acl_id,))
        changes += cursor.rowcount

    for acl_id in tracking.get("acl", {}).get("add", []):
        cursor.execute(
            f"UPDATE {ACL['main']} SET sync_status='synchronized' WHERE Acl_id=? AND (sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL)",
            (acl_id,),
        )
        changes += cursor.rowcount
    for kind, states in tracking.get("rules", {}).items():
        for row_id in states.get("add", []):
            cursor.execute(
                f"UPDATE {ACL[kind]} SET sync_status='synchronized' WHERE id=? AND (sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL)",
                (row_id,),
            )
            changes += cursor.rowcount
    for row_id in bindings.get("add", []):
        cursor.execute(
            f"UPDATE {ACL['bindings']} SET sync_status='synchronized' WHERE id=? AND (sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL)",
            (row_id,),
        )
        changes += cursor.rowcount
    return changes


def apply_acl_results(
    tasks: list[dict[str, Any]],
    results: list[dict[str, Any]],
    db_path: str = DB_PATH,
) -> list[dict[str, Any]]:
    tasks_by_ip: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        tasks_by_ip.setdefault(str(task.get("target", {}).get("ip") or ""), []).append(task)

    report: list[dict[str, Any]] = []
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        for result in results:
            ip = str(result.get("target") or result.get("ip") or result.get("host") or "")
            succeeded = str(result.get("status", "")).lower() == "success"
            changed = 0
            if succeeded:
                for task in tasks_by_ip.get(ip, []):
                    changed += _apply_tracking(cursor, task.get("tracking", {}))
            status = "SUCCESS" if succeeded and changed > 0 else "FAIL"
            message = str(result.get("message") or "")
            if succeeded and changed <= 0:
                message = (message + " " if message else "") + "Worker succeeded, but no ACL database rows were updated."
            report.append({"ip": ip, "status": status, "log": message, "db_updated": changed > 0})
        conn.commit()
    return report


def acl_dispatcher(target_ip: str = "all", dry_run: bool = False, session_provider=None) -> list[dict[str, Any]]:
    tasks = collect_acl_tasks(target_ip, DB_PATH)
    if dry_run or not tasks:
        return tasks
    from .worker import run_acl_config

    run_acl_config(tasks, DB_PATH, ACL_OUTPUT, session_provider=session_provider)
    output_path = Path(ACL_OUTPUT)
    results = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else []
    apply_acl_results(tasks, results, DB_PATH)
    return tasks
