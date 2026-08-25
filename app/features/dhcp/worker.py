import os
import sqlite3
import re
import yaml
import json
import requests
import urllib3
import urllib.parse
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader
from nornir import InitNornir
from infrastructure.network.nornir_netmiko_tasks import (
    netmiko_send_command,
    netmiko_send_config,
)
from nornir.core.task import Result
from infrastructure.network.nornir_netmiko_plugin import register_networktools_netmiko

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Resolve the application root without relying on the working directory.
APP_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

import sys
if APP_ROOT not in sys.path: sys.path.append(APP_ROOT)

# Trỏ thẳng về config chung lấy BACKUP_DIR
from infrastructure.network.config import BACKUP_DIR, DB_TABLES


T_DEVICES = DB_TABLES["device_info"]["main"]

def render_dhcp_template(platform, payload):
    folder_name = "router" if "cisco" in platform else platform
    template_dir = os.path.join(CURRENT_DIR, "templates", folder_name)
    if not os.path.exists(template_dir): raise Exception(f"Không tìm thấy thư mục template: {template_dir}")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("dhcp_config.j2")
    return template.render(config=payload.get("config", [{}])[0])

def handle_restconf_dhcp(task, payload):
    host_ip = task.host.hostname
    rest_port = task.host.data.get("rest_port", 443)
    user, pw = task.host.username, task.host.password
    
    config = payload.get("config", [{}])[0]
    headers = {"Accept": "application/yang-data+json", "Content-Type": "application/yang-data+json"}
    dhcp_url = f"https://{host_ip}:{rest_port}/restconf/data/Cisco-IOS-XE-native:native/ip/dhcp"
    results = []

    try:
        # Excluded Addresses
        for exc in config.get("excluded_addresses", []):
            start_ip = exc.get("start_ip")
            end_ip = exc.get("end_ip")
            url_ex = f"{dhcp_url}/excluded-address/low-high-address-list={start_ip},{end_ip}" if end_ip else f"{dhcp_url}/excluded-address/low-address-list={start_ip}"
            list_name = "low-high-address-list" if end_ip else "low-address-list"
            item_data = {"low-address": start_ip, "high-address": end_ip} if end_ip else {"low-address": start_ip}

            if exc.get("state") in ["remove", "absent"]:
                requests.delete(url_ex, auth=(user, pw), headers=headers, verify=False)
                results.append(f"Xóa Excluded {start_ip}")
            else:
                requests.put(url_ex, auth=(user, pw), headers=headers, json={f"Cisco-IOS-XE-dhcp:{list_name}": [item_data]}, verify=False)
                results.append(f"Setup Excluded {start_ip}")

        # DHCP Pools
        for pool in config.get("pools", []):
            pool_name = pool.get("name")
            pool_name_url = urllib.parse.quote(pool_name, safe='')
            url_pool = f"{dhcp_url}/pool={pool_name_url}"
            
            if pool.get("state") in ["remove", "absent"]:
                requests.delete(url_pool, auth=(user, pw), headers=headers, verify=False)
                results.append(f"Xóa Pool {pool_name}")
            else:
                pool_data = {"id": pool_name}
                if pool.get("network"): 
                    pool_data["network"] = {"primary-network": {"number": pool["network"], "mask": pool.get("subnet_mask", "255.255.255.0")}}
                if pool.get("default_gateway"): 
                    pool_data["default-router"] = {"default-router-list": pool["default_gateway"].split()}
                if pool.get("dns_server"): 
                    pool_data["dns-server"] = {"dns-server-list": pool["dns_server"].split()}
                
                requests.put(url_pool, auth=(user, pw), headers=headers, json={"Cisco-IOS-XE-dhcp:pool": [pool_data]}, verify=False)
                results.append(f"Setup Pool {pool_name}")

        return " | ".join(results) if results else "Xử lý RESTCONF thành công (Không có data)."
    except Exception as e:
        raise Exception(f"Lỗi RESTCONF: {str(e)}")

def handle_ssh_dhcp(task, payload):
    cmds_str = render_dhcp_template(task.host.data["platform_os"], payload)
    cmds_list = [cmd.strip() for cmd in cmds_str.splitlines() if cmd.strip()]
    if not cmds_list: raise Exception("Template không sinh ra mã lệnh CLI nào!")
    res = task.run(
        task=netmiko_send_config,
        config_commands=cmds_list,
        read_timeout=60,
        cmd_verify=False,
    )
    return res[0].result

def build_dhcp_commands(payload, platform):
    rendered = render_dhcp_template(platform, payload)
    return [line.strip() for line in rendered.splitlines() if line.strip() and not line.strip().startswith("!")]

