import os
import yaml
import sys
import sqlite3
import urllib3
from jinja2 import Environment, FileSystemLoader

from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================================================
# VĂN MẪU: BẬT RADAR TÌM GỐC DỰ ÁN
# =========================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../.."))
if PROJECT_ROOT not in sys.path: sys.path.append(PROJECT_ROOT)

from PyCode.share.config import TMP_DIR, DB_TABLES, ACL_TEMPLATE_DIR, SECURITY_DIR
from backend.PyCode.share.config import DB_TABLES, get_db_connection
# =========================================================
# HÀM GIẢI MÃ ACTION_CFG TỪ FRONTEND
# =========================================================
def has_int_bit(action_cfg, bit: int) -> bool:
    """Giải mã số nguyên Bitmask (Dùng cho ACL, NAT). VD: action=1, bit 0 -> True"""
    if action_cfg is None: return True # Mặc định bật
    try:
        return bool(int(action_cfg) & (1 << bit))
    except (ValueError, TypeError):
        return False

# =========================================================
# 1. TRÍCH XUẤT VÀ NẶN DATA TỪ DB CHO JINJA2 (CONTROLLER)
# =========================================================
def _format_rule_to_dict(rule_tuple, acl_type='extended'):
    r = ["" if str(x).strip().lower() in ['none', 'null', ''] else str(x).strip() for x in rule_tuple]
    if acl_type == 'dynamic': return {"seq": r[2], "action": r[3], "protocol": r[4], "src": r[5], "src_mask": r[6], "src_port": r[7], "dst": r[8], "dst_mask": r[9], "dst_port": r[10], "dyn_name": r[11], "timeout": r[12]}
    elif acl_type == 'mac': return {"seq": r[2], "action": r[3], "src_mac": r[4], "src_mask": r[5], "dst_mac": r[6], "dst_mask": r[7], "ethertype": r[8]}
    elif acl_type == 'reflexive': return {"seq": r[2], "action": r[3], "protocol": r[4], "src": r[5], "src_mask": r[6], "src_port": r[7], "dst": r[8], "dst_mask": r[9], "dst_port": r[10], "reflect_name": r[11], "timeout": r[12]}
    elif acl_type == 'standard': return {"seq": r[2], "action": r[3], "src": r[4], "src_mask": r[5]}
    else: return {"seq": r[2], "action": r[3], "protocol": r[4], "src": r[5], "src_mask": r[6], "src_port": r[7], "dst": r[8], "dst_mask": r[9], "dst_port": r[10]}

def build_acl_payload(acl_id):
    # 1. Lấy tên bảng cha (Vì nó cố định nên để trên cùng vô tư)
    T_MAIN = DB_TABLES["acl"]["main"]

    conn = get_db_connection() # Gọi thẳng hàm connection global
    cursor = conn.cursor()
    try:
        # 2. Truy vấn DB lấy thông tin ACL
        cursor.execute(f"SELECT acl_name, acl_type, success, action_Cfg, description FROM {T_MAIN} WHERE Acl_id = ?", (acl_id,))
        row = cursor.fetchone()
        if not row: return None
        
        # 3. Rút data từ dòng vừa quét ra (Lúc này biến acl_type mới chính thức ra đời)
        acl_name, acl_type, success_db, action_cfg, desc = row
        
        # 4. CHÍNH LÀ CHỖ NÀY! Giờ mới có acl_type để gọi T_RULES
        T_RULES = DB_TABLES["acl"][acl_type.lower()]

        # Giải mã Bit 0 để quyết định sinh lệnh remark, MAC ACL thì bỏ qua
        push_desc = has_int_bit(action_cfg, 0) if acl_type.lower() != 'mac' else None

        payload = {
            "acl_id": acl_id, "acl_name": acl_name, "acl_type": acl_type.lower(),
            "action": "", "push_desc": push_desc, "description": desc,
            "rules_del": [], "rules_add": [], 
            "tracking_ids": {"del": [], "add": []}
        }
        if success_db == -1:
            payload["action"] = "delete"
            return payload

        cursor.execute(f"SELECT * FROM {T_RULES} WHERE acl_id = ? ORDER BY sequence ASC", (acl_id,))
        all_rules = cursor.fetchall()

        pending_del = [r for r in all_rules if r[-1] == -1]
        pending_add = [r for r in all_rules if r[-1] == 0] 
        done_rules  = [r for r in all_rules if r[-1] == 1] 

        is_new_acl = (len(done_rules) == 0 and len(pending_add) > 0)
        payload["action"] = "set" if is_new_acl else "change"
        
        for r in pending_del:
            payload["rules_del"].append(_format_rule_to_dict(r, payload["acl_type"]))
            payload["tracking_ids"]["del"].append(r[0])
            
        for r in pending_add:
            payload["rules_add"].append(_format_rule_to_dict(r, payload["acl_type"]))
            payload["tracking_ids"]["add"].append(r[0])

        return payload
    except Exception as e:
        print(f"[-] Lỗi Build ACL Payload: {e}")
        return None
    finally:
        conn.close()

