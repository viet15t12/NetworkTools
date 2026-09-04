import json
import os
import sys
import sqlite3
import argparse
import jinja2

# Setup radar đường dẫn
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../../.."))
if PROJECT_ROOT not in sys.path: sys.path.append(PROJECT_ROOT)
if CURRENT_DIR not in sys.path: sys.path.append(CURRENT_DIR)

from PyCode.share.config import DB_PATH, ROUTE_OUTPUT, TMP_DIR, DB_TABLES

try:
    from worker_nat import run_nat_config
except ImportError as e:
    print(f"[-] Lỗi Import Worker: Không tìm thấy file 'worker_nat.py'!\n    Chi tiết: {e}")
    sys.exit(1)

# =========================================================
# HÀM GIẢI MÃ ACTION_CFG (KIỂU SỐ NGUYÊN)
# =========================================================
def has_int_bit(action_cfg, bit: int) -> bool:
    """Giải mã số nguyên Bitmask (Dùng cho ACL, NAT). VD: action=1, bit 0 -> True"""
    if action_cfg is None: return True # Mặc định bật theo schema
    try:
        return bool(int(action_cfg) & (1 << bit))
    except (ValueError, TypeError):
        return False

def nat_dispatcher(target_ip="all"):
    """
    Hàm điều phối cấu hình NAT được gọi từ API Server.
    """
    # Đã bỏ phần argparse đi vì API sẽ truyền target_ip thẳng vào hàm
    
    if not os.path.exists(DB_PATH):
        print(f"[-] LỖI: Không tìm thấy file Database tại: {DB_PATH}")
        return

    valid_data = []

    T_NAT_ACL_MAIN = DB_TABLES["nat_acl"]["main"]
    T_NAT_ACL_STD = DB_TABLES["nat_acl"]["standard"]
    T_NAT_ACL_EXT = DB_TABLES["nat_acl"]["extended"]
    T_NAT_MAIN = DB_TABLES["nat"]["main"]
    T_NAT_INTF = DB_TABLES["nat"]["interfaces"]
    T_NAT_POOL = DB_TABLES["nat"]["pools"]
    T_NAT_STATIC = DB_TABLES["nat"]["static_mappings"]
    T_NAT_DYNAMIC = DB_TABLES["nat"]["dynamic_rules"]
    T_NAT_OVERLOAD = DB_TABLES["nat"]["overload_rules"]
    T_NAT_EXEMPT = DB_TABLES["nat"]["exempt_rules"]
    T_ROUTE_MAP_MAIN = DB_TABLES["route_map"]["main"]
    T_ROUTE_MAP_ENTRIES = DB_TABLES["route_map"]["entries"]
    
    CHILD_NAT_TABLES = [T_NAT_INTF, T_NAT_POOL, T_NAT_STATIC, T_NAT_DYNAMIC, T_NAT_OVERLOAD, T_NAT_EXEMPT]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        target_hosts = []
        if target_ip == "all":
            cursor.execute(f"SELECT DISTINCT host FROM {T_NAT_MAIN} UNION SELECT host FROM {T_NAT_ACL_MAIN}")
            target_hosts = [r[0] for r in cursor.fetchall()]
        else:
            target_hosts = [target_ip]

        for host in target_hosts:
            host_config = {"target": {"ip": host}, "nat_acl": [], "nat": []}
            pending_acl_ids_add, pending_acl_ids_del = [], []
            pending_nat_ids_add, pending_nat_ids_del = [], []
            pending_rm_ids_add, pending_rm_ids_del = [], []
            
            # --- PHẦN 1: THU THẬP NAT ACL ---
            try:
                cursor.execute(f"SELECT nat_acl_id, acl_name, acl_type, description, success, action_cfg FROM {T_NAT_ACL_MAIN} WHERE host = ? AND (success <= 0 OR success IS NULL)", (host,))
                for acl_id, acl_name, acl_type, desc, success, act_cfg in cursor.fetchall():
                    state = "remove" if success == -1 else "setup"
                    push_desc = has_int_bit(act_cfg, 0) # Dịch bit 0 cho remark
                    
                    acl_item = {"acl_id": acl_id, "acl_name": acl_name, "acl_type": acl_type, "description": desc, "push_desc": push_desc, "state": state, "rules": []}
                    
                    # Bốc rules Standard
                    cursor.execute(f"SELECT id, sequence, action, source, wildcard, success FROM {T_NAT_ACL_STD} WHERE nat_acl_id = ?", (acl_id,))
                    for rid, seq, act, src, wild, r_success in cursor.fetchall():
                        # BÍ KÍP NẰM Ở ĐÂY: Nếu đã chạy rồi (1) thì ignore, chưa chạy (0) thì setup
                        if r_success in (-1, '-1') or state == "remove": r_state = "remove"
                        elif r_success in (0, '0', None): r_state = "setup"
                        else: r_state = "ignore" 
                        
                        acl_item["rules"].append({"id": rid, "sequence": seq, "action": act, "source": src, "wildcard": wild, "state": r_state, "type": "std"})
                    
                    # Bốc rules Extended
                    cursor.execute(f"SELECT id, sequence, action, protocol, source, src_wildcard, src_port, destination, dst_wildcard, dst_port, success FROM {T_NAT_ACL_EXT} WHERE nat_acl_id = ?", (acl_id,))
                    for rid, seq, act, proto, src, src_w, src_p, dst, dst_w, dst_p, r_success in cursor.fetchall():
                        # BÍ KÍP NẰM Ở ĐÂY
                        if r_success in (-1, '-1') or state == "remove": r_state = "remove"
                        elif r_success in (0, '0', None): r_state = "setup"
                        else: r_state = "ignore"
                        
                        acl_item["rules"].append({
                            "id": rid, "sequence": seq, "action": act, "protocol": proto, "source": src, "src_wildcard": src_w, 
                            "src_port": src_p, "destination": dst, "dst_wildcard": dst_w, "dst_port": dst_p, "state": r_state, "type": "ext"
                        })
                    
                    host_config["nat_acl"].append(acl_item)
                    if success == -1: pending_acl_ids_del.append(acl_id)
                    else: pending_acl_ids_add.append(acl_id)
            except sqlite3.OperationalError as e:
                print(f"[-] Lỗi truy vấn bảng NAT_ACL_DB (kiểm tra cột action_cfg): {e}")

            # --- PHẦN 2: THU THẬP NAT ENGINE ---
            try:
                cursor.execute(f"SELECT nat_id, nat_name, nat_type, description, success, action_cfg FROM {T_NAT_MAIN} WHERE host = ? AND (success <= 0 OR success IS NULL)", (host,))
                for n_id, n_name, n_type, n_desc, n_success, act_cfg in cursor.fetchall():
                    
                    parent_state = "remove" if n_success == -1 else "setup"
                    push_desc = has_int_bit(act_cfg, 0)
                    
                    nat_item = {"nat_id": n_id, "nat_name": n_name, "nat_type": n_type, "description": n_desc, "push_desc": push_desc, "state": parent_state, 
                                "interfaces": [], "pools": [], "static_mappings": [], "dynamic_rules": [], "overload_rules": [], "exempt_rules": [], "route_map_nat_rules": []}
                    
                    # Interfaces
                    cursor.execute(f"SELECT id, interface_name, nat_role, success FROM {T_NAT_INTF} WHERE nat_id = ?", (n_id,))
                    for iid, iname, irole, isuccess in cursor.fetchall():
                        # Logic 3 trạng thái: Xóa dây chuyền -> Setup -> Ignore
                        if parent_state == "remove" or isuccess in (-1, '-1'): istate = "remove"
                        elif isuccess in (0, '0', None): istate = "setup"
                        else: istate = "ignore"
                        nat_item["interfaces"].append({"id": iid, "interface_name": iname, "nat_role": irole, "state": istate})

                    # Pools
                    cursor.execute(f"SELECT pool_id, pool_name, start_ip, end_ip, netmask, prefix_length, success FROM {T_NAT_POOL} WHERE nat_id = ?", (n_id,))
                    for pid, pname, start, end, mask, prefix, psuccess in cursor.fetchall():
                        if parent_state == "remove" or psuccess in (-1, '-1'): pstate = "remove"
                        elif psuccess in (0, '0', None): pstate = "setup"
                        else: pstate = "ignore"
                        nat_item["pools"].append({"pool_id": pid, "pool_name": pname, "start_ip": start, "end_ip": end, "netmask": mask, "prefix_length": prefix, "state": pstate})

                    # Static Mappings
                    cursor.execute(f"SELECT id, inside_local_ip, inside_global_ip, protocol, local_port, global_port, is_extendable, success FROM {T_NAT_STATIC} WHERE nat_id = ?", (n_id,))
                    for sid, l_ip, g_ip, proto, l_port, g_port, ext, ssuccess in cursor.fetchall():
                        if parent_state == "remove" or ssuccess in (-1, '-1'): sstate = "remove"
                        elif ssuccess in (0, '0', None): sstate = "setup"
                        else: sstate = "ignore"
                        nat_item["static_mappings"].append({
                            "id": sid, "inside_local_ip": l_ip, "inside_global_ip": g_ip, "protocol": proto, 
                            "local_port": l_port, "global_port": g_port, "is_extendable": ext, "state": sstate
                        })

                    # Dynamic Rules
                    cursor.execute(f"""
                        SELECT dr.id, acl.acl_name, p.pool_name, dr.overload, dr.success 
                        FROM {T_NAT_DYNAMIC} dr
                        JOIN {T_NAT_ACL_MAIN} acl ON dr.nat_acl_id = acl.nat_acl_id
                        JOIN {T_NAT_POOL} p ON dr.pool_id = p.pool_id
                        WHERE dr.nat_id = ?
                    """, (n_id,))
                    for did, acl_n, pool_n, ovl, dsuccess in cursor.fetchall():
                        if parent_state == "remove" or dsuccess in (-1, '-1'): dstate = "remove"
                        elif dsuccess in (0, '0', None): dstate = "setup"
                        else: dstate = "ignore"
                        nat_item["dynamic_rules"].append({"id": did, "acl_name": acl_n, "pool_name": pool_n, "overload": ovl, "state": dstate})

                    # Overload Rules
                    cursor.execute(f"""
                        SELECT ov.id, acl.acl_name, ov.outside_interface, ov.overload, ov.success 
                        FROM {T_NAT_OVERLOAD} ov
                        JOIN {T_NAT_ACL_MAIN} acl ON ov.nat_acl_id = acl.nat_acl_id
                        WHERE ov.nat_id = ?
                    """, (n_id,))
                    for oid, acl_n, out_intf, ovl, osuccess in cursor.fetchall():
                        if parent_state == "remove" or osuccess in (-1, '-1'): ostate = "remove"
                        elif osuccess in (0, '0', None): ostate = "setup"
                        else: ostate = "ignore"
                        nat_item["overload_rules"].append({"id": oid, "acl_name": acl_n, "outside_interface": out_intf, "overload": ovl, "state": ostate})

                    # Route-Map Exempts
                    cursor.execute(f"""
                        SELECT rm.route_map_id, rm.route_map_name, rme.sequence, rme.action, acl.acl_name, ex.success, rm.success 
                        FROM {T_NAT_EXEMPT} ex 
                        JOIN {T_ROUTE_MAP_MAIN} rm ON ex.route_map_id = rm.route_map_id
                        JOIN {T_ROUTE_MAP_ENTRIES} rme ON rm.route_map_id = rme.route_map_id
                        LEFT JOIN {T_NAT_ACL_MAIN} acl ON rme.nat_acl_id = acl.nat_acl_id
                        WHERE ex.nat_id = ?
                        ORDER BY rme.sequence
                    """, (n_id,))
                    
                    for rm_id, rm_n, seq, act, acl_n, esuccess, rm_success in cursor.fetchall():
                        # Xử lý ID cho Route-Map tracking
                        if rm_success == -1 or esuccess == -1 or parent_state == "remove":
                            if rm_id not in pending_rm_ids_del: pending_rm_ids_del.append(rm_id)
                        else:
                            if rm_id not in pending_rm_ids_add: pending_rm_ids_add.append(rm_id)
                            
                        # Logic 3 trạng thái cho Exempt
                        if parent_state == "remove" or rm_success in (-1, '-1') or esuccess in (-1, '-1'): estate = "remove"
                        elif esuccess in (0, '0', None): estate = "setup"
                        else: estate = "ignore"
                        
                        nat_item["exempt_rules"].append({
                            "route_map_name": rm_n, 
                            "sequence": seq, 
                            "action": act, 
                            "acl_name": acl_n, 
                            "state": estate
                        })

                    # ==============================================================
                    # 🛠️ TỰ ĐỘNG THU THẬP VÀ ĐÓNG GÓI CHO BLOCK 7 (ROUTE-MAP TO INTERFACE)
                    # Không dùng bảng mới, tự quét tìm cổng outside trong chính cụm NAT này
                    # ==============================================================
                    outside_intf = next((i["interface_name"] for i in nat_item["interfaces"] if i["nat_role"] == "outside"), None)
                    if outside_intf:
                        seen_route_maps = set()
                        for ex_rule in nat_item["exempt_rules"]:
                            rm_name = ex_rule["route_map_name"]
                            if rm_name not in seen_route_maps:
                                seen_route_maps.add(rm_name)
                                nat_item["route_map_nat_rules"].append({
                                    "route_map_name": rm_name,
                                    "outside_interface": outside_intf,
                                    "overload": 1,  # Thường Policy NAT sẽ đi kèm cờ Overload ra cổng WAN
                                    "state": ex_rule["state"]
                                })

                    host_config["nat"].append(nat_item)
                    if n_success == -1: pending_nat_ids_del.append(n_id)
                    else: pending_nat_ids_add.append(n_id)
            except sqlite3.OperationalError as e:
                print(f"[-] Lỗi truy vấn bảng NAT_DB: {e}")

            if host_config["nat_acl"] or host_config["nat"]:
                valid_data.append({
                    "module": "nat", "target": {"ip": host}, 
                    "config": host_config,
                    "tracking": {
                        "acl_add": pending_acl_ids_add, "acl_del": pending_acl_ids_del,
                        "nat_add": pending_nat_ids_add, "nat_del": pending_nat_ids_del,
                        "rm_add": pending_rm_ids_add, "rm_del": pending_rm_ids_del
                    }
                })

                # ==============================================================
                # [ỐNG NHÒM] IN LỆNH SẼ ĐƯỢC CHẠY TRÊN ROUTER
                # ==============================================================
                templates_dir = os.path.join(CURRENT_DIR, "templates")
                
                # Hàm tự động quét tìm file template ở bất kỳ thư mục con nào
                def find_template(name):
                    for root, dirs, files in os.walk(templates_dir):
                        if name in files: return os.path.join(root, name)
                    return None

                template_file_acl = find_template("nat_acl.j2")
                template_file_nat = find_template("nat.j2")
                
                print(f"\n[+] ĐANG CHUẨN BỊ LỆNH XUỐNG: {host}")
                print("-" * 50)
                
                # Lặp qua từng ACL để in (Khớp 100% với logic của worker_nat.py)
                if template_file_acl and host_config["nat_acl"]:
                    with open(template_file_acl, "r", encoding="utf-8") as tf:
                        template = jinja2.Template(tf.read())
                        for acl in host_config["nat_acl"]:
                            for line in template.render(config=acl).split('\n'):
                                if line.strip(): print("  " + line)
                elif not template_file_acl and host_config["nat_acl"]:
                    print("  [-] LỖI ỐNG NHÒM: Không tìm thấy file nat_acl.j2 trong thư mục templates/")

                # Lặp qua từng cụm NAT để in (Khớp 100% với logic của worker_nat.py)
                if template_file_nat and host_config["nat"]:
                    with open(template_file_nat, "r", encoding="utf-8") as tf:
                        template = jinja2.Template(tf.read())
                        for nat in host_config["nat"]:
                            for line in template.render(config=nat).split('\n'):
                                if line.strip(): print("  " + line)
                elif not template_file_nat and host_config["nat"]:
                    print("  [-] LỖI ỐNG NHÒM: Không tìm thấy file nat.j2 trong thư mục templates/")
                    
                print("-" * 50)

        if not valid_data: return

        print(f"[INFO] Đang đẩy {len(valid_data)} gói cấu hình NAT sang Worker...")
        run_nat_config(valid_data, DB_PATH, ROUTE_OUTPUT)

        # --- UPDATE DATABASE AFTER WORKER ---
        if os.path.exists(ROUTE_OUTPUT):
            with open(ROUTE_OUTPUT, 'r', encoding='utf-8') as f:
                try:
                    results = json.load(f)
                except json.JSONDecodeError:
                    results = []
            
            for res in results:
                if res.get("status") == "success":
                    ip = res.get("target") or res.get("ip") or res.get("host")
                    for item in valid_data:
                        if item["target"]["ip"] == ip:
                            print(f"[*] Đang ghi nhận DB cho NAT: {ip}")
                            for aid in item["tracking"]["acl_add"]:
                                cursor.execute(f"UPDATE {T_NAT_ACL_MAIN} SET success = 1 WHERE nat_acl_id = ?", (aid,))
                                cursor.execute(f"UPDATE {T_NAT_ACL_STD} SET success = 1 WHERE nat_acl_id = ? AND (success <= 0 OR success IS NULL)", (aid,))
                                cursor.execute(f"UPDATE {T_NAT_ACL_EXT} SET success = 1 WHERE nat_acl_id = ? AND (success <= 0 OR success IS NULL)", (aid,))
                                cursor.execute(f"DELETE FROM {T_NAT_ACL_STD} WHERE nat_acl_id = ? AND success = -1", (aid,))
                                cursor.execute(f"DELETE FROM {T_NAT_ACL_EXT} WHERE nat_acl_id = ? AND success = -1", (aid,))
                            for aid in item["tracking"]["acl_del"]: cursor.execute(f"DELETE FROM {T_NAT_ACL_MAIN} WHERE nat_acl_id = ?", (aid,))
                            
                            for nid in item["tracking"]["nat_add"]: 
                                cursor.execute(f"UPDATE {T_NAT_MAIN} SET success = 1 WHERE nat_id = ?", (nid,))
                                for table in CHILD_NAT_TABLES:
                                    cursor.execute(f"DELETE FROM {table} WHERE nat_id = ? AND success = -1", (nid,))
                                    cursor.execute(f"UPDATE {table} SET success = 1 WHERE nat_id = ? AND (success <= 0 OR success IS NULL)", (nid,))
                            for nid in item["tracking"]["nat_del"]: cursor.execute(f"DELETE FROM {T_NAT_MAIN} WHERE nat_id = ?", (nid,))
                            
                            for rmid in item["tracking"]["rm_add"]:
                                cursor.execute(f"UPDATE {T_ROUTE_MAP_MAIN} SET success = 1 WHERE route_map_id = ?", (rmid,))
                                cursor.execute(f"UPDATE {T_ROUTE_MAP_ENTRIES} SET success = 1 WHERE route_map_id = ? AND (success <= 0 OR success IS NULL)", (rmid,))
                                cursor.execute(f"DELETE FROM {T_ROUTE_MAP_ENTRIES} WHERE route_map_id = ? AND success = -1", (rmid,))
                            for rmid in item["tracking"]["rm_del"]:
                                cursor.execute(f"DELETE FROM {T_ROUTE_MAP_MAIN} WHERE route_map_id = ?", (rmid,))
            conn.commit()
            print("[*] Đã đồng bộ Database NAT thành công.")

    except Exception as e:
        print(f"[-] Lỗi: {e}")
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    nat_dispatcher()