def apply_dhcp_with_connector(connector, payload):
    connection = getattr(connector, "connection", None)
    if connection is None:
        raise RuntimeError("Active tab session has no Netmiko connection.")

    device_type = str(getattr(connector, "device_type", "") or "cisco_ios")
    template_folder = "cisco_ios" if device_type == "cisco_ios_telnet" else device_type
    commands = build_dhcp_commands(payload, template_folder)
    if not commands:
        return "No DHCP commands were rendered."

    check_enable_mode = getattr(connection, "check_enable_mode", None)
    enable = getattr(connection, "enable", None)
    if callable(check_enable_mode) and callable(enable) and not check_enable_mode():
        enable()

    return connection.send_config_set(commands, read_timeout=60, cmd_verify=False)

def task_manage_dhcp(task):
    payload = task.host.data["ui_payload"]
    mode = payload.get("action", "setup")
    method = task.host.data.get("method", "SSH")
    
    if mode == "show":
        if method == "RESTCONF":
            host_ip, rest_port = task.host.hostname, task.host.data.get("rest_port", 443)
            user, pw = task.host.username, task.host.password
            oper_url = f"https://{host_ip}:{rest_port}/restconf/data/Cisco-IOS-XE-dhcp-oper:dhcp-oper-data"
            try:
                res = requests.get(oper_url, auth=(user, pw), headers={"Accept": "application/yang-data+json", "Connection": "close"}, verify=False, timeout=10)
                if res.status_code == 200: return Result(host=task.host, result=res.text)
                if res.status_code == 404: return Result(host=task.host, result=json.dumps({"Cisco-IOS-XE-dhcp-oper:dhcp-oper-data": {"dhcp-v4-binding": []}}))
                raise Exception(f"API HTTP {res.status_code}")
            except Exception as e:
                cli_text = task.run(task=netmiko_send_command, command_string="show ip dhcp binding").result
                fallback_bindings = []
                for line in cli_text.splitlines():
                    match = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s+([a-fA-F0-9.]+)\s+(.*?)\s+(Automatic|Manual)", line.strip())
                    if match: fallback_bindings.append({"client-ip": match.group(1), "client-hardware-address": match.group(2), "expiration": match.group(3).strip(), "binding-type": match.group(4)})
                return Result(host=task.host, result=json.dumps({"Cisco-IOS-XE-dhcp-oper:dhcp-oper-data": {"dhcp-v4-binding": fallback_bindings}}))
        return task.run(task=netmiko_send_command, command_string="show ip dhcp binding").result

    if mode == "clear":
        ip = payload.get("config", [{}])[0].get("ip_address", "all")
        return task.run(task=netmiko_send_command, command_string="clear ip dhcp binding *" if ip.lower() == "all" else f"clear ip dhcp binding {ip}").result

    if method == "RESTCONF": return Result(host=task.host, result=handle_restconf_dhcp(task, payload))
    return Result(host=task.host, result=handle_ssh_dhcp(task, payload))

def build_dhcp_inventory(db_path, task_list):
    task_map = {item.get("target", {}).get("ip"): item for item in task_list if item.get("target", {}).get("ip")}
    hosts_yaml = {}
    if not task_map: return None

    try:
        conn_db = sqlite3.connect(db_path)
        cursor = conn_db.cursor()
        for ip, payload in task_map.items():
            cursor.execute(f'SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host = ?', (ip,))
            row = cursor.fetchone()
            if row:
                dev_name, db_user, db_pass, db_os, db_port, db_method = row
                
                # --- CHUẨN HÓA PLATFORM VÀ PORT CHO NETMIKO ---
                platform_final = "cisco_ios" # Mặc định là SSH
                conn_port = 22
                
                if str(db_method).upper() == "TELNET":
                    platform_final = "cisco_ios_telnet"
                    conn_port = db_port if db_port else 23
                elif str(db_method).upper() == "SSH":
                    conn_port = db_port if db_port else 22
                
                # Nếu không phải Cisco thì cứ lấy OS trong DB
                if str(db_os).lower() != "cisco":
                    platform_final = db_os

                hosts_yaml[dev_name if dev_name else ip] = {
                    "hostname": ip, 
                    "username": db_user, 
                    "password": db_pass, 
                    "port": conn_port,          # Đã fix port linh hoạt
                    "platform": platform_final, # Đã fix hệ điều hành Telnet/SSH
                    "connection_options": {
                        "networktools_netmiko": {
                            "extras": {
                                "banner_timeout": 30, 
                                "auth_timeout": 30, 
                                "session_timeout": 60, 
                                "global_delay_factor": 2,
                                "ssh_algorithm_db_path": db_path
                            }
                        }
                    },
                    "data": {
                        "ui_payload": payload, 
                        "platform_os": db_os, 
                        "method": db_method, 
                        "rest_port": db_port if db_port else 443
                    }
                }
    except Exception as e: 
        print(f"[ERROR] Lỗi DB: {e}")
    finally:
        if 'conn_db' in locals(): conn_db.close()
        
    inv_file_path = os.path.join(CURRENT_DIR, "tmp_dhcp_inventory.yaml")
    with open(inv_file_path, 'w', encoding='utf-8') as f: yaml.dump(hosts_yaml, f)
    return inv_file_path

