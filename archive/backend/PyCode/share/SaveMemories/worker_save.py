import os
import json
import yaml
import sqlite3
import requests
import urllib3
from ncclient import manager
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_save_config
from nornir.core.task import Result

# Tắt cảnh báo SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 1. BUILD INVENTORY TỪ DATABASE
# ==========================================
def build_save_inventory(db_path, task_list):
    task_map = {item.get("target", {}).get("ip"): item for item in task_list if item.get("target", {}).get("ip")}
    hosts_yaml = {}
    
    if not task_map: return None

    try:
        conn_db = sqlite3.connect(db_path)
        cursor = conn_db.cursor()
        
        for ip, payload in task_map.items():
            cursor.execute('SELECT device_name, username, password, os, portnumber, method FROM devices WHERE host = ?', (ip,))
            row = cursor.fetchone()
            
            if row:
                dev_name, db_user, db_pass, db_os, db_port, db_method = row
                platform = "cisco_ios" if db_os == "cisco" else db_os
                host_key = dev_name if dev_name else ip
                
                hosts_yaml[host_key] = {
                    "hostname": ip, "username": db_user, "password": db_pass,
                    "port": db_port if db_port else 22, "platform": platform,
                    "data": {"method": db_method}
                }
    except Exception as e: print(f"[-] Lỗi DB: {e}")
    finally:
        if 'conn_db' in locals(): conn_db.close()
        
    inv_file_path = os.path.join(CURRENT_DIR, "tmp_save_inventory.yaml")
    with open(inv_file_path, 'w', encoding='utf-8') as f: yaml.dump(hosts_yaml, f)
    return inv_file_path

# ==========================================
# 2. XỬ LÝ LƯU CẤU HÌNH QUA API (REST & NET)
# ==========================================
def handle_api_save(task, method):
    host_ip = task.host.hostname
    user = task.host.username
    pw = task.host.password
    port = task.host.port

    try:
       # --- NHÁNH NETCONF ---
        if method == "NETCONF":
            with manager.connect(
                host=host_ip, port=port or 830, username=user, password=pw,
                hostkey_verify=False, device_params={'name': 'default'}, timeout=15
            ) as m:
                res = m.copy_config(source='running', target='startup')
                if res.ok:
                    return "Đã lưu cấu hình qua NETCONF thành công (HTTP 200)"
                else:
                    raise Exception(f"Thiết bị từ chối lưu qua NETCONF: {res.error}")

        # --- NHÁNH RESTCONF ---
        elif method == "RESTCONF":
            headers = {"Accept": "application/yang-data+json", "Content-Type": "application/yang-data+json"}
            # API chuẩn của Cisco IOS-XE để Write Memory
            save_url = f"https://{host_ip}:{port or 443}/restconf/operations/cisco-ia:save-config"
            
            res = requests.post(save_url, auth=(user, pw), headers=headers, json={}, verify=False, timeout=15)
            if res.status_code in [200, 204]:
                return f"Đã lưu cấu hình qua RESTCONF: HTTP {res.status_code}"
            else:
                raise Exception(f"Lỗi RESTCONF HTTP {res.status_code}: {res.text}")

    except Exception as e:
        raise Exception(f"Lỗi API Save ({method}): {str(e)}")

# ==========================================
# 3. NORNIR TASK: ĐIỀU PHỐI ĐA GIAO THỨC
# ==========================================
def task_save_memory(task):
    method = task.host.data.get("method", "SSH")
    
    if method in ["NETCONF", "RESTCONF"]:
        msg = handle_api_save(task, method)
        return Result(host=task.host, result=msg)
    else:
        # --- NHÁNH SSH ---
        # Thư viện Nornir đã có sẵn hàm cực xịn này để tự động gõ "write memory" hoặc "copy run start"
        save_res = task.run(task=netmiko_save_config, name="Save Configuration")
        return save_res[0].result

# ==========================================
# 4. HÀM CHẠY CHÍNH VÀ XUẤT OUTPUT
# ==========================================
def run_save_config(task_list, db_path, output_path):
    print("\n[INFO] Khởi động Nornir Save Memory Worker...")
    inv_file_path = build_save_inventory(db_path, task_list)
    if not inv_file_path: return
    
    nr = InitNornir(runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
                    inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file_path}}, 
                    logging={"enabled": False})
    
    print(f"[*] Đang thực thi lệnh 'Write Memory' trên {len(nr.inventory.hosts)} thiết bị...")
    results = nr.run(task=task_save_memory)
    
    output_data = []
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        message = str(task_res.exception) if task_res.failed else str(task_res[0].result if type(task_res) is not Result else task_res.result)
        
        if status == "success":
            print(f"[+] Thành công: {host} -> {message}")
        else:
            print(f"[-] Thất bại: {host} -> {message}")
            
        output_data.append({
            "target": nr.inventory.hosts[host].hostname,
            "task": "SAVE_MEMORY",
            "status": status,
            "log": message
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    print(f"\n[*] Đã xuất kết quả Save Memory tại: {output_path}")
    if os.path.exists(inv_file_path): os.remove(inv_file_path)