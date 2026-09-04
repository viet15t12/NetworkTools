import os
import json
import yaml
import sqlite3
from jinja2 import Environment, FileSystemLoader

from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config

from backend.PyCode.share.config import TMP_DIR, DB_TABLES, L2_TEMPLATE_DIR

def render_traffic_control_config(interfaces_data):
    """Render lệnh Cisco IOS từ Template traffic_control.j2"""
    env = Environment(loader=FileSystemLoader(L2_TEMPLATE_DIR))
    return env.get_template("traffic_control.j2").render(interfaces=interfaces_data)

def task_push_traffic_control(task):
    """Nhiệm vụ Nornir đẩy cấu hình Traffic Control & QoS xuống Switch"""
    interfaces_data = task.host.data.get("tc_payload", [])
    
    commands_str = render_traffic_control_config(interfaces_data)
    all_commands = [l.strip() for l in commands_str.splitlines() if l.strip() and not l.strip().startswith('!')]

    if not all_commands:
        return "No commands generated."

    # Tắt log console tạm thời để chống rác terminal
    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")
    all_commands.append("logging console")
    all_commands.append("logging monitor")

    # [1] IN CHIỀU ĐI: Lệnh chuẩn bị đẩy
    debug_output = f"\n======================================================\n"
    debug_output += f"[+] CHI TIẾT LỆNH TRAFFIC CONTROL -> {task.host.hostname}\n"
    debug_output += f"======================================================\n"
    for idx, cmd in enumerate(all_commands, 1): 
        debug_output += f"  [{task.host.hostname}] {idx:02d}. {cmd}\n"
    debug_output += f"======================================================\n"
    print(debug_output)

    # Đẩy lệnh xuống thiết bị
    res = task.run(
        task=netmiko_send_config, 
        config_commands=all_commands,
        read_timeout=60,
        cmd_verify=False
    )
    
    # [2] IN CHIỀU VỀ: Phản hồi thực tế từ Switch (MỚI THÊM)
    device_output = res[0].result
    print(f"\n[<<<] PHẢN HỒI TỪ SWITCH {task.host.hostname}:")
    print(f"------------------------------------------------------")
    print(device_output)
    print(f"------------------------------------------------------\n")
    
    return device_output

def build_l2_inventory(db_path, task_list):
    """Tạo file YAML Inventory động cho Nornir"""
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
                    "data": {"tc_payload": item["interfaces"]}
                }
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi build Traffic Control inventory: {e}")
        
    inv_file = os.path.join(TMP_DIR, "tmp_tc_inventory.yaml")
    with open(inv_file, 'w', encoding='utf-8') as f: 
        yaml.dump(hosts_yaml, f)
    return inv_file

def run_traffic_control_worker(input_data, db_path, output_path):
    """Khởi chạy đa luồng Nornir Worker cho Traffic Control"""
    inv_file = build_l2_inventory(db_path, input_data)
    if not inv_file: 
        return

    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_push_traffic_control)
    output_data = []
    
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        msg = str(task_res.exception) if task_res.failed else str(task_res[0].result)
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": msg})
        
    with open(output_path, 'w', encoding='utf-8') as f: 
        json.dump(output_data, f)
        
    if os.path.exists(inv_file): 
        os.remove(inv_file)