# =========================================================
# 2. XỬ LÝ TEMPLATE VÀ ĐẨY LỆNH (NORNIR TASK)
# =========================================================
def task_push_acl(task):
    payload = task.host.data["ui_payload"]
    acl_type = payload['acl_type']
    tpl_name = 'extended' if acl_type in ['dynamic', 'reflexive'] else acl_type
    
    template_dir = os.path.join(ACL_TEMPLATE_DIR, task.host.data['template_folder'])
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(f"{tpl_name}.j2")
    commands_str = template.render(**payload)
    
    cmds = [l.strip() for l in commands_str.splitlines() if l.strip() and not l.strip().startswith('!')]
    if not cmds: return "No commands."
    
    print(f"\n[DEBUG] Lệnh đẩy xuống {task.host.hostname} (ACL_ID {payload['acl_id']}):")
    for cmd in cmds: print("  " + cmd)

    cmds.insert(0, "no logging console")
    res = task.run(task=netmiko_send_config, config_commands=cmds, read_timeout=120, cmd_verify=False)
    return res[0].result

# =========================================================
# 3. UPDATE DB SAU KHI THÀNH CÔNG (SUCCESS = 1)
# =========================================================
def update_db_after_success(payload):
    T_MAIN = DB_TABLES["acl"]["main"]
    T_RULES = DB_TABLES["acl"][payload['acl_type']]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        a_id = payload["acl_id"]
        if payload["action"] == "delete":
            cursor.execute(f"DELETE FROM {T_RULES} WHERE acl_id = ?", (a_id,))
            cursor.execute(f"DELETE FROM {T_MAIN} WHERE Acl_id = ?", (a_id,))
        else:
            for r_id in payload["tracking_ids"]["del"]: cursor.execute(f"DELETE FROM {T_RULES} WHERE id = ?", (r_id,))
            for r_id in payload["tracking_ids"]["add"]: cursor.execute(f"UPDATE {T_RULES} SET success = 1 WHERE id = ?", (r_id,))
            cursor.execute(f"UPDATE {T_MAIN} SET success = 1 WHERE Acl_id = ?", (a_id,))
            
        conn.commit()
    except Exception as e: print(f"[-] Lỗi Update DB: {e}")
    finally: conn.close()

# =========================================================
# 3.5. TỰ ĐỘNG ROLLBACK NẾU THẤT BẠI (CHỐNG KẸT DB)
# =========================================================
def update_db_after_fail(payload):
    T_MAIN = DB_TABLES["acl"]["main"]
    T_RULES = DB_TABLES["acl"][payload['acl_type']]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        a_id = payload["acl_id"]
        for r_id in payload["tracking_ids"]["add"]: cursor.execute(f"DELETE FROM {T_RULES} WHERE id = ?", (r_id,))
        for r_id in payload["tracking_ids"]["del"]: cursor.execute(f"UPDATE {T_RULES} SET success = 1 WHERE id = ?", (r_id,))
        cursor.execute(f"UPDATE {T_MAIN} SET success = 1 WHERE Acl_id = ?", (a_id,))
        conn.commit()
    except Exception as e: print(f"[-] Lỗi Update DB (Rollback Fail): {e}")
    finally: conn.close()

