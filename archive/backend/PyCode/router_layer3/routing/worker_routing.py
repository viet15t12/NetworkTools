import os
import json
import yaml
import sys
import sqlite3
import requests
import urllib3
import time
from jinja2 import Environment, FileSystemLoader

# --- SETUP NORNIR & NETMIKO ---
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config
from nornir.core.task import Result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# CƠ CHẾ ĐƯỜNG DẪN ĐỒNG BỘ 100%
# =====================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# GỌI CÁC THAM SỐ TỪ TRẠM KIỂM SOÁT
from PyCode.share.config import TMP_DIR, ROUTING_TEMPLATE_DIR, DB_TABLES

def render_routing_config(platform, sub_type, config_data, mode):
    # Dùng ROUTING_TEMPLATE_DIR quy hoạch sẵn trong config.py
    template_dir = os.path.join(ROUTING_TEMPLATE_DIR, platform)
    template_file = f"{sub_type}/{sub_type}.j2"
    if not os.path.exists(os.path.join(template_dir, template_file)):
        raise Exception(f"MISSING TEMPLATE: {template_file}")
    try:
        env = Environment(loader=FileSystemLoader(template_dir))
        return env.get_template(template_file).render(config=config_data, mode=mode)
    except Exception as e:
        raise Exception(f"JINJA2 ERROR: {str(e)}")

