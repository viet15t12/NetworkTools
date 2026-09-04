import os
import re
from datetime import datetime

def extract_section(raw_text, section_keyword):
    if section_keyword not in raw_text:
        return ""
    content = raw_text.split(section_keyword)[1]
    content = content.lstrip(" =\n")
    if "[ SHOW" in content:
        content = content.split("[ SHOW")[0]
    if "====================" in content:
        content = content.split("====================")[0]
    return content

def process_acl_data(host, file_path, db_cursor):
    if not os.path.exists(file_path):
        print(f"      [-] Worker ACL: Không tìm thấy file tại {file_path}")
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_cursor.execute("""
        INSERT INTO t10_info_acl_collection (host, command, started_at, collection_state, acl_count, rule_count) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (host, "show access-lists", start_time, "running", 0, 0))
    collection_id = db_cursor.lastrowid

    acl_sec = extract_section(raw_text, "[ SHOW ACCESS-LISTS ]")
    run_sec = extract_section(raw_text, "[ SHOW RUNNING-CONFIG ]")
    # Khai thác thêm dữ liệu từ phần policy-map interface mới kéo về
    pmap_iface_sec = extract_section(raw_text, "[ SHOW POLICY-MAP INTERFACE ]")

    # =========================================================
    # BƯỚC 0.5: HACK - PRE-PARSE MQC QOS (Bắt full VLAN, CoS, DSCP)
    # =========================================================
    qos_mapping = {} # {acl_name: {'cos': int, 'vlan': int, 'dscp': str}}
    if run_sec:
        cmap_to_acl = {}
        cmap_to_vlan = {} 
        pmap_to_cos = {}
        pmap_to_dscp = {} # Bổ sung hứng biến DSCP
        curr_cmap = None
        curr_pmap = None
        curr_class = None
        
        for line in run_sec.splitlines():
            line = line.strip()
            # Bóc tách Class-Map
            if line.startswith("class-map "):
                curr_cmap = line.split()[-1]
            elif curr_cmap and line.startswith("match access-group name "):
                cmap_to_acl[curr_cmap] = line.split("name ")[1].strip()
            elif curr_cmap and line.startswith("match vlan "):
                try: cmap_to_vlan[curr_cmap] = int(line.split("vlan ")[1].strip())
                except ValueError: pass
            elif line == "!" and curr_cmap:
                curr_cmap = None
                
            # Bóc tách Policy-Map
            if line.startswith("policy-map "):
                curr_pmap = line.split()[-1]
            elif curr_pmap and line.startswith("class "):
                curr_class = line.split("class ")[1].strip()
            elif curr_pmap and curr_class and line.startswith("set cos "):
                try: pmap_to_cos[curr_class] = int(line.split("cos ")[1].strip())
                except ValueError: pass
            elif curr_pmap and curr_class and line.startswith("set dscp "):
                pmap_to_dscp[curr_class] = line.split("dscp ")[1].strip()
            elif line == "!":
                if curr_class: curr_class = None
                elif curr_pmap: curr_pmap = None

        # Gộp tất cả data (VLAN, CoS, DSCP) ánh xạ vào Tên ACL
        for cmap, a_name in cmap_to_acl.items():
            qos_mapping[a_name] = {}
            if cmap in pmap_to_cos:
                qos_mapping[a_name]['cos'] = pmap_to_cos[cmap]
            if cmap in pmap_to_dscp:
                qos_mapping[a_name]['dscp'] = pmap_to_dscp[cmap]
            if cmap in cmap_to_vlan:
                qos_mapping[a_name]['vlan'] = cmap_to_vlan[cmap]

    # =========================================================
    # BƯỚC 0: FETCH TRẠNG THÁI DATABASE HIỆN TẠI
    # =========================================================
    db_cursor.execute("SELECT info_acl_id, acl_name FROM t10_info_acl_db WHERE host = ?", (host,))
    existing_acls = {row[1]: row[0] for row in db_cursor.fetchall()}

    db_cursor.execute("""
        SELECT info_acl_id, sequence, info_rule_id 
        FROM t10_info_acl_rules 
        WHERE info_acl_id IN (SELECT info_acl_id FROM t10_info_acl_db WHERE host = ?)
    """, (host,))
    existing_rules = {}
    for acl_id, seq, rule_id in db_cursor.fetchall():
        if acl_id not in existing_rules:
            existing_rules[acl_id] = {}
        existing_rules[acl_id][seq] = rule_id

    seen_acls = set()
    seen_rules = {} 

    total_acls = 0
    total_rules = 0
    current_acl_id = None
    current_acl_name_tracker = None
    current_acl_type = None
    mock_sequence = 10  

    # =========================================================
    # BƯỚC 1: PARSE VÀ ĐỒNG BỘ DỮ LIỆU ACL & RULES
    # =========================================================
    if acl_sec:
        for line in acl_sec.splitlines():
            line = line.rstrip()
            if not line: continue

            header_match = re.match(r"^(Standard|Extended|IPv6|MAC)\s+(.*?)access\s+list\s+(.+)$", line, re.I)
            if header_match:
                prefix = header_match.group(1).lower()
                middle = header_match.group(2).lower()
                acl_name = header_match.group(3).strip()
                current_acl_name_tracker = acl_name

                if "mac" in middle or prefix == "mac":
                    address_family = "mac"
                    current_acl_type = "mac"  
                    acl_type = "extended" 
                elif "ipv6" in middle or prefix == "ipv6":
                    address_family = "ipv6"
                    current_acl_type = "ipv6"
                    acl_type = prefix if prefix in ["standard", "extended"] else "extended"
                else:
                    address_family = "ipv4"
                    current_acl_type = prefix
                    acl_type = prefix

                acl_format = 'numbered' if acl_name.isdigit() else 'named'

                if acl_name in existing_acls:
                    current_acl_id = existing_acls[acl_name]
                    db_cursor.execute("""
                        UPDATE t10_info_acl_db 
                        SET acl_type = ?, address_family = ?, acl_format = ?, is_applied = 0, rule_count = 0, raw_output = ?
                        WHERE info_acl_id = ?
                    """, (acl_type, address_family, acl_format, line, current_acl_id))
                else:
                    db_cursor.execute("""
                        INSERT INTO t10_info_acl_db (host, acl_name, acl_type, address_family, acl_format, is_applied, rule_count, raw_output) 
                        VALUES (?, ?, ?, ?, ?, 0, 0, ?)
                    """, (host, acl_name, acl_type, address_family, acl_format, line))
                    current_acl_id = db_cursor.lastrowid
                    existing_acls[acl_name] = current_acl_id 

                seen_acls.add(current_acl_id)
                if current_acl_id not in seen_rules:
                    seen_rules[current_acl_id] = set()
                
                total_acls += 1
                mock_sequence = 10
                continue

            if current_acl_id and (line.startswith(" ") or line.startswith("\t")):
                rule_str = line.strip()
                
                seq_at_end = None
                end_seq_match = re.search(r"\bsequence\s+(\d+)$", rule_str, re.I)
                if end_seq_match:
                    seq_at_end = int(end_seq_match.group(1))
                    rule_str = rule_str[:end_seq_match.start()].strip()

                seq_match = re.match(r"^(?:(\d+)\s+)?(permit|deny|remark|evaluate|dynamic)\b\s*(.*)", rule_str, re.I)
                
                if seq_match:
                    if seq_at_end is not None:
                        sequence = seq_at_end               
                        mock_sequence = sequence + 10
                    elif seq_match.group(1):
                        sequence = int(seq_match.group(1))  
                        mock_sequence = sequence + 10
                    else:
                        sequence = mock_sequence            
                        mock_sequence += 10
                        
                    action = seq_match.group(2).lower()
                    remainder = seq_match.group(3)

                    match_count = 0
                    matches_match = re.search(r"\((\d+)\s+match(?:es)?\)", remainder, re.I)
                    if matches_match:
                        match_count = int(matches_match.group(1))
                        remainder = remainder.replace(matches_match.group(0), "").strip()

                    logging = None
                    if remainder.endswith(" log"):
                        logging = "log"
                        remainder = remainder[:-4].strip()
                    elif remainder.endswith(" log-input"):
                        logging = "log-input"
                        remainder = remainder[:-10].strip()

                    parsed_ok = 1
                    source = dst = src_wild = dst_wild = protocol = None
                    src_port_op = src_port_start = src_port_end = None
                    dst_port_op = dst_port_start = dst_port_end = None
                    tcp_flags = icmp_type = icmp_code = dynamic_name = reflect_name = evaluate_name = None
                    remark_text = None
                    
                    ethertype = vlan_id = cos_value = None
                    original_action = action
                    
                    if action == "evaluate":
                        evaluate_name = remainder.strip()
                        action = "permit"  
                    elif action == "dynamic":
                        parts = remainder.split()
                        if len(parts) >= 2:
                            dynamic_name = parts[0]
                            action = parts[1].lower() 
                            remainder = " ".join(parts[2:])
                    
                    if original_action == "remark":
                        remark_text = remainder
                    
                    elif original_action != "evaluate" and current_acl_type == "standard":
                        remainder = remainder.replace(",", "").replace("wildcard bits", "").strip()
                        if remainder == "any":
                            source = "any"
                        elif remainder.startswith("host "):
                            source = remainder.split()[1]
                            src_wild = "0.0.0.0"
                        else:
                            parts = remainder.split()
                            if len(parts) >= 2:
                                source, src_wild = parts[0], parts[1]
                            elif len(parts) == 1 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]):
                                source = parts[0]
                                src_wild = "0.0.0.0"
                            else:
                                source = remainder
                                parsed_ok = 0
                    
                    elif original_action != "evaluate" and current_acl_type == "mac":
                        tokens = remainder.split()
                        def parse_mac_block(tks):
                            mac_val = mask_val = None
                            if not tks: return mac_val, mask_val
                            if tks[0] == "any":
                                mac_val = tks.pop(0)
                            elif tks[0] == "host":
                                tks.pop(0)
                                if tks:
                                    mac_val = tks.pop(0)
                                    mask_val = "0000.0000.0000"
                            else:
                                mac_val = tks.pop(0)
                                if tks and re.match(r"^[0-9a-fA-F\.]+$", tks[0]):
                                    mask_val = tks.pop(0)
                            return mac_val, mask_val

                        try:
                            source, src_wild = parse_mac_block(tokens)
                            dst, dst_wild = parse_mac_block(tokens)
                            
                            if tokens and tokens[0] not in ['vlan', 'cos', 'log']:
                                ethertype = tokens.pop(0)
                                if ethertype == "lsap" and len(tokens) >= 2:
                                    ethertype = f"lsap {tokens.pop(0)} {tokens.pop(0)}"

                            while tokens:
                                tok = tokens.pop(0).lower()
                                if tok == "vlan" and tokens:
                                    try: vlan_id = int(tokens.pop(0)) 
                                    except ValueError: pass
                                elif tok == "cos" and tokens:
                                    try: cos_value = int(tokens.pop(0)) 
                                    except ValueError: pass
                                elif tok == "log":
                                    logging = "log"
                                    
                            # Bơm dữ liệu QoS từ MQC vào biến của bảng con
                            if current_acl_name_tracker in qos_mapping:
                                if qos_mapping[current_acl_name_tracker].get('cos') is not None:
                                    cos_value = qos_mapping[current_acl_name_tracker]['cos']
                                if qos_mapping[current_acl_name_tracker].get('vlan') is not None:
                                    vlan_id = qos_mapping[current_acl_name_tracker]['vlan']
                                # Lưu ý: dscp đã được parse trong qos_mapping nhưng chưa có cột trong DB
                                    
                        except Exception:
                            parsed_ok = 0
                            
                    elif original_action != "evaluate" and current_acl_type == "extended":
                        tokens = remainder.split()
                        if tokens: protocol = tokens.pop(0)
                        
                        def parse_ip_block(tks):
                            ip_val = wild_val = None
                            if not tks: return ip_val, wild_val
                            if tks[0] == "any":
                                ip_val = tks.pop(0)
                            elif tks[0] == "host":
                                tks.pop(0)
                                if tks:
                                    ip_val = tks.pop(0)
                                    wild_val = "0.0.0.0"
                            else:
                                ip_val = tks.pop(0)
                                if tks and re.match(r"^\d+\.\d+\.\d+\.\d+$", tks[0]):
                                    wild_val = tks.pop(0)
                            return ip_val, wild_val

                        def parse_port_block(tks):
                            op = p_start = p_end = None
                            if tks and tks[0] in ["eq", "neq", "lt", "gt", "range"]:
                                op = tks.pop(0)
                                if tks: p_start = tks.pop(0)
                                if op == "range" and tks: p_end = tks.pop(0)
                            return op, p_start, p_end

                        try:
                            source, src_wild = parse_ip_block(tokens)
                            src_port_op, src_port_start, src_port_end = parse_port_block(tokens)
                            dst, dst_wild = parse_ip_block(tokens)
                            dst_port_op, dst_port_start, dst_port_end = parse_port_block(tokens)
                            
                            while tokens:
                                tok = tokens.pop(0).lower()
                                if tok == "reflect" and tokens:
                                    reflect_name = tokens.pop(0)
                                elif tok == "timeout" and tokens:
                                    try: timeout_seconds = int(tokens.pop(0))
                                    except ValueError: pass
                                elif tok == "established": tcp_flags = "established"
                                elif tok in ["syn", "ack", "fin", "rst", "urg", "psh"]: tcp_flags = tok
                                elif protocol == "icmp" and not icmp_type:
                                    tok_lower = tok
                                    icmp_comprehensive_mapping = {
                                        "echo": ("8", "0"), "echo-reply": ("0", "0"), "unreachable": ("3", None)
                                        # (Giữ nguyên phần còn lại của mapping theo chuẩn code cũ)
                                    }
                                    if tok_lower in icmp_comprehensive_mapping:
                                        icmp_type, icmp_code = icmp_comprehensive_mapping[tok_lower]
                                    elif tok_lower.isdigit():
                                        icmp_type = tok_lower
                                        if tokens and tokens[0].isdigit(): icmp_code = tokens.pop(0)
                                    else:
                                        icmp_type = tok_lower
                        except Exception:
                            parsed_ok = 0 

                    rule_tuple = (
                        action, protocol, source, src_wild, src_port_op, src_port_start, src_port_end,
                        dst, dst_wild, dst_port_op, dst_port_start, dst_port_end,
                        tcp_flags, icmp_type, icmp_code, dynamic_name, reflect_name, evaluate_name,
                        match_count, logging, remark_text, parsed_ok, rule_str
                    )

                    rule_id_db = None
                    if current_acl_id in existing_rules and sequence in existing_rules[current_acl_id]:
                        rule_id_db = existing_rules[current_acl_id][sequence]
                        db_cursor.execute("""
                            UPDATE t10_info_acl_rules SET 
                                action=?, protocol=?, source=?, src_wildcard=?, src_port_operator=?, src_port_start=?, src_port_end=?,
                                destination=?, dst_wildcard=?, dst_port_operator=?, dst_port_start=?, dst_port_end=?,
                                tcp_flags=?, icmp_type=?, icmp_code=?, dynamic_name=?, reflect_name=?, evaluate_name=?,
                                match_count=?, logging=?, remark_text=?, parsed_ok=?, raw_line=?
                            WHERE info_rule_id = ?
                        """, (*rule_tuple, rule_id_db))
                    else:
                        db_cursor.execute("""
                            INSERT INTO t10_info_acl_rules (
                                info_acl_id, sequence, action, protocol, source, src_wildcard, src_port_operator, src_port_start, src_port_end,
                                destination, dst_wildcard, dst_port_operator, dst_port_start, dst_port_end,
                                tcp_flags, icmp_type, icmp_code, dynamic_name, reflect_name, evaluate_name,
                                match_count, logging, remark_text, parsed_ok, raw_line
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (current_acl_id, sequence, *rule_tuple))
                        rule_id_db = db_cursor.lastrowid 

                    if current_acl_type == "mac" and original_action != "remark" and rule_id_db is not None:
                        db_cursor.execute("SELECT id FROM t10_info_mac_acl_rule_details WHERE info_rule_id = ?", (rule_id_db,))
                        if db_cursor.fetchone():
                            db_cursor.execute("""
                                UPDATE t10_info_mac_acl_rule_details SET 
                                    src_mac=?, src_mask=?, dst_mac=?, dst_mask=?, ethertype=?, vlan_id=?, cos_value=?, raw_line=?
                                WHERE info_rule_id = ?
                            """, (source, src_wild, dst, dst_wild, ethertype, vlan_id, cos_value, rule_str, rule_id_db))
                        else:
                            db_cursor.execute("""
                                INSERT INTO t10_info_mac_acl_rule_details (
                                    info_rule_id, src_mac, src_mask, dst_mac, dst_mask, ethertype, vlan_id, cos_value, raw_line
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (rule_id_db, source, src_wild, dst, dst_wild, ethertype, vlan_id, cos_value, rule_str))

                    seen_rules[current_acl_id].add(sequence)
                    db_cursor.execute("UPDATE t10_info_acl_db SET rule_count = rule_count + 1 WHERE info_acl_id = ?", (current_acl_id,))
                    total_rules += 1

    # =========================================================
    # BƯỚC 1.5: QUÉT LẠI RUNNING-CONFIG (BẮT TIMEOUT & DESCRIPTION)
    # =========================================================
    if run_sec:
        current_acl_name = None
        has_seen_action = False  
        
        for line in run_sec.splitlines():
            line = line.strip()
            
            if line.startswith("ip access-list "):
                current_acl_name = line.split()[-1]
                has_seen_action = False  
                continue
            elif line == "!":
                current_acl_name = None
                has_seen_action = False
                continue
                
            if current_acl_name and current_acl_name in existing_acls:
                acl_id = existing_acls[current_acl_name]
                
                if re.match(r"^(permit|deny|evaluate|dynamic)\b", line, re.I):
                    has_seen_action = True
                    timeout_match = re.search(r"timeout\s+(\d+)", line, re.I)
                    if timeout_match:
                        t_val = int(timeout_match.group(1))
                        dyn_match = re.search(r"dynamic\s+(\S+)", line, re.I)
                        ref_match = re.search(r"reflect\s+(\S+)", line, re.I)
                        
                        if dyn_match:
                            db_cursor.execute("UPDATE t10_info_acl_rules SET timeout_seconds = ? WHERE info_acl_id = ? AND dynamic_name = ?", (t_val, acl_id, dyn_match.group(1)))
                        elif ref_match:
                            db_cursor.execute("UPDATE t10_info_acl_rules SET timeout_seconds = ? WHERE info_acl_id = ? AND reflect_name = ?", (t_val, acl_id, ref_match.group(1)))
                            
                remark_match = re.match(r"^remark\s+(.*)", line, re.I)
                if remark_match:
                    rem_text = remark_match.group(1).strip()
                    if not has_seen_action:
                        db_cursor.execute("UPDATE t10_info_acl_db SET description = ? WHERE info_acl_id = ?", (rem_text, acl_id))
                    else:
                        db_cursor.execute("SELECT info_rule_id FROM t10_info_acl_rules WHERE info_acl_id = ? AND action = 'remark' AND remark_text = ?", (acl_id, rem_text))
                        if not db_cursor.fetchone():
                            db_cursor.execute("""
                                INSERT INTO t10_info_acl_rules (
                                    info_acl_id, sequence, action, protocol, source, src_wildcard, src_port_operator, src_port_start, src_port_end,
                                    destination, dst_wildcard, dst_port_operator, dst_port_start, dst_port_end,
                                    tcp_flags, icmp_type, icmp_code, dynamic_name, reflect_name, evaluate_name,
                                    match_count, logging, remark_text, parsed_ok, raw_line
                                ) VALUES (?, NULL, 'remark', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, ?, 1, ?)
                            """, (acl_id, rem_text, line))
                            db_cursor.execute("UPDATE t10_info_acl_db SET rule_count = rule_count + 1 WHERE info_acl_id = ?", (acl_id,))
                            
            m_std = re.match(r"^access-list\s+(\S+)\s+(.*)", line, re.I)
            if m_std:
                acl_name = m_std.group(1)
                content = m_std.group(2)
                
                if current_acl_name != acl_name:
                    current_acl_name = acl_name
                    has_seen_action = False
                
                if current_acl_name in existing_acls:
                    acl_id = existing_acls[current_acl_name]
                    if content.lower().startswith("remark "):
                        rem_text = content[7:].strip()
                        if not has_seen_action:
                            db_cursor.execute("UPDATE t10_info_acl_db SET description = ? WHERE info_acl_id = ?", (rem_text, acl_id))
                        else:
                            db_cursor.execute("SELECT info_rule_id FROM t10_info_acl_rules WHERE info_acl_id = ? AND action = 'remark' AND remark_text = ?", (acl_id, rem_text))
                            if not db_cursor.fetchone():
                                db_cursor.execute("""
                                    INSERT INTO t10_info_acl_rules (
                                        info_acl_id, sequence, action, protocol, source, src_wildcard, src_port_operator, src_port_start, src_port_end,
                                        destination, dst_wildcard, dst_port_operator, dst_port_start, dst_port_end,
                                        tcp_flags, icmp_type, icmp_code, dynamic_name, reflect_name, evaluate_name,
                                        match_count, logging, remark_text, parsed_ok, raw_line
                                    ) VALUES (?, NULL, 'remark', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, ?, 1, ?)
                                """, (acl_id, rem_text, line))
                                db_cursor.execute("UPDATE t10_info_acl_db SET rule_count = rule_count + 1 WHERE info_acl_id = ?", (acl_id,))
                    else:
                        has_seen_action = True

    # =========================================================
    # BƯỚC 2: DỌN DẸP DỮ LIỆU CŨ & ĐỒNG BỘ INTERFACE
    # =========================================================
    for acl_id, seq_dict in existing_rules.items():
        if acl_id in seen_rules:
            for old_seq, rule_id in seq_dict.items():
                if old_seq not in seen_rules[acl_id]:
                    db_cursor.execute("DELETE FROM t10_info_acl_rules WHERE info_rule_id = ?", (rule_id,))

    for old_acl_id in list(existing_acls.values()):
        if old_acl_id not in seen_acls:
            db_cursor.execute("DELETE FROM t10_info_acl_rules WHERE info_acl_id = ?", (old_acl_id,))
            db_cursor.execute("DELETE FROM t10_info_acl_db WHERE info_acl_id = ?", (old_acl_id,))

    db_cursor.execute("DELETE FROM t10_info_iface_acl WHERE host = ?", (host,))
    
    if run_sec:
        current_iface = None
        for line in run_sec.splitlines():
            line = line.strip()
            if line.startswith("interface "):
                current_iface = line.split("interface ")[1]
            elif current_iface and line.startswith("ip access-group "):
                parts = line.split()
                if len(parts) >= 4:
                    acl_name = parts[2]
                    direction = parts[3].lower()
                    
                    if acl_name in existing_acls:
                        acl_id = existing_acls[acl_name]
                        if direction in ['in', 'out']:
                            db_cursor.execute("""
                                INSERT INTO t10_info_iface_acl (host, interface_name, info_acl_id, acl_name, direction, address_family, apply_scope, raw_line) 
                                VALUES (?, ?, ?, ?, ?, 'ipv4', 'interface', ?)
                            """, (host, current_iface, acl_id, acl_name, direction, line))
                            db_cursor.execute("UPDATE t10_info_acl_db SET is_applied = 1 WHERE info_acl_id = ?", (acl_id,))

    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_cursor.execute("""
        UPDATE t10_info_acl_collection 
        SET completed_at = ?, collection_state = ?, acl_count = ?, rule_count = ? 
        WHERE collection_id = ?
    """, (end_time, "completed", total_acls, total_rules, collection_id))

    return True