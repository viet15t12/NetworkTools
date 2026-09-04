import os
import json
import yaml
import sqlite3
from jinja2 import Environment, FileSystemLoader
from nornir.core.exceptions import NornirSubTaskError
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config

# Import cấu hình chuẩn từ file config của sếp
from backend.PyCode.share.config import TMP_DIR, DB_TABLES, L2_TEMPLATE_DIR

def render_security_config(global_sec, interfaces):
    """
    Load file Jinja2 và nhồi 2 cục data (global & interfaces) vào để render ra mã lệnh
    """
    env = Environment(loader=FileSystemLoader(L2_TEMPLATE_DIR))
    return env.get_template("security_l2.j2").render(
        global_sec=global_sec, 
        interfaces=interfaces
    )

def task_push_security(task):
    """
    Task thực thi của Nornir: Bắn lệnh cấu hình xuống thiết bị thật
    """
    # Lấy data từ biến temporary do Nornir Inventory truyền vào
    global_data = task.host.data.get("global_sec")
    ifaces_data = task.host.data.get("interfaces", [])
    
    # Render lệnh
    commands_str = render_security_config(global_data, ifaces_data)
    
    # Lọc bỏ các dòng trống và dòng comment (bắt đầu bằng dấu !)
    all_commands = [l.strip() for l in commands_str.splitlines() if l.strip() and not l.strip().startswith('!')]

    if not all_commands:
        return "No commands."

    print(f"\n[+] ĐANG CHUẨN BỊ LỆNH SECURITY XUỐNG: {task.host.hostname}")
    for cmd in all_commands: 
        print(f"  {cmd}")

    # Trick: Tắt log console tạm thời để Netmiko không bị đọc nhầm prompt (kế thừa từ logic cũ của sếp)
    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")
    all_commands.append("logging console")
    all_commands.append("logging monitor")

    try:
        res = task.run(
            task=netmiko_send_config, 
            config_commands=all_commands,
            read_timeout=200,
            cmd_verify=False 
        )
        return str(res[0].result)
        
    except NornirSubTaskError as e:
        return f"Push thất bại do lỗi kết nối hoặc Timeout: {str(e)}"

def build_security_inventory(db_path, task_list):
    """
    Truy xuất DB Letos để lấy username/password và bọc data payload thành file YAML cho Nornir
    """
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
                    "data": {
                        "global_sec": item.get("global_sec"),
                        "interfaces": item.get("interfaces", [])
                    }
                }
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi build L2 Security inventory: {e}")
        
    inv_file = os.path.join(TMP_DIR, "tmp_l2_security_inventory.yaml")
    with open(inv_file, 'w', encoding='utf-8') as f: 
        yaml.dump(hosts_yaml, f)
    return inv_file

def run_security_worker(input_data, db_path, output_path):
    """
    Hàm main khởi chạy Nornir Worker, được gọi từ file main.py (Dispatcher)
    """
    inv_file = build_security_inventory(db_path, input_data)
    if not inv_file: 
        return

    # Khởi tạo Nornir với 10 luồng xử lý song song (Threaded)
    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_push_security)
    output_data = []
    
    # Gom kết quả từ tất cả các luồng để kết xuất ra file log JSON
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        msg = str(task_res.exception) if task_res.failed else str(task_res[0].result)
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": msg})
        
    with open(output_path, 'w', encoding='utf-8') as f: 
        json.dump(output_data, f)
        
    # Xóa file temp đi cho sạch sẽ
    if os.path.exists(inv_file): 
        os.remove(inv_file)