import os
import re
from backend.PyCode.share.config import get_db_connection, DB_TABLES, BACKUP_DIR

# Kéo tên bảng từ SSoT
TBL_STP_GLOBAL = DB_TABLES["l2_stp"]["global"]
TBL_STP_IFACE = DB_TABLES["l2_stp"]["interface"]
TBL_IFACE = DB_TABLES["l2_interfaces"]["main"]

def sync_stp_worker(host_ip):
    raw_file_path = os.path.join(BACKUP_DIR, host_ip, f"{host_ip}_running-config.txt")
    
    if not os.path.exists(raw_file_path):
        print(f"[-] File raw config của {host_ip} không tồn tại.")
        return

    with open(raw_file_path, 'r', encoding='utf-8') as f:
        config_text = f.read()

    mode_match = re.search(r'spanning-tree mode (pvst|rapid-pvst|mst)', config_text)
    stp_mode = mode_match.group(1) if mode_match else 'rapid-pvst'

    interfaces = re.findall(r'interface (.*?)\n(.*?)(?=\ninterface|\Z)', config_text, re.DOTALL)
    iface_stp_data = []
    
    for if_name, if_config in interfaces:
        if if_name.strip() in ['GigabitEthernet0/0', 'Gi0/0', 'g0/0']:
            continue
            
        portfast = 'enabled' if 'spanning-tree portfast' in if_config else 'disabled'
        bpduguard = 'enabled' if 'spanning-tree bpduguard enable' in if_config else 'disabled'
        bpdufilter = 'enabled' if 'spanning-tree bpdufilter enable' in if_config else 'disabled'
        
        iface_stp_data.append({
            "if_name": if_name.strip(),
            "portfast": portfast,
            "bpduguard": bpduguard,
            "bpdufilter": bpdufilter
        })

    try:
        conn = get_db_connection()
        c = conn.cursor()

        # Dùng f-string để nạp tên bảng, vlan_id là số 1 theo chuẩn mới
        c.execute(f"""
            INSERT INTO {TBL_STP_GLOBAL} (host, stp_mode, vlan_id)
            VALUES (?, ?, 1)
            ON CONFLICT(host, vlan_id) DO UPDATE SET stp_mode=excluded.stp_mode
        """, (host_ip, stp_mode))

        for iface in iface_stp_data:
            c.execute(f"SELECT id FROM {TBL_IFACE} WHERE host = ? AND if_name = ?", (host_ip, iface['if_name']))
            res = c.fetchone()
            if not res: continue
                
            iface_id = res[0]
            
            # Cập nhật không chứa cột host, điền đầy đủ root/loop_guard
            c.execute(f"""
                INSERT INTO {TBL_STP_IFACE} (iface_id, portfast, bpduguard, bpdufilter, root_guard, loop_guard)
                VALUES (?, ?, ?, ?, 'disabled', 'disabled')
                ON CONFLICT(iface_id) DO UPDATE SET 
                    portfast=excluded.portfast,
                    bpduguard=excluded.bpduguard,
                    bpdufilter=excluded.bpdufilter
            """, (iface_id, iface['portfast'], iface['bpduguard'], iface['bpdufilter']))

        conn.commit()
        print(f"[+] Đã đồng bộ cấu hình STP của {host_ip} vào Database Letos thành công!")

    except Exception as e:
        print(f"[-] Lỗi đồng bộ STP DB cho {host_ip}: {e}")
    finally:
        if 'conn' in locals(): conn.close()