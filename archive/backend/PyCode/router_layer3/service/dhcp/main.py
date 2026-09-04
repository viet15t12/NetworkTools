import os
import sys
import json
import sqlite3
import argparse
import jinja2

# Setup radar đường dẫn
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "..", ".."))

if BACKEND_DIR not in sys.path: sys.path.append(BACKEND_DIR)
if CURRENT_DIR not in sys.path: sys.path.append(CURRENT_DIR)

from PyCode.share.config import DB_PATH, DHCP_OUTPUT, TMP_DIR, DB_TABLES

try:
    from worker_dhcp import run_dhcp_config
except ImportError as e:
    print(f"[-] Lỗi Import Worker: {e}")
    sys.exit(1)

# =========================================================
# HÀM GIẢI MÃ ACTION_CFG TỪ FRONTEND
# =========================================================
def has_text_bit(action_cfg: str, bit_index_from_right: int) -> bool:
    if not action_cfg: return True 
    pos = len(action_cfg) - 1 - bit_index_from_right
    if pos < 0 or pos >= len(action_cfg): return False
    return action_cfg[pos] == '1'

def success_state(val):
    if val in (0, '0', None): return "setup"
    if val in (-1, '-1'): return "remove"
    return "ignore"

def main():
    parser = argparse.ArgumentParser(description="DHCP Automation Controller")
    parser.add_argument("-t", "--target", type=str, default="all")
    args = parser.parse_args()
    
    target_ip = args.target
    T_DHCP_POOL = DB_TABLES["dhcp"]["pools"]
    T_DHCP_EXC = DB_TABLES["dhcp"]["excluded"]
    T_HELPER = DB_TABLES["dhcp"]["helper"]
    T_IFACE = DB_TABLES["interfaces"]["main"]
    valid_data = []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query_hosts = f"""
            SELECT host FROM {T_DHCP_POOL} WHERE success <= 0 OR success IS NULL
            UNION SELECT host FROM {T_DHCP_EXC} WHERE success <= 0 OR success IS NULL
            UNION SELECT i.host FROM {T_HELPER} h JOIN {T_IFACE} i ON h.iface_id = i.iface_id WHERE h.success <= 0 OR h.success IS NULL
        """
        if target_ip != "all":
            query_hosts = f"SELECT host FROM ({query_hosts}) WHERE host = ?"
            cursor.execute(query_hosts, (target_ip,))
        else:
            cursor.execute(query_hosts)
            
        hosts = [row[0] for row in cursor.fetchall()]
        
        for host in hosts:
            config_data = {"pools": [], "excluded_addresses": [], "relays": []}
            ids = {
        "pool_add": [], "pool_del": [], 
        "exc_add": [], "exc_del": [], 
        "helper_add": [], "helper_del": []  
    }
            
            # 1. Bốc Excluded
            cursor.execute(f"SELECT ex_id, start_ip, end_ip, success FROM {T_DHCP_EXC} WHERE host = ? AND (success <= 0 OR success IS NULL)", (host,))
            for ex_id, s_ip, e_ip, succ in cursor.fetchall():
                state = success_state(succ)
                config_data["excluded_addresses"].append({"start_ip": s_ip, "end_ip": e_ip, "state": state})
                if state == "remove": ids["exc_del"].append(ex_id)
                else: ids["exc_add"].append(ex_id)
                
            # 2. Bốc Pools
            
            cursor.execute(f"SELECT dhcp_id, pool, network, subnetmask, defaut, dns, lease, success, action_Cfg FROM {T_DHCP_POOL} WHERE host = ? AND (success <= 0 OR success IS NULL)", (host,))
            for p_id, p_name, net, mask, gw, dns, lease, succ, act_cfg in cursor.fetchall():
                    state = success_state(succ)
                    
                    config_data["pools"].append({
                        "name": p_name, 
                        "network": net, 
                        "subnet_mask": mask, 
                        "default_gateway": gw, 
                        "dns_server": dns, 
                        "lease": lease,
                        "push_default": has_text_bit(act_cfg, 2), 
                        "push_dns": has_text_bit(act_cfg, 1),         
                        "push_lease": has_text_bit(act_cfg, 0),     
                        "state": state
                    })
                    if state == "remove": ids["pool_del"].append(p_id)
                    else: ids["pool_add"].append(p_id)
            # 3. Bốc Helper
            cursor.execute(f"""
                SELECT h.id, h.helper_ip, i.interface_name, h.success 
                FROM {T_HELPER} h JOIN {T_IFACE} i ON h.iface_id = i.iface_id 
                WHERE i.host = ? AND (h.success <= 0 OR h.success IS NULL)
            """, (host,))
            for h_id, h_ip, iface, succ in cursor.fetchall():
                state = success_state(succ)
                config_data["relays"].append({"interface": iface, "helper_address": h_ip, "state": state})
                if state == "remove": ids["helper_del"].append(h_id)
                else: ids["helper_add"].append(h_id)

         
                
            if any(ids.values()):
                valid_data.append({"target": {"ip": host}, "action": "setup", "ids": ids, "config": [config_data]})
                
