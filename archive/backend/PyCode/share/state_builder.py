import os
import json
from backend.PyCode.share.config import get_db_connection, DB_TABLES, L2_BACKUP_DIR, L3_BACKUP_DIR

# ================= MAP CÁC BẢNG TỪ SINGLE SOURCE OF TRUTH =================
TBL_VLAN = DB_TABLES["l2_vlan"]["main"]
TBL_IFACE = DB_TABLES["l2_interfaces"]["main"]
TBL_ACC = DB_TABLES["l2_interfaces"]["access"]
TBL_TRUNK = DB_TABLES["l2_interfaces"]["trunk"]
TBL_PO = DB_TABLES["l2_etherchannel"]["main"]
TBL_STP_GLOBAL = DB_TABLES["l2_stp"]["global"]
TBL_STP_IFACE = DB_TABLES["l2_stp"]["interface"]
TBL_VTP_DOMAINS = DB_TABLES["l2_vtp"]["domains"]
TBL_VTP_SWITCHES = DB_TABLES["l2_vtp"]["switches"]
TBL_VTP_MODES = DB_TABLES["l2_vtp"]["modes"]

# Map thêm các bảng Security & Traffic Control để tránh hardcode
TBL_SEC_GLOBAL = DB_TABLES.get("l2_security", {}).get("global", "t06_security_global")
TBL_SEC_DHCP = DB_TABLES.get("l2_security", {}).get("dhcp_trust", "t06_dhcp_snooping_trust")
TBL_SEC_PORT = DB_TABLES.get("l2_security", {}).get("port_sec", "t06_port_security")
TBL_SEC_MAC = DB_TABLES.get("l2_security", {}).get("mac_table", "t06_mac_address_table")

TBL_TC_STORM = DB_TABLES.get("l2_traffic_control", {}).get("storm_control", "t06_iface_storm_control")
TBL_TC_QOS = DB_TABLES.get("l2_traffic_control", {}).get("qos", "t06_iface_qos")


# ================= CÁC HÀM XÂY DỰNG TRẠNG THÁI =================

def build_vlan_state(host, c):
    c.execute(f"SELECT vlan_id, vlan_name, state FROM {TBL_VLAN} WHERE host = ?", (host,))
    records = c.fetchall()
    return [{"vlan_id": r[0], "vlan_name": r[1], "state": r[2]} for r in records]

def build_interface_state(host, c):
    c.execute(f"""
        SELECT i.if_name, i.description, i.mode, i.admin_status, i.speed, i.duplex,
               a.access_vlan, a.voice_vlan, 
               t.allowed_vlans, t.native_vlan, t.encapsulation, t.pruning_vlans
        FROM {TBL_IFACE} i
        LEFT JOIN {TBL_ACC} a ON i.id = a.iface_id
        LEFT JOIN {TBL_TRUNK} t ON i.id = t.iface_id
        WHERE i.host = ?
    """, (host,))
    iface_records = c.fetchall()
    
    c.execute(f"SELECT po_number, protocol, mode, member_ports FROM {TBL_PO} WHERE host = ?", (host,))
    po_records = c.fetchall()

    full_interfaces = []
    for r in iface_records:
        iface_dict = {
            "if_name": r[0], "description": r[1], "mode": r[2], "admin_status": r[3], 
            "speed": r[4], "duplex": r[5], "access_vlan": r[6], "voice_vlan": r[7],
            "allowed_vlans": r[8], "native_vlan": r[9], "encapsulation": r[10],
            "pruning_vlans": r[11],
            "channel_group": "None", "channel_protocol": "None", "channel_group_mode": "None"
        }
        for po_num, po_proto, po_mode, members in po_records:
            if members:
                # Strip khoảng trắng tránh lỗi so khớp chuỗi
                member_list = [m.strip() for m in members.split(',')]
                if iface_dict["if_name"] in member_list:
                    iface_dict["channel_group"] = po_num
                    iface_dict["channel_protocol"] = po_proto if po_proto != 'static' else 'None'
                    iface_dict["channel_group_mode"] = po_mode
                    break 
        full_interfaces.append(iface_dict)
    return full_interfaces

def build_stp_state(host, c):
    c.execute(f"SELECT vlan_id, stp_mode, priority, root_role FROM {TBL_STP_GLOBAL} WHERE host = ?", (host,))
    global_records = c.fetchall()
    
    c.execute(f"""
        SELECT i.if_name, s.portfast, s.bpduguard, s.bpdufilter, s.root_guard, s.loop_guard
        FROM {TBL_STP_IFACE} s
        JOIN {TBL_IFACE} i ON s.iface_id = i.id
        WHERE i.host = ? AND i.if_name NOT IN ('GigabitEthernet0/0', 'Gi0/0', 'g0/0')
    """, (host,))
    iface_records = c.fetchall()

    return {
        "global": [{"vlan_id": r[0], "stp_mode": r[1], "priority": r[2], "root_role": r[3]} for r in global_records],
        "interfaces": [{"if_name": r[0], "portfast": r[1], "bpduguard": r[2], "bpdufilter": r[3], "root_guard": r[4], "loop_guard": r[5]} for r in iface_records]
    }

def build_vtp_state(host, c):
    c.execute(f"""
        SELECT d.domain_name, d.version, d.password_type, d.password_value, s.pruning, m.mode, m.primary_server
        FROM {TBL_VTP_SWITCHES} s
        JOIN {TBL_VTP_DOMAINS} d ON s.vtp_domain_id = d.vtp_domain_id
        LEFT JOIN {TBL_VTP_MODES} m ON s.vtp_switch_id = m.vtp_switch_id AND m.database_type = 'vlan'
        WHERE s.host = ?
    """, (host,))
    rec = c.fetchone()
    if not rec: return {}
    return {
        "domain_name": rec[0], "version": rec[1], "password_type": rec[2],
        "password_value": rec[3], "pruning": rec[4], 
        "mode": rec[5] or "transparent",
        "primary_server": rec[6] if rec[6] is not None else 0
    }

