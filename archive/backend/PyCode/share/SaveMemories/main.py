import os
import sys
import json
from worker_save import run_save_config

def get_external_path(relative_path):
    if hasattr(sys, 'frozen'):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(base_dir, relative_path))

if __name__ == "__main__":
    # Lùi 3 bước (SaveMemories -> share -> PyCode -> Root) để vào thư mục Tmp
    input_path = get_external_path("../../../Tmp/save_input.json")
    output_path = get_external_path("../../../Tmp/save_output.json")
    
    # [ĐÃ FIX ĐƯỜNG DẪN DB] - Trỏ sang thư mục database nằm ngay cạnh SaveMemories
    db_path = get_external_path("../database/device_network.db")

    if not os.path.exists(input_path):
        print(f"[ERROR] Không tìm thấy file yêu cầu lưu cấu hình tại: {input_path}")
        sys.exit(1)

    # Thêm check nhỏ cho an toàn
    if not os.path.exists(db_path):
        print(f"[ERROR] Không tìm thấy file Database tại: {db_path}")
        sys.exit(1)

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
            
        run_save_config(input_data, db_path, output_path)
    except Exception as e:
        print(f"[ERROR] Hệ thống gặp sự cố: {e}")