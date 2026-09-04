import os
import re
from backend.PyCode.share.config import get_db_connection, DB_TABLES, STATE_DIR

TBL_VLAN = DB_TABLES["l2_vlan"]["main"]

def extract_section(raw_text, section_keyword):
    if section_keyword not in raw_text: return ""
    content = raw_text.split(section_keyword)[1].lstrip(" =\n")
    if "[ SHOW" in content: content = content.split("[ SHOW")[0]
    return content

def sync_l2_vlan_worker(host_ip: str):
    # ĐÃ SỬA ĐƯỜNG DẪN: Trỏ về STATE_DIR và tên file chuẩn của Cò thu thập
    file_path = os.path.join(STATE_DIR, f"{host_ip}_running.txt")
    if not os.path.exists(file_path):
        print(f"[-] [SYNC VLAN] Không tìm thấy file {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    vlan_sec = extract_section(raw_text, "[ SHOW VLAN BRIEF ]")
    if not vlan_sec:
        vlan_sec = extract_section(raw_text, "[ SHOW VLAN ]")
        
    if not vlan_sec:
        print(f"[-] [SYNC VLAN] Không tìm thấy dữ liệu VLAN trong file của {host_ip}")
        return

    parsed_vlans = {}
    pattern = re.compile(r"^(\d+)\s+([a-zA-Z0-9_-]+)\s+(active|suspended|suspend)", re.MULTILINE)
    
    for match in pattern.finditer(vlan_sec):
        vlan_id = int(match.group(1))
        if 1002 <= vlan_id <= 1005: 
            continue
            
        raw_state = match.group(3)
        state = "suspend" if "suspend" in raw_state else "active"
        
        parsed_vlans[vlan_id] = {"name": match.group(2), "state": state}

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(f"SELECT vlan_id, id FROM {TBL_VLAN} WHERE host=?", (host_ip,))
        db_vlans = {row[0]: row[1] for row in c.fetchall()}

        db_vlan_ids = set(db_vlans.keys())
        run_vlan_ids = set(parsed_vlans.keys())

        for v_id in (db_vlan_ids - run_vlan_ids):
            if v_id != 1: c.execute(f"DELETE FROM {TBL_VLAN} WHERE id=?", (db_vlans[v_id],))

        for v_id in (run_vlan_ids - db_vlan_ids):
            data = parsed_vlans[v_id]
            c.execute(f"INSERT INTO {TBL_VLAN} (host, vlan_id, vlan_name, state) VALUES (?, ?, ?, ?)", 
                      (host_ip, v_id, data['name'], data['state']))

        for v_id in (db_vlan_ids & run_vlan_ids):
            data = parsed_vlans[v_id]
            c.execute(f"UPDATE {TBL_VLAN} SET vlan_name=?, state=? WHERE id=?", 
                      (data['name'], data['state'], db_vlans[v_id]))

        conn.commit()
        print(f"  [+] [VLAN SYNC] Đã đồng bộ thành công VLAN từ file cho {host_ip}")
    except Exception as e:
        conn.rollback()
        print(f"  [-] LỖI DATABASE KHI SYNC VLAN ({host_ip}): {e}")
    finally:
        conn.close()