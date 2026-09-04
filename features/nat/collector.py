from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from infrastructure.network.config import DB_PATH, DB_TABLES


ACL = DB_TABLES["nat_acl"]
NAT = DB_TABLES["nat"]
ROUTE_MAP = DB_TABLES["route_map"]


def _state(value: Any, parent_remove: bool = False) -> str:
    if parent_remove or value == "pending_delete":
        return "remove"
    if value is None or value == "pending_apply":
        return "setup"
    return "ignore"


def _pending(value: Any) -> bool:
    return value is None or value in ("pending_apply", "pending_delete")


def _track(tracking: dict[str, dict[str, list[int]]], key: str, row_id: int, state: str) -> None:
    tracking[key]["del" if state == "remove" else "add"].append(row_id)


def _empty_tracking() -> dict[str, dict[str, list[int]]]:
    keys = (
        "acl", "acl_std", "acl_ext", "nat", "interface", "pool", "static",
        "dynamic", "overload", "exempt", "route_map", "route_map_entry",
    )
    return {key: {"add": [], "del": []} for key in keys}


def _collect_acl(cursor: sqlite3.Cursor, host: str, tracking: dict) -> list[dict]:
    rows = cursor.execute(
        f"""
        SELECT a.nat_acl_id, a.acl_name, a.acl_type, a.description, a.sync_status, a.action_Cfg
        FROM {ACL['main']} a
        WHERE a.host = ? AND (
            a.sync_status IN ('pending_apply', 'pending_delete') OR a.sync_status IS NULL
            OR EXISTS (SELECT 1 FROM {ACL['standard']} s WHERE s.nat_acl_id=a.nat_acl_id AND (s.sync_status IN ('pending_apply', 'pending_delete') OR s.sync_status IS NULL))
            OR EXISTS (SELECT 1 FROM {ACL['extended']} e WHERE e.nat_acl_id=a.nat_acl_id AND (e.sync_status IN ('pending_apply', 'pending_delete') OR e.sync_status IS NULL))
        )
        ORDER BY a.nat_acl_id
        """,
        (host,),
    ).fetchall()
    output = []
    for row in rows:
        acl_id, name, acl_type, description, sync_status, action_cfg = row
        parent_state = _state(sync_status)
        item = {
            "acl_id": acl_id, "acl_name": name, "acl_type": acl_type,
            "description": description, "push_desc": bool(int(action_cfg or 0) & 1),
            "state": "remove" if parent_state == "remove" else "setup", "rules": [],
        }
        if _pending(sync_status):
            _track(tracking, "acl", acl_id, parent_state)

        std_rows = cursor.execute(
            f"SELECT id, sequence, action, source, wildcard, sync_status FROM {ACL['standard']} WHERE nat_acl_id=? ORDER BY COALESCE(sequence, id * 10), id",
            (acl_id,),
        ).fetchall()
        for rule in std_rows:
            rule_id, sequence, action, source, wildcard, rule_success = rule
            rule_state = _state(rule_success, parent_state == "remove")
            item["rules"].append({
                "id": rule_id, "sequence": sequence or rule_id * 10, "action": action,
                "source": source, "wildcard": wildcard, "state": rule_state, "type": "std",
            })
            if _pending(rule_success):
                _track(tracking, "acl_std", rule_id, rule_state)

        ext_rows = cursor.execute(
            f"""SELECT id, sequence, action, protocol, source, src_wildcard, src_port,
                       destination, dst_wildcard, dst_port, sync_status
                FROM {ACL['extended']} WHERE nat_acl_id=? ORDER BY COALESCE(sequence, id * 10), id""",
            (acl_id,),
        ).fetchall()
        for rule in ext_rows:
            rule_id, sequence, action, protocol, source, src_wild, src_port, dest, dst_wild, dst_port, rule_success = rule
            rule_state = _state(rule_success, parent_state == "remove")
            item["rules"].append({
                "id": rule_id, "sequence": sequence or rule_id * 10, "action": action,
                "protocol": protocol, "source": source, "src_wildcard": src_wild,
                "src_port": src_port, "destination": dest, "dst_wildcard": dst_wild,
                "dst_port": dst_port, "state": rule_state, "type": "ext",
            })
            if _pending(rule_success):
                _track(tracking, "acl_ext", rule_id, rule_state)
        output.append(item)
    return output


