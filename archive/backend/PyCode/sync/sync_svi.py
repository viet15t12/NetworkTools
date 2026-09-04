import os
import re
from backend.PyCode.share.config import get_db_connection, DB_TABLES, STATE_DIR

TBL_L3_GLOBAL = DB_TABLES.get("l3_switch", {}).get("global", "t06_switch_l3_config")
TBL_SVI = DB_TABLES.get("l3_switch", {}).get("svi", "t06_svi_interface")

def sync_svi_worker(host_ip: str):
    """
    Bóc tách cấu hình IP routing và SVI từ file running-config của Switch L3
    và đồng bộ ngược lại vào Database Letos.
    """
    file_path = os.path.join(STATE_DIR, f"{host_ip}_running.txt")
    if not os.path.exists(file_path):
        print(f"[-] [SYNC SVI] Không tìm thấy file {file_path}")
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # 1. Kiểm tra trạng thái Global IP Routing
    ip_routing_enabled = 1 if re.search(r"^ip routing\s*$", raw_text, re.MULTILINE | re.IGNORECASE) else 0

    # 2. Bóc tách các block interface Vlan
    # Mẫu regex quét từ "interface Vlan<id>" cho tới dấu "!" kết thúc block
    vlan_blocks = re.findall(r"(interface Vlan(\d+).*?)(?=^!|\Z)", raw_text, re.DOTALL | re.MULTILINE)
    
    parsed_svis = {}
    for block_text, vlan_id_str in vlan_blocks:
        vlan_id = int(vlan_id_str)
        
        # Tìm IP và Subnet Mask
        ip_mask_match = re.search(r"ip address\s+([\d.]+)\s+([\d.]+)", block_text)
        if ip_mask_match:
            ip_addr = ip_mask_match.group(1)
            subnet = ip_mask_match.group(2)
        else:
            ip_addr = None
            subnet = None

        # Kiểm tra trạng thái shutdown
        shutdown = 1 if re.search(r"\bshutdown\b", block_text) and not re.search(r"\bno shutdown\b", block_text) else 0

        parsed_svis[vlan_id] = {
            "ip_address": ip_addr,
            "subnet_mask": subnet,
            "shutdown": shutdown
        }

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # --- CẬP NHẬT GLOBAL L3 CONFIG ---
        c.execute(f"SELECT host FROM {TBL_L3_GLOBAL} WHERE host = ?", (host_ip,))
        if c.fetchone():
            c.execute(f"UPDATE {TBL_L3_GLOBAL} SET ip_routing = ? WHERE host = ?", (ip_routing_enabled, host_ip))
        else:
            c.execute(f"INSERT INTO {TBL_L3_GLOBAL} (host, ip_routing) VALUES (?, ?)", (host_ip, ip_routing_enabled))

        # --- CẬP NHẬT CÁC BẢN GHI SVI ---
        for v_id, data in parsed_svis.items():
            if not data["ip_address"]: 
                continue # Bỏ qua SVI không có IP cấu hình
                
            c.execute(f"SELECT id, success FROM {TBL_SVI} WHERE host = ? AND vlan_id = ?", (host_ip, v_id))
            row = c.fetchone()
                                                                                                                                                                                                                                                                                          
            if row:
                # Nếu đã tồn tại -> Update thông tin và gán success = 1 (đã đồng bộ khớp thiết bị)
                svi_db_id = row[0]
                c.execute(f"""                                                                                                                                                                                                                                                                                                   
                    UPDATE {TBL_SVI} 
                    SET ip_address = ?, subnet_mask = ?, shutdown = ?, success = 1
                    WHERE id = ?
                """, (data["ip_address"], data["subnet_mask"], data["shutdown"], svi_db_id))
            else:
                # Nếu chưa có trong DB (thiết bị cấu hình thủ công ngoài đời thực) -> Insert mới
                c.execute(f"""
                    INSERT INTO {TBL_SVI} (host, vlan_id, ip_address, subnet_mask, shutdown, success)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (host_ip, v_id, data["ip_address"], data["subnet_mask"], data["shutdown"]))

        conn.commit()
        print(f"  [+] [SVI SYNC] Đồng bộ thành công cấu hình SVI/Routing cho {host_ip}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"  [-] LỖI DATABASE KHI SYNC SVI ({host_ip}): {e}")
        return False
    finally:
        conn.close()