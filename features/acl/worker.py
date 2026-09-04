from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader

from infrastructure.network.config import ACL_TEMPLATE_DIR, DB_TABLES, TMP_DIR
from infrastructure.network.nornir_netmiko_plugin import register_cams_netmiko


T_DEVICES = DB_TABLES["device_info"]["main"]
CLI_ERRORS = (
    "% Invalid input",
    "Invalid input detected",
    "% Incomplete command",
    "% Ambiguous command",
    "% Bad mask",
)


def _command_lines(rendered: str) -> list[str]:
    return [
        line.strip()
        for line in rendered.splitlines()
        if line.strip() and not line.strip().startswith("!")
    ]


def render_acl_payload(payload: dict[str, Any], platform: str = "cisco_ios") -> list[str]:
    config = payload.get("config", payload)
    acl_type = str(config.get("acl_type") or "standard").lower()
    template_name = "extended" if acl_type in {"dynamic", "reflexive"} else acl_type
    template_dir = Path(ACL_TEMPLATE_DIR) / platform
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    rendered = env.get_template(f"{template_name}.j2").render(**config)

    commands: list[str] = []
    bindings = config.get("bindings", [])
    for binding in bindings:
        if binding.get("state") == "remove":
            commands.extend(_binding_commands(config["acl_name"], binding))
    commands.extend(_command_lines(rendered))
    for binding in bindings:
        if binding.get("state") != "remove":
            commands.extend(_binding_commands(config["acl_name"], binding))
    return commands


def _binding_commands(acl_name: str, binding: dict[str, Any]) -> list[str]:
    prefix = "no " if binding.get("state") == "remove" else ""
    return [
        f"interface {binding['interface_name']}",
        f"{prefix}ip access-group {acl_name} {binding['direction']}",
        "exit",
    ]


def _guarded(commands: list[str]) -> list[str]:
    return ["no logging console", *commands, "logging console"] if commands else []


def _check_output(output: str) -> str:
    if any(marker.lower() in output.lower() for marker in CLI_ERRORS):
        raise RuntimeError(f"Router rejected one or more ACL commands: {output}")
    return output


def apply_acl_with_connector(connector: Any, host_tasks: list[dict[str, Any]]) -> str:
    connection = getattr(connector, "connection", None)
    if connection is None:
        raise RuntimeError("Active tab session has no Netmiko connection.")
    device_type = str(getattr(connector, "device_type", "") or "cisco_ios")
    platform = "cisco_ios" if device_type == "cisco_ios_telnet" else device_type
    commands: list[str] = []
    for task in host_tasks:
        commands.extend(render_acl_payload(task, platform))
    commands = _guarded(commands)
    if not commands:
        return "No ACL commands were rendered."
    check_enable = getattr(connection, "check_enable_mode", None)
    enable = getattr(connection, "enable", None)
    if callable(check_enable) and callable(enable) and not check_enable():
        enable()
    return _check_output(str(connection.send_config_set(commands, read_timeout=60, cmd_verify=False)))


def _target_ips(tasks: list[dict[str, Any]]) -> list[str]:
    return sorted({str(task.get("target", {}).get("ip") or "") for task in tasks} - {""})


def _dev_hosts(db_path: str, tasks: list[dict[str, Any]]) -> set[str]:
    targets = _target_ips(tasks)
    if not targets:
        return set()
    placeholders = ",".join("?" for _ in targets)
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            f"SELECT host FROM {T_DEVICES} WHERE COALESCE(dev, 0)=1 AND host IN ({placeholders})",
            tuple(targets),
        ).fetchall()
    return {str(row[0]) for row in rows}