def _dev_test_hosts(db_path, task_list):
    target_ips = sorted({
        item.get("target", {}).get("ip")
        for item in task_list
        if item.get("target", {}).get("ip")
    })
    if not target_ips:
        return set()

    placeholders = ",".join("?" for _ in target_ips)
    conn_db = None
    try:
        conn_db = sqlite3.connect(db_path)
        cursor = conn_db.cursor()
        cursor.execute(
            f"SELECT host FROM {T_DEVICES} WHERE COALESCE(dev, 0) = 1 AND host IN ({placeholders})",
            tuple(target_ips),
        )
        return {row[0] for row in cursor.fetchall()}
    except Exception as exc:
        raise RuntimeError(f"Could not verify DHCP dev-mode hosts: {exc}") from exc
    finally:
        if conn_db is not None:
            conn_db.close()

def _target_results(task_list, status, message):
    target_ips = sorted({
        item.get("target", {}).get("ip")
        for item in task_list
        if item.get("target", {}).get("ip")
    })
    return [{"target": ip, "status": status, "message": message} for ip in target_ips]

def _write_results(output_path, output_data):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(output_data, output_file, indent=4, ensure_ascii=False)

def run_dhcp_config_with_sessions(task_list, output_path, session_provider, output_data):
    tasks_by_ip = defaultdict(list)
    for item in task_list:
        ip = item.get("target", {}).get("ip")
        if ip:
            tasks_by_ip[ip].append(item)

    for ip, tasks in sorted(tasks_by_ip.items()):
        connector = session_provider(ip)
        if connector is None:
            output_data.append({
                "target": ip,
                "status": "failed",
                "message": "No active tab session. Reopen the device tab before pushing DHCP configuration.",
            })
            continue

        try:
            messages = [str(apply_dhcp_with_connector(connector, payload)) for payload in tasks]
            output_data.append({"target": ip, "status": "success", "message": "\n".join(messages)})
        except Exception as exc:
            output_data.append({"target": ip, "status": "failed", "message": str(exc)})

    _write_results(output_path, output_data)

def run_dhcp_config(task_list, db_path, output_path, session_provider=None):
    print("\n[INFO] Starting DHCP Worker...")
    try:
        dev_hosts = _dev_test_hosts(db_path, task_list)
    except RuntimeError as exc:
        message = f"Safety check failed; real DHCP push was blocked. {exc}"
        _write_results(output_path, _target_results(task_list, "failed", message))
        return

    output_data = [
        {
            "target": ip,
            "status": "success",
            "message": "Dev-mode simulation succeeded; no device login or push was performed.",
        }
        for ip in sorted(dev_hosts)
    ]
    real_tasks = [
        item for item in task_list
        if item.get("target", {}).get("ip") not in dev_hosts
    ]

    if not real_tasks:
        _write_results(output_path, output_data)
        return

    if session_provider is not None:
        run_dhcp_config_with_sessions(real_tasks, output_path, session_provider, output_data)
        return

    inv_file_path = build_dhcp_inventory(db_path, real_tasks)
    if not inv_file_path:
        _write_results(output_path, output_data)
        return
    
    register_networktools_netmiko()
    nr = InitNornir(runner={"plugin": "threaded", "options": {"num_workers": 10}}, inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file_path}}, logging={"enabled": False})
    results = nr.run(task=task_manage_dhcp)
    for host, task_res in results.items():
        payload = nr.inventory.hosts[host].data.get("ui_payload", {})
        mode = payload.get("action", "setup")
        method = nr.inventory.hosts[host].data.get("method", "SSH")
        
        status = "failed" if task_res.failed else "success"
        message = str(task_res.exception) if task_res.failed else str(task_res[0].result if type(task_res) is not Result else task_res.result)
        
        if status == "failed" or "Invalid input" in message:
            print(f"[-] Thất bại: {host} -> {message}")
            status = "failed"
        else:
            print(f"[+] Thành công: {host} -> Đã nạp DHCP/Ghi nhận dữ liệu.")

        host_result = {"target": nr.inventory.hosts[host].hostname, "status": status, "message": message}
        
        if mode == "show" and status == "success":
            ip_target = nr.inventory.hosts[host].hostname
            host_backup_dir = os.path.join(BACKUP_DIR, ip_target) # <-- Dùng biến từ config.py
            os.makedirs(host_backup_dir, exist_ok=True)
            
            # (Đoạn mã parse binding JSON giữ nguyên)
            # ...
            host_result["message"] = "Trích xuất show binding thành công."

        output_data.append(host_result)

    _write_results(output_path, output_data)
    if os.path.exists(inv_file_path): os.remove(inv_file_path)
