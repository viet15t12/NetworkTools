import sqlite3
import re

# Lấy cấu hình động từ config.py
from backend.PyCode.share.config import DB_TABLES

# Bắt tên bảng từ Single Source of Truth
TBL_POOL = DB_TABLES["dhcp"]["pools"]
TBL_EXC = DB_TABLES["dhcp"]["excluded"]
TBL_IFACE = DB_TABLES["interfaces"]["main"] 
TBL_HELPER = DB_TABLES["dhcp"]["helper"]

def sync_dhcp_worker(host_ip: str, parse_obj, db_path: str):
    """
    Thợ phụ xử lý DHCP: Quét Pool, Excluded Addresses và IP Helper (Relay).
    """
    parsed_exc = set()
    parsed_pools = {}
    parsed_helpers = set()

    # -------------------------------------------------------------
    # BƯỚC A: TRÍCH XUẤT TỪ FILE CONFIG (ciscoconfparse)
    # -------------------------------------------------------------
    # 1. Băm Excluded Address
    for line in parse_obj.find_objects(r"^ip dhcp excluded-address"):
        parts = line.text.strip().split()
        if len(parts) >= 4:
            start_ip = parts[3]
            end_ip = parts[4] if len(parts) > 4 else ""
            parsed_exc.add((start_ip, end_ip))

    # 2. Băm DHCP Pool
    for pool_obj in parse_obj.find_objects(r"^ip dhcp pool "):
        p_name = pool_obj.text.split("ip dhcp pool ")[-1].strip()
        
        net_obj = pool_obj.re_search_children(r"^\s+network ")
        if net_obj:
            parts = net_obj[0].text.strip().split()
            network = parts[1] if len(parts) > 1 else ""
            mask = parts[2] if len(parts) > 2 else ""
        else:
            network, mask = "", ""
            
        gw_obj = pool_obj.re_search_children(r"^\s+default-router ")
        gw = gw_obj[0].text.split("default-router ")[-1].strip() if gw_obj else ""
        
        dns_obj = pool_obj.re_search_children(r"^\s+dns-server ")
        dns = dns_obj[0].text.split("dns-server ")[-1].strip() if dns_obj else ""
        
        lease_obj = pool_obj.re_search_children(r"^\s+lease ")
        lease = lease_obj[0].text.split("lease ")[-1].strip() if lease_obj else "1"
        
        parsed_pools[p_name] = {
            'network': network, 'mask': mask, 'gw': gw, 'dns': dns, 'lease': lease
        }

    # 3. Băm IP Helper từ Interface
    for intf_obj in parse_obj.find_objects(r"^interface "):
        iface_name = intf_obj.text.split("interface ")[-1].strip()
        for helper_obj in intf_obj.re_search_children(r"^\s+ip helper-address "):
            helper_ip = helper_obj.text.split("ip helper-address ")[-1].strip()
            parsed_helpers.add((iface_name, helper_ip))


    # -------------------------------------------------------------
    # BƯỚC B: ĐỒNG BỘ XUỐNG DATABASE LETOS
    # -------------------------------------------------------------
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()
    
    try:
        # ==========================================
        # 1. XỬ LÝ EXCLUDED ADDRESSES
        # ==========================================
        c.execute(f"SELECT ex_id, start_ip, end_ip FROM {TBL_EXC} WHERE host=?", (host_ip,))
        db_exc_map = {(row[1], row[2]): row[0] for row in c.fetchall()}
        db_exc_set = set(db_exc_map.keys())
        
        for exc in (db_exc_set - parsed_exc): c.execute(f"DELETE FROM {TBL_EXC} WHERE ex_id=?", (db_exc_map[exc],))
        for exc in (parsed_exc - db_exc_set): c.execute(f"INSERT INTO {TBL_EXC} (host, start_ip, end_ip, success) VALUES (?, ?, ?, 1)", (host_ip, exc[0], exc[1]))
        for exc in (db_exc_set & parsed_exc): c.execute(f"UPDATE {TBL_EXC} SET success=1 WHERE ex_id=?", (db_exc_map[exc],))

        # ==========================================
        # 2. XỬ LÝ DHCP POOLS
        # ==========================================
        c.execute(f"SELECT dhcp_id, pool FROM {TBL_POOL} WHERE host=?", (host_ip,))
        db_pool_map = {row[1]: row[0] for row in c.fetchall()}
        db_pool_set = set(db_pool_map.keys())
        run_pool_set = set(parsed_pools.keys())
        
        for p in (db_pool_set - run_pool_set): c.execute(f"DELETE FROM {TBL_POOL} WHERE dhcp_id=?", (db_pool_map[p],))
        for p in (run_pool_set - db_pool_set):
            data = parsed_pools[p]
            c.execute(f"INSERT INTO {TBL_POOL} (host, pool, network, subnetmask, defaut, dns, lease, success, action_Cfg) VALUES (?, ?, ?, ?, ?, ?, ?, 1, '111')", 
                      (host_ip, p, data['network'], data['mask'], data['gw'], data['dns'], data['lease']))
        for p in (db_pool_set & run_pool_set):
            data = parsed_pools[p]
            c.execute(f"UPDATE {TBL_POOL} SET network=?, subnetmask=?, defaut=?, dns=?, lease=?, success=1, action_Cfg='111' WHERE dhcp_id=?", 
                      (data['network'], data['mask'], data['gw'], data['dns'], data['lease'], db_pool_map[p]))

        # ==========================================
        # 3. XỬ LÝ IP HELPER (Truy vấn liên bảng)
        # ==========================================
        # Lấy từ điển: {interface_name: iface_id} của con Router này
        c.execute(f"SELECT interface_name, iface_id FROM {TBL_IFACE} WHERE host=?", (host_ip,))
        iface_map = {row[0]: row[1] for row in c.fetchall()}

        # Lấy danh sách Helper hiện tại trên Letos DB
        c.execute(f"""
            SELECT h.id, i.interface_name, h.helper_ip 
            FROM {TBL_HELPER} h 
            JOIN {TBL_IFACE} i ON h.iface_id = i.iface_id 
            WHERE i.host=?
        """, (host_ip,))
        db_helper_map = {(row[1], row[2]): row[0] for row in c.fetchall()}
        db_helper_set = set(db_helper_map.keys())

        # Lọc an toàn: Chỉ lấy những Helper thuộc về các Interface có tồn tại trong DB
        valid_run_helpers = { (iface, ip) for iface, ip in parsed_helpers if iface in iface_map }

        # Xóa (Có trong DB Letos nhưng file cấu hình không có)
        for h in (db_helper_set - valid_run_helpers):
            c.execute(f"DELETE FROM {TBL_HELPER} WHERE id=?", (db_helper_map[h],))
        
        # Thêm Mới (File cấu hình có, DB Letos chưa có)
        for h in (valid_run_helpers - db_helper_set):
            iface_name, helper_ip = h
            iface_id = iface_map[iface_name]
            c.execute(f"INSERT INTO {TBL_HELPER} (iface_id, helper_ip, success) VALUES (?, ?, 1)", (iface_id, helper_ip))

        # Cập nhật (Có ở cả 2, ép lại success = 1)
        for h in (db_helper_set & valid_run_helpers):
            c.execute(f"UPDATE {TBL_HELPER} SET success=1 WHERE id=?", (db_helper_map[h],))

        conn.commit()
        print(f"[+] DHCP Worker: Đồng bộ thành công Pool, Excluded và IP Helper cho {host_ip}")
        
    except Exception as e:
        print(f"[-] DHCP Worker LỖI: {e}")
        conn.rollback()
    finally:
        conn.close()