def _run_with_sessions(
    tasks: list[dict[str, Any]],
    session_provider: Callable[[str], Any],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        grouped[str(task["target"]["ip"])].append(task)
    output: list[dict[str, Any]] = []
    for ip, host_tasks in sorted(grouped.items()):
        connector = session_provider(ip)
        if connector is None:
            output.append({
                "target": ip,
                "status": "failed",
                "message": "No active tab session. Reopen the device tab before pushing ACL configuration.",
            })
            continue
        try:
            message = apply_acl_with_connector(connector, host_tasks)
            output.append({"target": ip, "status": "success", "message": message})
        except Exception as exc:
            output.append({"target": ip, "status": "failed", "message": str(exc)})
    return output


def _build_inventory(
    db_path: str,
    tasks: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        grouped[str(task["target"]["ip"])].append(task)
    hosts: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    with closing(sqlite3.connect(db_path)) as conn:
        for ip, host_tasks in grouped.items():
            row = conn.execute(
                f"SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host=?",
                (ip,),
            ).fetchone()
            if not row:
                errors.append({"target": ip, "status": "failed", "message": "Device credentials were not found."})
                continue
            name, user, password, os_name, port, method = row
            method = str(method or "SSH").upper()
            if method == "RESTCONF":
                errors.append({
                    "target": ip,
                    "status": "failed",
                    "message": "ACL push over RESTCONF is not supported; use SSH or Telnet.",
                })
                continue
            platform = (
                "cisco_ios_telnet"
                if method == "TELNET" and str(os_name).lower() == "cisco"
                else ("cisco_ios" if str(os_name).lower() == "cisco" else str(os_name))
            )
            hosts[str(name or ip)] = {
                "hostname": ip,
                "username": user,
                "password": password,
                "port": int(port or (23 if method == "TELNET" else 22)),
                "platform": platform,
                "connection_options": {"cams_netmiko": {"extras": {
                    "banner_timeout": 30,
                    "auth_timeout": 30,
                    "session_timeout": 60,
                    "ssh_algorithm_db_path": db_path,
                }}},
                "data": {
                    "template_folder": "cisco_ios" if platform == "cisco_ios_telnet" else platform,
                    "ui_payloads": host_tasks,
                },
            }
    if not hosts:
        return None, errors
    import yaml

    inventory_path = str(Path(TMP_DIR) / "tmp_acl_inventory.yaml")
    Path(inventory_path).parent.mkdir(parents=True, exist_ok=True)
    Path(inventory_path).write_text(yaml.safe_dump(hosts, allow_unicode=True), encoding="utf-8")
    return inventory_path, errors


def _task_push_acl(task):
    from nornir.core.task import Result
    from infrastructure.network.nornir_netmiko_tasks import netmiko_send_config

    platform = task.host.data.get("template_folder", "cisco_ios")
    commands: list[str] = []
    for payload in task.host.data["ui_payloads"]:
        commands.extend(render_acl_payload(payload, platform))
    commands = _guarded(commands)
    if not commands:
        return Result(host=task.host, result="No ACL commands were rendered.")
    response = task.run(task=netmiko_send_config, config_commands=commands, read_timeout=60)
    return Result(host=task.host, result=_check_output(str(response[0].result)))


def _run_with_nornir(tasks: list[dict[str, Any]], db_path: str) -> list[dict[str, Any]]:
    inventory_path, output = _build_inventory(db_path, tasks)
    if not inventory_path:
        return output
    from nornir import InitNornir

    try:
        register_cams_netmiko()
        nr = InitNornir(
            runner={"plugin": "threaded", "options": {"num_workers": 3}},
            inventory={"plugin": "SimpleInventory", "options": {"host_file": inventory_path}},
            logging={"enabled": False},
        )
        results = nr.run(task=_task_push_acl)
        for host, result in results.items():
            output.append({
                "target": nr.inventory.hosts[host].hostname,
                "status": "failed" if result.failed else "success",
                "message": str(result.exception) if result.failed else str(result[0].result),
            })
        return output
    finally:
        if os.path.exists(inventory_path):
            os.remove(inventory_path)


def run_acl_config(
    tasks: list[dict[str, Any]],
    db_path: str,
    output_path: str,
    session_provider=None,
) -> None:
    try:
        dev_hosts = _dev_hosts(db_path, tasks)
    except Exception as exc:
        results = [
            {"target": ip, "status": "failed", "message": f"Safety check failed; ACL push was blocked. {exc}"}
            for ip in _target_ips(tasks)
        ]
    else:
        results = [
            {
                "target": ip,
                "status": "success",
                "message": "Dev-mode simulation succeeded; no device login or ACL push was performed.",
            }
            for ip in sorted(dev_hosts)
        ]
        real_tasks = [
            task for task in tasks
            if str(task.get("target", {}).get("ip") or "") not in dev_hosts
        ]
        if real_tasks:
            results.extend(
                _run_with_sessions(real_tasks, session_provider)
                if session_provider
                else _run_with_nornir(real_tasks, db_path)
            )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=4, ensure_ascii=False), encoding="utf-8")
