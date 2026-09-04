import sqlite3
import re

# IMPORT ĐỘNG TỪ CONFIG.PY THEO ĐÚNG KIẾN TRÚC
from backend.PyCode.share.config import DB_TABLES, get_db_connection

# ==========================================
# KHAI BÁO BẢNG OSPF (LẤY TỪ DICTIONARY)
# ==========================================
TBL_OSPF_PROC = DB_TABLES["routing_ospf"]["processes"]
TBL_OSPF_NET = DB_TABLES["routing_ospf"]["networks"]
TBL_OSPF_DIST = DB_TABLES["routing_ospf"]["distance"]
TBL_OSPF_AREAS = DB_TABLES["routing_ospf"]["areas"]
TBL_OSPF_RANGES = DB_TABLES["routing_ospf"]["area_ranges"]
TBL_OSPF_REDIS = DB_TABLES["routing_ospf"]["redistribute"]
TBL_OSPF_PASSIVE = DB_TABLES["routing_ospf"]["passive_interfaces"]
TBL_OSPF_TUNING = DB_TABLES["routing_ospf"]["tuning"]
TBL_OSPF_INTF = DB_TABLES["routing_ospf"]["interface_settings"]

PROC_COL_ID = "ospf_id" 
PROC_COL_HOST = "host"
PROC_COL_PID = "process_id"
PROC_COL_RID = "router_id"
PROC_COL_DEF_ORIG = "default_originate"
PROC_COL_DEF_ALW = "default_originate_always"
PROC_COL_SUC = "success"

NET_COL_ID = "id" 
NET_COL_OSPF_ID = "ospf_id" 
NET_COL_NET = "network"
NET_COL_WILD = "wildcard"
NET_COL_AREA = "area"
NET_COL_SUC = "success"

# ==========================================
# KHAI BÁO BẢNG EIGRP (LẤY TỪ DICTIONARY)
# ==========================================
T_EIGRP_PROC = DB_TABLES["routing_eigrp"]["processes"]
T_EIGRP_NET = DB_TABLES["routing_eigrp"]["networks"]
T_EIGRP_PASS = DB_TABLES["routing_eigrp"]["passive_interfaces"]
T_EIGRP_DIST = DB_TABLES["routing_eigrp"]["distribute_lists"]
T_EIGRP_OFF = DB_TABLES["routing_eigrp"]["offset_lists"]
T_EIGRP_REDIS = DB_TABLES["routing_eigrp"]["redistribute"]
T_EIGRP_KEY = DB_TABLES["routing_eigrp"]["key_chains"]
T_EIGRP_ROUTER_IFACE = DB_TABLES["routing_eigrp"]["interface_settings"]

# ==========================================
# KHAI BÁO BẢNG STATIC (LẤY TỪ DICTIONARY)
# ==========================================
T_STATIC_DEF = DB_TABLES["routing_static"]["default"]
T_STATIC_RT = DB_TABLES["routing_static"]["routes"]

# ==========================================
# HELPER: LẤY IFACE_ID
# ==========================================
def get_iface_id(cursor, host_ip, interface_name):
    cursor.execute("SELECT iface_id FROM t02_interface_name WHERE host=? AND interface_name=?", (host_ip, interface_name))
    row = cursor.fetchone()
    return row[0] if row else None


