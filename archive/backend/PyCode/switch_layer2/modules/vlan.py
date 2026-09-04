import os
import json
import yaml
import sqlite3
from jinja2 import Environment, FileSystemLoader

# Dùng Nornir và Netmiko chuẩn như OSPF
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config
from nornir.core.task import Result

# Kéo config
from backend.PyCode.share.config import TMP_DIR, DB_TABLES, L2_TEMPLATE_DIR

def render_vlan_config(config_data):
    env = Environment(loader=FileSystemLoader(L2_TEMPLATE_DIR))
    return env.get_template("vlan.j2").render(vlans=config_data)

def task_push_vlan(task):
    """Nhiệm vụ của Nornir trên từng Switch"""
    vlans_data = task.host.data.get("vlan_payload", [])
    
    # 1. Sinh lệnh từ Jinja2
    commands_str = render_vlan_config(vlans_data)
    all_commands = [l.strip() for l in commands_str.splitlines() if l.strip() and not l.strip().startswith('!')]

    if not all_commands:
        return "No commands."

    print(f"\n[+] ĐANG CHUẨN BỊ LỆNH VLAN XUỐNG: {task.host.hostname}")
    for cmd in all_commands: print(f"  {cmd}")

    # 2. Đẩy lệnh qua Netmiko (Kế thừa bí kíp tắt log console của sếp)
    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")
    all_commands.append("exit")
    all_commands.append("logging console")
    all_commands.append("logging monitor")

    res = task.run(
        task=netmiko_send_config, 
        config_commands=all_commands,
        read_timeout=60,
        cmd_verify=False
    )
    
    return res[0].result

def build_l2_inventory(db_path, task_list):
    """Tạo Inventory YAML cho Nornir giống hệt hệ thống định tuyến"""
    hosts_yaml = {}
    T_DEVICES = DB_TABLES["device_info"]["main"]
    
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        for item in task_list:
            ip = item["target"]
            c.execute(f'SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host = ?', (ip,))
            row = c.fetchone()
            if row:
                dev_name, db_user, db_pass, db_os, db_port, db_method = row
                hosts_yaml[dev_name or ip] = {
                    "hostname": ip, 
                    "username": db_user, 
                    "password": db_pass,
                    "platform": "cisco_ios" if db_os == "cisco" else db_os,
                    "data": {"vlan_payload": item["vlans"]}
                }
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi build L2 inventory: {e}")
        
    inv_file = os.path.join(TMP_DIR, "tmp_l2_inventory.yaml")
    with open(inv_file, 'w', encoding='utf-8') as f: yaml.dump(hosts_yaml, f)
    return inv_file

def run_vlan_worker(input_data, db_path, output_path):
    """Khởi chạy Nornir Worker"""
    inv_file = build_l2_inventory(db_path, input_data)
    if not inv_file: return

    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_push_vlan)
    output_data = []
    
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        msg = str(task_res.exception) if task_res.failed else str(task_res[0].result)
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": msg})
        
    with open(output_path, 'w', encoding='utf-8') as f: json.dump(output_data, f)
    if os.path.exists(inv_file): os.remove(inv_file)