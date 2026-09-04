import os
import json
import yaml
import re
import sys
import ipaddress
import sqlite3
import requests
import urllib3
import urllib.parse
from ncclient import manager
from jinja2 import Environment, FileSystemLoader

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from netmiko import ConnectHandler
except ImportError:
    pass

from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config
from nornir.core.task import Result

# ĐỒNG BỘ 100% TỪ TRẠM KIỂM SOÁT
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../../"))
if PROJECT_ROOT not in sys.path: sys.path.append(PROJECT_ROOT)

from PyCode.share.config import DB_PATH, DB_TABLES, INTERFACE_TEMPLATE_DIR, TMP_DIR

def netmask_to_cidr(network_str):
    try:
        if str(network_str).isdigit(): return int(network_str)
        return ipaddress.ip_network(f"0.0.0.0/{network_str}", strict=False).prefixlen
    except:
        return network_str

def parse_interface_name(intf_full_name):
    match = re.match(r"([a-zA-Z]+)([\d\./]+)", intf_full_name)
    if match: return match.group(1), match.group(2)
    return None, None

def render_interface_config(platform_folder, config_data, mode="setup", template_name="interface.j2"):
    template_dir = os.path.join(INTERFACE_TEMPLATE_DIR, platform_folder)
    if not os.path.exists(template_dir): return None
    try:
        env = Environment(loader=FileSystemLoader(template_dir))
        return env.get_template(template_name).render(config=config_data, mode=mode)
    except Exception as e:
        print(f"[-] Lỗi Render Template Interface ({template_name}): {e}")
        return None

# =========================================================
# XỬ LÝ RESTCONF / NETCONF (Giữ lại frame chính)
# =========================================================
def handle_restconf_interface(task, payload, mode):
    host_ip, port = task.host.hostname, task.host.port or 443
    user, pw = task.host.username, task.host.password
    headers = {"Accept": "application/yang-data+json", "Content-Type": "application/yang-data+json"}
    results = []
    
    template_dir = os.path.join(INTERFACE_TEMPLATE_DIR, task.host.data.get("template_folder", "cisco_ios"))
    env = Environment(loader=FileSystemLoader(template_dir))
    configs = payload.get("config", [])
    
    try:
        for config in configs:
            intf_name = config.get("name", "")
            intf_type, intf_id = parse_interface_name(intf_name)
            if not intf_type: continue
            intf_id_url = urllib.parse.quote(intf_id, safe='')
            base_url = f"https://{host_ip}:{port}/restconf/data/Cisco-IOS-XE-native:native/interface/{intf_type}={intf_id_url}"
            
            # Xóa IP nếu yêu cầu
            if config.get("ip_address") == "remove":
                requests.delete(f"{base_url}/ip/address/primary", auth=(user, pw), headers=headers, verify=False)
            
            # Gửi Gói JSON cho các thông số còn lại
            template_json = env.get_template('interface_restconf.j2')
            payload_json = template_json.render(config=config, intf_type=intf_type, intf_id=intf_id)
            res = requests.patch(base_url, auth=(user, pw), headers=headers, json=json.loads(payload_json), verify=False)
            results.append(f"Config {intf_name}: {res.status_code}")
                
        return " | ".join(results)
    except Exception as e: raise Exception(f"Lỗi RESTCONF: {str(e)}")

# =========================================================
# QUẢN LÝ INVENTORY & RUNNER
# =========================================================
def build_worker_inventory(task_list):
    task_map = {item.get("target", {}).get("ip"): item for item in task_list if item.get("target", {}).get("ip")}
    hosts_yaml = {}
    T_DEVICES = DB_TABLES["device_info"]["main"]
    try:
        conn_db = sqlite3.connect(DB_PATH)
        cursor = conn_db.cursor()
        for ip, payload in task_map.items():
            cursor.execute(f'SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host = ?', (ip,))
            row = cursor.fetchone()
            if row:
                dev_name, db_user, db_pass, db_os, db_port, db_method = row
                platform = "cisco_ios" if db_os == "cisco" else db_os
                tpl_folder = "cisco_ios" if platform == "cisco_ios_telnet" else platform
                hosts_yaml[dev_name or ip] = {
                    "hostname": ip, "username": db_user, "password": db_pass,
                    "port": db_port or (23 if db_method == "TELNET" else 22), "platform": platform,
                    "data": {"template_folder": tpl_folder, "ui_payload": payload, "method": db_method}
                }
        conn_db.close()
    except Exception as e: print(f"[-] Lỗi DB Worker: {e}")
    
    inv_file_path = os.path.join(TMP_DIR, "tmp_interface_inventory.yaml")
    with open(inv_file_path, 'w', encoding='utf-8') as f: yaml.dump(hosts_yaml, f)
    return inv_file_path

# =========================================================
# TASK PUSH CHÍNH
# =========================================================
def task_push_interface(task):
    my_payload = task.host.data["ui_payload"]
    mode = my_payload.get("action", "setup").lower()
    method = task.host.data.get("method", "SSH")
    
    if method == "RESTCONF": return Result(host=task.host, result=handle_restconf_interface(task, my_payload, mode))
    
    configs = my_payload.get("config", [])
    template_folder = task.host.data["template_folder"]
    all_commands = []
    
    for cfg in configs:
        if not cfg.get("name"): continue
        cmd_str = render_interface_config(template_folder, cfg, mode, template_name='interface.j2')
        if cmd_str: 
            lines = [l.strip() for l in cmd_str.splitlines() if l.strip() and not l.strip().startswith('!')]
            all_commands.extend(lines)

    if not all_commands: return "No commands to push."
    
    print(f"\n[DEBUG] Lệnh đấm xuống {task.host.hostname}: {all_commands}")
    res = task.run(
        task=netmiko_send_config, 
        config_commands=all_commands,
        read_timeout=90
    )
    return res[0].result

def run_interface_config(task_list, output_path):
    inv_path = build_worker_inventory(task_list)
    if not inv_path: return
    
    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 20}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_path}}, 
        logging={"enabled": False}
    )
    results = nr.run(task=task_push_interface)
    output_data = []
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        message = str(task_res.exception) if task_res.failed else (str(task_res[0].result) if hasattr(task_res[0], 'result') else str(task_res[0]))
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": message})
        print(f"[{'+' if status == 'success' else '-'}] {host}: {message}")
        
    with open(output_path, 'w', encoding='utf-8') as f: json.dump(output_data, f, indent=4, ensure_ascii=False)
    if os.path.exists(inv_path): os.remove(inv_path)