# ==========================================
# 1. THỢ PHỤ STATIC ROUTES
# ==========================================
def sync_static_worker(host_ip: str, parse_obj, db_path: str):
    print(f"[INFO] Bắt đầu đồng bộ Static Route cho {host_ip}...")
    # SỬ DỤNG KẾT NỐI TẬP TRUNG TỪ CONFIG.PY
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute(f"DELETE FROM {T_STATIC_DEF} WHERE host=?", (host_ip,))
        c.execute(f"DELETE FROM {T_STATIC_RT} WHERE host=?", (host_ip,))
        
        for route_obj in parse_obj.find_objects(r"^ip route "):
            parts = route_obj.text.strip().split()
            if len(parts) >= 5:
                network = parts[2]
                mask = parts[3]
                next_hop = parts[4]
                ad = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 1
                
                if network == "0.0.0.0" and mask == "0.0.0.0":
                    c.execute(f"INSERT INTO {T_STATIC_DEF} (host, next_hop_ip, success) VALUES (?, ?, 1)", 
                              (host_ip, next_hop))
                else:
                    c.execute(f"INSERT INTO {T_STATIC_RT} (host, network, subnet_mask, next_hop, ad, success) VALUES (?, ?, ?, ?, ?, 1)", 
                              (host_ip, network, mask, next_hop, ad))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[-] Static Route Worker LỖI: {e}")
    finally:
        conn.close()