# ==============================================================
                #  IN LỆNH SẼ ĐƯỢC CHẠY TRÊN ROUTER
                # ==============================================================
                # Sửa lại đường dẫn chọc thẳng vào thư mục templates/router
                template_file = os.path.join(CURRENT_DIR, "templates", "router", "dhcp_config.j2")
                
                if os.path.exists(template_file):
                    print(f"\n[+] ĐANG CHUẨN BỊ LỆNH XUỐNG: {host}")
                    print("-" * 50)
                    with open(template_file, "r", encoding="utf-8") as tf:
                        template = jinja2.Template(tf.read())
                        rendered_cmds = template.render(config=config_data)
                        # In các dòng không bị rỗng
                        for line in rendered_cmds.split('\n'):
                            if line.strip(): print("  " + line)
                    print("-" * 50)
                else:
                    # Báo lỗi to chà bá nếu vẫn tìm không ra file
                    print(f"\n[-] ỐNG NHÒM BỊ LỖI: Không tìm thấy file template tại đường dẫn:\n  {template_file}")
                
        if not valid_data: return
        
        print(f"\n[INFO] Đang đẩy {len(valid_data)} gói cấu hình DHCP sang Worker...")
        run_dhcp_config(valid_data, DB_PATH, DHCP_OUTPUT)
        
        # --- Cập nhật DB sau khi Worker chạy xong ---
        if os.path.exists(DHCP_OUTPUT):
            with open(DHCP_OUTPUT, 'r', encoding='utf-8') as f:
                results = json.load(f)
            for res in results:
                if res.get("status") == "success":
                    res_ip = res.get("target") or res.get("ip") or res.get("host")
                    
                    for item in valid_data:
                        # KIỂM TRA ĐIỀU KIỆN ĐỂ CẬP NHẬT DB (Đảm bảo Success nhảy lên 1)
                        if item["target"]["ip"] == res_ip:
                            d = item["ids"]
                            
                            # Đã thêm lệnh In ra để sếp check Log DB
                            print(f"[*] Đang ghi nhận DB cho {res_ip}: {len(d['pool_add'])} Thêm, {len(d['pool_del'])} Xóa")
                            for pid in d["pool_add"]: cursor.execute(f"UPDATE {T_DHCP_POOL} SET success = 1 WHERE dhcp_id = ?", (pid,))
                            for pid in d["pool_del"]: cursor.execute(f"DELETE FROM {T_DHCP_POOL} WHERE dhcp_id = ?", (pid,))
                            for eid in d["exc_add"]: cursor.execute(f"UPDATE {T_DHCP_EXC} SET success = 1 WHERE ex_id = ?", (eid,))
                            for eid in d["exc_del"]: cursor.execute(f"DELETE FROM {T_DHCP_EXC} WHERE ex_id = ?", (eid,))
                            for hid in d["helper_add"]: cursor.execute(f"UPDATE {T_HELPER} SET success = 1 WHERE id = ?", (hid,))
                            for hid in d["helper_del"]: cursor.execute(f"DELETE FROM {T_HELPER} WHERE id = ?", (hid,))
                            
                            
            conn.commit()
            print("[*] Đồng bộ DB DHCP thành công!")
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == "__main__": main()