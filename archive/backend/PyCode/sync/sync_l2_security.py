import os
import re
from backend.PyCode.share.config import get_db_connection, DB_TABLES, STATE_DIR

# =====================================================================
# KÉO TÊN BẢNG TỪ SSoT CỦA SẾP
# =====================================================================
TBL_SEC_GLOBAL = DB_TABLES["l2_security"]["global"]
TBL_DHCP_TRUST = DB_TABLES["l2_security"]["dhcp_trust"]
TBL_PORT_SEC = DB_TABLES["l2_security"]["port_sec"]
TBL_MAC_TABLE = DB_TABLES["l2_security"]["mac_table"]
TBL_IFACE = DB_TABLES["l2_interfaces"]["main"]

def sync_l2_security_worker(host_ip: str):
    """
    Bóc tách cấu hình L2 Security (DHCP Snooping, DAI, Port Security, MAC Table)
    từ file running-config và đẩy ngược vào Database Letos.
    """
    file_path = os.path.join(STATE_DIR, f"{host_ip}_running.txt")
    if not os.path.exists(file_path):
        print(f"[-] [SYNC SECURITY] Không tìm thấy file {file_path}")
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # =====================================================================
    # 1. BÓC TÁCH DHCP SNOOPING VÀ DAI (GLOBAL & VLAN)
    # =====================================================================
    dhcp_snoop_match = re.search(r"={5,}\s*\[\s*SHOW IP DHCP SNOOPING\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
    dai_match = re.search(r"={5,}\s*\[\s*SHOW IP ARP INSPECTION\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_text, re.DOTALL | re.IGNORECASE)

    dhcp_vlans = set()
    trusted_ports = []
    dai_vlans = set()

    if dhcp_snoop_match:
        dhcp_text = dhcp_snoop_match.group(1)
        # Quét VLAN bật DHCP Snooping
        vlan_line = re.search(r"DHCP snooping is configured on following VLANs:\n([\d,\-\s]+)", dhcp_text)
        if vlan_line:
            v_list = vlan_line.group(1).replace("\n", "").split(",")
            for v in v_list:
                if v.strip().isdigit(): dhcp_vlans.add(int(v.strip()))
        
        # Quét Trust Port
        trust_lines = re.findall(r"^(GigabitEthernet[\d/]+|FastEthernet[\d/]+|TenGigabitEthernet[\d/]+|Eth[\d/]+)\s+yes", dhcp_text, re.MULTILINE | re.IGNORECASE)
        trusted_ports.extend([p.strip() for p in trust_lines])

    if dai_match:
        dai_text = dai_match.group(1)
        # Quét VLAN bật DAI (nhìn vào bảng Vlan Configuration)
        dai_lines = re.findall(r"^\s*(\d+)\s+Enabled", dai_text, re.MULTILINE)
        for v in dai_lines: dai_vlans.add(int(v))

    # Gom chung tất cả các VLAN có bật ít nhất 1 tính năng
    all_sec_vlans = dhcp_vlans.union(dai_vlans)

    # =====================================================================
    # 2. BÓC TÁCH PORT SECURITY CHI TIẾT DƯỚI CỔNG (VÁ LỖI STICKY)
    # =====================================================================
    port_sec_data = {}
    
    # Kéo khối SHOW RUNNING-CONFIG ra trước để soi lệnh gốc
    run_conf_match = re.search(r"={5,}\s*\[\s*SHOW RUNNING-CONFIG\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
    run_conf_text = run_conf_match.group(1) if run_conf_match else ""

    port_sec_blocks = re.findall(r"={5,}\s*\[\s*SHOW PORT-SECURITY INTERFACE (.*?)\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
    
    for iface_name, block_text in port_sec_blocks:
        if "Port Security              : Enabled" in block_text:
            max_mac = re.search(r"Maximum MAC Addresses\s*:\s*(\d+)", block_text)
            violation = re.search(r"Violation Mode\s*:\s*(Shutdown|Restrict|Protect)", block_text, re.IGNORECASE)
            aging_time = re.search(r"Aging Time\s*:\s*(\d+) mins", block_text)
            aging_type = re.search(r"Aging Type\s*:\s*(Absolute|Inactivity)", block_text, re.IGNORECASE)
            
            # --- LOGIC MỚI: SOI THẲNG VÀO RUNNING-CONFIG ĐỂ BẮT STICKY ---
            sticky_status = 0
            if run_conf_text:
                # Quét đúng khối cấu hình của cổng đang xét (VD: interface GigabitEthernet0/3)
                iface_pattern = r"^interface\s+" + re.escape(iface_name.strip()) + r"\n(.*?)(?=^!|^interface|\Z)"
                iface_run_match = re.search(iface_pattern, run_conf_text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
                
                if iface_run_match:
                    iface_config = iface_run_match.group(1)
                    # Chỉ cần dòng lệnh chứa chữ "mac-address sticky" xuất hiện là xác nhận bật (1)
                    if re.search(r"switchport port-security mac-address sticky", iface_config, re.IGNORECASE):
                        sticky_status = 1

            port_sec_data[iface_name.strip()] = {
                "max_mac": int(max_mac.group(1)) if max_mac else 1,
                "violation": violation.group(1).lower() if violation else "shutdown",
                "aging_time": int(aging_time.group(1)) if aging_time else 0,
                "aging_type": aging_type.group(1).lower() if aging_type else "absolute",
                "sticky": sticky_status
            }

# =====================================================================
    # 3. BÓC TÁCH BẢNG MAC ADDRESS (TỔNG HỢP)
    # =====================================================================
    mac_records = []
    
    # 3.1 Quét bảng MAC tổng (Lấy toàn bộ DYNAMIC và STATIC cơ bản)
    mac_main_match = re.search(r"={5,}\s*\[\s*SHOW MAC ADDRESS-TABLE\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
    if mac_main_match:
        # Bắt các dòng dạng: 99    5000.0002.0000    DYNAMIC     Gi0/0
        main_lines = re.findall(r"^\s*(\d+|All)\s+([0-9a-fA-F.]+)\s+(STATIC|DYNAMIC)\s+(\S+)", mac_main_match.group(1), re.MULTILINE | re.IGNORECASE)
        for v_id_str, mac, m_type, port in main_lines:
            if v_id_str.lower() == "all": continue # Bỏ qua MAC Multicast/CPU
            mac_records.append({"vlan_id": int(v_id_str), "mac_addr": mac.lower(), "mac_type": m_type.lower(), "port": port})

    # 3.2 Quét bảng Port-Security để "Nâng cấp" loại MAC (từ static thành secure/sticky)
    mac_secure_match = re.search(r"={5,}\s*\[\s*SHOW PORT-SECURITY ADDRESS\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
    if mac_secure_match:
        # Bắt các dòng dạng: 1    5000.000d.0002    SecureSticky                  Gi0/1
        sec_lines = re.findall(r"^\s*(\d+)\s+([0-9a-fA-F.]+)\s+(SecureSticky|SecureConfigured|SecureDynamic)\s+(\S+)", mac_secure_match.group(1), re.MULTILINE | re.IGNORECASE)
        for v_id, mac, m_type, port in sec_lines:
            mapped_type = "secure"
            if m_type.lower() == "securesticky": mapped_type = "sticky"
            elif m_type.lower() == "securedynamic": mapped_type = "dynamic"
            mac_records.append({"vlan_id": int(v_id), "mac_addr": mac.lower(), "mac_type": mapped_type, "port": port})

    # =====================================================================
    # ĐỔ DỮ LIỆU VÀO DATABASE
    # =====================================================================
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(f"SELECT id, if_name FROM {TBL_IFACE} WHERE host = ?", (host_ip,))
        iface_map = {}
        for row in c.fetchall():
            full_name = row[1]
            iface_map[full_name.lower()] = row[0]
            if full_name.startswith("GigabitEthernet"):
                iface_map[full_name.replace("GigabitEthernet", "Gi").lower()] = row[0]
            elif full_name.startswith("FastEthernet"):
                iface_map[full_name.replace("FastEthernet", "Fa").lower()] = row[0]

        # 1. Đồng bộ t06_security_l2
        c.execute(f"DELETE FROM {TBL_SEC_GLOBAL} WHERE host = ?", (host_ip,))
        for vlan in all_sec_vlans:
            c.execute(f"INSERT INTO {TBL_SEC_GLOBAL} (host, vlan_id, dhcp_snooping, dai_enabled) VALUES (?, ?, ?, ?)", 
                      (host_ip, vlan, 1 if vlan in dhcp_vlans else 0, 1 if vlan in dai_vlans else 0))

        # 2. Đồng bộ t06_dhcp_trust_ports
        c.execute(f"DELETE FROM {TBL_DHCP_TRUST} WHERE host = ?", (host_ip,))
        for port in trusted_ports:
            c.execute(f"INSERT INTO {TBL_DHCP_TRUST} (host, if_name) VALUES (?, ?)", (host_ip, port))

        # 3. Đồng bộ t06_iface_port_security
        for iface_name, p_data in port_sec_data.items():
            i_id = iface_map.get(iface_name.lower())
            if i_id:
                c.execute(f"DELETE FROM {TBL_PORT_SEC} WHERE iface_id = ?", (i_id,))
                c.execute(f"""
                    INSERT INTO {TBL_PORT_SEC} (iface_id, max_mac, violation, sticky, aging_type, aging_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (i_id, p_data["max_mac"], p_data["violation"], p_data["sticky"], p_data["aging_type"], p_data["aging_time"]))

        # 4. Đồng bộ t06_iface_mac_table
        c.execute(f"DELETE FROM {TBL_MAC_TABLE} WHERE iface_id IN (SELECT id FROM {TBL_IFACE} WHERE host = ?)", (host_ip,))
        
        for mac in mac_records:
            i_id = iface_map.get(mac["port"].lower())
            if i_id:
                # SỬ DỤNG 'INSERT OR REPLACE' ĐỂ GHI ĐÈ LOGIC MAC (TỪ STATIC -> SECURE/STICKY) MÀ KHÔNG BỊ LỖI CONSTRAINT
                c.execute(f"""
                    INSERT OR REPLACE INTO {TBL_MAC_TABLE} (iface_id, mac_addr, vlan_id, mac_type)
                    VALUES (?, ?, ?, ?)
                """, (i_id, mac["mac_addr"], mac["vlan_id"], mac["mac_type"]))

        conn.commit()
        print(f"  [+] [SYNC SECURITY] Đồng bộ thành công cấu hình bảo mật L2 cho {host_ip}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"  [-] LỖI DATABASE KHI SYNC SECURITY ({host_ip}): {e}")
        return False
    finally:
        conn.close()