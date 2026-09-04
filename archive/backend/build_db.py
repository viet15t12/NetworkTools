import sqlite3
import os

# 1. Xác định tọa độ chuẩn xác
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = CURRENT_DIR # Vì file này đang nằm ngay gốc backend
DB_DIR = os.path.join(PROJECT_ROOT, "PyCode", "share", "database")
DB_PATH = os.path.join(DB_DIR, "device_network.db")
SQL_FILE = os.path.join(PROJECT_ROOT, "main.sql")

# Đảm bảo thư mục database tồn tại
os.makedirs(DB_DIR, exist_ok=True)

def build_database_from_sql():
    print(f"[*] Đang dọn dẹp mặt bằng...")
    # Xóa file db cũ nếu có để đúc lại từ đầu cho sạch
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("  -> Đã xóa DB cũ.")

    print(f"[*] Đang đọc bản thiết kế từ: {SQL_FILE}")
    try:
        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            sql_script = f.read()
    except Exception as e:
        print(f"[-] LỖI CRITICAL: Không đọc được file SQL. Chi tiết: {e}")
        return

    print(f"[*] Đang đổ bê tông (Build Database) tại: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Bật khóa ngoại
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Thực thi nguyên cả file SQL
        cursor.executescript(sql_script)
        
        conn.commit()
        print("\n[+] XONG RỰC RỠ! Toàn bộ 27 bảng đã được đúc thành công!")
        
    except sqlite3.Error as e:
        print(f"[-] LỖI SQLITE: Quá trình đúc thất bại. Chi tiết: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    build_database_from_sql()