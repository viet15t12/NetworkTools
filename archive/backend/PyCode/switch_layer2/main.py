import os
import json
import sqlite3

# ================= IMPORT WORKER L2 =================
from backend.PyCode.switch_layer2.modules.stp import run_stp_worker
from backend.PyCode.switch_layer2.modules.vlan import run_vlan_worker
from backend.PyCode.switch_layer2.modules.interface_l2 import run_interface_worker
from backend.PyCode.switch_layer2.modules.vtp import run_vtp_worker
from backend.PyCode.switch_layer2.modules.security_worker import run_security_worker
from backend.PyCode.switch_layer2.modules.traffic_control_worker import run_traffic_control_worker

# ================= IMPORT WORKER SWITCH_L3 =================
from backend.PyCode.switch_layer2.modules.svi_worker import run_svi_worker

# ================= IMPORT CONFIG VÀ STATE BUILDER =================
from backend.PyCode.share.config import (
    get_db_connection, DB_PATH, DB_TABLES, TMP_DIR, 
    L2_BACKUP_DIR, L3_BACKUP_DIR  
)
from backend.PyCode.share.state_builder import update_snapshot

# ================= ĐỊNH TUYẾN FILE LOG =================
L2_OUTPUT = os.path.join(TMP_DIR, "l2_output_log.json")
L3_OUTPUT = os.path.join(TMP_DIR, "l3_output_log.json")

# ================= BẢNG DATABASE L2 =================
TBL_STP_GLOBAL = DB_TABLES["l2_stp"]["global"]
TBL_STP_IFACE = DB_TABLES["l2_stp"]["interface"]
TBL_DEVICES = DB_TABLES["device_info"]["main"]
TBL_VLAN = DB_TABLES["l2_vlan"]["main"]
TBL_IFACE = DB_TABLES["l2_interfaces"]["main"]
TBL_ACC = DB_TABLES["l2_interfaces"]["access"]
TBL_TRUNK = DB_TABLES["l2_interfaces"]["trunk"]
TBL_PO = DB_TABLES["l2_etherchannel"]["main"]
TBL_VTP_DOMAINS = DB_TABLES["l2_vtp"]["domains"]
TBL_VTP_SWITCHES = DB_TABLES["l2_vtp"]["switches"]
TBL_VTP_MODES = DB_TABLES["l2_vtp"]["modes"]

# ================= BẢNG DATABASE L3 =================
TBL_L3_GLOBAL = DB_TABLES.get("l3_switch", {}).get("global", "t06_switch_l3_config")
TBL_SVI = DB_TABLES.get("l3_switch", {}).get("svi", "t06_svi_interface")


