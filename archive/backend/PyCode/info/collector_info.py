import os
import re
import sqlite3
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
# Tuân thủ quy tắc: Trỏ về config.py để lấy chuẩn thư mục và đường dẫn DB
from backend.PyCode.share.config import STATE_DIR, DB_DEVICE_NETWORK

# =====================================================================
# HÀM PHỤ TRỢ: SOI DATABASE ĐỂ TÌM ROLE CỦA THIẾT BỊ
# =====================================================================
def get_device_role(hostname):
    """Đọc cột device_type từ bảng t01_devices trong device_network.db"""
    try:
        conn = sqlite3.connect(DB_DEVICE_NETWORK)
        cursor = conn.cursor()
        cursor.execute("SELECT device_type FROM t01_devices WHERE host = ?", (hostname,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0].lower().strip()
        return "unknown"
    except Exception as e:
        print(f"[-] Lỗi đọc DB để lấy Role cho {hostname}: {e}")
        return "unknown"

# =====================================================================
# [TẦNG 1] MASTER FETCHER: KÉO DỮ LIỆU TỔNG HỢP VÀ LƯU FILE
# =====================================================================
def task_pull_running_config(task):
    hostname = task.host.hostname
    print(f"[*] Đang kéo dữ liệu giám sát tổng hợp từ {hostname}...")
    
    dev_type = get_device_role(hostname)
    
    if dev_type == "router" or dev_type == "rou":
        commands_to_run = [
            "show running-config",
            "show ip route",
            "show ip dhcp binding",
            "show ip dhcp conflict",
            "show ip dhcp pool",
            "show ip dhcp server statistics",
            "show ip dhcp database",  
            "show access-lists",
            "show ip nat translations verbose",
            "show ip nat statistics",
            "show class-map",              
            "show policy-map",             
            "show policy-map interface"    
        ]
        
    elif "sw" in dev_type:
        commands_to_run = [
            "show running-config",
            "show vlan brief",              
            "show interfaces status",       
            "show mac address-table",
            "show spanning-tree summary",
            "show interfaces trunk",
            "show etherchannel summary",
            "show vtp status",            
            "show vtp password",          
            "show access-lists",
            "show class-map",              
            "show policy-map",             
            "show policy-map interface",
            "show ip route",  
            "show ip interface brief",
            # ==========================================
            # 5 LỆNH SECURITY TỔNG QUAN
            # ==========================================
            "show ip dhcp snooping",
            "show ip arp inspection",
            "show port-security",
            "show port-security address",
            "show mac address-table static"
        ]

        # ==========================================
        # XỬ LÝ LẶP ĐỘNG CHO LỆNH SHOW PORT-SECURITY INTERFACE
        # ==========================================
        try:
            # Chạy trước lệnh show ip int br để lấy danh sách
            int_res = task.run(
                task=netmiko_send_command, 
                command_string="show ip interface brief",
                use_textfsm=False,
                enable=True
            )
            int_output = int_res[0].result
            
            # Quét Regex để bóc tách TẤT CẢ các cổng vật lý (Gi, Fa, Eth, Te) 
            physical_ifaces = re.findall(
                r"^(GigabitEthernet[\d/]+|FastEthernet[\d/]+|Ethernet[\d/]+|TenGigabitEthernet[\d/]+)", 
                int_output, 
                re.MULTILINE | re.IGNORECASE
            )
            
            # Nhồi lệnh show chi tiết cho từng cổng bắt được vào hàng đợi
            for iface in physical_ifaces:
                commands_to_run.append(f"show port-security interface {iface}")
                
        except Exception as e:
            print(f"[-] Lỗi khi lấy danh sách interface động cho {hostname}: {e}")

    else:
        commands_to_run = ["show running-config"]
    
    full_output = f"!!! DEVICE TYPE: {dev_type.upper()} !!!\n"
    
    try:
        for cmd in commands_to_run:
            result = task.run(
                task=netmiko_send_command, 
                command_string=cmd,
                use_textfsm=False,
                enable=True,
                read_timeout=120,
                delay_factor=2
            )
            full_output += f"\n\n==================== [ {cmd.upper()} ] ====================\n"
            
            if not result[0].result:
                full_output += "!!! NO DATA RETURNED OR TIMEOUT !!!\n\n"
            else:
                full_output += result[0].result.strip() + "\n\n"
        
        file_name = f"{hostname}_running.txt"
        file_path = os.path.join(STATE_DIR, file_name)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_output)
            
        print(f"[+] Đã tạo và ghi file thành công tại: {file_path}")
        return f"Thành công! Đã chạy {len(commands_to_run)} lệnh cho {dev_type.upper()} và lưu tại: {file_path}"
    
    except Exception as e:
        return f"[-] Lỗi khi kéo config từ {hostname}: {e}"

