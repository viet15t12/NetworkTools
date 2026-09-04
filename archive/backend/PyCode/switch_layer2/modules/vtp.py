import os
import json
import yaml
from jinja2 import Environment, FileSystemLoader
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config
from backend.PyCode.share.config import TMP_DIR, DB_TABLES, L2_TEMPLATE_DIR, get_db_connection

def render_vtp_config(vtp_data):
    env = Environment(loader=FileSystemLoader(L2_TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("vtp.j2")
    return template.render(vtp_data=vtp_data)

def task_push_vtp(task):
    host_data = task.host.data.get("vtp_payload", {})
    commands_str = render_vtp_config(host_data)
    all_commands = [cmd.strip() for cmd in commands_str.splitlines() if cmd.strip() and not cmd.startswith('!')]

    if not all_commands:
        return "No commands to push."

    print(f"\n[+] ĐANG CHUẨN BỊ LỆNH VTP XUỐNG: {task.host.hostname}")
    for cmd in all_commands: 
        print(f"  {cmd}")

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

def build_vtp_inventory(db_path, task_list):
    """Tạo Inventory YAML tạm cho Nornir"""
    hosts_yaml = {}
    T_DEVICES = DB_TABLES["device_info"]["main"]
    
    try:
        conn = get_db_connection()
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
                    "data": {"vtp_payload": item["vtp_data"]}
                }
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi build VTP inventory: {e}")
        
    inv_file = os.path.join(TMP_DIR, "tmp_l2_vtp_inventory.yaml")
    with open(inv_file, 'w', encoding='utf-8') as f: 
        yaml.dump(hosts_yaml, f)
    return inv_file

def run_vtp_worker(input_data, db_path, output_path):
    """Khởi chạy Nornir Worker đẩy lệnh VTP"""
    inv_file = build_vtp_inventory(db_path, input_data)
    if not inv_file: 
        return

    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_push_vtp)
    output_data = []
    
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        msg = str(task_res.exception) if task_res.failed else str(task_res[0].result)
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": msg})
        
    with open(output_path, 'w', encoding='utf-8') as f: 
        json.dump(output_data, f, indent=4)
        
    if os.path.exists(inv_file): 
        os.remove(inv_file)