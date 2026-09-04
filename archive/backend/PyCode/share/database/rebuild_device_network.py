import sqlite3
import os

# =====================================================================
# SCRIPT BUILD DATABASE DEVICE_NETWORK (LETOS)
# =====================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Trỏ đường dẫn ra file device_network.db chuẩn theo config.py
DB_PATH = os.path.join(BASE_DIR, "device_network", "device_network.db")

# Danh sách các file SQL core và L2/L3 của Letos theo đúng thứ tự khởi tạo khóa ngoại
SQL_SUBDIR = "device_network"
SQL_FILES = [
    "01_core_devices.sql",
    "02_interface_router_l3.sql",
    "03_dhcp_helper.sql",
    "04_routing.sql",
    "05_security_nat.sql",
    "06_l2_switching.sql",
    "07_vrf.sql",
    "08_fhrp.sql",
    "09_vtp.sql"
]

def rebuild_device_network_db():
    # Tạo thư mục chứa db nếu chưa tồn tại
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[*] Đã xóa file device_network.db cũ: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    # Bật tính năng khóa ngoại cho SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        for sql_file in SQL_FILES:
            file_path = os.path.join(BASE_DIR, SQL_SUBDIR, sql_file)
            if os.path.exists(file_path):
                print(f"[*] Đang thực thi script Letos: {sql_file}...")
                with open(file_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                    cursor.executescript(sql_script)
            else:
                print(f"[-] CẢNH BÁO: Không tìm thấy file {sql_file} trong thư mục {SQL_SUBDIR}")

        conn.commit()
        print("\n[+] XONG! Khởi tạo device_network.db THÀNH CÔNG với đầy đủ bảng thiết bị và L2/L3!")
        
    except Exception as e:
        print(f"\n[-] LỖI trong quá trình build device_network: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    rebuild_device_network_db()