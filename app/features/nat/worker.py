from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader

from infrastructure.network.config import DB_TABLES, NAT_TEMPLATE_DIR, TMP_DIR
from infrastructure.network.nornir_netmiko_plugin import register_networktools_netmiko


T_DEVICES = DB_TABLES["device_info"]["main"]
CLI_ERRORS = ("% Invalid input", "Invalid input detected", "% Incomplete command", "% Ambiguous command")


def render_nat_template(platform: str, template_name: str, config_data: dict[str, Any]) -> str:
    template_dir = Path(NAT_TEMPLATE_DIR) / platform
    # Cisco CLI commands must retain their physical line boundaries.  Enabling
    # trim_blocks here can join the last command of one loop iteration with the
    # first command of the next one (most visible with multiple static maps).
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    try:
        return env.get_template(f"{template_name}.j2").render(config=config_data)
    except Exception as exc:
        raise RuntimeError(f"JINJA2 ERROR ({template_name}): {exc}") from exc


def render_nat_payload(payload: dict[str, Any], platform: str = "cisco_ios") -> list[str]:
    config = payload.get("config", payload)
    commands: list[str] = []
    for acl in config.get("nat_acl", []):
        commands.extend(_command_lines(render_nat_template(platform, "nat_acl", acl)))
    for nat in config.get("nat", []):
        commands.extend(_command_lines(render_nat_template(platform, "nat", nat)))
    return commands


def _command_lines(rendered: str) -> list[str]:
    return [line.strip() for line in rendered.splitlines() if line.strip() and not line.strip().startswith("!")]


def _with_logging_guard(commands: list[str]) -> list[str]:
    if not commands:
        return []
    return ["no logging console", "no logging monitor", *commands, "logging console", "logging monitor"]


def _ensure_no_cli_error(output: str) -> str:
    if any(marker.lower() in output.lower() for marker in CLI_ERRORS):
        raise RuntimeError(f"Router rejected one or more NAT commands: {output}")
    return output


def apply_nat_with_connector(connector: Any, payload: dict[str, Any]) -> str:
    return apply_nat_batch_with_connector(connector, [payload])


def apply_nat_batch_with_connector(
    connector: Any, payloads: list[dict[str, Any]]
) -> str:
    """Apply every pending NAT payload for a host in one config transaction."""
    connection = getattr(connector, "connection", None)
    if connection is None:
        raise RuntimeError("Active tab session has no Netmiko connection.")
    device_type = str(getattr(connector, "device_type", "") or "cisco_ios")
    platform = "cisco_ios" if device_type == "cisco_ios_telnet" else device_type
    commands = _with_logging_guard(
        [
            command
            for payload in payloads
            for command in render_nat_payload(payload, platform)
        ]
    )
    if not commands:
        return "No NAT commands were rendered."
    check_enable = getattr(connection, "check_enable_mode", None)
    enable = getattr(connection, "enable", None)
    if callable(check_enable) and callable(enable) and not check_enable():
        enable()
    output = str(connection.send_config_set(commands, read_timeout=60, cmd_verify=False))
    return _ensure_no_cli_error(output)


def _write_results(output_path: str, results: list[dict[str, Any]]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=4, ensure_ascii=False), encoding="utf-8")


def _target_ips(tasks: list[dict[str, Any]]) -> list[str]:
    return sorted({task.get("target", {}).get("ip") for task in tasks if task.get("target", {}).get("ip")})


def _dev_test_hosts(db_path: str, tasks: list[dict[str, Any]]) -> set[str]:
    targets = _target_ips(tasks)
    if not targets:
        return set()
    placeholders = ",".join("?" for _ in targets)
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            rows = conn.execute(
                f"SELECT host FROM {T_DEVICES} WHERE COALESCE(dev, 0)=1 AND host IN ({placeholders})",
                tuple(targets),
            ).fetchall()
        return {row[0] for row in rows}
    except Exception as exc:
        raise RuntimeError(f"Could not verify NAT dev-mode hosts: {exc}") from exc


