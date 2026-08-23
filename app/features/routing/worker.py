import os
import json
import sys
import sqlite3
import requests
import urllib3
import time
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader

# --- SETUP NORNIR & NETMIKO ---
from nornir.core import Nornir
from nornir.core.configuration import Config
from nornir.core.inventory import ConnectionOptions, Host, Hosts, Inventory
from nornir.core.plugins.connections import ConnectionPluginRegister
from infrastructure.network.nornir_netmiko_tasks import netmiko_send_config
from nornir.core.task import Result
from nornir.init_nornir import load_runner

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
NETWORK_TIMEOUT = 15

# =====================================================================
# CƠ CHẾ ĐƯỜNG DẪN ĐỒNG BỘ 100%
# =====================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../.."))
FEATURES_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
if FEATURES_ROOT not in sys.path:
    sys.path.append(FEATURES_ROOT)

# GỌI CÁC THAM SỐ TỪ TRẠM KIỂM SOÁT
from infrastructure.network.config import TMP_DIR, ROUTING_TEMPLATE_DIR, DB_TABLES
from infrastructure.network.nornir_netmiko_plugin import register_networktools_netmiko

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
                requests.delete(f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/maximum-paths", auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
                tuning.pop("maximum_paths", None)
            
            if tuning.get("max_lsa") in ["remove", "absent", "none"]:
                requests.delete(f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/max-lsa", auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
                tuning.pop("max_lsa", None)

            if tuning.get("timers") in ["remove", "absent", "none"]:
                requests.delete(f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/timers", auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
                tuning.pop("timers", None)
                
            if not tuning: config_data.pop("tuning", None)

        # --- XỬ LÝ TUYẾN ĐƯỜNG NGOẠI LAI (EXTERNAL) BẰNG DIRECT API ---
        def_orig = config_data.get("default_originate")
        if def_orig in ["remove", "absent", "none"] or (isinstance(def_orig, dict) and def_orig.get("state") in ["remove", "absent"]):
            requests.delete(f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/default-information", auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
            config_data.pop("default_originate", None)
        elif def_orig or isinstance(def_orig, dict):
            inner_def = {}
            if isinstance(def_orig, dict) and def_orig.get("always"): inner_def["always"] = [None]
            patch_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}"
            patch_payload = {"Cisco-IOS-XE-ospf:process-id": [{"id": pid, "default-information": {"originate": inner_def}}]}
            requests.patch(patch_url, auth=(user, pw), headers=headers, json=patch_payload, verify=False, timeout=NETWORK_TIMEOUT)
            config_data.pop("default_originate", None)

        # --- XỬ LÝ KHOẢNG CÁCH QUẢN TRỊ (DISTANCE OSPF) ---
        distance_cfg = config_data.get("distance")
        if isinstance(distance_cfg, dict):
            if distance_cfg.get("state") in ["remove", "absent"]:
                dist_del_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/distance/ospf"
                requests.delete(dist_del_url, auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
            else:
                inner_dist = {}
                if "external" in distance_cfg: inner_dist["external"] = distance_cfg["external"]
                if "inter_area" in distance_cfg: inner_dist["inter-area"] = distance_cfg["inter_area"]
                if "intra_area" in distance_cfg: inner_dist["intra-area"] = distance_cfg["intra_area"]
                
                if inner_dist:
                    dist_patch_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}"
                    dist_payload = {"Cisco-IOS-XE-ospf:process-id": [{"id": pid, "distance": {"ospf": inner_dist}}]}
                    requests.patch(dist_patch_url, auth=(user, pw), headers=headers, json=dist_payload, verify=False, timeout=NETWORK_TIMEOUT)
            config_data.pop("distance", None)

        # --- A. GỠ NETWORK & PASSIVE ---
        for net in config_data.get("networks", []):
            if net.get("state") in ["remove", "absent"]:
                u = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/network={net.get('network')},{net.get('wildcard')}"
                requests.delete(u, auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
        
        for intf in config_data.get("passive_interfaces", []):
            if str(intf.get("passive")).lower() == "false" or intf.get("passive") is False:
                u = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/passive-interface/interface={intf.get('name')}"
                requests.delete(u, auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)

        # --- B. QUẢN LÝ AREA (BACKUP TOÀN DIỆN VÀ LÀM SẠCH) ---
        active_areas = []
        for area in config_data.get("areas", []):
            area_id = area.get("id")
            base_area_url = f"https://{host_ip}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={pid}/area={area_id}"
            
            if area.get("state") in ["remove", "absent"]:
                requests.delete(base_area_url, auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
                continue

            auth_req = area.get("authentication")
            if (auth_req in ["remove", "none", "absent"]) or (isinstance(auth_req, dict) and auth_req.get("type") in ["remove", "none", "absent"]):
                requests.delete(f"{base_area_url}/authentication", auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
                area.pop("authentication", None)

            area_range = area.get("range")
            if isinstance(area_range, dict) and area_range.get("state") in ["remove", "absent"]:
                r_ip, r_mask = area_range.get("ip"), area_range.get("mask")
                if r_ip and r_mask: requests.delete(f"{base_area_url}/ipv4-range/range={r_ip},{r_mask}", auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
                area.pop("range", None)

            area_type = area.get("type")
            if (area_type in ["normal", "remove", "absent"]) or (area_type in ["stub", "nssa"]):
                backup_area = {}
                get_res = requests.get(base_area_url, auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
                if get_res.status_code == 200:
                    try:
                        curr_area = get_res.json().get("Cisco-IOS-XE-ospf:area", [{}])[0]
                        curr_area.pop("stub", None)
                        curr_area.pop("nssa", None)
                        backup_area = curr_area
                    except: pass

                requests.delete(base_area_url, auth=(user, pw), headers=headers, verify=False, timeout=NETWORK_TIMEOUT)
                time.sleep(1.5)
                
                if len(backup_area.keys()) > 1:
                    restore_payload = {"Cisco-IOS-XE-native:router": {"Cisco-IOS-XE-ospf:router-ospf": {"ospf": {"process-id": [{"id": pid, "area": [backup_area]}]}}}}
                    requests.patch(router_patch_url, auth=(user, pw), headers=headers, json=restore_payload, verify=False, timeout=NETWORK_TIMEOUT)

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
    
    res = requests.patch(router_patch_url, auth=(user, pw), headers=headers, json=json.loads(json_payload), verify=False, timeout=NETWORK_TIMEOUT)
    
    if res.status_code >= 400: raise Exception(f"HTTP {res.status_code} - Router rejected PATCH request: {res.text}")
    return f"Success {res.status_code}"

# =========================================================
# 3. ĐIỀU PHỐI (Dispatcher) & RUNNER
# =========================================================
def build_cli_routing_commands(payload, template_folder, sub_type, mode):
    all_commands = []

    raw_config = payload.get("config", [])
    configs = [raw_config] if isinstance(raw_config, dict) else raw_config

    for cfg in configs:
        commands = render_routing_config(template_folder, sub_type, cfg, mode)
        if commands:
            all_commands.extend([l.strip() for l in commands.splitlines() if l.strip() and not l.strip().startswith('!')])

    if not all_commands:
        return []

    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")
    all_commands.append("logging console")
    all_commands.append("logging monitor")
    return all_commands


def print_cli_routing_commands(hostname, sub_type, commands):
    visible_commands = [
        cmd for cmd in commands
        if cmd not in {"no logging console", "no logging monitor", "logging console", "logging monitor"}
    ]
    print(f"\n[INFO] Preparing commands for {hostname} (protocol: {sub_type.upper()})")
    print("-" * 50)
    for cmd in visible_commands:
        print(f"  {cmd}")
    print("-" * 50)


def send_cli_routing_commands(hostname, connection, sub_type, commands):
    if not commands:
        return "No commands."

    print_cli_routing_commands(hostname, sub_type, commands)

    check_enable_mode = getattr(connection, "check_enable_mode", None)
    enable = getattr(connection, "enable", None)
    if callable(check_enable_mode) and callable(enable) and not check_enable_mode():
        enable()

    output_log = connection.send_config_set(
        commands,
        read_timeout=60,
        cmd_verify=False,
    )

    print(f"\n[INFO] Router response log from {hostname}:")
    print(output_log)
    print("=" * 50)
    return output_log


def apply_routing_with_connector(connector, payload):
    sub_type = payload.get("sub_type", "static").lower()
    mode = payload.get("action", "setup").lower()
    connection = getattr(connector, "connection", None)
    if connection is None:
        raise RuntimeError("Active tab session has no Netmiko connection.")

    device_type = str(getattr(connector, "device_type", "") or "cisco_ios")
    template_folder = "cisco_ios" if device_type == "cisco_ios_telnet" else device_type
    commands = build_cli_routing_commands(payload, template_folder, sub_type, mode)
    return send_cli_routing_commands(getattr(connector, "host", "device"), connection, sub_type, commands)


def apply_routing_batch_with_connector(connector, payloads):
    """Apply every pending routing package for one host in one config transaction."""
    connection = getattr(connector, "connection", None)
    if connection is None:
        raise RuntimeError("Active tab session has no Netmiko connection.")
    device_type = str(getattr(connector, "device_type", "") or "cisco_ios")
    template_folder = "cisco_ios" if device_type == "cisco_ios_telnet" else device_type
    wrappers = {
        "no logging console", "no logging monitor",
        "logging console", "logging monitor",
    }
    commands = []
    for payload in payloads:
        rendered = build_cli_routing_commands(
            payload,
            template_folder,
            payload.get("sub_type", "static").lower(),
            payload.get("action", "setup").lower(),
        )
        commands.extend(command for command in rendered if command not in wrappers)
    if not commands:
        return "No commands."
    combined = ["no logging console", "no logging monitor", *commands,
                "logging console", "logging monitor"]
    return send_cli_routing_commands(
        getattr(connector, "host", "device"), connection, "batch", combined
    )


def task_push_routing(task):
    my_payload = task.host.data["ui_payload"]
    sub_type = my_payload.get("sub_type", "static").lower()
    mode = my_payload.get("action", "setup").lower()
    method = task.host.data.get("method", "RESTCONF")
    
    # 1. Hỗ trợ giao thức RESTCONF
    if method == "RESTCONF":
        return Result(host=task.host, result=handle_restconf_routing(task, my_payload, mode, sub_type))
    
    all_commands = build_cli_routing_commands(my_payload, task.host.data["template_folder"], sub_type, mode)

    if not all_commands: 
        return "No commands."
    
    print_cli_routing_commands(task.host.hostname, sub_type, all_commands)

    # 5. Gõ lệnh thật xuống Router
    res = task.run(
        task=netmiko_send_config, 
        config_commands=all_commands,
        read_timeout=60,
        cmd_verify=False
    )
    
    output_log = res[0].result

    # ==============================================================
    # [BÍ KÍP 2] IN LOG PHẢN HỒI THỰC TẾ TỪ ROUTER
    # ==============================================================
    print(f"\n[INFO] Router response log from {task.host.hostname}:")
    print(output_log)
    print("=" * 50)

    return output_log

def build_worker_inventory(db_path, task_list):
    task_map = {item.get("target", {}).get("ip"): item for item in task_list if item.get("target", {}).get("ip")}
    hosts = {}
    
    # Read the device table name from the shared config.
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
                method = (db_method or "SSH").upper()
                platform = (
                    "cisco_ios_telnet"
                    if method == "TELNET" and str(db_os).lower() in {"cisco", "cisco_ios"}
                    else "cisco_ios"
                    if str(db_os).lower() in {"cisco", "cisco_ios"}
                    else (db_os or "cisco_ios")
                )
                tpl_folder = "cisco_ios" if platform == "cisco_ios_telnet" else platform
                default_port = 23 if method == "TELNET" else 443 if method == "RESTCONF" else 22
                
                host_name = dev_name or ip
                hosts[host_name] = Host(
                    name=host_name,
                    hostname=ip,
                    username=db_user,
                    password=db_pass,
                    port=int(db_port) if db_port else default_port,
                    platform=platform,
                    connection_options={
                        "networktools_netmiko": ConnectionOptions(
                            extras={
                                "conn_timeout": NETWORK_TIMEOUT,
                                "banner_timeout": NETWORK_TIMEOUT,
                                "auth_timeout": NETWORK_TIMEOUT,
                                "blocking_timeout": NETWORK_TIMEOUT,
                                "session_timeout": NETWORK_TIMEOUT,
                                "timeout": NETWORK_TIMEOUT,
                                "global_delay_factor": 2,
                                "ssh_algorithm_db_path": db_path,
                            }
                        )
                    },
                    data={"template_folder": tpl_folder, "ui_payload": payload, "method": method},
                )
        conn_db.close()
    except Exception as e: 
        print(f"[ERROR] Failed to build routing inventory: {e}")
    
    return hosts

def _dev_test_hosts(db_path, input_data):
    """Return dev-mode targets; raise when the safety lookup cannot be completed."""
    target_ips = sorted({
        item.get("target", {}).get("ip")
        for item in input_data
        if item.get("target", {}).get("ip")
    })
    if not target_ips:
        return set()

    placeholders = ",".join("?" for _ in target_ips)
    conn_db = None
    try:
        T_DEVICES = DB_TABLES["device_info"]["main"]
        conn_db = sqlite3.connect(db_path)
        cursor = conn_db.cursor()
        cursor.execute(
            f"SELECT host FROM {T_DEVICES} WHERE COALESCE(dev, 0) = 1 AND host IN ({placeholders})",
            tuple(target_ips),
        )
        return {row[0] for row in cursor.fetchall()}
    except Exception as e:
        raise RuntimeError(f"Could not verify routing dev-mode hosts: {e}") from e
    finally:
        if conn_db is not None:
            conn_db.close()


def _target_results(input_data, status, message):
    target_ips = sorted({
        item.get("target", {}).get("ip")
        for item in input_data
        if item.get("target", {}).get("ip")
    })
    return [
        {"target": ip, "status": status, "message": message}
        for ip in target_ips
    ]


def _write_results(output_path, output_data):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)

def run_routing_config_with_sessions(input_data, output_path, session_provider, output_data):
    tasks_by_ip = defaultdict(list)
    for item in input_data:
        ip = item.get("target", {}).get("ip")
        if ip:
            tasks_by_ip[ip].append(item)

    for ip, tasks in sorted(tasks_by_ip.items()):
        connector = session_provider(ip)
        if connector is None:
            output_data.append({
                "target": ip,
                "status": "failed",
                "message": "No active tab session. Reopen the device tab before pushing routing configuration.",
            })
            continue

        try:
            result = apply_routing_batch_with_connector(connector, tasks)
            output_data.append({"target": ip, "status": "success", "message": str(result)})
            print(f"[+] {ip}: pushed via active tab session")
        except Exception as e:
            output_data.append({"target": ip, "status": "failed", "message": str(e)})
            print(f"[-] {ip}: {e}")

    _write_results(output_path, output_data)


def run_routing_config(input_data, db_path, output_path, session_provider=None):
    print(f"\n[INFO] Starting Routing Worker...")
    try:
        dev_hosts = _dev_test_hosts(db_path, input_data)
    except RuntimeError as exc:
        message = f"Safety check failed; real routing push was blocked. {exc}"
        print(f"[-] {message}")
        _write_results(output_path, _target_results(input_data, "failed", message))
        return
    output_data = [
        {
            "target": ip,
            "status": "success",
            "message": "Dev-mode simulation succeeded; no device login or push was performed.",
        }
        for ip in sorted(dev_hosts)
    ]

    real_input_data = [
        item for item in input_data
        if item.get("target", {}).get("ip") not in dev_hosts
    ]

    if not real_input_data:
        _write_results(output_path, output_data)
        return

    if session_provider is not None:
        run_routing_config_with_sessions(real_input_data, output_path, session_provider, output_data)
        return

    hosts = build_worker_inventory(db_path, real_input_data)
    if not hosts:
        _write_results(output_path, output_data)
        return

    ConnectionPluginRegister.auto_register()
    register_networktools_netmiko()
    config = Config.from_dict(
        runner={"plugin": "threaded", "options": {"num_workers": 5}},
        logging={"enabled": False},
    )
    nr = Nornir(
        inventory=Inventory(hosts=Hosts(hosts)),
        runner=load_runner(config),
        config=config,
    )
    
    results = nr.run(task=task_push_routing)
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        message = str(task_res.exception) if task_res.failed else (str(task_res[0].result) if hasattr(task_res[0], 'result') else str(task_res[0]))
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": message})
        print(f"[{'+' if status == 'success' else '-'}] {host}: {message}")
        
    _write_results(output_path, output_data)
