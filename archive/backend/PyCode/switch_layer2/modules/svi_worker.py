import os
import json
import yaml
import sqlite3
from jinja2 import Environment, FileSystemLoader

from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config


from backend.PyCode.share.config import TMP_DIR, DB_TABLES, L2_TEMPLATE_DIR

def render_svi_config(payload_data):
    """Render lệnh Cisco IOS từ Template svi.j2"""
    env = Environment(loader=FileSystemLoader(L2_TEMPLATE_DIR))
    # payload_data sẽ chứa 2 key: "l3_config" và "svis"
    return env.get_template("svi.j2").render(
        l3_config=payload_data.get("l3_config", {}),
        svis=payload_data.get("svis", [])
    )

def task_push_svi(task):
    """Nhiệm vụ Nornir đẩy cấu hình Routing & SVI xuống Switch L3"""
    payload_data = task.host.data.get("l3_payload", {})
    
    commands_str = render_svi_config(payload_data)
    all_commands = [l.strip() for l in commands_str.splitlines() if l.strip() and not l.strip().startswith('!')]

    if not all_commands:
        return "No commands generated."

    # Tắt log console tạm thời để chống rác terminal
    all_commands.insert(0, "no logging monitor")
    all_commands.insert(0, "no logging console")
    all_commands.append("logging console")
    all_commands.append("logging monitor")

    # [1] IN CHIỀU ĐI: Lệnh chuẩn bị đẩy
    debug_output = f"\n======================================================\n"
    debug_output += f"[+] CHI TIẾT LỆNH SVI & ROUTING -> {task.host.hostname}\n"
    debug_output += f"======================================================\n"
    for idx, cmd in enumerate(all_commands, 1): 
        debug_output += f"  [{task.host.hostname}] {idx:02d}. {cmd}\n"
    debug_output += f"======================================================\n"
    print(debug_output)

    # Đẩy lệnh xuống thiết bị
    res = task.run(
        task=netmiko_send_config, 
        config_commands=all_commands,
        read_timeout=60,
        cmd_verify=False
    )
    
    # [2] IN CHIỀU VỀ: Phản hồi thực tế từ Switch
    device_output = res[0].result
    print(f"\n[<<<] PHẢN HỒI TỪ SWITCH {task.host.hostname}:")
    print(f"------------------------------------------------------")
    print(device_output)
    print(f"------------------------------------------------------\n")
    
    return device_output

def build_l3_inventory(db_path, task_list):
    """Tạo file YAML Inventory động cho Nornir"""
    hosts_yaml = {}
    T_DEVICES = DB_TABLES["device_info"]["main"]
    
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        for item in task_list:
            ip = item["target"]
            c.execute(f'SELECT device_name, username, password, os, portnumber, method FROM {T_DEVICES} WHERE host = ?', (ip,))
            row = c.fetchone()
            if row:
                dev_name, db_user, db_pass, db_os, db_port, db_method = row
                hosts_yaml[dev_name or ip] = {
                    "hostname": ip, 
                    "username": db_user, 
                    "password": db_pass,
                    "platform": "cisco_ios" if db_os == "cisco" else db_os,
                    "data": {"l3_payload": item["payload"]} # Gói toàn bộ dữ liệu SVI vào đây
                }
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi build L3 inventory: {e}")
        
    inv_file = os.path.join(TMP_DIR, "tmp_l3_inventory.yaml")
    with open(inv_file, 'w', encoding='utf-8') as f: 
        yaml.dump(hosts_yaml, f)
    return inv_file

def run_svi_worker(input_data, db_path, output_path):
    """Khởi chạy đa luồng Nornir Worker cho SVI/Routing"""
    inv_file = build_l3_inventory(db_path, input_data)
    if not inv_file: 
        return

    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 10}}, 
        inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}}, 
        logging={"enabled": False}
    )
    
    results = nr.run(task=task_push_svi)
    output_data = []
    
    for host, task_res in results.items():
        status = "failed" if task_res.failed else "success"
        msg = str(task_res.exception) if task_res.failed else str(task_res[0].result)
        output_data.append({"target": nr.inventory.hosts[host].hostname, "status": status, "message": msg})
        
    with open(output_path, 'w', encoding='utf-8') as f: 
        json.dump(output_data, f)
        
    # === CƠ CHẾ TỰ ĐỘNG CẬP NHẬT / XÓA DATABASE SAU KHI PUSH THÀNH CÔNG ===
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for host, task_res in results.items():
            target_ip = nr.inventory.hosts[host].hostname
            is_failed = task_res.failed
            
            if not is_failed:
                # 1. Thành công: Chỉ cập nhật các dòng SVI đang ở success = 0 lên thành 1
                cursor.execute(f"UPDATE {DB_TABLES['l3_switch']['svi']} SET success = 1 WHERE host = ? AND success = 0", (target_ip,))
                
                # 2. Nếu là lệnh xóa (success = -1): Đẩy no interface xong thì XÓA SẠCH khỏi DB
                cursor.execute(f"DELETE FROM {DB_TABLES['l3_switch']['svi']} WHERE host = ? AND success = -1", (target_ip,))
            else:
                # Nếu push thất bại: Giữ nguyên trạng thái để lần sau retry
                pass
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi cập nhật Database sau khi chạy SVI worker: {e}")
        
    if os.path.exists(inv_file): 
        os.remove(inv_file)