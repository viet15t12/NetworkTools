import sqlite3
import os

# =====================================================================
# SCRIPT BUILD DATABASE INFO_COLLECTED MỚI
# =====================================================================

# Lấy đường dẫn thư mục hiện tại (nơi chứa script này)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "info_collected.db")

# Danh sách các file SQL cần build (đã sắp xếp đúng thứ tự)
SQL_SUBDIR = "info_collected"
SQL_FILES = [
    "08_info_routing_table.sql",
    "09_info_dhcp.sql",
    "10_info_acl.sql",
    "11_info_nat.sql",
    "12_info_syslog.sql"
]

def rebuild_database():
    # Xóa file db cũ nếu đang tồn tại (để build lại từ đầu, phòng hờ)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[*] Đã xóa file cũ: {DB_PATH}")

    # Kết nối sẽ tự động tạo file DB mới
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        for sql_file in SQL_FILES:
            file_path = os.path.join(BASE_DIR, SQL_SUBDIR, sql_file)
            if os.path.exists(file_path):
                print(f"[*] Đang thực thi script: {sql_file}...")
                with open(file_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                    # executescript cho phép chạy nhiều câu lệnh SQL cùng lúc
                    cursor.executescript(sql_script)
            else:
                print(f"[-] CẢNH BÁO: Không tìm thấy file {sql_file}")

        conn.commit()
        print("\n[+] XONG! Khởi tạo info_collected.db THÀNH CÔNG với đầy đủ các bảng!")
        
    except Exception as e:
        print(f"\n[-] LỖI trong quá trình build: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    rebuild_database()