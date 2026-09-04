import os
import json
import yaml
import sys
import sqlite3
import urllib3
from jinja2 import Environment, FileSystemLoader

# --- SETUP NORNIR & NETMIKO ---
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config
from nornir.core.task import Result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# GỌI CÁC THAM SỐ TỪ TRẠM KIỂM SOÁT
from PyCode.share.config import TMP_DIR, DB_TABLES

# [NOTE] Cấu hình đường dẫn thư mục chứa template riêng cho cụm NAT
NAT_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

def render_nat_template(platform, template_name, config_data):
    """ Hàm render Jinja2 ra file text chứa lệnh cấu hình """
    template_dir = os.path.join(NAT_TEMPLATE_DIR, platform)
    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        return env.get_template(f"{template_name}.j2").render(config=config_data)
    except Exception as e:
        raise Exception(f"JINJA2 ERROR ({template_name}): {str(e)}")

def task_push_nat(task):
    """ Task của Nornir: Render lệnh và đẩy qua Netmiko """
    payload = task.host.data["ui_payload"]
    host_config = payload.get("config", {})
    all_commands = []

    # [NOTE] 1. Render NAT ACL trước (Bắt buộc ACL phải có trước thì pool/interface mới xài được)
    for acl in host_config.get("nat_acl", []):
        cmds = render_nat_template(task.host.data["template_folder"], "nat_acl", acl)
        if cmds: all_commands.extend([l.strip() for l in cmds.splitlines() if l.strip()])

    # [NOTE] 2. Render NAT Engine sau (Interfaces, Pools, Mappings, PAT)
    for nat in host_config.get("nat", []):
        cmds = render_nat_template(task.host.data["template_folder"], "nat", nat)
        if cmds: all_commands.extend([l.strip() for l in cmds.splitlines() if l.strip()])

    if not all_commands: return "No NAT commands to push."

    # [NOTE] Sandwich log: Tắt log lúc bắt đầu đẩy và bật lại lúc kết thúc để CLI không bị nhiễu
    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")
    all_commands.append("logging console")
    all_commands.append("logging monitor")

    # [NOTE] In danh sách lệnh nháp (Dự kiến) xuống dòng rõ ràng để dễ kiểm tra chéo
    print(f"\n[+] ĐANG ĐẨY {len(all_commands)} LỆNH NAT XUỐNG: {task.host.hostname}")
    print("--------------------------------------------------")
    for cmd in all_commands:
        print(f"  {cmd}")
    print("--------------------------------------------------")

    # Đẩy lệnh thực tế xuống Router
    res = task.run(
        task=netmiko_send_config, 
        config_commands=all_commands,
        read_timeout=120,
        delay_factor=1.5  # [FIX TỐI ƯU 1] Giảm từ 2 xuống 1.5 để Router không bị bắt chờ quá lâu giữa các lệnh
    )
    return res[0].result

def build_nat_inventory(db_path, task_list):
    """ Hàm tạo file inventory (danh sách thiết bị) động cho Nornir """
    T_DEVICES = DB_TABLES["device_info"]["main"]
    hosts_yaml = {}
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for task in task_list:
        ip = task["target"]["ip"]
        cursor.execute(f'SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host = ?', (ip,))
        row = cursor.fetchone()
        if row:
            name, user, pw, os_type, port, method = row
            platform = "cisco_ios" if os_type == "cisco" else os_type
            hosts_yaml[name or ip] = {
                "hostname": ip, 
                "username": user, 
                "password": pw,
                "port": int(port) if port else (23 if method == "TELNET" else 22), 
                "platform": platform,
                "connection_options": {
                    "netmiko": {
                        "extras": {
                            "banner_timeout": 30,
                            "auth_timeout": 30,
                            "session_timeout": 60,
                            "global_delay_factor": 1  # [FIX TỐI ƯU 2] Trả về 1 để Netmiko gõ lệnh nhanh hơn
                        }
                    }
                },
                "data": {"template_folder": "cisco_ios", "ui_payload": task}
            }
    conn.close()
    
    inv_path = os.path.join(TMP_DIR, "tmp_nat_inventory.yaml")
    with open(inv_path, 'w', encoding='utf-8') as f: yaml.dump(hosts_yaml, f)
    return inv_path

def run_nat_config(input_data, db_path, output_path):
    """ Hàm Runner khởi tạo Nornir và xử lý kết quả """
    inv_path = build_nat_inventory(db_path, input_data)
    nr = InitNornir(
        # [FIX TỐI ƯU 3] Hạ số worker xuống 3 để tránh vắt kiệt RAM gây hiện tượng Swapping/treo máy
        runner={"plugin": "threaded", "options": {"num_workers": 3}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_path}}, 
        logging={"enabled": False}
    )
    results = nr.run(task=task_push_nat)
    
    output = []
    for host, res in results.items():
        status = "failed" if res.failed else "success"
        message = str(res.exception) if res.failed else str(res[0].result)
        output.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": message})
        
        # [NOTE - FIX] In kết quả thực thi (CLI Output) trực tiếp trả về từ Router
        print(f"\n[{'+' if status == 'success' else '-'}] {host}:\n{message}")
    
    # Xuất log ra file JSON cho hệ thống Web Frontend đọc
    with open(output_path, 'w', encoding='utf-8') as f: json.dump(output, f, indent=4)
    if os.path.exists(inv_path): os.remove(inv_path)