# =====================================================================
# [MAIN DISPATCHER 1] LUỒNG ĐIỀU PHỐI LAYER 2
# =====================================================================
def l2_dispatcher(target: str = "all", feature: str = "vlan"):
    print(f"\n[*] [L2 Master] Target: {target} | Feature: {feature.upper()}")
    
    valid_data = []
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if target.lower() == "all":
            c.execute(f"SELECT host FROM {TBL_DEVICES} WHERE TRIM(LOWER(role)) IN ('sw2', 'sw3') OR LOWER(role) LIKE '%sw%'")
            target_hosts = [row[0] for row in c.fetchall()]
        else:
            target_hosts = [target]

        for host in target_hosts:
            # --- Nhánh 1: VLAN ---
            if feature == "vlan":
                c.execute(f"SELECT id, vlan_id, vlan_name, state FROM {TBL_VLAN} WHERE host = ?", (host,))
                vlan_records = c.fetchall()
                if not vlan_records: continue
                
                full_vlans = [{"vlan_id": v_id, "vlan_name": v_name, "state": v_state} for _, v_id, v_name, v_state in vlan_records]

                state_file = os.path.join(L2_BACKUP_DIR, f"{host}_vlan_state.json")
                last_state = []
                if os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f:
                        last_state = json.load(f)

                last_state_dict = {str(v["vlan_id"]): v for v in last_state}
                vlans_to_push = [v for v in full_vlans if not last_state_dict.get(str(v["vlan_id"])) or v != last_state_dict.get(str(v["vlan_id"]))]

                if not vlans_to_push:
                    print(f"[*] [SKIP] Không có thay đổi VLAN nào trên {host}. Bỏ qua!")
                    continue

                valid_data.append({"target": host, "vlans": vlans_to_push})

            # --- Nhánh 2: INTERFACE ---
            elif feature == "interface":
                c.execute(f"""
                    SELECT i.id, i.if_name, i.description, i.mode, i.admin_status, i.speed, i.duplex,
                           a.access_vlan, a.voice_vlan,
                           t.allowed_vlans, t.native_vlan, t.encapsulation
                    FROM {TBL_IFACE} i
                    LEFT JOIN {TBL_ACC} a ON i.id = a.iface_id
                    LEFT JOIN {TBL_TRUNK} t ON i.id = t.iface_id
                    WHERE i.host = ?
                """, (host,))
                iface_records = c.fetchall()
                if not iface_records: continue

                c.execute(f"SELECT po_number, protocol, mode, member_ports FROM {TBL_PO} WHERE host = ?", (host,))
                po_records = c.fetchall()

                full_interfaces = []
                for r in iface_records:
                    iface_dict = {
                        "if_name": r[1], "description": r[2], "mode": r[3], "admin_status": r[4], 
                        "speed": r[5], "duplex": r[6], "access_vlan": r[7], "voice_vlan": r[8],
                        "allowed_vlans": r[9], "native_vlan": r[10], "encapsulation": r[11],
                        "channel_group": "None", "channel_protocol": "None", "channel_group_mode": "None"
                    }
                    for po_num, po_proto, po_mode, members in po_records:
                        if members and iface_dict["if_name"] in members.split(','):
                            iface_dict["channel_group"] = po_num
                            iface_dict["channel_protocol"] = po_proto if po_proto != 'static' else 'None'
                            iface_dict["channel_group_mode"] = po_mode
                            break 
                    full_interfaces.append(iface_dict)

                state_file = os.path.join(L2_BACKUP_DIR, f"{host}_iface_state.json")
                last_state = []
                if os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f:
                        last_state = json.load(f)

                last_state_dict = {iface["if_name"]: iface for iface in last_state}
                interfaces_to_push = [i for i in full_interfaces if not last_state_dict.get(i["if_name"]) or i != last_state_dict.get(i["if_name"])]

                if not interfaces_to_push:
                    print(f"[*] [SKIP] Không có thay đổi Interface trên {host}. Bỏ qua!")
                    continue

                valid_data.append({"target": host, "interfaces": interfaces_to_push})

            # --- Nhánh 3: STP ---
            elif feature == "stp":
                c.execute(f"SELECT vlan_id, stp_mode, priority, root_role FROM {TBL_STP_GLOBAL} WHERE host = ?", (host,))
                global_records = c.fetchall()
                
                c.execute(f"""
                    SELECT i.if_name, s.portfast, s.bpduguard, s.bpdufilter, s.root_guard, s.loop_guard
                    FROM {TBL_STP_IFACE} s
                    JOIN {TBL_IFACE} i ON s.iface_id = i.id
                    WHERE i.host = ? AND i.if_name NOT IN ('GigabitEthernet0/0', 'Gi0/0', 'g0/0')
                """, (host,))
                iface_records = c.fetchall()

                if not global_records and not iface_records: continue

                curr_stp_state = {
                    "global": [{"vlan_id": r[0], "stp_mode": r[1], "priority": r[2], "root_role": r[3]} for r in global_records],
                    "interfaces": [{"if_name": r[0], "portfast": r[1], "bpduguard": r[2], "bpdufilter": r[3], "root_guard": r[4], "loop_guard": r[5]} for r in iface_records]
                }

                state_file = os.path.join(L2_BACKUP_DIR, f"{host}_stp_state.json")
                last_state = {"global": [], "interfaces": []}
                if os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f:
                        last_state = json.load(f)

                global_to_push = [g for g in curr_stp_state["global"] if g not in last_state.get("global", [])]
                ifaces_to_push = [i for i in curr_stp_state["interfaces"] if i not in last_state.get("interfaces", [])]

                if not global_to_push and not ifaces_to_push:
                    print(f"[*] [SKIP] Không có thay đổi STP trên {host}. Bỏ qua!")
                    continue

                valid_data.append({"target": host, "stp_globals": global_to_push, "stp_interfaces": ifaces_to_push})

            # --- Nhánh 4: VTP ---
            elif feature == "vtp":
                c.execute(f"""
                    SELECT s.vtp_switch_id, s.vtp_domain_id, d.domain_name, d.version, 
                           d.password_type, d.password_value, s.pruning, m.mode, m.primary_server, s.success
                    FROM {TBL_VTP_SWITCHES} s
                    LEFT JOIN {TBL_VTP_DOMAINS} d ON s.vtp_domain_id = d.vtp_domain_id
                    LEFT JOIN {TBL_VTP_MODES} m ON s.vtp_switch_id = m.vtp_switch_id AND m.database_type = 'vlan'
                    WHERE TRIM(s.host) = TRIM(?)
                """, (host,))
                vtp_record = c.fetchone()
                
                if not vtp_record:
                    print(f"[-] [DEBUG] Không tìm thấy dữ liệu VTP của switch {host} trong DB.")
                    continue

                (vtp_sw_id, vtp_dom_id, dom_name, ver, 
                 pwd_type, pwd_val, pruning, mode, primary_server, success) = vtp_record

                curr_vtp_state = {
                    "domain_name": dom_name,
                    "version": int(ver) if ver else 2,
                    "password_type": pwd_type or "none",
                    "password_value": pwd_val or "",
                    "pruning": int(pruning) if pruning is not None else 0,
                    "mode": mode or "transparent",
                    "primary_server": int(primary_server) if primary_server else 0
                }

                # Đọc Snapshot JSON cũ
                state_file = os.path.join(L2_BACKUP_DIR, f"{host}_vtp_state.json")
                last_state = {}
                if os.path.exists(state_file):
                    try:
                        with open(state_file, 'r', encoding='utf-8') as f:
                            last_state = json.load(f)
                    except Exception:
                        last_state = {}

                # So khớp: Đẩy lệnh khi có khác biệt so với Snapshot HOẶC success == 0
                has_changed = (curr_vtp_state != last_state)

                if has_changed or success == 0:
                    if has_changed:
                        print(f"[*] [DELTA DETECTED] Phát hiện thay đổi cấu hình VTP trên {host} so với Snapshot. Đẩy cấu hình mới!")
                    
                    valid_data.append({
                        "target": host,
                        "vtp_switch_id": vtp_sw_id,
                        "vtp_data": curr_vtp_state
                    })
                else:
                    print(f"[*] [SKIP] Switch {host} đã có success = 1 và trùng khớp Snapshot. Bỏ qua!")
                    continue

           # --- Nhánh 5: SECURITY ---
            elif feature == "security":
                # 1. Ép thứ tự theo vlan_id
                c.execute(f"SELECT vlan_id, dhcp_snooping, dai_enabled FROM {DB_TABLES['l2_security']['global']} WHERE host = ? ORDER BY vlan_id ASC", (host,))
                global_records = c.fetchall()
                curr_security_state = {"global_sec": [{"vlan_id": gr[0], "dhcp_snooping": gr[1], "dai_enabled": gr[2]} for gr in global_records] if global_records else [], "interfaces": []}

                # 2. Ép thứ tự theo if_name (Tên cổng)
                c.execute(f"""
                    SELECT i.if_name, t.id as is_trusted, p.max_mac, p.violation, p.sticky, p.aging_type, p.aging_time, i.id as iface_id
                    FROM t06_interface_l2 i
                    LEFT JOIN {DB_TABLES['l2_security']['dhcp_trust']} t ON i.if_name = t.if_name AND i.host = t.host
                    LEFT JOIN {DB_TABLES['l2_security']['port_sec']} p ON i.id = p.iface_id
                    WHERE i.host = ? AND (t.id IS NOT NULL OR p.iface_id IS NOT NULL OR i.id IN (SELECT iface_id FROM {DB_TABLES['l2_security']['mac_table']}))
                    ORDER BY i.if_name ASC
                """, (host,))
                iface_records = c.fetchall()

                # 3. Ép thứ tự theo mac_addr
                c.execute(f"""
                    SELECT m.iface_id, m.mac_addr, m.vlan_id, m.mac_type
                    FROM {DB_TABLES['l2_security']['mac_table']} m
                    JOIN t06_interface_l2 i ON m.iface_id = i.id WHERE i.host = ?
                    ORDER BY m.mac_addr ASC
                """, (host,))
                mac_dict = {}
                for m in c.fetchall():
                    mac_dict.setdefault(m[0], []).append({"mac_addr": m[1], "vlan_id": m[2], "mac_type": m[3]})

                for r in iface_records:
                    curr_security_state["interfaces"].append({
                        "if_name": r[0], "is_trusted": 1 if r[1] else 0, "max_mac": r[2], "violation": r[3],
                        "sticky": r[4], "aging_type": r[5], "aging_time": r[6], "static_macs": mac_dict.get(r[7], []) 
                    })

                if not curr_security_state["global_sec"] and not curr_security_state["interfaces"]: continue
                
                state_file = os.path.join(L2_BACKUP_DIR, f"{host}_security_state.json")
                last_state = {"global_sec": None, "interfaces": []}
                if os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f: last_state = json.load(f)

                if curr_security_state != last_state:
                    valid_data.append({"target": host, "global_sec": curr_security_state["global_sec"], "interfaces": curr_security_state["interfaces"]})
                else:
                    print(f"[*] [SKIP] Không có thay đổi Security trên {host}. Bỏ qua!")
                    continue

            # --- Nhánh 6: TRAFFIC CONTROL & QOS ---
            elif feature in ("traffic_control", "traffic"):
                c.execute("""
                    SELECT i.id, i.if_name, sc.bc_level, sc.mc_level, sc.uc_level, sc.action,
                           q.trust_mode, q.cos_value, q.dscp_value, q.policy_in, q.policy_out
                    FROM t06_interface_l2 i
                    LEFT JOIN t06_iface_storm_control sc ON i.id = sc.iface_id
                    LEFT JOIN t06_iface_qos q ON i.id = q.iface_id
                    WHERE i.host = ? AND (sc.iface_id IS NOT NULL OR q.iface_id IS NOT NULL)
                """, (host,))
                tc_records = c.fetchall()
                if not tc_records: continue

                curr_tc_interfaces = []
                for r in tc_records:
                    if_id, if_name, bc_lvl, mc_lvl, uc_lvl, action, trust, cos, dscp, pol_in, pol_out = r
                    iface_entry = {"if_name": if_name}
                    iface_entry["storm_control"] = {"bc_level": bc_lvl, "mc_level": mc_lvl, "uc_level": uc_lvl, "action": action} if bc_lvl is not None else None
                    iface_entry["qos"] = {"trust_mode": trust or "none", "cos_value": cos or 0, "dscp_value": dscp or 0, "policy_in": pol_in or "", "policy_out": pol_out or ""} if (trust is not None or cos != 0 or dscp != 0 or pol_in or pol_out) else None
                    curr_tc_interfaces.append(iface_entry)

                state_file = os.path.join(L2_BACKUP_DIR, f"{host}_traffic_control_state.json")
                last_state = []
                if os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f: last_state = json.load(f)

                if curr_tc_interfaces != last_state:
                    valid_data.append({"target": host, "interfaces": curr_tc_interfaces})
                else:
                    print(f"[*] [SKIP] Không có thay đổi Traffic Control/QoS trên {host}. Bỏ qua!")
                    continue

        # --- GỌI WORKER L2 ---
        if not valid_data:
            print(f"[INFO] Tất cả cấu hình L2 đã đồng bộ, không cần đẩy lệnh.")
            return

        if feature == "vlan": run_vlan_worker(valid_data, DB_PATH, L2_OUTPUT)
        elif feature == "interface": run_interface_worker(valid_data, DB_PATH, L2_OUTPUT)
        elif feature == "stp": run_stp_worker(valid_data, DB_PATH, L2_OUTPUT)
        elif feature == "vtp": run_vtp_worker(valid_data, DB_PATH, L2_OUTPUT)
        elif feature == "security": run_security_worker(valid_data, DB_PATH, L2_OUTPUT)
        elif feature in ("traffic_control", "traffic"): run_traffic_control_worker(valid_data, DB_PATH, L2_OUTPUT)
            
        # --- GHI SNAPSHOT L2 VÀ CẬP NHẬT DB (DUY NHẤT 1 LẦN) ---
        if os.path.exists(L2_OUTPUT):
            with open(L2_OUTPUT, 'r', encoding='utf-8') as f:
                out_results = json.load(f)

            conn_update = get_db_connection()
            c_update = conn_update.cursor()

            for res in out_results:
                ip = res.get("target")
                if res.get("status") == "success":
                    print(f"[*] Push L2 {feature.upper()} cho {ip}: THÀNH CÔNG")
                    
                    # Cập nhật success = 1 cho VTP
                    if feature == "vtp":
                        c_update.execute(f"UPDATE {TBL_VTP_SWITCHES} SET success = 1 WHERE host = ?", (ip,))
                        print(f"  [+] Đã UPDATE success = 1 cho VTP của {ip} trong DB.")

                    # Tạo Snapshot mới
                    update_snapshot(ip, feature)
                else:
                    print(f"[*] Push L2 {feature.upper()} cho {ip}: THẤT BẠI ({res.get('message')})")
                    print(f"  [-] Giữ nguyên trạng thái do cấu hình thất bại.")

            conn_update.commit()
            conn_update.close()

    except Exception as e:
        print(f"[-] LỖI L2 DISPATCHER: {e}")
    finally:
        if 'conn' in locals(): 
            conn.close()


