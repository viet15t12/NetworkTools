import json
import os
import sys
import sqlite3
import argparse
from collections import defaultdict

# Setup radar đường dẫn
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../.."))
if PROJECT_ROOT not in sys.path: sys.path.append(PROJECT_ROOT)
if CURRENT_DIR not in sys.path: sys.path.append(CURRENT_DIR)

# [ĐỒNG BỘ 100%] Gọi tất cả vũ khí từ Trạm kiểm soát
from PyCode.share.config import DB_PATH, ROUTE_OUTPUT, TMP_DIR, DB_TABLES

try:
    from worker_routing import run_routing_config
except ImportError as e:
    print(f"[-] Lỗi Import Worker: Không tìm thấy file 'worker_routing.py'!\n    Chi tiết: {e}")
    sys.exit(1)

# =====================================================================
# HỆ THỐNG HÀM HELPER HỖ TRỢ LOGIC 3 TRẠNG THÁI 
# =====================================================================

def has_eigrp_text_bit(action_cfg: str, bit_index_from_left: int) -> bool:
    if not action_cfg: return True
    if bit_index_from_left < 0 or bit_index_from_left >= len(action_cfg): return False
    return action_cfg[bit_index_from_left] == '1'

def state_3(val):
    if val in (0, '0', 0.0, '0.0'): return True
    if val in (-1, '-1', -1.0, '-1.0'): return "remove"
    return None

def success_state(val):
    if val is None or val in (0, '0', 0.0, '0.0'): return "setup"
    if val in (-1, '-1', -1.0, '-1.0'): return "remove"
    return "ignore"

def clean_sql(fields):
    if not fields: return ""
    return ", " + ", ".join([f"{f} = CASE WHEN {f} IN (0, '0', 0.0, '0.0') THEN 1 WHEN {f} IN (-1, '-1', -1.0, '-1.0') THEN NULL ELSE {f} END" for f in fields])

# =====================================================================
# HÀM ĐIỀU PHỐI (DÙNG CHO CẢ API VÀ TERMINAL)
# =====================================================================