def _nat_parent_rows(cursor: sqlite3.Cursor, host: str) -> list[sqlite3.Row]:
    child_checks = " OR ".join(
        f"EXISTS (SELECT 1 FROM {table} c WHERE c.nat_id=n.nat_id AND (c.sync_status IN ('pending_apply', 'pending_delete') OR c.sync_status IS NULL))"
        for table in (NAT["interfaces"], NAT["pools"], NAT["static_mappings"], NAT["dynamic_rules"], NAT["overload_rules"], NAT["exempt_rules"])
    )
    return cursor.execute(
        f"""SELECT n.nat_id, n.nat_name, n.nat_type, n.description, n.sync_status, n.action_Cfg
            FROM {NAT['main']} n WHERE n.host=?
              AND (n.sync_status IN ('pending_apply', 'pending_delete') OR n.sync_status IS NULL OR {child_checks})
            ORDER BY n.nat_id""",
        (host,),
    ).fetchall()


def _append_simple(cursor, item, tracking, key, track_key, table, id_col, columns, nat_id, parent_remove=False):
    names = ", ".join((id_col, *columns, "sync_status"))
    rows = cursor.execute(f"SELECT {names} FROM {table} WHERE nat_id=? ORDER BY {id_col}", (nat_id,)).fetchall()
    for row in rows:
        row_id, *values, sync_status = row
        state = _state(sync_status, parent_remove)
        data = dict(zip(columns, values))
        data[id_col] = row_id
        data["state"] = state
        item[key].append(data)
        if _pending(sync_status):
            _track(tracking, track_key, row_id, state)


def _collect_nat(cursor: sqlite3.Cursor, host: str, tracking: dict) -> list[dict]:
    output = []
    for row in _nat_parent_rows(cursor, host):
        nat_id, name, nat_type, description, sync_status, action_cfg = row
        parent_state = _state(sync_status)
        remove = parent_state == "remove"
        item = {
            "nat_id": nat_id, "nat_name": name, "nat_type": nat_type,
            "description": description, "push_desc": bool(int(action_cfg or 0) & 1),
            "state": "remove" if remove else "setup", "interfaces": [], "pools": [],
            "static_mappings": [], "dynamic_rules": [], "overload_rules": [],
            "exempt_rules": [], "route_map_nat_rules": [],
        }
        if _pending(sync_status):
            _track(tracking, "nat", nat_id, parent_state)

        _append_simple(cursor, item, tracking, "interfaces", "interface", NAT["interfaces"], "id", ("t02_interface_name", "nat_role"), nat_id, remove)
        for interface in item["interfaces"]:
            interface["interface_name"] = interface.pop("t02_interface_name")
        _append_simple(cursor, item, tracking, "pools", "pool", NAT["pools"], "pool_id", ("pool_name", "start_ip", "end_ip", "netmask", "prefix_length"), nat_id, remove)
        _append_simple(cursor, item, tracking, "static_mappings", "static", NAT["static_mappings"], "id", ("inside_local_ip", "inside_global_ip", "protocol", "local_port", "global_port", "is_extendable"), nat_id, remove)

        dynamic_rows = cursor.execute(
            f"""SELECT d.id, a.acl_name, p.pool_name, d.overload, d.sync_status
                FROM {NAT['dynamic_rules']} d JOIN {ACL['main']} a ON a.nat_acl_id=d.nat_acl_id
                JOIN {NAT['pools']} p ON p.pool_id=d.pool_id WHERE d.nat_id=? ORDER BY d.id""",
            (nat_id,),
        ).fetchall()
        for rule_id, acl_name, pool_name, overload, rule_success in dynamic_rows:
            state = _state(rule_success, remove)
            item["dynamic_rules"].append({"id": rule_id, "acl_name": acl_name, "pool_name": pool_name, "overload": overload, "state": state})
            if _pending(rule_success):
                _track(tracking, "dynamic", rule_id, state)

        overload_rows = cursor.execute(
            f"""SELECT o.id, a.acl_name, o.outside_interface, o.overload, o.sync_status
                FROM {NAT['overload_rules']} o JOIN {ACL['main']} a ON a.nat_acl_id=o.nat_acl_id
                WHERE o.nat_id=? ORDER BY o.id""",
            (nat_id,),
        ).fetchall()
        for rule_id, acl_name, outside, overload, rule_success in overload_rows:
            state = _state(rule_success, remove)
            item["overload_rules"].append({"id": rule_id, "acl_name": acl_name, "outside_interface": outside, "overload": overload, "state": state})
            if _pending(rule_success):
                _track(tracking, "overload", rule_id, state)

        outside = next((x["interface_name"] for x in item["interfaces"] if x["nat_role"] == "outside" and x["state"] != "remove"), None)
        exempt_rows = cursor.execute(
            f"""SELECT e.id, r.route_map_id, r.route_map_name, e.sync_status
                FROM {NAT['exempt_rules']} e JOIN {ROUTE_MAP['main']} r ON r.route_map_id=e.route_map_id
                WHERE e.nat_id=? ORDER BY e.id""",
            (nat_id,),
        ).fetchall()
        for exempt_id, route_map_id, route_map_name, exempt_success in exempt_rows:
            state = _state(exempt_success, remove)
            if outside and state != "ignore":
                item["route_map_nat_rules"].append({"route_map_name": route_map_name, "outside_interface": outside, "overload": 1, "state": state})
            if _pending(exempt_success):
                _track(tracking, "exempt", exempt_id, state)
        output.append(item)
    return output