# =====================================================================
# [TẦNG 2] BỘ CÔNG CỤ TRÍCH XUẤT (CẤP VỐN CHO TỪNG GÓC BẢNG)
# =====================================================================
def load_saved_config(hostname):
    file_path = os.path.join(STATE_DIR, f"{hostname}_running.txt")
    if not os.path.exists(file_path): return None
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def get_vtp_section(hostname):
    """Trích xuất khối dữ liệu VTP thô cho sync_vtp.py"""
    raw_config = load_saved_config(hostname)
    if not raw_config: return None
    
    vtp_status_match = re.search(r"={5,}\s*\[\s*SHOW VTP STATUS\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_config, re.DOTALL | re.IGNORECASE)
    vtp_pass_match = re.search(r"={5,}\s*\[\s*SHOW VTP PASSWORD\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_config, re.DOTALL | re.IGNORECASE)
    vtp_running_cmds = re.findall(r"^vtp\s+.*$", raw_config, re.MULTILINE)

    return {
        "vtp_status_raw": vtp_status_match.group(1).strip() if vtp_status_match else "",
        "vtp_pass_raw": vtp_pass_match.group(1).strip() if vtp_pass_match else "",
        "vtp_running_cmds": vtp_running_cmds
    }

def get_routing_section(hostname):
    raw_config = load_saved_config(hostname)
    if not raw_config: return None
    ospf_pattern = re.compile(r"(router ospf \d+.*?)(?=^!)", re.MULTILINE | re.DOTALL)
    static_pattern = re.compile(r"^(ip route .*)$", re.MULTILINE)
    return {"ospf": ospf_pattern.findall(raw_config), "static": static_pattern.findall(raw_config)}

def get_dhcp_section(hostname):
    raw_config = load_saved_config(hostname)
    if not raw_config: return None
    pool_pattern = re.compile(r"(ip dhcp pool .*?)(?=^!)", re.MULTILINE | re.DOTALL)
    exclude_pattern = re.compile(r"^(ip dhcp excluded-address .*)$", re.MULTILINE)
    return {"pools": pool_pattern.findall(raw_config), "excludes": exclude_pattern.findall(raw_config)}

def get_acl_section(hostname):
    raw_config = load_saved_config(hostname)
    if not raw_config: return None
    standard_ext_pattern = re.compile(r"^(access-list .*)$", re.MULTILINE)
    named_acl_pattern = re.compile(r"(ip access-list .*?)(?=^!)", re.MULTILINE | re.DOTALL)
    return {"numbered": standard_ext_pattern.findall(raw_config), "named": named_acl_pattern.findall(raw_config)}

def get_nat_section(hostname):
    raw_config = load_saved_config(hostname)
    if not raw_config: return None
    nat_pattern = re.compile(r"^(ip nat .*)$", re.MULTILINE)
    return nat_pattern.findall(raw_config)

def run_master_collector(inv_file):
    nr = InitNornir(runner={"plugin": "threaded", "options": {"num_workers": 10}}, inventory={"plugin": "SimpleInventory", "options": {"host_file": inv_file}}, logging={"enabled": False})
    results = nr.run(task=task_pull_running_config)
    for host, task_res in results.items():
        if task_res.failed:
            print(f"[-] THẤT BẠI: {host} - {task_res.exception}")
        else:
            print(f"[+] {host}: {task_res[0].result}")