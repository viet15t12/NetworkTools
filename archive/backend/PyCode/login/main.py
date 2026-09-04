import sqlite3
import json
import os
import sys
import urllib3
import re
import requests
from ncclient import manager
from nornir import InitNornir
from nornir.core.task import Task
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from nornir.core.inventory import Inventory, Host
from nornir.core.plugins.inventory import InventoryPluginRegister

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))

if project_root not in sys.path:
    sys.path.append(project_root)

# NHẬP KHẨU BẢN ĐỒ TỪ TRẠM KIỂM SOÁT
from PyCode.share.config import DB_DEVICE_NETWORK, TMP_DIR, DB_TABLES, FILE_LOGIN_EXPORT

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CustomDictInventory:
    def __init__(self, hosts):
        self.hosts = hosts

    def load(self):
        parsed_hosts = {}
        for k, v in self.hosts.items():
            parsed_hosts[k] = Host(name=k, **v)
        return Inventory(hosts=parsed_hosts, groups={}, defaults={})

InventoryPluginRegister.register("DictInventory", CustomDictInventory)

def login_and_probe_task(task: Task):
    
    host_ip = task.host.hostname
    user = task.host.username
    pw = task.host.password
    port = task.host.port
    method = task.host.data.get("method", "SSH").upper() 

    detected_os = "unknown"
    role = "unknown"
    real_hostname = host_ip
    success = False
    error_msg = "" 

    if method == "RESTCONF":
        url = f"https://{host_ip}:{port}/restconf/data/ietf-interfaces:interfaces"
        headers = {"Accept": "application/yang-data+json", "Content-Type": "application/yang-data+json"}
        url_hostname = f"https://{host_ip}:{port}/restconf/data/Cisco-IOS-XE-native:native/hostname"
        try:
            res = requests.get(url, auth=(user, pw), verify=False, timeout=5)
            if res.status_code == 200:
                detected_os, role, success = "cisco_xe_restconf", "Router", True
                res_host = requests.get(url_hostname, auth=(user, pw), headers=headers, verify=False, timeout=5)
                if res_host.status_code == 200:
                    try: real_hostname = res_host.json().get("Cisco-IOS-XE-native:hostname", host_ip)
                    except: pass
            elif res.status_code == 401: error_msg = "Sai tài khoản/mật khẩu RESTCONF"
            else: error_msg = f"RESTCONF từ chối truy cập (Mã: {res.status_code})"
        except requests.exceptions.Timeout: error_msg = "Timeout: Không thể kết nối RESTCONF (Kiểm tra IP/Port)"
        except Exception as e: error_msg = f"Lỗi RESTCONF: {str(e)}"

    elif method == "NETCONF":
        try:
            with manager.connect(host=host_ip, port=port, username=user, password=pw, hostkey_verify=False, device_params={'name': 'default'}, timeout=10) as m:
                detected_os, role, success = "cisco_xe_netconf", "Router", True
                host_filter = '<native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"><hostname/></native>'
                try:
                    host_reply = m.get_config(source='running', filter=('subtree', host_filter)).xml
                    host_match = re.search(r'<[^>]*hostname[^>]*>([^<]+)</[^>]*hostname>', host_reply)
                    if host_match: real_hostname = host_match.group(1).strip()
                except: pass
        except Exception as e:
            if "Authentication" in str(e): error_msg = "Sai tài khoản/mật khẩu NETCONF"
            else: error_msg = f"Lỗi NETCONF: {str(e)}"

    else: 
        candidates = ["cisco_ios", "mikrotik_routeros", "huawei_vrp"]
        if method == "TELNET": candidates = ["cisco_ios_telnet", "huawei_vrp_telnet"]

        connection_success = False
        for os_type in candidates:
            try:
                device_dict = {"device_type": os_type, "host": host_ip, "username": user, "password": pw, "port": port, "global_delay_factor": 1}
                from netmiko import ConnectHandler
                with ConnectHandler(**device_dict) as net_connect:
                    run_output = net_connect.send_command("show run | include hostname")
                    match = re.search(r'hostname\s+(\S+)', run_output)
                    if match: real_hostname = match.group(1)
                    
                    sh_ver_raw = net_connect.send_command("show version")
                    sh_ver = sh_ver_raw.upper()

                    try:
                        sh_run_routing = net_connect.send_command("show run | include ip routing")
                        if any(kw in sh_ver for kw in ["ASA", "FIREPOWER", "PIX"]): role = "Firewall"
                        elif any(kw in sh_ver for kw in ["AIR-", "WIRELESS", "WLC"]): role = "Access Point"
                        elif any(kw in sh_ver for kw in ["VIOS_L2", "CATALYST", "C2960", "C3560", "C3850", "C9300"]):
                            role = "Switch L3" if "ip routing" in sh_run_routing else "Switch L2"
                        elif any(kw in sh_ver for kw in ["IOSV", "VIOS", "ISR", "ASR", "C19", "C29"]): role = "Router"
                        elif any(kw in sh_ver for kw in ["LINUX", "UBUNTU", "CENTOS"]): role = "Server"
                        else: role = "Unknown Device"
                    except Exception as e:
                        print(f"[-] Lỗi khi quét Role thiết bị ở IP {host_ip}: {e}")
                        role = "Unknown"

                detected_os = os_type
                success = True
                connection_success = True
                break 
            except NetmikoAuthenticationException: error_msg = "Sai tài khoản/mật khẩu đăng nhập"; break 
            except NetmikoTimeoutException: error_msg = "Timeout: Không thấy thiết bị phản hồi"; break
            except Exception: continue 

        if not connection_success and not error_msg: error_msg = "Thiết bị từ chối kết nối hoặc OS không hỗ trợ"

    task.host.data.update({"real_name": real_hostname, "os": detected_os, "role": role, "success": success, "error_msg": error_msg})