def _collect_route_maps(cursor: sqlite3.Cursor, host: str, tracking: dict) -> list[dict]:
    rows = cursor.execute(
        f"""SELECT r.route_map_id, r.route_map_name, r.sync_status
            FROM {ROUTE_MAP['main']} r WHERE r.host=? AND (
                r.sync_status IN ('pending_apply', 'pending_delete') OR r.sync_status IS NULL OR EXISTS (
                    SELECT 1 FROM {ROUTE_MAP['entries']} e WHERE e.route_map_id=r.route_map_id
                    AND (e.sync_status IN ('pending_apply', 'pending_delete') OR e.sync_status IS NULL))) ORDER BY r.route_map_id""",
        (host,),
    ).fetchall()
    if not rows:
        return []
    item = {"nat_id": 0, "nat_name": "route-maps", "nat_type": "dynamic", "description": None,
            "push_desc": False, "state": "setup", "interfaces": [], "pools": [], "static_mappings": [],
            "dynamic_rules": [], "overload_rules": [], "exempt_rules": [], "route_map_nat_rules": []}
    for route_map_id, name, sync_status in rows:
        parent_state = _state(sync_status)
        if _pending(sync_status):
            _track(tracking, "route_map", route_map_id, parent_state)
        entries = cursor.execute(
            f"""SELECT e.id, e.sequence, e.action, a.acl_name, e.sync_status
                FROM {ROUTE_MAP['entries']} e LEFT JOIN {ACL['main']} a ON a.nat_acl_id=e.nat_acl_id
                WHERE e.route_map_id=? ORDER BY e.sequence""",
            (route_map_id,),
        ).fetchall()
        for entry_id, sequence, action, acl_name, entry_success in entries:
            state = _state(entry_success, parent_state == "remove")
            item["exempt_rules"].append({"route_map_name": name, "sequence": sequence, "action": action, "acl_name": acl_name, "state": state})
            if _pending(entry_success):
                _track(tracking, "route_map_entry", entry_id, state)
    return [item]


def collect_nat_tasks(target_ip: str = "all", db_path: str = DB_PATH) -> list[dict]:
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        if target_ip == "all":
            hosts = [row[0] for row in cursor.execute(
                f"SELECT host FROM {NAT['main']} UNION SELECT host FROM {ACL['main']} UNION SELECT host FROM {ROUTE_MAP['main']} ORDER BY host"
            ).fetchall()]
        else:
            hosts = [target_ip]
        tasks = []
        for host in hosts:
            tracking = _empty_tracking()
            config = {"target": {"ip": host}, "nat_acl": _collect_acl(cursor, host, tracking), "nat": []}
            config["nat"].extend(_collect_nat(cursor, host, tracking))
            config["nat"].extend(_collect_route_maps(cursor, host, tracking))
            if config["nat_acl"] or config["nat"]:
                tasks.append({"module": "nat", "target": {"ip": host}, "action": "setup", "config": config, "tracking": tracking})
        return tasks
