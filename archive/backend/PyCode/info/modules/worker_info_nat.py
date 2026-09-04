import os
import re
from datetime import datetime

# =====================================================================
# HÀM PHỤ TRỢ 1: CẮT SECTION
# =====================================================================
def extract_section(raw_text, section_keyword):
    """Hàm phụ trợ cắt đúng phần text của từng lệnh"""
    if section_keyword not in raw_text:
        return ""
    content = raw_text.split(section_keyword)[1]
    content = content.lstrip(" =\n")
    if "[ SHOW" in content:
        content = content.split("[ SHOW")[0]
    if "====================" in content:
        content = content.split("====================")[0]
    return content

# =====================================================================
# HÀM PHỤ TRỢ 2: PARSE TRANSLATIONS VERBOSE (ĐÃ CHUYỂN RA NGOÀI)
# =====================================================================
def parse_nat_translations_verbose(raw_config, hostname):
    translations_data = []
    
    trans_match = re.search(
        r"==================== \[ SHOW IP NAT TRANSLATIONS VERBOSE \] ====================\n(.*?)(?=\n={20}|\Z)", 
        raw_config, 
        re.DOTALL
    )
    
    if trans_match:
        trans_text = trans_match.group(1).strip()
        trans_text = re.sub(r"^Pro Inside global.*?\n", "", trans_text, flags=re.MULTILINE)
        
        blocks = re.split(r'\n(?=tcp |udp |icmp |--- )', trans_text)
        
        for block in blocks:
            if not block.strip():
                continue
                
            first_line_match = re.search(r"^(tcp|udp|icmp|---)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", block)
            if not first_line_match:
                continue
                
            protocol = first_line_match.group(1) if first_line_match.group(1) != "---" else None
            ig_full = first_line_match.group(2)
            il_full = first_line_match.group(3)
            ol_full = first_line_match.group(4) if first_line_match.group(4) != "---" else None
            og_full = first_line_match.group(5) if first_line_match.group(5) != "---" else None
            
            def split_ip_port(ip_port_str):
                if not ip_port_str: return None, None
                parts = ip_port_str.split(':')
                if len(parts) == 2: return parts[0], int(parts[1])
                return parts[0], None
                
            ig_ip, ig_port = split_ip_port(ig_full)
            il_ip, il_port = split_ip_port(il_full)
            ol_ip, ol_port = split_ip_port(ol_full)
            og_ip, og_port = split_ip_port(og_full)
            
            trans_type = "extended" if protocol else "static"
            
            expires = None
            left_match = re.search(r"left (\d{2}):(\d{2}):(\d{2})", block)
            if left_match:
                h, m, s = map(int, left_match.groups())
                expires = h * 3600 + m * 60 + s
                
            use_count = 0
            use_match = re.search(r"use_count:\s*(\d+)", block)
            if use_match:
                use_count = int(use_match.group(1))
                
            flags = None
            flags_match = re.search(r"flags:\s*\n(.*?),\s+use_count", block)
            if flags_match:
                flags = flags_match.group(1).strip()
                
            translations_data.append({
                "host": hostname,
                "protocol": protocol,
                "inside_global_ip": ig_ip,
                "inside_global_port": ig_port,
                "inside_local_ip": il_ip,
                "inside_local_port": il_port,
                "outside_local_ip": ol_ip,
                "outside_local_port": ol_port,
                "outside_global_ip": og_ip,
                "outside_global_port": og_port,
                "translation_type": trans_type,
                "expires_in_seconds": expires,
                "use_count": use_count,
                "flags": flags,
                "raw_line": block.replace("\n", "  ").strip()
            })
            
    return translations_data

