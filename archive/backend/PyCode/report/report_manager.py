import json
import datetime

# Tên file đầu ra (Front-end sẽ đọc file này)
OUTPUT_FILE = 'report_result.json'

def write_report(status, ip, role, msg, details=""):
    """
    Hàm dùng chung để ghi log báo cáo.
    Tham số:
      - status: "success" hoặc "error"
      - ip: Địa chỉ IP thiết bị
      - role: Vai trò (router/switch)
      - msg: Thông báo ngắn gọn
      - details: Chi tiết lỗi hoặc kết quả (Output)
    """
    
    # 1. Đóng gói dữ liệu
    report_data = {
        "status": status,
        "device_ip": ip,
        "role": role,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": msg,
        "details": str(details) # Ép kiểu chuỗi để tránh lỗi nếu details là object
    }
    
    # 2. Ghi file (Có xử lý tiếng Việt utf-8)
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=4, ensure_ascii=False)
        print(f"\n📝 [REPORT] Đã xuất báo cáo: {status.upper()} -> {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ [REPORT ERROR] Không ghi được file báo cáo: {e}")