def main():
    db_path = DB_DEVICE_NETWORK
    json_export_path = FILE_LOGIN_EXPORT
    table_name = DB_TABLES["device_info"]["main"]

    print(f"[*] Đang nạp Database từ: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # SỬ DỤNG F-STRING ĐỂ GỌI TÊN BẢNG TỪ CONFIG
        cursor.execute(f"SELECT host, method, portnumber, username, password FROM {table_name} WHERE success = 0 OR success IS NULL")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[-] Lỗi Critical: Không thể đọc Database! {e}")
        return

    if not rows:
        print("[INFO] Không có thiết bị nào cần probe (Toàn bộ đã success = 1).")
        conn.close()
        return

    hosts_config = {}
    for row in rows:
        ip, method, portnumber, username, password = row
        method = method.upper().strip() if method else "SSH"
        
        if not portnumber:
            if method == "NETCONF": port = 830
            elif method == "RESTCONF": port = 443
            elif method == "TELNET": port = 23
            else: port = 22
        else:
            port = int(portnumber)

        hosts_config[ip] = {"hostname": ip, "username": username, "password": password, "port": port, "data": {"method": method}}

    nr = InitNornir(inventory={"plugin": "DictInventory", "options": {"hosts": hosts_config}}, logging={"enabled": False})

    print(f"\n[INFO] Đang probe {len(nr.inventory.hosts)} thiết bị. Vui lòng chờ...")
    results = nr.run(task=login_and_probe_task)

    ui_report = []

    for ip, task_result in results.items():
        host_data = nr.inventory.hosts[ip].data
        is_success = host_data["success"]
        
        report_item = {
            "ip": ip, "status": "SUCCESS" if is_success else "FAIL", "method": host_data.get("method"),
            "hostname": host_data.get("real_name", ""), "os": host_data.get("os", ""),
            "role": host_data.get("role", ""), "error_reason": host_data.get("error_msg", "")
        }

        if is_success:
            # SỬ DỤNG TÊN BẢNG TỪ CONFIG ĐỂ UPDATE
            cursor.execute(f"""
                UPDATE {table_name} 
                SET success=1, os=?, role=?, device_name=? 
                WHERE host=?
            """, (report_item["os"], report_item["role"], report_item["hostname"], ip))
            print(f"[+] SUCCESS - Đã lưu cấu hình IP {ip} với Role là [{report_item['role']}]")
        else:
            # SỬ DỤNG TÊN BẢNG TỪ CONFIG ĐỂ DELETE
            cursor.execute(f"DELETE FROM {table_name} WHERE host=?", (ip,))
            print(f"[-] FAIL - Đã XÓA IP {ip} khỏi Database. Lý do: {report_item['error_reason']}")

        ui_report.append(report_item)

    conn.commit()
    conn.close()

    # THƯ MỤC TMP_DIR ĐÃ ĐƯỢC ĐẢM BẢO TẠO SẴN TRONG FILE CONFIG
    with open(json_export_path, 'w', encoding='utf-8') as f:
        json.dump(ui_report, f, ensure_ascii=False, indent=4)
        
    print(f"\n[INFO] Đã xuất file báo cáo cho UI tại: {json_export_path}")

if __name__ == "__main__":
    main()