# ==========================================
# 2. THỢ PHỤ OSPF 
# ==========================================
def sync_ospf_worker(host_ip: str, parse_obj, db_path: str):
    print(f"[INFO] Bắt đầu đồng bộ OSPF nâng cao cho {host_ip}...")
    parsed_processes = {}
    
    for ospf_obj in parse_obj.find_objects(r"^router ospf "):
        pid = int(ospf_obj.text.split("router ospf ")[-1].strip())
        
        rid_obj = ospf_obj.re_search_children(r"^\s+router-id ")
        router_id = rid_obj[0].text.split("router-id ")[-1].strip() if rid_obj else None
        
        def_orig_obj = ospf_obj.re_search_children(r"^\s+default-information originate")
        def_orig = 1 if def_orig_obj else 0
        always = 1 if def_orig_obj and "always" in def_orig_obj[0].text else 0
        
        ref_bw_obj = ospf_obj.re_search_children(r"^\s+auto-cost reference-bandwidth")
        ref_bw = int(ref_bw_obj[0].text.split()[-1]) if ref_bw_obj else None
        
        pass_def_obj = ospf_obj.re_search_children(r"^\s+passive-interface default")
        pass_def = 1 if pass_def_obj else 0
        
        max_path_obj = ospf_obj.re_search_children(r"^\s+maximum-paths")
        max_paths = int(max_path_obj[0].text.split()[-1]) if max_path_obj else None
        
        networks, redistribute, passive_intfs = [], [], []
        
        for net_obj in ospf_obj.re_search_children(r"^\s+network "):
            parts = net_obj.text.strip().split()
            if len(parts) >= 5:
                networks.append({'network': parts[1], 'wildcard': parts[2], 'area': int(parts[4])})
                
        for redis_obj in ospf_obj.re_search_children(r"^\s+redistribute "):
            text = redis_obj.text.strip()
            parts = text.split()
            proto = parts[1]
            subnets = 1 if "subnets" in text else 0
            metric = int(re.search(r"metric (\d+)", text).group(1)) if "metric " in text else None
            m_type = int(re.search(r"metric-type (\d+)", text).group(1)) if "metric-type" in text else None
            r_map = re.search(r"route-map (\S+)", text).group(1) if "route-map" in text else None
            redistribute.append({'proto': proto, 'subnets': subnets, 'metric': metric, 'm_type': m_type, 'r_map': r_map})

        for pass_obj in ospf_obj.re_search_children(r"^\s+passive-interface (?!default)"):
            passive_intfs.append(pass_obj.text.strip().split()[-1])
                
        parsed_processes[pid] = {
            'router_id': router_id, 'default_originate': def_orig, 'default_originate_always': always,
            'reference_bandwidth': ref_bw, 'passive_default': pass_def, 'maximum_paths': max_paths,
            'networks': networks, 'redistribute': redistribute, 'passive_interfaces': passive_intfs
        }

    # SỬ DỤNG KẾT NỐI TẬP TRUNG TỪ CONFIG.PY
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute(f"SELECT {PROC_COL_PID}, {PROC_COL_ID} FROM {TBL_OSPF_PROC} WHERE {PROC_COL_HOST}=?", (host_ip,))
        db_pids_map = {row[0]: row[1] for row in c.fetchall()}
        db_pids = set(db_pids_map.keys())
        run_pids = set(parsed_processes.keys())
        
        for pid in (db_pids - run_pids):
            ospf_id = db_pids_map[pid]
            for tbl in [TBL_OSPF_NET, TBL_OSPF_REDIS, TBL_OSPF_PASSIVE, TBL_OSPF_TUNING, TBL_OSPF_PROC]:
                c.execute(f"DELETE FROM {tbl} WHERE ospf_id=?", (ospf_id,))
            
        for pid in (run_pids - db_pids):
            d = parsed_processes[pid]
            c.execute(f"""
                INSERT INTO {TBL_OSPF_PROC} 
                (host, process_id, router_id, default_originate, default_originate_always, reference_bandwidth, passive_default, success) 
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (host_ip, pid, d['router_id'], d['default_originate'], d['default_originate_always'], d['reference_bandwidth'], d['passive_default']))
            new_ospf_id = c.lastrowid
            db_pids_map[pid] = new_ospf_id 
            
        for pid in run_pids:
            d = parsed_processes[pid]
            ospf_id = db_pids_map[pid]
            
            if pid in (db_pids & run_pids):
                c.execute(f"""
                    UPDATE {TBL_OSPF_PROC} 
                    SET router_id=?, default_originate=?, default_originate_always=?, reference_bandwidth=?, passive_default=?, success=1 
                    WHERE ospf_id=?
                """, (d['router_id'], d['default_originate'], d['default_originate_always'], d['reference_bandwidth'], d['passive_default'], ospf_id))
            
            for tbl in [TBL_OSPF_NET, TBL_OSPF_REDIS, TBL_OSPF_PASSIVE, TBL_OSPF_TUNING]:
                c.execute(f"DELETE FROM {tbl} WHERE ospf_id=?", (ospf_id,))
                
            if d['maximum_paths']:
                c.execute(f"INSERT INTO {TBL_OSPF_TUNING} (ospf_id, maximum_paths, success) VALUES (?, ?, 1)", (ospf_id, d['maximum_paths']))
                
            for net in d['networks']:
                c.execute(f"INSERT INTO {TBL_OSPF_NET} (ospf_id, network, wildcard, area, success) VALUES (?, ?, ?, ?, 1)", 
                          (ospf_id, net['network'], net['wildcard'], net['area']))
                          
            for r in d['redistribute']:
                c.execute(f"INSERT INTO {TBL_OSPF_REDIS} (ospf_id, protocol, subnets, metric, metric_type, route_map, success) VALUES (?, ?, ?, ?, ?, ?, 1)",
                          (ospf_id, r['proto'], r['subnets'], r['metric'], r['m_type'], r['r_map']))
                          
            for pi in d['passive_interfaces']:
                c.execute(f"INSERT INTO {TBL_OSPF_PASSIVE} (ospf_id, interface_name, passive, success) VALUES (?, ?, 1, 1)", (ospf_id, pi))

        conn.commit()
        print(f"[+] OSPF Worker: Đồng bộ thành công {TBL_OSPF_PROC} cho {host_ip}")
        
    except Exception as e:
        print(f"[-] OSPF Worker LỖI: {e}")
        conn.rollback()
    finally:
        conn.close()


# ==========================================
# 3. THỢ PHỤ EIGRP
# ==========================================
def sync_eigrp_worker(host_ip: str, parse_obj, db_path: str):
    print(f"[INFO] Bắt đầu băm 100% cấu hình EIGRP cho {host_ip}...")
    parsed_processes = {}
    
    for eigrp_obj in parse_obj.find_objects(r"^router eigrp \d+"):
        as_num = int(eigrp_obj.text.split()[-1])
        parsed_processes[as_num] = {
            'router_id': None, 'auto_summary': 0, 'passive_default': 0,
            'timers_active_time': None, 'bfd_all': 0, 'variance': None, 'max_paths': None, 
            'dist_int': None, 'dist_ext': None, 'stub': 0, 'stub_opt': None,
            'networks': [], 'passive_interfaces': [], 'redistribute': [], 
            'distribute': [], 'offset': []
        }
        
        for child in eigrp_obj.children:
            text = child.text.strip()
            if text.startswith("eigrp router-id"): parsed_processes[as_num]['router_id'] = text.split()[-1]
            elif text == "auto-summary": parsed_processes[as_num]['auto_summary'] = 1
            elif text == "passive-interface default": parsed_processes[as_num]['passive_default'] = 1
            elif text.startswith("timers active-time"): parsed_processes[as_num]['timers_active_time'] = int(text.split()[-1])
            elif text == "bfd all-interfaces": parsed_processes[as_num]['bfd_all'] = 1
            elif text.startswith("variance"): parsed_processes[as_num]['variance'] = int(text.split()[-1])
            elif text.startswith("maximum-paths"): parsed_processes[as_num]['max_paths'] = int(text.split()[-1])
            elif text.startswith("distance eigrp"):
                p = text.split()
                parsed_processes[as_num]['dist_int'], parsed_processes[as_num]['dist_ext'] = int(p[2]), int(p[3])
            elif text.startswith("eigrp stub"):
                parsed_processes[as_num]['stub'] = 1
                parsed_processes[as_num]['stub_opt'] = text.replace("eigrp stub", "").strip()
                
            elif text.startswith("network"):
                parts = text.split()
                parsed_processes[as_num]['networks'].append({"net": parts[1], "wild": parts[2] if len(parts) > 2 else ""})
            elif text.startswith("redistribute"):
                p = text.split()
                r_data = {"proto": p[1], "map": None, "bw": None, "dly": None, "rel": None, "load": None, "mtu": None}
                if "route-map" in text: r_data["map"] = re.search(r"route-map (\S+)", text).group(1)
                m_match = re.search(r"metric (\d+) (\d+) (\d+) (\d+) (\d+)", text)
                if m_match:
                    r_data["bw"], r_data["dly"], r_data["rel"], r_data["load"], r_data["mtu"] = m_match.groups()
                parsed_processes[as_num]['redistribute'].append(r_data)
                
            elif text.startswith("distribute-list"):
                p = text.split()
                parsed_processes[as_num]['distribute'].append({"list": p[1], "dir": p[2], "intf": p[4] if len(p) > 4 else None})
            elif text.startswith("offset-list"):
                p = text.split()
                parsed_processes[as_num]['offset'].append({"list": p[1], "dir": p[2], "val": p[3], "intf": p[4] if len(p) > 4 else None})
            elif text.startswith("passive-interface"):
                parsed_processes[as_num]['passive_interfaces'].append({"name": text.split()[-1], "mode": "passive"})

    # SỬ DỤNG KẾT NỐI TẬP TRUNG TỪ CONFIG.PY
    conn = get_db_connection()
    c = conn.cursor()
    try:
        for kc_obj in parse_obj.find_objects(r"^key chain "):
            kc_name = kc_obj.text.split()[2]
            c.execute(f"DELETE FROM {T_EIGRP_KEY} WHERE host=? AND chain_name=?", (host_ip, kc_name))
            for key_obj in kc_obj.re_search_children(r"^\s+key \d+"):
                key_id = key_obj.text.split()[1]
                key_str_obj = key_obj.re_search_children(r"^\s+key-string ")
                key_string = key_str_obj[0].text.split()[-1] if key_str_obj else None
                accept_obj = key_obj.re_search_children(r"^\s+accept-lifetime ")
                accept_life = accept_obj[0].text.split("accept-lifetime ")[-1].strip() if accept_obj else None
                send_obj = key_obj.re_search_children(r"^\s+send-lifetime ")
                send_life = send_obj[0].text.split("send-lifetime ")[-1].strip() if send_obj else None
            
                c.execute(f"""
                    INSERT INTO {T_EIGRP_KEY} 
                    (host, chain_name, key_id, key_string, accept_lifetime, send_lifetime, success) 
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (host_ip, kc_name, key_id, key_string, accept_life, send_life))

        for as_num, data in parsed_processes.items():
            c.execute(f"""
                INSERT OR REPLACE INTO {T_EIGRP_PROC} 
                (host, as_number, router_id, auto_summary, passive_default, timers_active_time, bfd_all_interfaces, variance, maximum_paths, distance_internal, distance_external, stub_enabled, stub_options, success) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (host_ip, as_num, data['router_id'], data['auto_summary'], data['passive_default'], 
                  data['timers_active_time'], data['bfd_all'], data['variance'], data['max_paths'], 
                  data['dist_int'], data['dist_ext'], data['stub'], data['stub_opt']))
            e_id = c.lastrowid
            
            for table in [T_EIGRP_NET, T_EIGRP_PASS, T_EIGRP_REDIS, T_EIGRP_DIST, T_EIGRP_OFF, T_EIGRP_ROUTER_IFACE]:
                c.execute(f"DELETE FROM {table} WHERE eigrp_id=?", (e_id,))
            
            for n in data['networks']: 
                c.execute(f"INSERT INTO {T_EIGRP_NET} (eigrp_id, network, wildcard, success) VALUES (?, ?, ?, 1)", (e_id, n['net'], n['wild']))
            for p in data['passive_interfaces']: 
                c.execute(f"INSERT INTO {T_EIGRP_PASS} (eigrp_id, interface_name, mode, success) VALUES (?, ?, ?, 1)", (e_id, p['name'], p['mode']))
            
            for r in data['redistribute']: 
                c.execute(f"""
                    INSERT INTO {T_EIGRP_REDIS} (eigrp_id, protocol, route_map, metric_bw, metric_delay, metric_reliability, metric_load, metric_mtu, success) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (e_id, r['proto'], r['map'], r['bw'], r['dly'], r['rel'], r['load'], r['mtu']))
                
            for d in data['distribute']:
                c.execute(f"INSERT INTO {T_EIGRP_DIST} (eigrp_id, list_name, direction, interface_name, success) VALUES (?, ?, ?, ?, 1)", (e_id, d['list'], d['dir'], d['intf']))
            for o in data['offset']:
                c.execute(f"INSERT INTO {T_EIGRP_OFF} (eigrp_id, list_name, direction, value, interface_name, success) VALUES (?, ?, ?, ?, ?, 1)", (e_id, o['list'], o['dir'], o['val'], o['intf']))
            
            for intf_obj in parse_obj.find_objects(r"^interface "):
                if intf_obj.re_search_children(rf"eigrp {as_num}") or intf_obj.re_search_children(r"ip bandwidth-percent eigrp"):
                    intf_name = intf_obj.text.split()[-1]
                    iface_id = get_iface_id(c, host_ip, intf_name)
                    
                    if iface_id:
                        hello_obj = intf_obj.re_search_children(rf"ip hello-interval eigrp {as_num} ")
                        hello = int(hello_obj[0].text.split()[-1]) if hello_obj else None
                        
                        hold_obj = intf_obj.re_search_children(rf"ip hold-time eigrp {as_num} ")
                        hold = int(hold_obj[0].text.split()[-1]) if hold_obj else None
                        
                        split_hz_obj = intf_obj.re_search_children(rf"no ip split-horizon eigrp {as_num}")
                        split_hz = 0 if split_hz_obj else 1
                        
                        c.execute(f"""
                            INSERT INTO {T_EIGRP_ROUTER_IFACE} 
                            (iface_id, eigrp_id, hello_interval, hold_time, split_horizon, success) 
                            VALUES (?, ?, ?, ?, ?, 1)
                        """, (iface_id, e_id, hello, hold, split_hz))
            
        conn.commit()
        print(f"[+] EIGRP Worker: Đồng bộ thành công {T_EIGRP_PROC} cho {host_ip}")
    except Exception as e:
        conn.rollback()
        print(f"[-] EIGRP Worker LỖI: {e}")
    finally:
        conn.close()