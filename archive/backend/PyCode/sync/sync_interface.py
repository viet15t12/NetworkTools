import sqlite3

# IMPORT ĐỘNG TỪ CONFIG.PY (Không gán cứng nữa)
from backend.PyCode.share.config import DB_TABLES

# Lấy tên bảng "t02_interface_name" thông qua dict DB_TABLES
TBL_IFACE = DB_TABLES["interfaces"]["main"] 

COL_HOST = "host"
COL_IFACE_NAME = "interface_name"
COL_IP = "ip_address"
COL_MASK = "subnet_mask"
COL_DESC = "description"
COL_SHUTDOWN = "shutdown"
COL_SUCCESS = "success"

def sync_interface_worker(host_ip: str, parse_obj, db_path: str):
    """
    Thợ phụ xử lý Interface.
    B3: Ưu tiên File Config. Xóa -> Thêm -> Ghi đè.
    """
    parsed_interfaces = {}
    
    for intf_obj in parse_obj.find_objects(r"^interface "):
        iface_name = intf_obj.text.split("interface ")[-1].strip()
        
        ip_obj = intf_obj.re_search_children(r"^\s+ip address ")
        if ip_obj:
            parts = ip_obj[0].text.strip().split()
            ip_addr = parts[2] if len(parts) >= 3 else None
            subnet = parts[3] if len(parts) >= 4 else None
        else:
            ip_addr, subnet = None, None
            
        desc_obj = intf_obj.re_search_children(r"^\s+description ")
        desc = desc_obj[0].text.split("description ")[-1].strip() if desc_obj else ""
        
        is_shutdown = 1 if intf_obj.has_child_with(r"^\s+shutdown$") else 0
        
        parsed_interfaces[iface_name] = {
            'ip_address': ip_addr,
            'subnet_mask': subnet,
            'description': desc,
            'shutdown': is_shutdown
        }

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()
    
    try:
        c.execute(f"SELECT {COL_IFACE_NAME} FROM {TBL_IFACE} WHERE {COL_HOST}=?", (host_ip,))
        db_ifaces = set(row[0] for row in c.fetchall())
        run_ifaces = set(parsed_interfaces.keys())
        
        for iface in (db_ifaces - run_ifaces):
            c.execute(f"DELETE FROM {TBL_IFACE} WHERE {COL_HOST}=? AND {COL_IFACE_NAME}=?", (host_ip, iface))
            
        for iface in (run_ifaces - db_ifaces):
            data = parsed_interfaces[iface]
            c.execute(f"""
                INSERT INTO {TBL_IFACE} 
                ({COL_HOST}, {COL_IFACE_NAME}, {COL_IP}, {COL_MASK}, {COL_DESC}, {COL_SHUTDOWN}, {COL_SUCCESS}) 
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (host_ip, iface, data['ip_address'], data['subnet_mask'], data['description'], data['shutdown']))
            
        for iface in (db_ifaces & run_ifaces):
            data = parsed_interfaces[iface]
            c.execute(f"""
                UPDATE {TBL_IFACE} 
                SET {COL_IP}=?, {COL_MASK}=?, {COL_DESC}=?, {COL_SHUTDOWN}=?, {COL_SUCCESS}=1 
                WHERE {COL_HOST}=? AND {COL_IFACE_NAME}=?
            """, (data['ip_address'], data['subnet_mask'], data['description'], data['shutdown'], host_ip, iface))
            
        conn.commit()
        print(f"[+] Interface Worker: Đồng bộ thành công {TBL_IFACE} cho {host_ip}")
        
    except Exception as e:
        print(f"[-] Interface Worker LỖI: {e}")
        conn.rollback()
    finally:
        conn.close()