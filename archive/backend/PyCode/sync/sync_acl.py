import sqlite3
import re

from backend.PyCode.share.config import DB_TABLES, get_db_connection

TBL_ACL_MAIN = DB_TABLES["acl"]["main"]
TBL_ACL_STD = DB_TABLES["acl"]["standard"]
TBL_ACL_EXT = DB_TABLES["acl"]["extended"]

def parse_standard_rule(rule_text):
    match = re.search(r"^(?P<seq>\d+)?\s*(?P<action>permit|deny)\s+(?P<src>any|host\s+\S+|\S+)(?:\s+(?P<wildcard>\S+))?", rule_text.strip())
    if not match: return None
    
    seq = match.group('seq')
    src = match.group('src')
    wildcard = match.group('wildcard') if match.group('wildcard') else ""
    
    if "host" in src:
        src = src.replace("host ", "").strip()
        wildcard = "0.0.0.0"
    elif src == "any":
        wildcard = "255.255.255.255"

    return {"sequence": seq, "action": match.group('action'), "source": src, "wildcard": wildcard}

def parse_extended_rule(rule_text):
    """
    Máy chém thông minh: Cắt chuỗi Extended ACL thành từng mảnh nhỏ
    Ví dụ: 'permit tcp any 192.168.1.0 0.0.0.255 eq 80' -> cắt sạch sẽ!
    """
    match = re.search(r"^(?P<seq>\d+)?\s*(?P<action>permit|deny)\s+(?P<protocol>\S+)\s+(?P<rest>.*)", rule_text.strip())
    if not match: return None
    
    seq = match.group('seq')
    action = match.group('action')
    protocol = match.group('protocol')
    
    # Tách phần còn lại thành các từ khóa (tokens) để băm
    tokens = match.group('rest').split()
    
    def extract_ip_port(tks):
        ip, wc, port = "", "", ""
        if not tks: return ip, wc, port, tks
        
        tk = tks.pop(0)
        if tk == "any":
            ip = "any"
        elif tk == "host":
            ip = tks.pop(0) if tks else ""
        else:
            ip = tk
            # Kiểm tra xem từ tiếp theo có phải wildcard mask không (vd: 0.0.0.255)
            if tks and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", tks[0]):
                wc = tks.pop(0)
                
        # Kiểm tra xem có Port đi kèm không (eq, neq, gt, lt, range)
        if tks and tks[0] in ["eq", "neq", "gt", "lt", "range"]:
            op = tks.pop(0)
            pval = tks.pop(0) if tks else ""
            port = f"{op} {pval}"
            if op == "range" and tks: # Range cần 2 giá trị port
                port += f" {tks.pop(0)}"
                
        return ip, wc, port, tks

    # Trích xuất Lần 1 (cho Source)
    src, src_wc, src_port, tokens = extract_ip_port(tokens)
    
    # Trích xuất Lần 2 (cho Destination từ phần còn dư)
    dst, dst_wc, dst_port, tokens = extract_ip_port(tokens)
    
    return {
        "sequence": seq, "action": action, "protocol": protocol,
        "source": src, "src_wildcard": src_wc, "src_port": src_port,
        "destination": dst, "dst_wildcard": dst_wc, "dst_port": dst_port
    }