# =====================================================================
# [MAIN DISPATCHER 2] LUỒNG ĐIỀU PHỐI LAYER 3 (SVI, ROUTING)
# =====================================================================
def l3_dispatcher(target: str = "all", feature: str = "svi"):
    print(f"\n[*] [L3 Master] Target: {target} | Feature: {feature.upper()}")
    
    valid_data = []
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if target.lower() == "all":
            c.execute(f"SELECT host FROM {TBL_DEVICES} WHERE TRIM(LOWER(role)) IN ('core') OR LOWER(role) LIKE '%core%' OR host IN ('192.168.113.104', '192.168.113.105')")
            target_hosts = [row[0] for row in c.fetchall()]
        else:
            target_hosts = [target]

        for host in target_hosts:
            if feature == "svi":
                c.execute(f"SELECT ip_routing FROM {TBL_L3_GLOBAL} WHERE host = ?", (host,))
                l3_global = c.fetchone()
                
                c.execute(f"SELECT vlan_id, ip_address, subnet_mask, shutdown, success FROM {TBL_SVI} WHERE host = ? AND success IN (0, -1)", (host,))
                svi_records = c.fetchall()

                if not l3_global and not svi_records:
                    continue

                curr_l3_state = {
                    "l3_config": {"ip_routing": l3_global[0] if l3_global else 0},
                    "svis": [{"vlan_id": r[0], "ip_address": r[1], "subnet_mask": r[2], "shutdown": r[3], "success": r[4]} for r in svi_records]
                }

                state_file = os.path.join(L3_BACKUP_DIR, f"{host}_svi_state.json")
                last_state = {}
                if os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f:
                        last_state = json.load(f)

                if curr_l3_state != last_state:
                    valid_data.append({"target": host, "payload": curr_l3_state})
                else:
                    print(f"[*] [SKIP] Không có thay đổi SVI/L3 nào trên {host}. Bỏ qua!")
                    continue

        if not valid_data:
            print(f"[INFO] Tất cả cấu hình L3 đã đồng bộ, không cần đẩy lệnh.")
            return

        if feature == "svi":
            run_svi_worker(valid_data, DB_PATH, L3_OUTPUT)
            
        # --- GHI SNAPSHOT L3 BẰNG STATE BUILDER ---
        if os.path.exists(L3_OUTPUT):
            with open(L3_OUTPUT, 'r', encoding='utf-8') as f:
                out_results = json.load(f)

            for res in out_results:
                ip = res.get("target")
                if res.get("status") == "success":
                    print(f"[*] Push L3 {feature.upper()} cho {ip}: THÀNH CÔNG")
                    update_snapshot(ip, feature)
                else:
                    print(f"[*] Push L3 {feature.upper()} cho {ip}: THẤT BẠI ({res.get('message')})")
                    print(f"  [-] Giữ nguyên Snapshot cũ do cấu hình thất bại.")

    except Exception as e:
        print(f"[-] LỖI L3 DISPATCHER: {e}")
    finally:
        if 'conn' in locals(): 
            conn.close()