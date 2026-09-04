import os
import sqlite3
import yaml
from nornir import InitNornir

from backend.PyCode.info.collector_info import task_pull_running_config, get_routing_section
from backend.PyCode.info.modules.worker_info_routing import process_routing_data
from backend.PyCode.info.modules.worker_info_dhcp import process_dhcp_data
from backend.PyCode.info.modules.worker_info_acl import process_acl_data
# ĐÃ BỔ SUNG: Import Worker NAT
from backend.PyCode.info.modules.worker_info_nat import process_nat_data

# Đồng bộ đường dẫn từ trạm kiểm soát (config.py)
from backend.PyCode.share.config import TMP_DIR, DB_DEVICE_NETWORK, PROJECT_ROOT, STATE_DIR

# =====================================================================
# HÀM PHỤ TRỢ: TẠO INVENTORY ĐỘNG CHO NORNIR (Giống file worker_routing.py)
# =====================================================================
def build_info_inventory(target="all"):
    """Truy xuất device_network.db và sinh file YAML tạm cho Nornir"""
    hosts_yaml = {}
    
    try:
        conn = sqlite3.connect(DB_DEVICE_NETWORK)
        cursor = conn.cursor()
        
        if target.lower() == "all":
            cursor.execute("SELECT host, device_name, username, password, portnumber, os, method FROM t01_devices")
        else:
            cursor.execute("SELECT host, device_name, username, password, portnumber, os, method FROM t01_devices WHERE host = ?", (target,))
            
        for row in cursor.fetchall():
            ip, dev_name, db_user, db_pass, db_port, db_os, db_method = row
            
            platform = "cisco_ios" if db_os == "cisco" else (db_os or "cisco_ios")
            port = int(db_port) if db_port else (23 if db_method == "TELNET" else 22)
            
            hosts_yaml[dev_name or ip] = {
                "hostname": ip, 
                "username": db_user, 
                "password": db_pass,
                "port": port, 
                "platform": platform,
                "connection_options": {
                    "netmiko": {
                        "extras": {
                            "global_delay_factor": 2 
                        }
                    }
                }
            }
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi build inventory cho Info Module: {e}")
        
    os.makedirs(TMP_DIR, exist_ok=True)
    inv_file_path = os.path.join(TMP_DIR, "tmp_info_inventory.yaml")
    
    with open(inv_file_path, 'w', encoding='utf-8') as f: 
        yaml.dump(hosts_yaml, f)
        
    return inv_file_path

# =====================================================================
# [CÒ 1] - BỘ ĐIỀU PHỐI KÉO DỮ LIỆU
# =====================================================================
def info_collect_dispatcher(target="all"):
    print(f"\n[CÒ 1 - COLLECT] Bắt đầu kết nối kéo file. Target: {target}")
    
    inv_file_path = build_info_inventory(target)
    
    if not os.path.exists(inv_file_path):
        print("[-] Không tạo được Inventory. Hủy quá trình thu thập.")
        return
    
    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file_path}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_pull_running_config)
    
    for host, task_res in results.items():
        if task_res.failed:
            print(f"[-] {host} LỖI KÉO FILE: {task_res.exception}")
        else:
            print(f"[+] {host}: {task_res[0].result}")
            
    if os.path.exists(inv_file_path):
        os.remove(inv_file_path)

# =====================================================================
# [CÒ 2] - BỘ ĐIỀU PHỐI ĐỌC FILE VÀ CẬP NHẬT DATABASE
# =====================================================================
def info_sync_dispatcher(target="all"):
    print(f"\n[CÒ 2 - SYNC DB] Bắt đầu điều phối luồng băm dữ liệu. Target: {target}")
    
    inv_file_path = build_info_inventory(target)
    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file_path}}, 
        logging={"enabled": False}
    )
    
    INFO_DB_PATH = os.path.join(PROJECT_ROOT, "backend", "PyCode", "share", "database", "info_collected.db")
    
    try:
        conn = sqlite3.connect(INFO_DB_PATH)
        cursor = conn.cursor()
        
        for host in nr.inventory.hosts.keys():
            file_path = os.path.join(STATE_DIR, f"{host}_running.txt")
            if not os.path.exists(file_path):
                print(f"[-] BỎ QUA {host}: Không tìm thấy file {file_path}")
                continue
                
            print(f"\n[*] [MAIN] Đang điều phối công việc cho {host}...")
            
            # --- BƯỚC 1: GỌI WORKER ROUTING ---
            print(f"   -> [MAIN] Gọi Worker Routing...")
            process_routing_data(
                host=host, 
                file_path=file_path, 
                db_cursor=cursor, 
                target_table="t08_info_routing_table"
            )
            # --- BƯỚC 2: GỌI WORKER DHCP ---
            print(f"   -> [MAIN] Gọi Worker DHCP...")
            process_dhcp_data(
                host=host,
                file_path=file_path,
                db_cursor=cursor
            )
            # --- BƯỚC 3: GỌI WORKER ACL ---
            print(f"   -> [MAIN] Gọi Worker ACL...")
            process_acl_data(
                host=host,
                file_path=file_path,
                db_cursor=cursor
            )
            # --- BƯỚC 4: GỌI WORKER NAT (MỚI THÊM) ---
            print(f"   -> [MAIN] Gọi Worker NAT...")
            process_nat_data(
                host=host,
                file_path=file_path,
                db_cursor=cursor
            )
            
        conn.commit() 
        print(f"\n[+] HOÀN TẤT: Toàn bộ Worker đã hoàn thành, DB đã được cập nhật an toàn!")
        
    except Exception as e:
        print(f"[-] LỖI ĐIỀU PHỐI NGHIÊM TRỌNG: {e}")
        if 'conn' in locals(): conn.rollback()
    finally:
        if 'conn' in locals(): conn.close()
        if os.path.exists(inv_file_path): os.remove(inv_file_path)