def _run_with_sessions(tasks: list[dict[str, Any]], session_provider: Callable[[str], Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        grouped[task["target"]["ip"]].append(task)
    output = []
    for ip, host_tasks in sorted(grouped.items()):
        connector = session_provider(ip)
        if connector is None:
            output.append({"target": ip, "status": "failed", "message": "No active tab session. Reopen the device tab before pushing NAT configuration."})
            continue
        try:
            message = apply_nat_batch_with_connector(connector, host_tasks)
            output.append({"target": ip, "status": "success", "message": message})
        except Exception as exc:
            output.append({"target": ip, "status": "failed", "message": str(exc)})
    return output


def _build_inventory(db_path: str, tasks: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    task_by_ip = {task["target"]["ip"]: task for task in tasks}
    hosts: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    with closing(sqlite3.connect(db_path)) as conn:
        for ip, payload in task_by_ip.items():
            row = conn.execute(
                f"SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host=?",
                (ip,),
            ).fetchone()
            if not row:
                errors.append({"target": ip, "status": "failed", "message": "Device credentials were not found in the database."})
                continue
            name, user, password, os_name, port, method = row
            method = str(method or "SSH").upper()
            if method == "RESTCONF":
                errors.append({"target": ip, "status": "failed", "message": "NAT push over RESTCONF is not supported by the imported backend; use an SSH or Telnet device session."})
                continue
            platform = "cisco_ios_telnet" if method == "TELNET" and str(os_name).lower() == "cisco" else ("cisco_ios" if str(os_name).lower() == "cisco" else os_name)
            hosts[name or ip] = {
                "hostname": ip, "username": user, "password": password,
                "port": int(port or (23 if method == "TELNET" else 22)), "platform": platform,
                "connection_options": {"networktools_netmiko": {"extras": {
                    "banner_timeout": 30,
                    "auth_timeout": 30,
                    "session_timeout": 60,
                    "ssh_algorithm_db_path": db_path,
                }}},
                "data": {"template_folder": "cisco_ios" if platform == "cisco_ios_telnet" else platform, "ui_payload": payload},
            }
    if not hosts:
        return None, errors
    import yaml

    inventory_path = str(Path(TMP_DIR) / "tmp_nat_inventory.yaml")
    Path(inventory_path).parent.mkdir(parents=True, exist_ok=True)
    Path(inventory_path).write_text(yaml.safe_dump(hosts, allow_unicode=True), encoding="utf-8")
    return inventory_path, errors


def _task_push_nat(task):
    from nornir.core.task import Result
    from infrastructure.network.nornir_netmiko_tasks import netmiko_send_config

    payload = task.host.data["ui_payload"]
    platform = task.host.data.get("template_folder", "cisco_ios")
    commands = _with_logging_guard(render_nat_payload(payload, platform))
    if not commands:
        return Result(host=task.host, result="No NAT commands were rendered.")
    response = task.run(task=netmiko_send_config, config_commands=commands, read_timeout=60)
    return Result(host=task.host, result=_ensure_no_cli_error(str(response[0].result)))


def _run_with_nornir(tasks: list[dict[str, Any]], db_path: str) -> list[dict[str, Any]]:
    inventory_path, output = _build_inventory(db_path, tasks)
    if not inventory_path:
        return output
    from nornir import InitNornir

    try:
        register_networktools_netmiko()
        nr = InitNornir(
            runner={"plugin": "threaded", "options": {"num_workers": 3}},
            inventory={"plugin": "SimpleInventory", "options": {"host_file": inventory_path}},
            logging={"enabled": False},
        )
        results = nr.run(task=_task_push_nat)
        for host, result in results.items():
            status = "failed" if result.failed else "success"
            message = str(result.exception) if result.failed else str(result[0].result)
            output.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": message})
        return output
    finally:
        if os.path.exists(inventory_path):
            os.remove(inventory_path)


def run_nat_config(tasks: list[dict[str, Any]], db_path: str, output_path: str, session_provider=None) -> None:
    try:
        dev_hosts = _dev_test_hosts(db_path, tasks)
    except RuntimeError as exc:
        _write_results(output_path, [{"target": ip, "status": "failed", "message": f"Safety check failed; real NAT push was blocked. {exc}"} for ip in _target_ips(tasks)])
        return
    output = [{"target": ip, "status": "success", "message": "Dev-mode simulation succeeded; no device login or NAT push was performed."} for ip in sorted(dev_hosts)]
    real_tasks = [task for task in tasks if task.get("target", {}).get("ip") not in dev_hosts]
    if real_tasks:
        output.extend(_run_with_sessions(real_tasks, session_provider) if session_provider else _run_with_nornir(real_tasks, db_path))
    _write_results(output_path, output)
