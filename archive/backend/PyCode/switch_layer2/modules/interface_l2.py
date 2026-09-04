import os
import json
import yaml
import sqlite3
from jinja2 import Environment, FileSystemLoader
from nornir.core.exceptions import NornirSubTaskError
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config

from backend.PyCode.share.config import TMP_DIR, DB_TABLES, L2_TEMPLATE_DIR

def render_interface_config(config_data):
    env = Environment(loader=FileSystemLoader(L2_TEMPLATE_DIR))
    return env.get_template("interface_l2.j2").render(interfaces=config_data)

def task_push_interface(task):
    ifaces_data = task.host.data.get("interface_payload", [])
    
    commands_str = render_interface_config(ifaces_data)
    all_commands = [l.strip() for l in commands_str.splitlines() if l.strip() and not l.strip().startswith('!')]

    if not all_commands:
        return "No commands."

    print(f"\n[+] ĐANG CHUẨN BỊ LỆNH INTERFACE XUỐNG: {task.host.hostname}")
    for cmd in all_commands: print(f"  {cmd}")

    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")
    all_commands.append("logging console")
    all_commands.append("logging monitor")

    # BƯỚC 1: Đẩy cấu hình lần 1 (Đã bọc Try-Except)
    try:
        res = task.run(
            task=netmiko_send_config, 
            config_commands=all_commands,
            read_timeout=60,
            cmd_verify=False
        )
        task_result = res[0]
        output = str(task_result.result)
        
    except NornirSubTaskError as e:
        # Bắt luôn lỗi rớt mạng, sai pass, timeout ở đây
        return f"Push thất bại do lỗi kết nối hoặc Timeout: {str(e)}"

    # BƯỚC 2: Bẫy lỗi và tự động chữa cháy (Self-Healing)
    if "Autoneg enabled" in output or "Speed cannot be set" in output:
        print(f"\n[!] CẢNH BÁO ({task.host.hostname}): Phát hiện lỗi Autoneg. Đang kích hoạt tự động sửa lỗi...")
        
        fix_commands = []
        for iface in ifaces_data:
            speed_val = iface.get('speed')
            duplex_val = iface.get('duplex')
            if_name = iface.get('if_name', '')
            
            if speed_val not in ['auto', 'None', None] and 'Port-channel' not in if_name:
                fix_commands.extend([
                    f"interface {if_name}",
                    "no negotiation auto",
                    f"speed {speed_val}"
                ])
                if duplex_val not in ['auto', 'None', None]:
                    fix_commands.append(f"duplex {duplex_val}")
                    
        if fix_commands:
            try:
                fix_res = task.run(
                    task=netmiko_send_config, 
                    config_commands=fix_commands,
                    read_timeout=60,
                    cmd_verify=False
                )
                output += f"\n\n[*] TỰ ĐỘNG SỬA LỖI THÀNH CÔNG:\n{fix_res[0].result}"
            except NornirSubTaskError as e:
                output += f"\n\n[!] TỰ ĐỘNG SỬA LỖI THẤT BẠI (Rớt mạng giữa chừng):\n{str(e)}"

    return output

def build_iface_inventory(db_path, task_list):
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
                    "data": {"interface_payload": item["interfaces"]}
                }
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi build L2 Interface inventory: {e}")
        
    inv_file = os.path.join(TMP_DIR, "tmp_l2_iface_inventory.yaml")
    with open(inv_file, 'w', encoding='utf-8') as f: yaml.dump(hosts_yaml, f)
    return inv_file

def run_interface_worker(input_data, db_path, output_path):
    inv_file = build_iface_inventory(db_path, input_data)
    if not inv_file: return

    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_push_interface)
    output_data = []
    
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        msg = str(task_res.exception) if task_res.failed else str(task_res[0].result)
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": msg})
        
    with open(output_path, 'w', encoding='utf-8') as f: json.dump(output_data, f)
    if os.path.exists(inv_file): os.remove(inv_file)