# =====================================================================
# HÀM CHÍNH: WORKER XỬ LÝ DỮ LIỆU
# =====================================================================
def process_nat_data(host, file_path, db_cursor):
    """Worker xử lý dữ liệu NAT - Thuật toán Wipe & Replace per Host"""
    if not os.path.exists(file_path):
        print(f"      [-] Worker NAT: Không tìm thấy file tại {file_path}")
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # 1. TẠO BẢN GHI COLLECTION
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_cursor.execute("""
        INSERT INTO t11_info_nat_collection (host, command, started_at, collection_state) 
        VALUES (?, ?, ?, ?)
    """, (host, "NAT Master Sync", start_time, "running"))
    collection_id = db_cursor.lastrowid

    run_sec = extract_section(raw_text, "[ SHOW RUNNING-CONFIG ]")
    stat_sec = extract_section(raw_text, "[ SHOW IP NAT STATISTICS ]")

    # 2. XÓA DỮ LIỆU CŨ CỦA HOST NÀY ĐỂ ĐỒNG BỘ MỚI
    db_cursor.execute("DELETE FROM t11_info_nat_statistics WHERE host = ?", (host,))
    db_cursor.execute("DELETE FROM t11_info_nat_translations WHERE host = ?", (host,))
    db_cursor.execute("DELETE FROM t11_info_nat_dynamic_rules WHERE host = ?", (host,))
    db_cursor.execute("DELETE FROM t11_info_nat_static_mappings WHERE host = ?", (host,))
    db_cursor.execute("DELETE FROM t11_info_nat_pools WHERE host = ?", (host,))
    db_cursor.execute("DELETE FROM t11_info_nat_db WHERE host = ?", (host,))

    count_static = 0
    count_dynamic = 0
    count_pool = 0
    count_trans = 0

    # 3. PARSE RUNNING-CONFIG (POOLS, STATIC, DYNAMIC)
    if run_sec:
        for line in run_sec.splitlines():
            line = line.strip()
            if not line.startswith("ip nat "):
                continue

            # 3a. Parse NAT Pools
            pool_match = re.match(r"^ip nat pool (\S+) (\S+) (\S+)(?: netmask (\S+))?(?: prefix-length (\d+))?", line)
            if pool_match:
                pool_name, start_ip, end_ip, netmask, prefix = pool_match.groups()
                db_cursor.execute("""
                    INSERT INTO t11_info_nat_pools (host, pool_name, start_ip, end_ip, netmask, prefix_length, raw_line)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (host, pool_name, start_ip, end_ip, netmask, prefix, line))
                count_pool += 1
                continue

            # 3b. Parse Static NAT/PAT
            static_match = re.match(r"^ip nat (inside|outside) source static\s+(tcp|udp|icmp)?\s*(\S+)(?:\s+(\d+))?\s+(\S+)(?:\s+(\d+))?(.*?)$", line, re.I)
            if static_match and not " list " in line:
                direction, protocol, local_ip, local_port, global_ip, global_port, remainder = static_match.groups()
                
                nat_type = 'port_forward' if local_port else 'static'
                nat_name = f"STATIC_{local_ip}_{global_ip}"
                if local_port: nat_name += f"_{local_port}"
                
                db_cursor.execute("""
                    INSERT INTO t11_info_nat_db (host, nat_name, nat_type, raw_line) VALUES (?, ?, ?, ?)
                """, (host, nat_name, nat_type, line))
                info_nat_id = db_cursor.lastrowid
                
                remainder_str = remainder.lower() if remainder else ""
                is_extendable = 1 if "extendable" in remainder_str else 0
                no_alias = 1 if "no-alias" in remainder_str else 0
                
                rm_match = re.search(r"route-map\s+(\S+)", remainder_str)
                route_map_name = rm_match.group(1) if rm_match else None
                
                red_match = re.search(r"redundancy\s+(\S+)", remainder_str)
                redundancy_name = red_match.group(1) if red_match else None

                db_cursor.execute("""
                    INSERT INTO t11_info_nat_static_mappings 
                    (host, info_nat_id, inside_local_ip, inside_global_ip, protocol, local_port, global_port, 
                     is_extendable, no_alias, route_map_name, redundancy_name, raw_line)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (host, info_nat_id, local_ip, global_ip, protocol, local_port, global_port, 
                      is_extendable, no_alias, route_map_name, redundancy_name, line))
                count_static += 1
                continue

            # 3c. Parse Dynamic NAT/PAT
            dyn_match = re.match(r"^ip nat (inside|outside) source (list|route-map) (\S+) (pool|interface) (\S+)(?:\s+(overload))?", line, re.I)
            if dyn_match:
                direction, match_type, match_name, trans_type, trans_name, overload_flag = dyn_match.groups()
                
                is_overload = 1 if overload_flag else 0
                nat_type = 'overload' if is_overload else 'dynamic'
                nat_name = f"DYN_{match_name}_{trans_name}"
                
                db_cursor.execute("""
                    INSERT INTO t11_info_nat_db (host, nat_name, nat_type, raw_line) VALUES (?, ?, ?, ?)
                """, (host, nat_name, nat_type, line))
                info_nat_id = db_cursor.lastrowid
                
                db_match_type = 'acl' if match_type.lower() == 'list' else 'route-map'
                acl_name = match_name if db_match_type == 'acl' else None
                route_map_name = match_name if db_match_type == 'route-map' else None
                
                pool_name = trans_name if trans_type.lower() == 'pool' else None
                outside_interface = trans_name if trans_type.lower() == 'interface' else None
                
                # SỬA LẠI ĐÚNG THEO CHECK CONSTRAINT CỦA BẢNG DYNAMIC RULES ('pool' hoặc 'interface')
                rule_trans_type = trans_type.lower()
                
                db_cursor.execute("""
                    INSERT INTO t11_info_nat_dynamic_rules (host, info_nat_id, match_type, acl_name, route_map_name, translation_type, pool_name, outside_interface, overload, raw_line)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (host, info_nat_id, db_match_type, acl_name, route_map_name, rule_trans_type, pool_name, outside_interface, is_overload, line))
                count_dynamic += 1
                continue

    # =====================================================================
    # 4. GỌI HÀM VÀ BƠM TRANSLATIONS VÀO DB
    # =====================================================================
    parsed_translations = parse_nat_translations_verbose(raw_text, host)
    for t in parsed_translations:
        db_cursor.execute("""
            INSERT INTO t11_info_nat_translations 
            (host, protocol, inside_global_ip, inside_global_port, inside_local_ip, inside_local_port, 
             outside_local_ip, outside_local_port, outside_global_ip, outside_global_port, 
             translation_type, expires_in_seconds, use_count, flags, raw_line)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t['host'], t['protocol'], t['inside_global_ip'], t['inside_global_port'], 
            t['inside_local_ip'], t['inside_local_port'], t['outside_local_ip'], 
            t['outside_local_port'], t['outside_global_ip'], t['outside_global_port'], 
            t['translation_type'], t['expires_in_seconds'], t['use_count'], t['flags'], t['raw_line']
        ))
        count_trans += 1

    # =====================================================================
    # 5. PARSE STATISTICS
    # =====================================================================
    if stat_sec:
        total = static = dynamic = extended = peak = hits = misses = expired = dynamic_maps = None
        
        m_total = re.search(r"Total active translations:\s*(\d+)\s*\((\d+)\s*static,\s*(\d+)\s*dynamic;\s*(\d+)\s*extended\)", stat_sec)
        if m_total:
            total, static, dynamic, extended = map(int, m_total.groups())
            
        m_peak = re.search(r"Peak translations:\s*(\d+)", stat_sec)
        if m_peak: peak = int(m_peak.group(1))
        
        m_hits = re.search(r"Hits:\s*(\d+)\s*Misses:\s*(\d+)", stat_sec)
        if m_hits: hits, misses = map(int, m_hits.groups())
        
        m_expired = re.search(r"Expired translations:\s*(\d+)", stat_sec)
        if m_expired: expired = int(m_expired.group(1))
        
        m_dyn_maps = re.search(r"Dynamic mappings:\s*(\d+)", stat_sec)
        if m_dyn_maps:
            dynamic_maps = int(m_dyn_maps.group(1))
        elif "Dynamic mappings:" in stat_sec:
            count_ids = stat_sec.count("[Id: ")
            dynamic_maps = count_ids if count_ids > 0 else 0
        
        if any(x is not None for x in [total, peak, hits]):
            db_cursor.execute("""
                INSERT INTO t11_info_nat_statistics (host, total_active, static_active, dynamic_active, extended_active, peak_translations, hits, misses, expired_translations, dynamic_mappings_count, raw_output)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (host, total or 0, static or 0, dynamic or 0, extended or 0, peak, hits, misses, expired, dynamic_maps, stat_sec))

        current_pool = None
        for line in stat_sec.splitlines():
            line = line.strip()
            m_pool = re.match(r"^pool\s+([^:]+):", line)
            if m_pool:
                current_pool = m_pool.group(1)
                
            if current_pool and "total addresses" in line:
                m_addr = re.search(r"total addresses\s+(\d+),\s*allocated\s+(\d+)", line)
                if m_addr:
                    t_addr = int(m_addr.group(1))
                    a_addr = int(m_addr.group(2))
                    
                    db_cursor.execute("""
                        UPDATE t11_info_nat_pools 
                        SET address_count = ?, allocated_count = ? 
                        WHERE host = ? AND pool_name = ?
                    """, (t_addr, a_addr, host, current_pool))
                    
                    current_pool = None

    # 6. CHỐT COLLECTION
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_cursor.execute("""
        UPDATE t11_info_nat_collection 
        SET completed_at = ?, collection_state = ?, static_count = ?, dynamic_count = ?, translation_count = ?, pool_count = ?
        WHERE collection_id = ?
    """, (end_time, "completed", count_static, count_dynamic, count_trans, count_pool, collection_id))

    return True