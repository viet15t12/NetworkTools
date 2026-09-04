import os
import re
import sqlite3
from backend.PyCode.share.config import get_db_connection, DB_TABLES, STATE_DIR

TBL_IFACE_L2 = DB_TABLES["l2_interfaces"]["main"]
TBL_IFACE_ACC = DB_TABLES["l2_interfaces"]["access"]
TBL_IFACE_TRUNK = DB_TABLES["l2_interfaces"]["trunk"]
TBL_ETHERCHANNEL = DB_TABLES["l2_etherchannel"]["main"]

def extract_section(raw_text, section_keyword):
    if section_keyword not in raw_text: return ""
    content = raw_text.split(section_keyword)[1].lstrip(" =\n")
    if "[ SHOW" in content: content = content.split("[ SHOW")[0]
    return content

def normalize_interface_name(name: str) -> str:
    if not name: return ""
    name = name.strip()
    if re.match(r'^Gi\d', name, re.IGNORECASE): return re.sub(r'^Gi', 'GigabitEthernet', name, count=1, flags=re.IGNORECASE)
    if re.match(r'^Fa\d', name, re.IGNORECASE): return re.sub(r'^Fa', 'FastEthernet', name, count=1, flags=re.IGNORECASE)
    if re.match(r'^Te\d', name, re.IGNORECASE): return re.sub(r'^Te', 'TenGigabitEthernet', name, count=1, flags=re.IGNORECASE)
    if re.match(r'^Po\d', name, re.IGNORECASE): return re.sub(r'^Po', 'Port-channel', name, count=1, flags=re.IGNORECASE)
    if re.match(r'^Eth\d', name, re.IGNORECASE): return re.sub(r'^Eth', 'Ethernet', name, count=1, flags=re.IGNORECASE)
    return name

