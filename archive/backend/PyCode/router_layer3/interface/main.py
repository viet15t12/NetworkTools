import os
import json
import sys
import sqlite3
import argparse
from collections import defaultdict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../../"))
if PROJECT_ROOT not in sys.path: sys.path.append(PROJECT_ROOT)
if CURRENT_DIR not in sys.path: sys.path.append(CURRENT_DIR)

# GỌI TRẠM KIỂM SOÁT
from PyCode.share.config import DB_PATH, INTERFACE_OUTPUT, DB_TABLES

try:
    from router_interface import run_interface_config
except ImportError as e:
    print(f"[-] Lỗi Import: Không tìm thấy file 'router_interface.py'!\n    Chi tiết: {e}")
    sys.exit(1)

def interface_dispatcher(target_ip="all"):
    print(f"\n[*] [Interface Master] Target: {target_ip} | DB: {os.path.basename(DB_PATH)}")

    if not os.path.exists(DB_PATH):
        print(f"[-] LỖI: Không tìm thấy file Database '{DB_PATH}'!")
        return

    # Lôi tên bảng Interface từ Trạm kiểm soát
    T_INTERFACE = DB_TABLES["interfaces"]["main"]
    valid_data = []

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Quét Database tìm cổng cần config
        query = f"SELECT iface_id, host, interface_name, ip_address, subnet_mask, description, shutdown, success FROM {T_INTERFACE} WHERE success = 0 OR success IS NULL OR success = -1"
        params = []
        if target_ip != "all":
            query += " AND host = ?"
            params.append(target_ip)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        if not rows:
            print("[INFO] Không có cấu hình Interface nào cần cập nhật.")
            return

        hosts_data = defaultdict(lambda: {"configs": [], "ids_success": [], "ids_delete": []})
        
        for row in rows:
            iface_id, host, intf_name, ip, mask, desc, shut, success = row
            cfg = {"name": intf_name, "shutdown": shut}
            
            if success == -1:
                cfg["ip_address"] = "remove"
                cfg["description"] = "remove"
                cfg["shutdown"] = 1
                hosts_data[host]["ids_delete"].append(iface_id)
            else:
                if ip and mask:
                    cfg["ip_address"] = ip
                    cfg["subnet_mask"] = mask
                if desc:
                    cfg["description"] = desc
                hosts_data[host]["ids_success"].append(iface_id)

            hosts_data[host]["configs"].append(cfg)

        for host, data in hosts_data.items():
            valid_data.append({
                "target": {"ip": host},
                "action": "setup",
                "tracking_ids": {"ids_success": data["ids_success"], "ids_delete": data["ids_delete"]},
                "config": data["configs"]
            })

    except Exception as e:
        print(f"[-] Lỗi Database: {e}")
        return
    finally:
        if 'conn' in locals(): conn.close()

    # Chuyển Data sang Worker
    run_interface_config(valid_data, INTERFACE_OUTPUT)

    # Cập nhật kết quả vào DB
    if os.path.exists(INTERFACE_OUTPUT):
        with open(INTERFACE_OUTPUT, 'r', encoding='utf-8') as f:
            results = json.load(f)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        success_count = 0

        for res in results:
            if res.get("status") == "success":
                ip = res.get("target")
                for item in valid_data:
                    if item["target"]["ip"] == ip:
                        for s_id in item["tracking_ids"]["ids_success"]:
                            cursor.execute(f"UPDATE {T_INTERFACE} SET success = 1 WHERE iface_id = ?", (s_id,))
                        for d_id in item["tracking_ids"]["ids_delete"]:
                            cursor.execute(f"DELETE FROM {T_INTERFACE} WHERE iface_id = ?", (d_id,))
                success_count += 1

        conn.commit()
        conn.close()
        print(f"\n[*] Đã đồng bộ Database Interface thành công cho {success_count} thiết bị.")

# --- ĐOẠN DÀNH CHO LỆNH TERMINAL ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interface Master Controller")
    parser.add_argument("-t", "--target", type=str, default="all", help="IP của Router")
    args = parser.parse_args()
    
    interface_dispatcher(target_ip=args.target)

if __name__ == "__main__":
    interface_dispatcher()