def sync_acl_worker(host_ip: str, parse_obj, db_path: str):
    parsed_acls = {}
    
    # -------------------------------------------------------------
    # BƯỚC A: TRÍCH XUẤT TỪ FILE CONFIG 
    # -------------------------------------------------------------
    
    # 1. BĂM NAMED ACL (Ví dụ: ip access-list extended TEST)
    for acl_obj in parse_obj.find_objects(r"^ip access-list "):
        parts = acl_obj.text.strip().split()
        if len(parts) >= 4:
            acl_type = parts[2]
            acl_name = parts[3]
            
            desc_obj = acl_obj.re_search_children(r"^\s+remark ")
            desc = desc_obj[0].text.split("remark ")[-1].strip() if desc_obj else ""
            
            if acl_name not in parsed_acls:
                parsed_acls[acl_name] = {"type": acl_type, "description": desc, "rules": []}
            
            for rule_obj in acl_obj.children:
                r_text = rule_obj.text.strip()
                if r_text.startswith("remark"): continue
                
                if acl_type == 'standard':
                    rule_data = parse_standard_rule(r_text)
                    if rule_data: parsed_acls[acl_name]["rules"].append(rule_data)
                elif acl_type == 'extended':
                    rule_data = parse_extended_rule(r_text)
                    if rule_data: parsed_acls[acl_name]["rules"].append(rule_data)

    # 2. BĂM NUMBERED ACL (Ví dụ: access-list 1 permit 10.1.20.0 0.0.0.255)
    for rule_obj in parse_obj.find_objects(r"^access-list \d+"):
        parts = rule_obj.text.strip().split()
        if len(parts) >= 4:
            acl_name = parts[1]
            
            # Phân loại Standard hay Extended dựa trên ID của Cisco
            acl_num = int(acl_name)
            if (1 <= acl_num <= 99) or (1300 <= acl_num <= 1999):
                acl_type = "standard"
            elif (100 <= acl_num <= 199) or (2000 <= acl_num <= 2699):
                acl_type = "extended"
            else:
                continue  # Bỏ qua nếu là các loại ACL dị biệt khác
                
            # Khởi tạo vỏ nếu chưa có
            if acl_name not in parsed_acls:
                parsed_acls[acl_name] = {"type": acl_type, "description": "", "rules": []}
                
            # Ép chuỗi về định dạng của Named ACL để tái sử dụng máy chém Regex
            reconstructed_rule = " ".join(parts[2:]) 
            
            if acl_type == 'standard':
                rule_data = parse_standard_rule(reconstructed_rule)
                if rule_data: parsed_acls[acl_name]["rules"].append(rule_data)
            elif acl_type == 'extended':
                rule_data = parse_extended_rule(reconstructed_rule)
                if rule_data: parsed_acls[acl_name]["rules"].append(rule_data)

    # 3. TỰ ĐỘNG ĐÁNH SỐ SEQUENCE (Chung cho cả Named và Numbered)
    for a_name, data in parsed_acls.items():
        current_seq = 10
        for r in data["rules"]:
            if not r.get('sequence'): 
                r['sequence'] = current_seq
            current_seq = int(r['sequence']) + 10

    # -------------------------------------------------------------
    # BƯỚC B: ĐỒNG BỘ XUỐNG DATABASE
    # -------------------------------------------------------------
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute(f"SELECT Acl_id, acl_name, acl_type FROM {TBL_ACL_MAIN} WHERE host=?", (host_ip,))
        db_acls = {row[1]: {"id": row[0], "type": row[2]} for row in c.fetchall()}
        
        db_acl_names = set(db_acls.keys())
        run_acl_names = set(parsed_acls.keys())
        
        for a_name in (db_acl_names - run_acl_names):
            c.execute(f"DELETE FROM {TBL_ACL_MAIN} WHERE Acl_id=?", (db_acls[a_name]["id"],))
            
        for a_name in (run_acl_names - db_acl_names):
            data = parsed_acls[a_name]
            c.execute(f"INSERT INTO {TBL_ACL_MAIN} (acl_name, acl_type, host, description, success, action_Cfg) VALUES (?, ?, ?, ?, 1, 1)", 
                      (a_name, data["type"], host_ip, data["description"]))
            db_acls[a_name] = {"id": c.lastrowid, "type": data["type"]}
            
        for a_name in run_acl_names:
            acl_id = db_acls[a_name]["id"]
            acl_type = db_acls[a_name]["type"]
            data = parsed_acls[a_name]
            
            c.execute(f"UPDATE {TBL_ACL_MAIN} SET description=?, success=1 WHERE Acl_id=?", (data["description"], acl_id))
            
            if acl_type == 'standard':
                c.execute(f"DELETE FROM {TBL_ACL_STD} WHERE acl_id=?", (acl_id,))
                for r in data["rules"]:
                    c.execute(f"INSERT INTO {TBL_ACL_STD} (acl_id, sequence, action, source, wildcard, success) VALUES (?, ?, ?, ?, ?, 1)", 
                              (acl_id, r["sequence"], r["action"], r["source"], r["wildcard"]))
                    
            elif acl_type == 'extended':
                c.execute(f"DELETE FROM {TBL_ACL_EXT} WHERE acl_id=?", (acl_id,))
                for r in data["rules"]:
                    c.execute(f"""
                        INSERT INTO {TBL_ACL_EXT} 
                        (acl_id, sequence, action, protocol, source, src_wildcard, src_port, destination, dst_wildcard, dst_port, success)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (acl_id, r["sequence"], r["action"], r["protocol"], r["source"], r["src_wildcard"], r["src_port"], r["destination"], r["dst_wildcard"], r["dst_port"]))

        conn.commit()
        print(f"[+] ACL Worker: Đồng bộ thành công cấu hình cho {host_ip}")
        
    except Exception as e:
        print(f"[-] ACL Worker LỖI: {e}")
        conn.rollback()
    finally:
        conn.close()