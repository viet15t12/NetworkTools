import os
import sqlite3
import re
import yaml
import json
import requests
import urllib3
import urllib.parse
from jinja2 import Environment, FileSystemLoader
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config, netmiko_send_command
from nornir.core.task import Result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Lùi 4 bước để ra tới thư mục 'backend'
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "..", ".."))

import sys
if BACKEND_DIR not in sys.path: sys.path.append(BACKEND_DIR)

# Trỏ thẳng về config chung lấy BACKUP_DIR
from PyCode.share.config import BACKUP_DIR
from PyCode.share.config import DB_TABLES


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
    res = task.run(task=netmiko_send_config, config_commands=cmds_list)
    return res[0].result

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
                        "netmiko": {
                            "extras": {
                                "banner_timeout": 30, 
                                "auth_timeout": 30, 
                                "session_timeout": 60, 
                                "global_delay_factor": 2
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

def run_dhcp_config(task_list, db_path, output_path):
    print("\n[INFO] Khởi động Nornir DHCP Worker (Đồng bộ Single Source of Truth)...")
    inv_file_path = build_dhcp_inventory(db_path, task_list)
    if not inv_file_path: return
    
    nr = InitNornir(runner={"plugin": "threaded", "options": {"num_workers": 10}}, inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file_path}}, logging={"enabled": False})
    results = nr.run(task=task_manage_dhcp)
    output_data = []

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

    with open(output_path, 'w', encoding='utf-8') as f: json.dump(output_data, f, indent=4, ensure_ascii=False)
    if os.path.exists(inv_file_path): os.remove(inv_file_path)