# =========================================================
# 4. HÀM RUNNER CHÍNH (ĐIỀU PHỐI WORKER)
# =========================================================
def build_inventory(target_ip, payloads):
    hosts_yaml = {}
    T_DEVICES = DB_TABLES["device_info"]["main"]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host = ?', (target_ip,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        dev_name, db_user, db_pass, db_os, db_port, db_method = row
        
        platform = "cisco_ios"
        conn_port = 22
        
        if str(db_method).upper() == "TELNET":
            platform = "cisco_ios_telnet"
            conn_port = db_port if db_port else 23
        elif str(db_method).upper() == "SSH":
            conn_port = db_port if db_port else 22
            
        if str(db_os).lower() != "cisco": platform = db_os

        tpl_folder = "cisco_ios" if platform in ["cisco_ios", "cisco_ios_telnet"] else platform
        
        hosts_yaml[dev_name or target_ip] = {
            "hostname": target_ip, "username": db_user, "password": db_pass,
            "port": int(conn_port), "platform": platform,
            "connection_options": {"netmiko": {"extras": {"global_delay_factor": 2}}},
            "data": {"template_folder": tpl_folder, "payloads": payloads}
        }
    
    inv_file = os.path.join(TMP_DIR, "tmp_acl_inventory.yaml")
    with open(inv_file, 'w', encoding='utf-8') as f: yaml.dump(hosts_yaml, f)
    return inv_file

def run_acl_worker(target_ip, acl_ids, db_path):
    print(f"\n[INFO] Khởi động ACL Worker (Jinja2) cho {target_ip}...")

    # Đã sửa lại chỉ gọi 1 tham số a_id
    payloads = [
        p for p in (build_acl_payload(a_id) for a_id in acl_ids)
        if p
    ]
    if not payloads:
        return

    # Đã bỏ tham số db_path
    inv_file = build_inventory(target_ip, payloads)

    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 5}},
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}},
        logging={"enabled": False}
    )

    try:
        for payload in payloads:
            print(f"\n[*] Đang thực thi ACL: {payload['acl_name']} (ID {payload['acl_id']} | Type: {payload['acl_type'].upper()})")

            for host in nr.inventory.hosts.values():
                host.data["ui_payload"] = payload

            results = nr.run(task=task_push_acl)

            for host, task_res in results.items():
                if task_res.failed:
                    print(f"[-] LỖI KẾT NỐI trên {host}: {task_res.exception}")
                    continue

                output_log = str(task_res.result)
                cisco_errors = [
                    "% Invalid input", "% Incomplete command", "% Ambiguous command",
                    "% Bad mask", "% Invalid wildcard", "% Duplicate", "% Access-list",
                    "% Interface", "% Object", "% Only one dynamic entry",
                    "Duplicate remark statement", "Duplicate sequence number"
                ]

                if any(err in output_log for err in cisco_errors):
                    print(f"[-] LỖI CÚ PHÁP TỪ ROUTER {host}! Kích hoạt Rollback DB!")
                    print(f"    [LOG CHI TIẾT TỪ ROUTER]:\n{output_log}\n" + "=" * 50)
                    update_db_after_fail(payload) # Đã bỏ db_path
                else:
                    print(f"[+] Thành công trên {host}! Thiết bị đã nhận lệnh.")
                    print(f"    [LOG CHI TIẾT TỪ ROUTER]:\n{output_log}\n" + "=" * 50)
                    update_db_after_success(payload) # Đã bỏ db_path

    finally:
        if os.path.exists(inv_file):
            os.remove(inv_file)

