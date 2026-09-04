import os
import re
import ipaddress

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

def process_dhcp_data(host, file_path, db_cursor):
    """Worker xử lý DHCP - Dùng ipaddress để map chính xác Subnet"""
    if not os.path.exists(file_path):
        print(f"      [-] Worker DHCP: Không tìm thấy file tại {file_path}")
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    active_pools = [] 
    pool_nets = {} # Dictionary lưu các object IPv4Network để quét subnet

    # =========================================================
    # BƯỚC 1: BÓC TÁCH RUNNING-CONFIG & POOL
    # =========================================================
    db_cursor.execute("DELETE FROM t09_info_dhcp_pool WHERE host = ?", (host,))
    
    run_sec = extract_section(raw_text, "[ SHOW RUNNING-CONFIG ]")
    pool_configs = {}
    if run_sec:
        current_pool = None
        for line in run_sec.splitlines():
            line = line.strip()
            if line.startswith("ip dhcp pool"):
                current_pool = line.split("ip dhcp pool")[1].strip()
                pool_configs[current_pool] = {"network": None, "subnet_mask": None, "prefix_length": 0}
            elif current_pool:
                if line.startswith("network"):
                    parts = line.split()
                    pool_configs[current_pool]['network'] = parts[1]
                    pool_configs[current_pool]['subnet_mask'] = parts[2] if len(parts) > 2 else "255.255.255.0"
                elif line.startswith("host"):
                    parts = line.split()
                    pool_configs[current_pool]['network'] = parts[1]
                    pool_configs[current_pool]['subnet_mask'] = parts[2] if len(parts) > 2 else "255.255.255.255"
                elif line == "!" or (line.startswith("ip ") and not line.startswith("ip dhcp")):
                    current_pool = None

        prefix_map = {"255.255.255.0": 24, "255.255.0.0": 16, "255.0.0.0": 8, "255.255.255.255": 32}
        for p, data in pool_configs.items():
            if data['subnet_mask'] in prefix_map:
                data['prefix_length'] = prefix_map[data['subnet_mask']]
            
            # Khởi tạo object Network để so sánh chuẩn xác IP ở Bước 2
            if data['network'] and data['subnet_mask']:
                try:
                    pool_nets[p] = ipaddress.IPv4Network(f"{data['network']}/{data['subnet_mask']}", strict=False)
                except Exception: pass

    p_sec = extract_section(raw_text, "[ SHOW IP DHCP POOL ]")
    if p_sec:
        try:
            pools = p_sec.split("Pool ")
            for p_chunk in pools:
                if not p_chunk.strip(): continue
                pool_data = {}
                lines = p_chunk.splitlines()
                first_line = lines[0].strip()
                pool_name = first_line.replace(":", "").strip()
                pool_data['pool_name'] = pool_name

                for line in lines[1:]:
                    line = line.strip()
                    if "Utilization mark" in line:
                        match = re.search(r"(\d+)\s*/\s*(\d+)", line)
                        if match:
                            pool_data['high_utilization'], pool_data['low_utilization'] = int(match.group(1)), int(match.group(2))
                    elif "Total addresses" in line:
                        parts = line.split(":")
                        if len(parts) > 1 and parts[1].strip().isdigit(): pool_data['total_addresses'] = int(parts[1].strip())
                    elif "Leased addresses" in line and ":" in line:
                        parts = line.split(":")
                        if len(parts) > 1 and parts[1].strip().isdigit(): pool_data['leased_addresses'] = int(parts[1].strip())
                    elif re.match(r"^\d+\.\d+\.\d+\.\d+", line) and "-" in line:
                        parts = line.split()
                        pool_data['current_index'], pool_data['first_address'], pool_data['last_address'] = parts[0], parts[1], parts[3]

                if 'pool_name' in pool_data:
                    p_name = pool_data['pool_name']
                    cfg = pool_configs.get(p_name, {})
                    network, subnet_mask, prefix_length = cfg.get("network", ""), cfg.get("subnet_mask", ""), cfg.get("prefix_length", 0)

                    total = pool_data.get('total_addresses', 0)
                    leased = pool_data.get('leased_addresses', 0)
                    exc = pool_data.get('excluded_addresses', 0)
                    available = total - leased - exc if total > 0 else 0
                    util_percent = round((leased / total * 100), 2) if total > 0 else 0.0

                    db_cursor.execute("""
                        INSERT INTO t09_info_dhcp_pool (
                            host, pool_name, network, subnet_mask, prefix_length, 
                            total_addresses, leased_addresses, excluded_addresses, 
                            available_addresses, utilization_percent, high_utilization, low_utilization, 
                            pending_event, first_address, last_address, current_index
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (host, p_name, network, subnet_mask, prefix_length, total, leased, exc, available, util_percent, pool_data.get('high_utilization'), pool_data.get('low_utilization'), pool_data.get('pending_event'), pool_data.get('first_address'), pool_data.get('last_address'), pool_data.get('current_index')))
        except Exception as e: print(f"      [-] Lỗi Parse Pool: {e}")

    # =========================================================
    # BƯỚC 2: BÓC TÁCH BINDING (Map chuẩn xác bằng ipaddress + Thêm cột)
    # =========================================================
    db_cursor.execute("DELETE FROM t09_info_dhcp_binding WHERE host = ?", (host,))
    b_sec = extract_section(raw_text, "[ SHOW IP DHCP BINDING ]")
    
    if b_sec:
        try:
            current_binding = None
            for line in b_sec.splitlines():
                original_line = line # Giữ lại dòng gốc cho cột raw_line
                line = line.strip()
                if not line or line.startswith("IP address") or line.startswith("Hardware") or line.startswith("User"): continue
                
                first_line_match = re.match(r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+(?P<identifier>[a-fA-F0-9\.]+)\s+(?P<lease>.+?)\s+(?P<type>\S+)$", line, re.I)
                
                if first_line_match:
                    if current_binding:
                        ip_val = current_binding['ip']
                        raw_id = current_binding['identifier']
                        lease_val = current_binding['lease']
                        type_val = current_binding['type']
                        raw_line_val = current_binding['raw_line']
                        
                        client_id_val = hw_addr_val = username_val = None
                        clean_dot_count = raw_id.count('.')
                        hex_str = raw_id.replace('.', '')
                        
                        decoded_user = None
                        try:
                            if len(hex_str) % 2 == 0 and len(hex_str) > 12:
                                ascii_str = bytes.fromhex(hex_str).decode('ascii')
                                if ascii_str.isprintable() and any(c.isalpha() for c in ascii_str):
                                    decoded_user = ascii_str
                        except Exception: pass

                        if decoded_user: username_val = decoded_user
                        elif clean_dot_count == 2 and len(hex_str) == 12: hw_addr_val = raw_id
                        else: client_id_val = raw_id

                        # LOGIC ÁNH XẠ POOL MỚI: Toán học Subnet
                        assigned_pool = None
                        try:
                            ip_obj = ipaddress.IPv4Address(ip_val)
                            for p_name, net_obj in pool_nets.items():
                                if ip_obj in net_obj:
                                    assigned_pool = p_name
                                    break
                        except Exception: pass

                        # LOGIC ĐIỀN DỮ LIỆU GIẢ LẬP ĐỂ TEST
                        binding_state_val = "Active"
                        interface_val = "Virtual-Access (PPPoE)" if type_val.lower() == "on-demand" else "N/A"

                        db_cursor.execute(
                            """INSERT INTO t09_info_dhcp_binding 
                            (host, pool_name, ip_address, client_id, hardware_address, username, lease_expiration, lease_type, binding_state, interface_name, raw_line) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                            (host, assigned_pool, ip_val, client_id_val, hw_addr_val, username_val, lease_val, type_val, binding_state_val, interface_val, raw_line_val)
                        )
                    
                    d = first_line_match.groupdict()
                    current_binding = {
                        'ip': d['ip'], 'identifier': d['identifier'], 
                        'lease': d['lease'].strip(), 'type': d['type'].strip(),
                        'raw_line': original_line # Bắt đầu lưu lại raw line
                    }
                elif current_binding and re.match(r"^[a-fA-F0-9\.]+$", line):
                    current_binding['identifier'] += line
                    current_binding['raw_line'] += f"\n{original_line}" # Cộng dồn dòng nếu bị ngắt dòng
            
            # Xử lý bản ghi cuối cùng trong vòng lặp
            if current_binding:
                ip_val = current_binding['ip']
                raw_id = current_binding['identifier']
                lease_val = current_binding['lease']
                type_val = current_binding['type']
                raw_line_val = current_binding['raw_line']
                
                client_id_val = hw_addr_val = username_val = None
                clean_dot_count = raw_id.count('.')
                hex_str = raw_id.replace('.', '')
                
                decoded_user = None
                try:
                    if len(hex_str) % 2 == 0 and len(hex_str) > 12:
                        ascii_str = bytes.fromhex(hex_str).decode('ascii')
                        if ascii_str.isprintable() and any(c.isalpha() for c in ascii_str):
                            decoded_user = ascii_str
                except Exception: pass

                if decoded_user: username_val = decoded_user
                elif clean_dot_count == 2 and len(hex_str) == 12: hw_addr_val = raw_id
                else: client_id_val = raw_id

                assigned_pool = None
                try:
                    ip_obj = ipaddress.IPv4Address(ip_val)
                    for p_name, net_obj in pool_nets.items():
                        if ip_obj in net_obj:
                            assigned_pool = p_name
                            break
                except Exception: pass

                binding_state_val = "Active"
                interface_val = "Virtual-Access (PPPoE)" if type_val.lower() == "on-demand" else "N/A"

                db_cursor.execute(
                    """INSERT INTO t09_info_dhcp_binding 
                    (host, pool_name, ip_address, client_id, hardware_address, username, lease_expiration, lease_type, binding_state, interface_name, raw_line) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                    (host, assigned_pool, ip_val, client_id_val, hw_addr_val, username_val, lease_val, type_val, binding_state_val, interface_val, raw_line_val)
                )
        except Exception as e: print(f"      [-] Lỗi Parse Binding thông minh: {e}")

    # =========================================================
    # BƯỚC 3: BÓC TÁCH CONFLICT, SERVER STATS, DATABASE (Giữ nguyên)
    # =========================================================
    db_cursor.execute("DELETE FROM t09_info_dhcp_conflict WHERE host = ?", (host,))
    c_sec = extract_section(raw_text, "[ SHOW IP DHCP CONFLICT ]")
    if c_sec:
        try:
            for match in re.finditer(r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+(?P<method>Ping|Gratuitous ARP)\s+(?P<time>.*?)(?:\s+VRF\s+\S+)?\s*$", c_sec, re.M | re.I):
                d = match.groupdict()
                db_cursor.execute("INSERT INTO t09_info_dhcp_conflict (host, ip_address, detection_method, detection_time) VALUES (?, ?, ?, ?)", (host, d['ip'], d['method'].strip(), d['time'].strip()))
        except Exception: pass

    db_cursor.execute("DELETE FROM t09_info_dhcp_server_statistics WHERE host = ?", (host,))
    s_sec = extract_section(raw_text, "[ SHOW IP DHCP SERVER STATISTICS ]")
    if s_sec:
        try:
            stats = {}
            for line in s_sec.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[-1].isdigit():
    # Thêm .replace(":", "") để lọc bỏ dấu hai chấm
                    key = " ".join(parts[:-1]).replace(":", "").strip().lower() 
                    stats[key] = int(parts[-1])
            db_cursor.execute("""
                INSERT INTO t09_info_dhcp_server_statistics (
                    host, memory_usage, address_pools, database_agents, automatic_bindings, manual_bindings, 
                    expired_bindings, malformed_messages, dhcp_discover_received, dhcp_offer_sent, 
                    dhcp_request_received, dhcp_decline_received, dhcp_ack_sent, dhcp_nak_sent, 
                    dhcp_release_received, dhcp_inform_received
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (host, stats.get('memory usage', 0), stats.get('address pools', 0), stats.get('database agents', 0), stats.get('automatic bindings', 0), stats.get('manual bindings', 0), stats.get('expired bindings', 0), stats.get('malformed messages', 0), stats.get('dhcpdiscover', 0), stats.get('dhcpoffer', 0), stats.get('dhcprequest', 0), stats.get('dhcpdecline', 0), stats.get('dhcpack', 0), stats.get('dhcpnak', 0), stats.get('dhcprelease', 0), stats.get('dhcpinform', 0)))
        except Exception: pass

    db_cursor.execute("DELETE FROM t09_info_dhcp_database WHERE host = ?", (host,))
    d_sec = extract_section(raw_text, "[ SHOW IP DHCP DATABASE ]")
    if d_sec:
        try:
            db_data = {}
            for line in d_sec.splitlines():
                if ":" in line:
                    key, val = map(str.strip, line.split(":", 1))
                    if "URL" in key: db_data['url'] = val
                    elif "Read" in key: db_data['read'] = val
                    elif "Written" in key: db_data['written'] = val
                    elif "Status" in key: db_data['status'] = val
                    elif "Delay" in key: db_data['delay'] = int(val.split()[0])
                    elif "Timeout" in key: db_data['timeout'] = int(val.split()[0])
            if 'url' in db_data:
                db_cursor.execute("INSERT INTO t09_info_dhcp_database (host, database_url, write_delay_seconds, timeout_seconds, last_write_time, last_read_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (host, db_data.get('url'), db_data.get('delay'), db_data.get('timeout'), db_data.get('written'), db_data.get('read'), db_data.get('status')))
        except Exception: pass

    return True