def build_security_state(host, c):
    c.execute(f"SELECT vlan_id, dhcp_snooping, dai_enabled FROM {TBL_SEC_GLOBAL} WHERE host = ?", (host,))
    global_records = c.fetchall()
    sec_state = {"global_sec": [{"vlan_id": gr[0], "dhcp_snooping": gr[1], "dai_enabled": gr[2]} for gr in global_records], "interfaces": []}

    c.execute(f"""
        SELECT i.if_name, t.id, p.max_mac, p.violation, p.sticky, p.aging_type, p.aging_time, i.id
        FROM {TBL_IFACE} i
        LEFT JOIN {TBL_SEC_DHCP} t ON i.if_name = t.if_name AND i.host = t.host
        LEFT JOIN {TBL_SEC_PORT} p ON i.id = p.iface_id
        WHERE i.host = ? AND (t.id IS NOT NULL OR p.iface_id IS NOT NULL)
    """, (host,))
    iface_records = c.fetchall()

    c.execute(f"""
        SELECT m.iface_id, m.mac_addr, m.vlan_id, m.mac_type
        FROM {TBL_SEC_MAC} m
        JOIN {TBL_IFACE} i ON m.iface_id = i.id WHERE i.host = ?
    """, (host,))
    mac_dict = {}
    for m in c.fetchall():
        mac_dict.setdefault(m[0], []).append({"mac_addr": m[1], "vlan_id": m[2], "mac_type": m[3]})

    for r in iface_records:
        sec_state["interfaces"].append({
            "if_name": r[0], "is_trusted": 1 if r[1] else 0, "max_mac": r[2], "violation": r[3],
            "sticky": r[4], "aging_type": r[5], "aging_time": r[6], "static_macs": mac_dict.get(r[7], []) 
        })
    return sec_state

def build_traffic_control_state(host, c):
    c.execute(f"""
        SELECT i.if_name, sc.bc_level, sc.mc_level, sc.uc_level, sc.action,
               q.trust_mode, q.cos_value, q.dscp_value, q.policy_in, q.policy_out
        FROM {TBL_IFACE} i
        LEFT JOIN {TBL_TC_STORM} sc ON i.id = sc.iface_id
        LEFT JOIN {TBL_TC_QOS} q ON i.id = q.iface_id
        WHERE i.host = ? AND (sc.iface_id IS NOT NULL OR q.iface_id IS NOT NULL)
    """, (host,))
    records = c.fetchall()
    
    tc_interfaces = []
    for r in records:
        if_name, bc_lvl, mc_lvl, uc_lvl, action, trust, cos, dscp, pol_in, pol_out = r
        entry = {"if_name": if_name}
        entry["storm_control"] = {"bc_level": bc_lvl, "mc_level": mc_lvl, "uc_level": uc_lvl, "action": action} if bc_lvl is not None else None
        entry["qos"] = {"trust_mode": trust or "none", "cos_value": cos or 0, "dscp_value": dscp or 0, "policy_in": pol_in or "", "policy_out": pol_out or ""} if (trust is not None or cos != 0 or dscp != 0 or pol_in or pol_out) else None
        tc_interfaces.append(entry)
    return tc_interfaces

def build_svi_state(host, c):
    tbl_l3_global = DB_TABLES.get("l3_switch", {}).get("global", "t06_switch_l3_config")
    tbl_svi = DB_TABLES.get("l3_switch", {}).get("svi", "t06_svi_interface")
    
    c.execute(f"SELECT ip_routing FROM {tbl_l3_global} WHERE host = ?", (host,))
    l3_global = c.fetchone()
    
    c.execute(f"SELECT vlan_id, ip_address, subnet_mask, shutdown, success FROM {tbl_svi} WHERE host = ? AND success IN (0, 1, -1)", (host,))
    svi_records = c.fetchall()
    
    return {
        "l3_config": {"ip_routing": l3_global[0] if l3_global else 0},
        "svis": [{"vlan_id": r[0], "ip_address": r[1], "subnet_mask": r[2], "shutdown": r[3], "success": r[4]} for r in svi_records]
    }

# ================= HÀM CHÍNH =================

def update_snapshot(host_ip: str, feature: str) -> bool:
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        if feature == "vlan": data = build_vlan_state(host_ip, c)
        elif feature == "interface": data = build_interface_state(host_ip, c)
        elif feature == "stp": data = build_stp_state(host_ip, c)
        elif feature == "vtp": data = build_vtp_state(host_ip, c)
        elif feature == "security": data = build_security_state(host_ip, c)
        elif feature in ("traffic_control", "traffic"): data = build_traffic_control_state(host_ip, c)
        elif feature == "svi": data = build_svi_state(host_ip, c)
        else: return False
        
        save_dir = L3_BACKUP_DIR if feature == "svi" else L2_BACKUP_DIR
        
        # Đảm bảo thư mục lưu trữ luôn tồn tại
        os.makedirs(save_dir, exist_ok=True)
        
        file_path = os.path.join(save_dir, f"{host_ip}_{feature}_state.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        print(f"  [+] Đã tạo Snapshot ({feature}) thành công cho {host_ip}")
        return True
        
    except Exception as e:
        print(f"  [-] Lỗi State Builder khi tạo snapshot {feature} cho {host_ip}: {e}")
        return False
    finally:
        conn.close()