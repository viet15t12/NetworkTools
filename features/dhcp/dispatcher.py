import argparse
import json
import os
import sqlite3
import sys
from contextlib import closing


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
FEATURES_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
if FEATURES_ROOT not in sys.path:
    sys.path.append(FEATURES_ROOT)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from infrastructure.network.config import DB_PATH, DHCP_OUTPUT, DB_TABLES
from .worker import run_dhcp_config


def has_text_bit(action_cfg, bit_index_from_right):
    if not action_cfg:
        return True
    action_cfg = str(action_cfg)
    position = len(action_cfg) - 1 - bit_index_from_right
    return 0 <= position < len(action_cfg) and action_cfg[position] == "1"


def success_state(value):
    if value in ("pending_apply", None):
        return "setup"
    if value == "pending_delete":
        return "remove"
    return "ignore"


def _interface_name_column(cursor, table_name):
    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if "interface_name" in columns:
        return "interface_name"
    if "t02_interface_name" in columns:
        return "t02_interface_name"
    raise sqlite3.OperationalError(f"{table_name} has no interface name column")


def _apply_successful_results(valid_data, results, table_names):
    tasks_by_ip = {item["target"]["ip"]: item for item in valid_data}
    report = []
    with closing(sqlite3.connect(DB_PATH)) as connection:
        cursor = connection.cursor()
        for result in results:
            ip = result.get("target") or result.get("ip") or result.get("host")
            succeeded = result.get("status") == "success"
            changes = 0
            task = tasks_by_ip.get(ip)
            if succeeded and task:
                ids = task["ids"]
                for row_id in ids["pool_add"]:
                    cursor.execute(
                        f"UPDATE {table_names['pool']} SET sync_status = 'synchronized', action_Cfg = '000' WHERE dhcp_id = ?",
                        (row_id,),
                    )
                    changes += cursor.rowcount
                for row_id in ids["pool_del"]:
                    cursor.execute(f"DELETE FROM {table_names['pool']} WHERE dhcp_id = ?", (row_id,))
                    changes += cursor.rowcount
                for row_id in ids["exc_add"]:
                    cursor.execute(f"UPDATE {table_names['excluded']} SET sync_status = 'synchronized' WHERE ex_id = ?", (row_id,))
                    changes += cursor.rowcount
                for row_id in ids["exc_del"]:
                    cursor.execute(f"DELETE FROM {table_names['excluded']} WHERE ex_id = ?", (row_id,))
                    changes += cursor.rowcount
                for row_id in ids["helper_add"]:
                    cursor.execute(f"UPDATE {table_names['helper']} SET sync_status = 'synchronized' WHERE id = ?", (row_id,))
                    changes += cursor.rowcount
                for row_id in ids["helper_del"]:
                    cursor.execute(f"DELETE FROM {table_names['helper']} WHERE id = ?", (row_id,))
                    changes += cursor.rowcount

            report.append({
                "ip": ip,
                "status": "SUCCESS" if succeeded else "FAIL",
                "log": result.get("message", result.get("msg", "")),
                "db_updated": changes > 0,
            })
        connection.commit()
    return report


def dhcp_dispatcher(target_ip="all", dry_run=False, session_provider=None):
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database file was not found: {DB_PATH}")

    tables = {
        "pool": DB_TABLES["dhcp"]["pools"],
        "excluded": DB_TABLES["dhcp"]["excluded"],
        "helper": DB_TABLES["dhcp"].get("helpers", DB_TABLES["dhcp"].get("helper")),
        "interface": DB_TABLES.get("interfaces", {}).get("main", "t02_interface_name"),
    }
    if not tables["helper"]:
        raise KeyError("DHCP helper table is not configured")

    valid_data = []
    with closing(sqlite3.connect(DB_PATH)) as connection:
        cursor = connection.cursor()
        interface_column = _interface_name_column(cursor, tables["interface"])
        host_query = f"""
            SELECT host FROM {tables['pool']} WHERE sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL
            UNION SELECT host FROM {tables['excluded']} WHERE sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL
            UNION SELECT i.host FROM {tables['helper']} h
                JOIN {tables['interface']} i ON h.iface_id = i.iface_id
                WHERE h.sync_status IN ('pending_apply', 'pending_delete') OR h.sync_status IS NULL
        """
        if target_ip != "all":
            cursor.execute(f"SELECT host FROM ({host_query}) WHERE host = ?", (target_ip,))
        else:
            cursor.execute(host_query)

        for host in [row[0] for row in cursor.fetchall()]:
            config = {"pools": [], "excluded_addresses": [], "relays": []}
            ids = {
                "pool_add": [], "pool_del": [],
                "exc_add": [], "exc_del": [],
                "helper_add": [], "helper_del": [],
            }

            cursor.execute(
                f"SELECT ex_id, start_ip, end_ip, sync_status FROM {tables['excluded']} "
                "WHERE host = ? AND (sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL)",
                (host,),
            )
            for row_id, start_ip, end_ip, state_value in cursor.fetchall():
                state = success_state(state_value)
                config["excluded_addresses"].append({"start_ip": start_ip, "end_ip": end_ip, "state": state})
                ids["exc_del" if state == "remove" else "exc_add"].append(row_id)

            cursor.execute(
                f"SELECT dhcp_id, pool, network, subnetmask, defaut, dns, lease, sync_status, action_Cfg "
                f"FROM {tables['pool']} WHERE host = ? AND (sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL)",
                (host,),
            )
            for row_id, name, network, mask, gateway, dns, lease, state_value, action_cfg in cursor.fetchall():
                state = success_state(state_value)
                config["pools"].append({
                    "name": name,
                    "network": network,
                    "subnet_mask": mask,
                    "default_gateway": gateway,
                    "dns_server": dns,
                    "lease": lease,
                    "push_default": has_text_bit(action_cfg, 2),
                    "push_dns": has_text_bit(action_cfg, 1),
                    "push_lease": has_text_bit(action_cfg, 0),
                    "state": state,
                })
                ids["pool_del" if state == "remove" else "pool_add"].append(row_id)

            cursor.execute(
                f"SELECT h.id, h.helper_ip, i.{interface_column}, h.sync_status "
                f"FROM {tables['helper']} h JOIN {tables['interface']} i ON h.iface_id = i.iface_id "
                "WHERE i.host = ? AND (h.sync_status IN ('pending_apply', 'pending_delete') OR h.sync_status IS NULL)",
                (host,),
            )
            for row_id, helper_ip, interface_name, state_value in cursor.fetchall():
                state = success_state(state_value)
                config["relays"].append({
                    "interface": interface_name,
                    "helper_address": helper_ip,
                    "state": state,
                })
                ids["helper_del" if state == "remove" else "helper_add"].append(row_id)

            if any(ids.values()):
                valid_data.append({
                    "target": {"ip": host},
                    "action": "setup",
                    "ids": ids,
                    "config": [config],
                })

    if dry_run or not valid_data:
        return valid_data

    run_dhcp_config(valid_data, DB_PATH, DHCP_OUTPUT, session_provider=session_provider)
    results = []
    if os.path.exists(DHCP_OUTPUT):
        with open(DHCP_OUTPUT, "r", encoding="utf-8") as output_file:
            results = json.load(output_file)
    _apply_successful_results(valid_data, results, tables)
    return valid_data


def main():
    parser = argparse.ArgumentParser(description="DHCP Automation Controller")
    parser.add_argument("-t", "--target", default="all")
    args = parser.parse_args()
    dhcp_dispatcher(args.target)


if __name__ == "__main__":
    main()
