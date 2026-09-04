import os
import sys
import argparse
import sqlite3

# =========================================================
# 1. SETUP RADAR ĐƯỜNG DẪN (CHỈ TRỎ ĐẾN GỐC DỰ ÁN)
# =========================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Lùi 2 nấc hoặc 3 nấc tùy cấu trúc của sếp để ra đến thư mục 'backend'
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../.."))

if PROJECT_ROOT not in sys.path: sys.path.append(PROJECT_ROOT)
if CURRENT_DIR not in sys.path: sys.path.append(CURRENT_DIR)

# =========================================================
# 2. HÚT 100% CẤU HÌNH TỪ CONFIG.PY (TRÁNH HARDCODE)
# =========================================================
from PyCode.share.config import DB_PATH, DB_TABLES

# IMPORT CÁC WORKER (Thêm Worker khác vào đây trong tương lai)
try:
    from ACL.worker_acl import run_acl_worker
except ImportError as e:
    print(f"[-] Lỗi Import Worker: {e}")
    sys.exit(1)


# =========================================================
# 3. HÀM ĐIỀU PHỐI (DÀNH CHO API VÀ TERMINAL DÙNG CHUNG)
# =========================================================
def security_dispatcher(target_ip="all", target_module="all", acl_id=None):
    """
    Hàm điều phối chính cho mảng Security.
    API sẽ truyền tham số trực tiếp vào đây.
    """
    if not os.path.exists(DB_PATH):
        print(f"[-] LỖI CRITICAL: Không tìm thấy Database tại: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # =======================================================
        # MODULE 1: XỬ LÝ ACCESS CONTROL LIST (ACL)
        # =======================================================
        if target_module in ['acl', 'all']:
            # BỐC TÊN BẢNG TỪ CONFIG
            T_ACL_MAIN = DB_TABLES.get("acl", {}).get("main", "ACL_DB")
            
            # KỊCH BẢN 1: CHẠY THEO ID (UI TRUYỀN VÀO)
            if acl_id:
                cursor.execute(f"SELECT host FROM {T_ACL_MAIN} WHERE Acl_id = ?", (acl_id,))
                row = cursor.fetchone()
                if row:
                    print(f"\n[*] [Security Gateway] Tra cứu ACL_ID {acl_id} -> Thuộc Host: {row[0]}")
                    run_acl_worker(row[0], [acl_id], DB_PATH)
                else:
                    print(f"\n[-] LỖI: Không tìm thấy ACL_ID {acl_id} trong DB!")
            
            # KỊCH BẢN 2: QUÉT HÀNG LOẠT (TÌM THẰNG NÀO CÓ LỆNH 0 HOẶC -1)
            else:
                print(f"\n[*] [Security Gateway] Quét ACL (pending) cho Target: {target_ip}")
                
                # 1. Bốc danh sách các IP (Host) có chứa tác vụ chờ xử lý
                query_hosts = f"SELECT DISTINCT host FROM {T_ACL_MAIN} WHERE success IN (0, -1)"
                params = []
                if target_ip != "all":
                    query_hosts += " AND host = ?"
                    params.append(target_ip)
                    
                cursor.execute(query_hosts, tuple(params))
                hosts = [row[0] for row in cursor.fetchall()]
                
                if hosts:
                    # 2. Vòng lặp chia bài: Lấy list ACL của từng Host và chạy Worker cho riêng Host đó
                    for h in hosts:
                        cursor.execute(f"SELECT Acl_id FROM {T_ACL_MAIN} WHERE host = ? AND success IN (0, -1)", (h,))
                        acl_list = [r[0] for r in cursor.fetchall()]
                        if acl_list:
                            run_acl_worker(h, acl_list, DB_PATH)
                else:
                    print(f"\n[INFO] Không có tác vụ ACL nào đang chờ cho {target_ip}.")

        # =======================================================
        # MODULE 2: XỬ LÝ DHCP SNOOPING (Ví dụ mở rộng)
        # =======================================================
        # if target_module in ['dhcp_snooping', 'all']:
        #     run_dhcp_snooping_worker(...)

    finally:
        conn.close()


# =========================================================
# 4. KHỐI LỆNH TERMINAL (DÀNH CHO GỌI TỪ CMD/POWERSHELL)
# =========================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Security Automation Gateway")
    parser.add_argument("-t", "--target", type=str, default="all", help="IP của Router (Mặc định: all)")
    
    # 🌟 MỞ RỘNG TÍNH NĂNG Ở ĐÂY:
    parser.add_argument("-m", "--module", type=str, choices=['acl', 'dhcp_snooping', 'all'], default="all", help="Tính năng Security muốn chạy")
    parser.add_argument("-id", "--acl_id", type=int, help="ID của tác vụ (Dành cho UI gọi lẻ)")
    args = parser.parse_args()

    # Truyền tham số từ Terminal vào thẳng hàm điều phối
    security_dispatcher(target_ip=args.target, target_module=args.module, acl_id=args.acl_id)