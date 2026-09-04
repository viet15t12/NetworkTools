import os
import json
import yaml
import sqlite3
from jinja2 import Environment, FileSystemLoader

from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config
from backend.PyCode.share.config import TMP_DIR, DB_TABLES, L2_TEMPLATE_DIR

def render_stp_config(stp_globals, stp_interfaces):
    # Dùng chung biến môi trường L2_TEMPLATE_DIR cho đồng bộ toàn project
    env = Environment(loader=FileSystemLoader(L2_TEMPLATE_DIR))
    template = env.get_template("stp.j2")
    return template.render(stp_globals=stp_globals, stp_interfaces=stp_interfaces)

def task_push_stp(task):
    # Lấy dữ liệu đã được tiêm qua Inventory
    host_data = task.host.data.get("stp_payload", {})
    stp_globals = host_data.get("stp_globals", [])
    stp_interfaces = host_data.get("stp_interfaces", [])

    commands_str = render_stp_config(stp_globals, stp_interfaces)
    all_commands = [cmd.strip() for cmd in commands_str.splitlines() if cmd.strip() and not cmd.startswith('!')]

    if not all_commands:
        return "No commands."

    print(f"\n[+] ĐANG CHUẨN BỊ LỆNH STP XUỐNG: {task.host.hostname}")
    for cmd in all_commands: print(f"  {cmd}")

    # Chống nhiễu log terminal trên Switch
    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")
    all_commands.append("logging console")
    all_commands.append("logging monitor")

    res = task.run(
        task=netmiko_send_config, 
        config_commands=all_commands,
        read_timeout=60,
        cmd_verify=False
    )
    return res[0].result

def build_stp_inventory(db_path, task_list):
    """Tạo Inventory YAML cho Nornir giống hệt nhánh VLAN và Interface"""
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
                    "data": {"stp_payload": item}  # Tiêm thẳng cấu hình STP vào đây
                }
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi build STP inventory: {e}")
        
    inv_file = os.path.join(TMP_DIR, "tmp_l2_stp_inventory.yaml")
    with open(inv_file, 'w', encoding='utf-8') as f: 
        yaml.dump(hosts_yaml, f)
    return inv_file

def run_stp_worker(input_data, db_path, output_path):
    """Khởi chạy Nornir Worker y hệt vlan.py và interface_l2.py"""
    inv_file = build_stp_inventory(db_path, input_data)
    if not inv_file: 
        return

    # Khởi tạo Nornir KHÔNG CẦN file config.yaml tĩnh
    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_push_stp)
    output_data = []
    
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        msg = str(task_res.exception) if task_res.failed else str(task_res[0].result)
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": msg})
        
    # Ghi log chuẩn để main.py nhận diện trạng thái success/failed
    with open(output_path, 'w', encoding='utf-8') as f: 
        json.dump(output_data, f)
        
    # Xóa file inventory tạm sau khi push xong
    if os.path.exists(inv_file): 
        os.remove(inv_file)