def sync_l2_interface_worker(host_ip: str):
    # ĐÃ SỬA ĐƯỜNG DẪN
    file_path = os.path.join(STATE_DIR, f"{host_ip}_running.txt")
    if not os.path.exists(file_path):
        print(f"[-] [SYNC L2 IFACE] Không tìm thấy file {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # BÓC TÁCH RIÊNG TỪNG SECTION
    status_sec = extract_section(raw_text, "[ SHOW INTERFACES STATUS ]")
    trunk_sec = extract_section(raw_text, "[ SHOW INTERFACES TRUNK ]")
    po_sec = extract_section(raw_text, "[ SHOW ETHERCHANNEL SUMMARY ]")

    intf_status, intf_trunk, etherchannel = [], [], []

    if status_sec:
        status_pattern = re.compile(r"^([a-zA-Z]+\d+(?:\/\d+)*)\s+(.*?)\s+(connected|notconnect|disabled|err-disabled)\s+(trunk|routed|unassigned|\d+)\s+(auto|a-full|full|a-half|half)\s+(auto|a-\d+|\d+)", re.MULTILINE | re.IGNORECASE)
        for m in status_pattern.finditer(status_sec):
            intf_status.append({
                "port": m.group(1), "name": m.group(2).strip(), "status": m.group(3),
                "vlan": m.group(4), "duplex": m.group(5), "speed": m.group(6)
            })

    if trunk_sec:
        trunk_pattern = re.compile(r"^([a-zA-Z]+\d+(?:\/\d+)*)\s+(on|desirable|auto|nonegotiate)\s+(802\.1q|isl|n-802\.1q|n-isl)\s+(trunking)\s+(\d+)", re.MULTILINE | re.IGNORECASE)
        for m in trunk_pattern.finditer(trunk_sec):
            raw_encap = m.group(3).lower()
            db_encap = "dot1q" if "802.1q" in raw_encap else ("isl" if "isl" in raw_encap else raw_encap)
            intf_trunk.append({
                "port": m.group(1), "encapsulation": db_encap, 
                "native_vlan": m.group(5), "vlans_allowed": "all"
            })

    if po_sec:
        po_pattern = re.compile(r"^(\d+)\s+(Po\d+)\((.*?)\)\s+(LACP|PAgP|-)(.*)", re.MULTILINE | re.IGNORECASE)
        for m in po_pattern.finditer(po_sec):
            flags = m.group(3)
            ports_raw = m.group(5)
            raw_protocol = m.group(4).lower()
            if raw_protocol == "-":
                raw_protocol = "static"
                po_mode = "on"
            elif raw_protocol == "lacp":
                po_mode = "active"
            elif raw_protocol == "pagp":
                po_mode = "desirable"
            
            etherchannel.append({
                "po_name": m.group(2), "status": "up" if "U" in flags else "down", 
                "protocol": raw_protocol, "mode": po_mode,
                "ports": re.findall(r"([a-zA-Z]+\d+(?:\/\d+)*)\([A-Za-z]+\)", ports_raw)
            })

    # (Phần 2 đổ DB giữ nguyên)
    conn = get_db_connection()
    c = conn.cursor()
    try:
        for po in etherchannel:
            po_num = po["po_name"].replace("Po", "")
            members = ",".join([normalize_interface_name(p) for p in po["ports"]])
            c.execute(f"SELECT id FROM {TBL_ETHERCHANNEL} WHERE host=? AND po_number=?", (host_ip, po_num))
            if c.fetchone():
                c.execute(f"UPDATE {TBL_ETHERCHANNEL} SET protocol=?, mode=?, member_ports=?, status=? WHERE host=? AND po_number=?", (po["protocol"], po["mode"], members, po["status"], host_ip, po_num))
            else:
                c.execute(f"INSERT INTO {TBL_ETHERCHANNEL} (host, po_number, protocol, member_ports, status, mode) VALUES (?, ?, ?, ?, ?, ?)", (host_ip, po_num, po["protocol"], members, po["status"], po["mode"]))

        for intf in intf_status:
            if_name = normalize_interface_name(intf["port"])
            speed = intf["speed"].replace("a-", "")
            duplex = intf["duplex"].replace("a-", "")
            admin_status = "down" if intf["status"] == "disabled" else "up"
            oper_status = "up" if intf["status"] == "connected" else ("err-disabled" if intf["status"] == "err-disabled" else "down")
            mode = "trunk" if intf["vlan"].lower() == "trunk" else ("routed" if intf["vlan"].lower() == "routed" else "access")
            
            c.execute(f"SELECT id FROM {TBL_IFACE_L2} WHERE host=? AND if_name=?", (host_ip, if_name))
            row = c.fetchone()
            if row:
                iface_id = row[0]
                c.execute(f"UPDATE {TBL_IFACE_L2} SET description=?, mode=?, admin_status=?, oper_status=?, speed=?, duplex=?, updated_at=datetime('now') WHERE id=?", 
                          (intf["name"], mode, admin_status, oper_status, speed, duplex, iface_id))
            else:
                c.execute(f"INSERT INTO {TBL_IFACE_L2} (host, if_name, description, mode, admin_status, oper_status, speed, duplex) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                          (host_ip, if_name, intf["name"], mode, admin_status, oper_status, speed, duplex))
                iface_id = c.lastrowid
            
            if mode == "access" and intf["vlan"].isdigit():
                c.execute(f"SELECT iface_id FROM {TBL_IFACE_ACC} WHERE iface_id=?", (iface_id,))
                if c.fetchone(): c.execute(f"UPDATE {TBL_IFACE_ACC} SET access_vlan=? WHERE iface_id=?", (intf["vlan"], iface_id))
                else: c.execute(f"INSERT INTO {TBL_IFACE_ACC} (iface_id, access_vlan) VALUES (?, ?)", (iface_id, intf["vlan"]))
                    
        for trunk in intf_trunk:
            t_port = normalize_interface_name(trunk["port"])
            c.execute(f"SELECT id FROM {TBL_IFACE_L2} WHERE host=? AND if_name=?", (host_ip, t_port))
            t_row = c.fetchone()
            if t_row:
                iface_id = t_row[0]
                c.execute(f"SELECT iface_id FROM {TBL_IFACE_TRUNK} WHERE iface_id=?", (iface_id,))
                if c.fetchone():
                    c.execute(f"UPDATE {TBL_IFACE_TRUNK} SET allowed_vlans=?, native_vlan=?, encapsulation=? WHERE iface_id=?", (trunk["vlans_allowed"], trunk["native_vlan"], trunk["encapsulation"], iface_id))
                else:
                    c.execute(f"INSERT INTO {TBL_IFACE_TRUNK} (iface_id, allowed_vlans, native_vlan, encapsulation) VALUES (?, ?, ?, ?)", (iface_id, trunk["vlans_allowed"], trunk["native_vlan"], trunk["encapsulation"]))
        
        conn.commit()
        print(f"  [+] [L2 IFACE] Đồng bộ thành công cho {host_ip}")
    except Exception as e:
        conn.rollback()
        print(f"  [-] LỖI DATABASE KHI SYNC L2 INTERFACE ({host_ip}): {e}")
    finally:
        conn.close()