def routing_dispatcher(target_ip="all", target_module="all"):
    print(f"\n[*] [Routing Master] Target: {target_ip} | Module: {target_module.upper()} | DB: {os.path.basename(DB_PATH)}")

    if not os.path.exists(DB_PATH):
        print(f"[-] LỖI: Không tìm thấy file Database tại: {DB_PATH}")
        return

    valid_data = []

    # ÉP KIỂU TÊN BẢNG TỪ FILE CONFIG.PY
    T_OSPF_PROC = DB_TABLES["routing_ospf"]["processes"]
    T_OSPF_NET = DB_TABLES["routing_ospf"]["networks"]
    T_OSPF_AREA = DB_TABLES["routing_ospf"]["areas"]
    T_OSPF_RANGE = DB_TABLES["routing_ospf"]["area_ranges"]
    T_OSPF_DIST = DB_TABLES["routing_ospf"]["distance"]
    T_OSPF_TUNE = DB_TABLES["routing_ospf"]["tuning"]
    T_OSPF_REDIS = DB_TABLES["routing_ospf"]["redistribute"]
    T_OSPF_PASS = DB_TABLES["routing_ospf"]["passive_interfaces"]
    T_OSPF_INTF = DB_TABLES["routing_ospf"]["interface_settings"]
    
    T_EIGRP_PROC = DB_TABLES["routing_eigrp"]["processes"]
    T_EIGRP_NET = DB_TABLES["routing_eigrp"]["networks"]
    T_EIGRP_INTF = DB_TABLES["routing_eigrp"]["interface_settings"]
    T_EIGRP_PASS = DB_TABLES["routing_eigrp"]["passive_interfaces"]
    T_EIGRP_DIST = DB_TABLES["routing_eigrp"]["distribute_lists"]
    T_EIGRP_OFF = DB_TABLES["routing_eigrp"]["offset_lists"]
    T_EIGRP_REDIS = DB_TABLES["routing_eigrp"]["redistribute"]
    T_EIGRP_KEY = DB_TABLES["routing_eigrp"]["key_chains"]

    T_STATIC_DEF = DB_TABLES["routing_static"]["default"]
    T_STATIC_RT = DB_TABLES["routing_static"]["routes"]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # --- PHẦN 1: THU THẬP DỮ LIỆU OSPF ---
        if target_module in ['ospf', 'all']:
            query_ospf = f"SELECT ospf_id, host, process_id, router_id, reference_bandwidth, passive_default, default_originate, default_originate_always, success FROM {T_OSPF_PROC}"
            params_ospf = []
            if target_ip != "all":
                query_ospf += " WHERE host = ?"
                params_ospf.append(target_ip)

            cursor.execute(query_ospf, tuple(params_ospf))
            for proc in cursor.fetchall():
                ospf_id, host, proc_id, router_id, ref_bw, passive_def, def_orig, def_always, proc_success = proc
                p_state = success_state(proc_success)
                
                d_orig = state_3(def_orig)
                d_always = state_3(def_always)
                def_orig_final = None
                if d_orig is True or d_always is True: 
                    def_orig_final = {"always": True if d_always is True else False}
                elif d_orig == "remove" or d_always == "remove": 
                    def_orig_final = "remove"

                config_data = {
                    "process_id": proc_id, 
                    "router_id": (router_id if router_id else "remove") if p_state != "ignore" else None,
                    "reference_bandwidth": (ref_bw if ref_bw else "remove") if p_state != "ignore" else None,
                    "passive_default": state_3(passive_def) if p_state != "ignore" else None,
                    "default_originate": def_orig_final if p_state != "ignore" else None,
                    "networks": [], "areas": [], "redistribute": [], "passive_interfaces": [], "interfaces": []
                }
                
                net_ids_add, net_ids_del = [], []
                area_ids_add, area_ids_del = [], []
                range_ids_add, range_ids_del = [], []
                dist_ids_add, dist_ids_del = [], []
                tune_ids_add, tune_ids_del = [], []
                redis_ids_add, redis_ids_del = [], []
                pass_ids_add, pass_ids_del = [], []
                intf_ids_add, intf_ids_del = [], []
                
                cursor.execute(f"SELECT id, network, wildcard, area, success FROM {T_OSPF_NET} WHERE ospf_id = ? AND (success = 0 OR success IS NULL OR success = -1)", (ospf_id,))
                for n_id, n_ip, n_wild, n_area, n_success in cursor.fetchall():
                    s_state = success_state(n_success)
                    config_data["networks"].append({"network": n_ip, "wildcard": n_wild, "area": n_area, "state": s_state})
                    if s_state == "remove": net_ids_del.append(n_id)
                    else: net_ids_add.append(n_id)

                cursor.execute(f"SELECT id, area_id, area_type, no_summary, authentication, success FROM {T_OSPF_AREA} WHERE ospf_id = ? AND (success <= 0 OR success IS NULL OR id IN (SELECT area_db_id FROM {T_OSPF_RANGE} WHERE success <= 0 OR success IS NULL))", (ospf_id,))
                for a_db_id, a_id, a_type, no_sum, auth, a_success in cursor.fetchall():
                    a_state = success_state(a_success)
                    area_item = {"id": a_id, "type": a_type, "no_summary": state_3(no_sum), "authentication": auth, "state": a_state}
                    
                    cursor.execute(f"SELECT id, ip, mask, advertise, cost, success FROM {T_OSPF_RANGE} WHERE area_db_id = ? AND (success = 0 OR success IS NULL OR success = -1)", (a_db_id,))
                    ranges = []
                    for r_id, r_ip, r_mask, r_adv, r_cost, r_success in cursor.fetchall():
                        r_state = success_state(r_success)
                        ranges.append({"ip": r_ip, "mask": r_mask, "advertise": False if r_adv in (0, '0', 0.0) else True, "cost": r_cost, "state": r_state})
                        if r_state == "remove": range_ids_del.append(r_id)
                        else: range_ids_add.append(r_id)
                    
                    if ranges: area_item["range"] = ranges
                    config_data["areas"].append(area_item)
                    
                    if a_state == "remove": area_ids_del.append(a_db_id)
                    elif a_state == "setup": area_ids_add.append(a_db_id) 

                cursor.execute(f"SELECT id, external, intra_area, inter_area, success FROM {T_OSPF_DIST} WHERE ospf_id = ? AND (success = 0 OR success IS NULL OR success = -1)", (ospf_id,))
                for d_id, ext, intra, inter, d_success in cursor.fetchall():
                    d_state = success_state(d_success)
                    config_data["distance"] = {"external": ext, "intra_area": intra, "inter_area": inter, "state": d_state}
                    if d_state == "remove": dist_ids_del.append(d_id)
                    else: dist_ids_add.append(d_id)

                cursor.execute(f"SELECT id, maximum_paths, max_lsa, spf_delay, spf_min_delay, spf_max_delay, lsa_delay, lsa_min_delay, lsa_max_delay, success FROM {T_OSPF_TUNE} WHERE ospf_id = ? AND (success = 0 OR success IS NULL OR success = -1)", (ospf_id,))
                for t_id, max_p, max_l, spf_d, spf_min, spf_max, lsa_d, lsa_min, lsa_max, t_success in cursor.fetchall():
                    t_state = success_state(t_success)
                    config_data["tuning"] = {"maximum_paths": max_p, "max_lsa": max_l, "timers": {"spf": {"delay": spf_d, "min_delay": spf_min, "max_delay": spf_max}, "lsa": {"delay": lsa_d, "min_delay": lsa_min, "max_delay": lsa_max}}, "state": t_state}
                    if t_state == "remove": tune_ids_del.append(t_id)
                    else: tune_ids_add.append(t_id)

                cursor.execute(f"SELECT id, protocol, process_id, subnets, metric, metric_type, route_map, success FROM {T_OSPF_REDIS} WHERE ospf_id = ? AND (success = 0 OR success IS NULL OR success = -1)", (ospf_id,))
                for r_id, proto, proto_id, subnets, metric, m_type, r_map, r_success in cursor.fetchall():
                    r_state = success_state(r_success)
                    config_data["redistribute"].append({"protocol": proto, "id": proto_id, "subnets": state_3(subnets), "metric": metric, "metric_type": m_type, "route_map": r_map, "state": r_state})
                    if r_state == "remove": redis_ids_del.append(r_id)
                    else: redis_ids_add.append(r_id)

                cursor.execute(f"SELECT id, interface_name, passive, success FROM {T_OSPF_PASS} WHERE ospf_id = ? AND (success = 0 OR success IS NULL OR success = -1)", (ospf_id,))
                for p_id, intf_name, pass_val, p_success in cursor.fetchall():
                    s_state = success_state(p_success)
                    p_final = "remove" if s_state == "remove" else state_3(pass_val)
                    if p_final is not None or s_state == "remove":
                        config_data["passive_interfaces"].append({"name": intf_name, "passive": p_final, "state": s_state})
                    if s_state == "remove": pass_ids_del.append(p_id)
                    else: pass_ids_add.append(p_id)

                cursor.execute(f"SELECT id, interface_name, area, cost, hello_interval, dead_interval, mtu_ignore, bfd, network_type, auth_type, success FROM {T_OSPF_INTF} WHERE ospf_id = ? AND (success = 0 OR success IS NULL OR success = -1)", (ospf_id,))
                for i_id, intf_name, area, cost, hello, dead, mtu, bfd, net_type, auth, i_success in cursor.fetchall():
                    i_state = success_state(i_success)
                    config_data["interfaces"].append({
                        "name": intf_name, "area": area, "cost": cost, "hello_interval": hello, "dead_interval": dead, 
                        "mtu_ignore": state_3(mtu), "bfd": state_3(bfd), "network_type": net_type, "auth_type": auth, "state": i_state
                    })
                    if i_state == "remove": intf_ids_del.append(i_id)
                    else: intf_ids_add.append(i_id)

                is_pending = (proc_success <= 0) or net_ids_add or net_ids_del or area_ids_add or area_ids_del or range_ids_add or range_ids_del or dist_ids_add or dist_ids_del or tune_ids_add or tune_ids_del or redis_ids_add or redis_ids_del or pass_ids_add or pass_ids_del or intf_ids_add or intf_ids_del

                if is_pending:
                    valid_data.append({
                        "module": "routing", "sub_type": "ospf", "action": "remove" if proc_success == -1 else "setup", 
                        "target": {"ip": host}, "ospf_id_db": ospf_id,
                        "net_ids_add": net_ids_add, "net_ids_del": net_ids_del, "area_ids_add": area_ids_add, "area_ids_del": area_ids_del,
                        "range_ids_add": range_ids_add, "range_ids_del": range_ids_del, "dist_ids_add": dist_ids_add, "dist_ids_del": dist_ids_del,
                        "tune_ids_add": tune_ids_add, "tune_ids_del": tune_ids_del, "redis_ids_add": redis_ids_add, "redis_ids_del": redis_ids_del,
                        "pass_ids_add": pass_ids_add, "pass_ids_del": pass_ids_del, "intf_ids_add": intf_ids_add, "intf_ids_del": intf_ids_del,
                        "config": [config_data]
                    })

    # --- PHẦN 2: THU THẬP DỮ LIỆU EIGRP ---
        if target_module in ['eigrp', 'all']:
            query_eigrp = f"SELECT eigrp_id, host, as_number, router_id, timers_active_time, bfd_all_interfaces, auto_summary, passive_default, metric_weights, distance_internal, distance_external, variance, maximum_paths, stub_enabled, stub_options, stub_leak_map, success, action_Cfg FROM {T_EIGRP_PROC}"
            params_eigrp = []
            if target_ip != "all":
                query_eigrp += " WHERE host = ?"
                params_eigrp.append(target_ip)

            cursor.execute(query_eigrp, tuple(params_eigrp))
            for proc in cursor.fetchall():
                e_id, host, as_num, r_id, t_active, bfd_all, auto_sum, pass_def, m_weights, d_int, d_ext, var, max_p, stub_en, stub_opt, stub_leak, proc_success, act_cfg = proc
                p_state = success_state(proc_success)
                
                push_router_id = has_eigrp_text_bit(act_cfg, 0)
                push_timers    = has_eigrp_text_bit(act_cfg, 1)
                push_bfd_all   = has_eigrp_text_bit(act_cfg, 2)
                push_auto_sum  = has_eigrp_text_bit(act_cfg, 3)
                push_pass_def  = has_eigrp_text_bit(act_cfg, 4)
                push_variance  = has_eigrp_text_bit(act_cfg, 5)
                push_max_paths = has_eigrp_text_bit(act_cfg, 6)

                config_data = {
                    "as_number": as_num, "state": p_state,
                    "router_id": r_id, "push_router_id": push_router_id,
                    "timers_active_time": t_active, "push_timers_active": push_timers,
                    "bfd_all_interfaces": bfd_all, "push_bfd_all": push_bfd_all,
                    "auto_summary": auto_sum, "push_auto_summary": push_auto_sum,
                    "passive_default": pass_def, "push_passive_def": push_pass_def,
                    "variance": var, "push_variance": push_variance,
                    "maximum_paths": max_p, "push_maximum_paths": push_max_paths,
                    "metric_weights": m_weights,
                    "distance_internal": d_int, "distance_external": d_ext,
                    "stub_enabled": stub_en, "stub_options": stub_opt, "stub_leak_map": stub_leak,
                    "networks": [], "interfaces": [], "redistribute": [],
                    "passive_interfaces": [], "distribute_lists": [], "offset_lists": [], "key_chains": []
                }
                
                # [1] BỐC DỮ LIỆU NETWORKS
                net_ids_add, net_ids_del = [], []
                cursor.execute(f"SELECT id, network, wildcard, success FROM {T_EIGRP_NET} WHERE eigrp_id = ?", (e_id,))
                for n_id, n_ip, n_wild, n_success in cursor.fetchall():
                    if p_state == "remove" or n_success in (-1, '-1'): n_state = "remove"
                    elif n_success in (0, '0', None): n_state = "setup"
                    else: n_state = "ignore"
                    
                    if n_state != "ignore":
                        config_data["networks"].append({"network": n_ip, "wildcard": n_wild, "state": n_state})
                        if n_state == "remove": net_ids_del.append(n_id)
                        else: net_ids_add.append(n_id)

                # [2] BỐC DỮ LIỆU REDISTRIBUTE
                redis_ids_add, redis_ids_del = [], []
                cursor.execute(f"SELECT id, protocol, metric_bw, metric_delay, metric_reliability, metric_load, metric_mtu, route_map, success FROM {T_EIGRP_REDIS} WHERE eigrp_id = ? AND (success <= 0 OR success IS NULL)", (e_id,))
                for r_id, proto, m_bw, m_dly, m_rel, m_load, m_mtu, r_map, r_success in cursor.fetchall():
                    r_state = success_state(r_success)
                    config_data["redistribute"].append({"protocol": proto, "metric_bw": m_bw, "metric_delay": m_dly, "metric_reliability": m_rel, "metric_load": m_load, "metric_mtu": m_mtu, "route_map": r_map, "state": r_state})
                    if r_state == "remove": redis_ids_del.append(r_id)
                    else: redis_ids_add.append(r_id)

                # [3] BỐC DỮ LIỆU PASSIVE INTERFACES
                pass_ids_add, pass_ids_del = [], []
                cursor.execute(f"SELECT id, interface_name, mode, success FROM {T_EIGRP_PASS} WHERE eigrp_id = ? AND (success <= 0 OR success IS NULL)", (e_id,))
                for p_id, intf_name, mode, p_success in cursor.fetchall():
                    p_state = success_state(p_success)
                    config_data["passive_interfaces"].append({"interface_name": intf_name, "mode": mode, "state": p_state})
                    if p_state == "remove": pass_ids_del.append(p_id)
                    else: pass_ids_add.append(p_id)

                # [4] BỐC DỮ LIỆU INTERFACE SETTINGS
                intf_ids_add, intf_ids_del = [], []
                cursor.execute(f"SELECT id, interface_name, bandwidth, delay, hello_interval, hold_time, auth_key_chain, summary_ip, summary_mask, split_horizon, bandwidth_percent, next_hop_self, bfd, bfd_tx, bfd_rx, bfd_multiplier, success FROM {T_EIGRP_INTF} WHERE eigrp_id = ? AND (success <= 0 OR success IS NULL)", (e_id,))
                for i_id, intf_name, bw, delay, hello, hold, auth, sum_ip, sum_mask, split, bw_pct, nhs, bfd, btx, brx, bmult, i_success in cursor.fetchall():
                    i_state = success_state(i_success)
                    config_data["interfaces"].append({"interface_name": intf_name, "bandwidth": bw, "delay": delay, "hello_interval": hello, "hold_time": hold, "auth_key_chain": auth, "summary_ip": sum_ip, "summary_mask": sum_mask, "split_horizon": split, "bandwidth_percent": bw_pct, "next_hop_self": nhs, "bfd": bfd, "bfd_tx": btx, "bfd_rx": brx, "bfd_multiplier": bmult, "state": i_state})
                    if i_state == "remove": intf_ids_del.append(i_id)
                    else: intf_ids_add.append(i_id)
                
                # [5] BỐC DỮ LIỆU KEY CHAINS
                key_ids_add, key_ids_del = [], []
                cursor.execute(f"SELECT id, chain_name, key_id, key_string, accept_lifetime, send_lifetime, success FROM {T_EIGRP_KEY} WHERE host = ? AND (success <= 0 OR success IS NULL)", (host,))
                for k_id_db, c_name, k_id_val, k_str, a_life, s_life, k_success in cursor.fetchall():
                    k_state = success_state(k_success)
                    config_data["key_chains"].append({
                        "chain_name": c_name, "key_id": k_id_val, "key_string": k_str, 
                        "accept_lifetime": a_life, "send_lifetime": s_life, "state": k_state
                    })
                    if k_state == "remove": key_ids_del.append(k_id_db)
                    else: key_ids_add.append(k_id_db)

                # [6] BỐC DỮ LIỆU OFFSET LISTS
                off_ids_add, off_ids_del = [], []
                cursor.execute(f"SELECT id, list_name, direction, value, interface_name, success FROM {T_EIGRP_OFF} WHERE eigrp_id = ? AND (success <= 0 OR success IS NULL)", (e_id,))
                for o_id_db, l_name, dir_val, val, intf_name, o_success in cursor.fetchall():
                    o_state = success_state(o_success)
                    config_data["offset_lists"].append({
                        "list_name": l_name, "direction": dir_val, "value": val, "interface_name": intf_name, "state": o_state
                    })
                    if o_state == "remove": off_ids_del.append(o_id_db)
                    else: off_ids_add.append(o_id_db)

                # [7] BỐC DỮ LIỆU DISTRIBUTE LISTS
                dist_ids_add, dist_ids_del = [], []
                cursor.execute(f"SELECT id, list_name, direction, interface_name, success FROM {T_EIGRP_DIST} WHERE eigrp_id = ? AND (success <= 0 OR success IS NULL)", (e_id,))
                for d_id_db, l_name, dir_val, intf_name, d_success in cursor.fetchall():
                    d_state = success_state(d_success)
                    config_data["distribute_lists"].append({
                        "list_name": l_name, "direction": dir_val, "interface_name": intf_name, "state": d_state
                    })
                    if d_state == "remove": dist_ids_del.append(d_id_db)
                    else: dist_ids_add.append(d_id_db)

                is_pending = (proc_success <= 0) or net_ids_add or net_ids_del or redis_ids_add or redis_ids_del or pass_ids_add or pass_ids_del or intf_ids_add or intf_ids_del or key_ids_add or key_ids_del or off_ids_add or off_ids_del or dist_ids_add or dist_ids_del

                if is_pending:
                    valid_data.append({
                        "module": "routing", "sub_type": "eigrp", "action": "remove" if proc_success == -1 else "setup", 
                        "target": {"ip": host}, "eigrp_id_db": e_id,
                        "net_ids_add": net_ids_add, "net_ids_del": net_ids_del,
                        "redis_ids_add": redis_ids_add, "redis_ids_del": redis_ids_del,
                        "pass_ids_add": pass_ids_add, "pass_ids_del": pass_ids_del,
                        "intf_ids_add": intf_ids_add, "intf_ids_del": intf_ids_del,
                        "key_ids_add": key_ids_add, "key_ids_del": key_ids_del,
                        "off_ids_add": off_ids_add, "off_ids_del": off_ids_del,
                        "dist_ids_add": dist_ids_add, "dist_ids_del": dist_ids_del,
                        "config": [config_data]
                    })
               

        # --- PHẦN 3: THU THẬP DỮ LIỆU STATIC & DEFAULT ROUTE ---
        if target_module in ['static', 'all']:
            hosts_data = defaultdict(lambda: {"def_routes": [], "stat_routes": [], "ids_add": {"def": [], "stat": []}, "ids_del": {"def": [], "stat": []}})

            query_def = f"SELECT id, host, next_hop_ip, success FROM {T_STATIC_DEF} WHERE (success = 0 OR success IS NULL OR success = -1)"
            params_def = []
            if target_ip != "all":
                query_def += " AND host = ?"
                params_def.append(target_ip)

            cursor.execute(query_def, tuple(params_def))
            for r_id, host, next_hop, success in cursor.fetchall():
                s_state = success_state(success)
                hosts_data[host]["def_routes"].append({"next_hop": next_hop, "state": s_state})
                if s_state == "remove": hosts_data[host]["ids_del"]["def"].append(r_id)
                else: hosts_data[host]["ids_add"]["def"].append(r_id)

            query_stat = f"SELECT id, host, network, subnet_mask, next_hop, ad, success FROM {T_STATIC_RT} WHERE (success = 0 OR success IS NULL OR success = -1)"
            params_stat = []
            if target_ip != "all":
                query_stat += " AND host = ?"
                params_stat.append(target_ip)

            cursor.execute(query_stat, tuple(params_stat))
            for r_id, host, net, mask, next_hop, ad, success in cursor.fetchall():
                s_state = success_state(success)
                route_item = {"network": net, "subnet_mask": mask, "next_hop": next_hop, "state": s_state}
                if ad: route_item["ad"] = ad
                hosts_data[host]["stat_routes"].append(route_item)
                if s_state == "remove": hosts_data[host]["ids_del"]["stat"].append(r_id)
                else: hosts_data[host]["ids_add"]["stat"].append(r_id)

            for host, data in hosts_data.items():
                config_data = {}
                if data["def_routes"]: config_data["default_routes"] = data["def_routes"]
                if data["stat_routes"]: config_data["static_routes"] = data["stat_routes"]

                if config_data:
                    valid_data.append({
                        "module": "routing", "sub_type": "static", "action": "setup",
                        "target": {"ip": host},
                        "tracking_ids": {"ids_add": data["ids_add"], "ids_del": data["ids_del"]},
                        "config": [config_data]
                    })

    except Exception as e:
        print(f"[-] Lỗi truy xuất Database: {e}")
        return
    finally:
        if 'conn' in locals(): conn.close()

    # --- PHẦN 4: ĐẨY LỆNH XUỐNG WORKER & UPDATE DB THÀNH CÔNG ---
    if not valid_data:
        print(f"\n[INFO] Không có dữ liệu {target_module.upper()} nào cần cập nhật cho {target_ip}.")
        return

    print(f"\n[INFO] Đang đẩy {len(valid_data)} gói cấu hình từ DB sang Worker...")
    run_routing_config(valid_data, DB_PATH, ROUTE_OUTPUT)

    if os.path.exists(ROUTE_OUTPUT):
        try:
            with open(ROUTE_OUTPUT, 'r', encoding='utf-8') as f:
                out_results = json.load(f)

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            ui_report = []
            success_count = 0

            for res in out_results:
                ip = res.get("target")
                status = res.get("status")
                report_item = {"ip": ip, "status": "SUCCESS" if status == "success" else "FAIL", "log": res.get("message", res.get("msg", "")), "db_updated": False}

                if status == "success":
                    for item in valid_data:
                        if item["target"]["ip"] == ip:
                            # --- 1. UPDATE DB CHO OSPF ---
                            if item["sub_type"] == "ospf":
                                o_id = item["ospf_id_db"]
                                if item["action"] == "remove": 
                                    cursor.execute(f"DELETE FROM {T_OSPF_PROC} WHERE ospf_id = ?", (o_id,))
                                else: 
                                    cursor.execute(f"UPDATE {T_OSPF_PROC} SET success = 1{clean_sql(['passive_default', 'default_originate', 'default_originate_always'])} WHERE ospf_id = ?", (o_id,))
                                
                                for n_id in item["net_ids_add"]: cursor.execute(f"UPDATE {T_OSPF_NET} SET success = 1 WHERE id = ?", (n_id,))
                                for n_id in item["net_ids_del"]: cursor.execute(f"DELETE FROM {T_OSPF_NET} WHERE id = ?", (n_id,))
                                
                                for a_id in item["area_ids_add"]: cursor.execute(f"UPDATE {T_OSPF_AREA} SET success = 1{clean_sql(['no_summary'])} WHERE id = ?", (a_id,))
                                for a_id in item["area_ids_del"]: cursor.execute(f"DELETE FROM {T_OSPF_AREA} WHERE id = ?", (a_id,))
                                
                                for r_id in item["range_ids_add"]: cursor.execute(f"UPDATE {T_OSPF_RANGE} SET success = 1 WHERE id = ?", (r_id,))
                                for r_id in item["range_ids_del"]: cursor.execute(f"DELETE FROM {T_OSPF_RANGE} WHERE id = ?", (r_id,))
                                
                                for d_id in item["dist_ids_add"]: cursor.execute(f"UPDATE {T_OSPF_DIST} SET success = 1 WHERE id = ?", (d_id,))
                                for d_id in item["dist_ids_del"]: cursor.execute(f"DELETE FROM {T_OSPF_DIST} WHERE id = ?", (d_id,))
                                
                                for t_id in item["tune_ids_add"]: cursor.execute(f"UPDATE {T_OSPF_TUNE} SET success = 1 WHERE id = ?", (t_id,))
                                for t_id in item["tune_ids_del"]: cursor.execute(f"DELETE FROM {T_OSPF_TUNE} WHERE id = ?", (t_id,))
                                
                                for re_id in item["redis_ids_add"]: cursor.execute(f"UPDATE {T_OSPF_REDIS} SET success = 1{clean_sql(['subnets'])} WHERE id = ?", (re_id,))
                                for re_id in item["redis_ids_del"]: cursor.execute(f"DELETE FROM {T_OSPF_REDIS} WHERE id = ?", (re_id,))
                                
                                for p_id in item["pass_ids_add"]: cursor.execute(f"UPDATE {T_OSPF_PASS} SET success = 1{clean_sql(['passive'])} WHERE id = ?", (p_id,))
                                for p_id in item["pass_ids_del"]: cursor.execute(f"DELETE FROM {T_OSPF_PASS} WHERE id = ?", (p_id,))
                                
                                for i_id in item["intf_ids_add"]: cursor.execute(f"UPDATE {T_OSPF_INTF} SET success = 1{clean_sql(['mtu_ignore', 'bfd'])} WHERE id = ?", (i_id,))
                                for i_id in item["intf_ids_del"]: cursor.execute(f"DELETE FROM {T_OSPF_INTF} WHERE id = ?", (i_id,))

                            # --- 2. UPDATE DB CHO EIGRP (FULL 8 BẢNG) ---
                            elif item["sub_type"] == "eigrp":
                                e_id = item["eigrp_id_db"]
                                if item["action"] == "remove":
                                    cursor.execute(f"DELETE FROM {T_EIGRP_PROC} WHERE eigrp_id = ?", (e_id,))
                                else:
                                    cursor.execute(f"UPDATE {T_EIGRP_PROC} SET success = 1 WHERE eigrp_id = ?", (e_id,))
                                
                                # Cập nhật các bảng con dựa trên tracking list từ cấu trúc dữ liệu
                                for n_id in item.get("net_ids_add", []): cursor.execute(f"UPDATE {T_EIGRP_NET} SET success = 1 WHERE id = ?", (n_id,))
                                for n_id in item.get("net_ids_del", []): cursor.execute(f"DELETE FROM {T_EIGRP_NET} WHERE id = ?", (n_id,))
                                
                                for r_id in item.get("redis_ids_add", []): cursor.execute(f"UPDATE {T_EIGRP_REDIS} SET success = 1 WHERE id = ?", (r_id,))
                                for r_id in item.get("redis_ids_del", []): cursor.execute(f"DELETE FROM {T_EIGRP_REDIS} WHERE id = ?", (r_id,))
                                
                                for p_id in item.get("pass_ids_add", []): cursor.execute(f"UPDATE {T_EIGRP_PASS} SET success = 1 WHERE id = ?", (p_id,))
                                for p_id in item.get("pass_ids_del", []): cursor.execute(f"DELETE FROM {T_EIGRP_PASS} WHERE id = ?", (p_id,))
                                
                                for i_id in item.get("intf_ids_add", []): cursor.execute(f"UPDATE {T_EIGRP_INTF} SET success = 1 WHERE id = ?", (i_id,))
                                for i_id in item.get("intf_ids_del", []): cursor.execute(f"DELETE FROM {T_EIGRP_INTF} WHERE id = ?", (i_id,))
                                
                                for d_id in item.get("dist_ids_add", []): cursor.execute(f"UPDATE {T_EIGRP_DIST} SET success = 1 WHERE id = ?", (d_id,))
                                for d_id in item.get("dist_ids_del", []): cursor.execute(f"DELETE FROM {T_EIGRP_DIST} WHERE id = ?", (d_id,))
                                
                                for o_id in item.get("off_ids_add", []): cursor.execute(f"UPDATE {T_EIGRP_OFF} SET success = 1 WHERE id = ?", (o_id,))
                                for o_id in item.get("off_ids_del", []): cursor.execute(f"DELETE FROM {T_EIGRP_OFF} WHERE id = ?", (o_id,))
                                
                                for k_id in item.get("key_ids_add", []): cursor.execute(f"UPDATE {T_EIGRP_KEY} SET success = 1 WHERE id = ?", (k_id,))
                                for k_id in item.get("key_ids_del", []): cursor.execute(f"DELETE FROM {T_EIGRP_KEY} WHERE id = ?", (k_id,))
                                
                                # Cập nhật danh sách Key Chains và Offset Lists
                                for k_id in item.get("key_ids_add", []): 
                                    cursor.execute(f"UPDATE {T_EIGRP_KEY} SET success = 1 WHERE id = ?", (k_id,))
                                for k_id in item.get("key_ids_del", []): 
                                    cursor.execute(f"DELETE FROM {T_EIGRP_KEY} WHERE id = ?", (k_id,))
                                
                                for o_id in item.get("off_ids_add", []): 
                                    cursor.execute(f"UPDATE {T_EIGRP_OFF} SET success = 1 WHERE id = ?", (o_id,))
                                for o_id in item.get("off_ids_del", []): 
                                    cursor.execute(f"DELETE FROM {T_EIGRP_OFF} WHERE id = ?", (o_id,))

                                # Cập nhật trạng thái cho Distribute Lists
                                for d_id in item.get("dist_ids_add", []): 
                                    cursor.execute(f"UPDATE {T_EIGRP_DIST} SET success = 1 WHERE id = ?", (d_id,))
                                for d_id in item.get("dist_ids_del", []): 
                                    cursor.execute(f"DELETE FROM {T_EIGRP_DIST} WHERE id = ?", (d_id,))
                                # --------------------------------------
                            # --- 3. UPDATE DB CHO STATIC ROUTE ---
                            elif item["sub_type"] == "static":
                                track = item["tracking_ids"]
                                for d_id in track["ids_add"]["def"]: cursor.execute(f"UPDATE {T_STATIC_DEF} SET success = 1 WHERE id = ?", (d_id,))
                                for s_id in track["ids_add"]["stat"]: cursor.execute(f"UPDATE {T_STATIC_RT} SET success = 1 WHERE id = ?", (s_id,))
                                for d_id in track["ids_del"]["def"]: cursor.execute(f"DELETE FROM {T_STATIC_DEF} WHERE id = ?", (d_id,))
                                for s_id in track["ids_del"]["stat"]: cursor.execute(f"DELETE FROM {T_STATIC_RT} WHERE id = ?", (s_id,))

                    success_count += 1
                    report_item["db_updated"] = True

                ui_report.append(report_item)

            conn.commit()
            conn.close()
            print(f"\n[*] Đã đồng bộ Database thành công cho {success_count} thiết bị.")

            # Xuất log cho UI Frontend
            log_filename = f"routing_log_{target_module}_{target_ip.replace('.', '_')}.json" if target_ip != "all" else "master_routing_log.json"
            os.makedirs(TMP_DIR, exist_ok=True)
            log_file_path = os.path.join(TMP_DIR, log_filename)
            with open(log_file_path, 'w', encoding='utf-8') as log_file:
                json.dump(ui_report, log_file, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"[-] Lỗi trong quá trình cập nhật kết quả: {e}")

# =====================================================================
# KHỐI LỆNH TERMINAL (DÀNH CHO GỌI TỪ CMD/POWERSHELL)
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Routing Automation Controller")
    parser.add_argument("-t", "--target", type=str, default="all", help="IP của Router (Mặc định: all)")
    parser.add_argument("-m", "--module", type=str, choices=['ospf', 'eigrp', 'static', 'all'], default="all", help="Giao thức (ospf, eigrp, static, all)")
    args = parser.parse_args()

    # Truyền lệnh từ Terminal vào hàm điều phối
    routing_dispatcher(target_ip=args.target, target_module=args.module)