# =========================================================
# 2. XỬ LÝ RESTCONF DÙNG API LÀ CHÍNH - MASTER VERSION
# (Giữ nguyên siêu thuật toán RESTCONF của sếp, cực kỳ tối ưu!)
# =========================================================
def handle_restconf_routing(task, payload, mode, sub_type):
    host_ip = task.host.hostname
    user, pw = task.host.username, task.host.password
    headers = {"Accept": "application/yang-data+json", "Content-Type": "application/yang-data+json"}
    config_data = payload.get("config", [{}])[0]
    
    router_patch_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router"
    
    if sub_type == "ospf":
        pid = config_data.get("process_id", 1)
        
        # --- BẮN TỈA TỐI ƯU HÓA HỆ THỐNG (TUNING) ---
        tuning = config_data.get("tuning", {})
        if isinstance(tuning, dict):
            if tuning.get("maximum_paths") in ["remove", "absent", "none"]:
                requests.delete(f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/maximum-paths", auth=(user, pw), headers=headers, verify=False)
                tuning.pop("maximum_paths", None)
            
            if tuning.get("max_lsa") in ["remove", "absent", "none"]:
                requests.delete(f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/max-lsa", auth=(user, pw), headers=headers, verify=False)
                tuning.pop("max_lsa", None)

            if tuning.get("timers") in ["remove", "absent", "none"]:
                requests.delete(f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/timers", auth=(user, pw), headers=headers, verify=False)
                tuning.pop("timers", None)
                
            if not tuning: config_data.pop("tuning", None)

        # --- XỬ LÝ TUYẾN ĐƯỜNG NGOẠI LAI (EXTERNAL) BẰNG DIRECT API ---
        def_orig = config_data.get("default_originate")
        if def_orig in ["remove", "absent", "none"] or (isinstance(def_orig, dict) and def_orig.get("state") in ["remove", "absent"]):
            requests.delete(f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/default-information", auth=(user, pw), headers=headers, verify=False)
            config_data.pop("default_originate", None)
        elif def_orig or isinstance(def_orig, dict):
            inner_def = {}
            if isinstance(def_orig, dict) and def_orig.get("always"): inner_def["always"] = [None]
            patch_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}"
            patch_payload = {"Cisco-IOS-XE-ospf:process-id": [{"id": pid, "default-information": {"originate": inner_def}}]}
            requests.patch(patch_url, auth=(user, pw), headers=headers, json=patch_payload, verify=False)
            config_data.pop("default_originate", None)

        # --- XỬ LÝ KHOẢNG CÁCH QUẢN TRỊ (DISTANCE OSPF) ---
        distance_cfg = config_data.get("distance")
        if isinstance(distance_cfg, dict):
            if distance_cfg.get("state") in ["remove", "absent"]:
                dist_del_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/distance/ospf"
                requests.delete(dist_del_url, auth=(user, pw), headers=headers, verify=False)
            else:
                inner_dist = {}
                if "external" in distance_cfg: inner_dist["external"] = distance_cfg["external"]
                if "inter_area" in distance_cfg: inner_dist["inter-area"] = distance_cfg["inter_area"]
                if "intra_area" in distance_cfg: inner_dist["intra-area"] = distance_cfg["intra_area"]
                
                if inner_dist:
                    dist_patch_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}"
                    dist_payload = {"Cisco-IOS-XE-ospf:process-id": [{"id": pid, "distance": {"ospf": inner_dist}}]}
                    requests.patch(dist_patch_url, auth=(user, pw), headers=headers, json=dist_payload, verify=False)
            config_data.pop("distance", None)

        # --- A. GỠ NETWORK & PASSIVE ---
        for net in config_data.get("networks", []):
            if net.get("state") in ["remove", "absent"]:
                u = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/network={net.get('network')},{net.get('wildcard')}"
                requests.delete(u, auth=(user, pw), headers=headers, verify=False)
        
        for intf in config_data.get("passive_interfaces", []):
            if str(intf.get("passive")).lower() == "false" or intf.get("passive") is False:
                u = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/passive-interface/interface={intf.get('name')}"
                requests.delete(u, auth=(user, pw), headers=headers, verify=False)

        # --- B. QUẢN LÝ AREA (BACKUP TOÀN DIỆN VÀ LÀM SẠCH) ---
        active_areas = []
        for area in config_data.get("areas", []):
            area_id = area.get("id")
            base_area_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/area={area_id}"
            
            if area.get("state") in ["remove", "absent"]:
                requests.delete(base_area_url, auth=(user, pw), headers=headers, verify=False)
                continue

            auth_req = area.get("authentication")
            if (auth_req in ["remove", "none", "absent"]) or (isinstance(auth_req, dict) and auth_req.get("type") in ["remove", "none", "absent"]):
                requests.delete(f"{base_area_url}/authentication", auth=(user, pw), headers=headers, verify=False)
                area.pop("authentication", None)

            area_range = area.get("range")
            if isinstance(area_range, dict) and area_range.get("state") in ["remove", "absent"]:
                r_ip, r_mask = area_range.get("ip"), area_range.get("mask")
                if r_ip and r_mask: requests.delete(f"{base_area_url}/ipv4-range/range={r_ip},{r_mask}", auth=(user, pw), headers=headers, verify=False)
                area.pop("range", None)

            area_type = area.get("type")
            if (area_type in ["normal", "remove", "absent"]) or (area_type in ["stub", "nssa"]):
                backup_area = {}
                get_res = requests.get(base_area_url, auth=(user, pw), headers=headers, verify=False)
                if get_res.status_code == 200:
                    try:
                        curr_area = get_res.json().get("Cisco-IOS-XE-ospf:area", [{}])[0]
                        curr_area.pop("stub", None)
                        curr_area.pop("nssa", None)
                        backup_area = curr_area
                    except: pass

                requests.delete(base_area_url, auth=(user, pw), headers=headers, verify=False)
                time.sleep(1.5)
                
                if len(backup_area.keys()) > 1:
                    restore_payload = {"Cisco-IOS-XE-native:router": {"Cisco-IOS-XE-ospf:router-ospf": {"ospf": {"process-id": [{"id": pid, "area": [backup_area]}]}}}}
                    requests.patch(router_patch_url, auth=(user, pw), headers=headers, json=restore_payload, verify=False)

                if area_type in ["normal", "remove", "absent"]: area.pop("type", None)
            
            if set(area.keys()) - {"id"}: active_areas.append(area)

        config_data["areas"] = active_areas

    time.sleep(1)

    # --- C. PATCH CUỐI CÙNG QUA JINJA2 ---
    if not any([bool(config_data.get("areas")), bool(config_data.get("networks")), bool(config_data.get("passive_interfaces")), bool(config_data.get("tuning"))]):
        return "Success 204 (Cleared/Normal)"

    template_dir = os.path.join(ROUTING_TEMPLATE_DIR, task.host.data['template_folder'])
    env = Environment(loader=FileSystemLoader(template_dir))
    json_payload = env.get_template(f"{sub_type}/{sub_type}_restconf.j2").render(config=config_data, mode=mode)
    
    res = requests.patch(router_patch_url, auth=(user, pw), headers=headers, json=json.loads(json_payload), verify=False)
    
    if res.status_code >= 400: raise Exception(f"HTTP {res.status_code} - Router từ chối nhịp PATCH: {res.text}")
    return f"Success {res.status_code}"

# =========================================================
# 3. ĐIỀU PHỐI (Dispatcher) & RUNNER
# =========================================================
def task_push_routing(task):
    my_payload = task.host.data["ui_payload"]
    sub_type = my_payload.get("sub_type", "static").lower()
    mode = my_payload.get("action", "setup").lower()
    method = task.host.data.get("method", "RESTCONF")
    
    # 1. Hỗ trợ giao thức RESTCONF
    if method == "RESTCONF":
        return Result(host=task.host, result=handle_restconf_routing(task, my_payload, mode, sub_type))
    
    all_commands = []
    
    # 2. Xử lý Payload thành Config JSON
    raw_config = my_payload.get("config", [])
    configs = [raw_config] if isinstance(raw_config, dict) else raw_config
    
    # 3. Quăng vào Jinja2 nhào nặn ra Lệnh CLI
    for cfg in configs:
        commands = render_routing_config(task.host.data["template_folder"], sub_type, cfg, mode)
        if commands:
            all_commands.extend([l.strip() for l in commands.splitlines() if l.strip() and not l.strip().startswith('!')])

    if not all_commands: 
        return "No commands."
    
    # ==============================================================
    # [BÍ KÍP 1] IN LỆNH SẼ CHẠY (Thấy trước lệnh - Ống nhòm)
    # ==============================================================
    print(f"\n[+] ĐANG CHUẨN BỊ LỆNH XUỐNG: {task.host.hostname} (Giao thức: {sub_type.upper()})")
    print("-" * 50)
    for cmd in all_commands:
        print(f"  {cmd}")
    print("-" * 50)

    # 4. Bịt mồm Log OSPF/EIGRP để tránh nhiễu Netmiko
    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")

    # [FIX] Tự động bật lại Log sau khi cấu hình xong (Áp dụng cho mọi giao thức)
    all_commands.append("logging console")
    all_commands.append("logging monitor")

    # 5. Gõ lệnh thật xuống Router
    res = task.run(
        task=netmiko_send_config, 
        config_commands=all_commands,
        read_timeout=120,
        cmd_verify=False
    )
    
    output_log = res[0].result

    # ==============================================================
    # [BÍ KÍP 2] IN LOG PHẢN HỒI THỰC TẾ TỪ ROUTER
    # ==============================================================
    print(f"\n[>] LOG TRẢ VỀ TỪ ROUTER {task.host.hostname}:")
    print(output_log)
    print("=" * 50)

    return output_log

def build_worker_inventory(db_path, task_list):
    task_map = {item.get("target", {}).get("ip"): item for item in task_list if item.get("target", {}).get("ip")}
    hosts_yaml = {}
    
    # Lấy tên bảng thiết bị từ Trạm kiểm soát
    T_DEVICES = DB_TABLES["device_info"]["main"]
    
    try:
        conn_db = sqlite3.connect(db_path)
        cursor = conn_db.cursor()
        for ip, payload in task_map.items():
            # Dùng f-string gọi biến bảng
            cursor.execute(f'SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host = ?', (ip,))
            row = cursor.fetchone()
            if row:
                dev_name, db_user, db_pass, db_os, db_port, db_method = row
                platform = "cisco_ios" if db_os == "cisco" else db_os
                tpl_folder = "cisco_ios" if platform == "cisco_ios_telnet" else platform
                
                hosts_yaml[dev_name or ip] = {
                    "hostname": ip, 
                    "username": db_user, 
                    "password": db_pass,
                    "port": int(db_port) if db_port else (23 if db_method == "TELNET" else 22), 
                    "platform": platform,
                    "connection_options": {
                        "netmiko": {
                            "extras": {
                                "banner_timeout": 30,
                                "auth_timeout": 30,
                                "session_timeout": 60,
                                "global_delay_factor": 2 
                            }
                        }
                    },
                    "data": {"template_folder": tpl_folder, "ui_payload": payload, "method": db_method}
                }
        conn_db.close()
    except Exception as e: 
        print(f"[-] Lỗi build inventory: {e}")
    
    inv_file_path = os.path.join(TMP_DIR, "tmp_route_inventory.yaml")
    with open(inv_file_path, 'w', encoding='utf-8') as f: yaml.dump(hosts_yaml, f)
    return inv_file_path

def run_routing_config(input_data, db_path, output_path):
    print(f"\n[INFO] Starting Routing Worker...")
    inv_file_path = build_worker_inventory(db_path, input_data)
    if not inv_file_path: return
    
    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 5}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file_path}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_push_routing)
    output_data = []
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        message = str(task_res.exception) if task_res.failed else (str(task_res[0].result) if hasattr(task_res[0], 'result') else str(task_res[0]))
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": message})
        print(f"[{'+' if status == 'success' else '-'}] {host}: {message}")
        
    with open(output_path, 'w', encoding='utf-8') as f: json.dump(output_data, f, indent=4, ensure_ascii=False)
    if os.path.exists(inv_file_path): os.remove(inv_file_path)