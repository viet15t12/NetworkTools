import os
import re

# Từ điển map mã protocol sang tên đầy đủ để làm đẹp dữ liệu cho bảng t08
PROTOCOL_MAP = {
    'C': 'Connected',
    'L': 'Local',
    'S': 'Static',
    'S*': 'Static Default',
    'O': 'OSPF',
    'O*E1': 'OSPF External Type 1',
    'O*E2': 'OSPF External Type 2',
    'D': 'EIGRP',
    'D*EX': 'EIGRP External',
    'B': 'BGP',
    'R': 'RIP'
}

def process_routing_data(host, file_path, db_cursor, target_table):
    """
    Worker xử lý dữ liệu Định tuyến (Routing Table).
    CHỈ NHẬN LỆNH TỪ MAIN.
    """
    if not os.path.exists(file_path):
        print(f"      [-] Worker Routing: Cảnh báo, không tìm thấy file tại {file_path}")
        return False

    # 1. ĐỌC FILE THEO LỆNH CỦA MAIN
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # 2. XÓA SẠCH DỮ LIỆU CŨ CỦA HOST NÀY (Cơ chế Clear & Replace)
    db_cursor.execute(f"DELETE FROM {target_table} WHERE host = ?", (host,))
    
    # 3. REGEX BĂM DỮ LIỆU BẢNG ĐỊNH TUYẾN (ĐÃ FIX DẤU /)
    route_pattern = re.compile(
        r"^(?P<protocol>[A-Za-z\*]{1,4})\s+"                     
        r"(?P<network>\d{1,3}(?:\.\d{1,3}){3})(?:/(?P<prefix>\d+))?" # <- SỬA TẠI ĐÂY: Cho dấu / vào trong ngoặc optional
        r"(?:\s+\[(?P<ad>\d+)/(?P<metric>\d+)\])?"               
        r"(?:\s+via\s+(?P<nexthop>\d{1,3}(?:\.\d{1,3}){3}))?"    
        r"(?:,\s+(?P<age>\d[wdyhms0-9:]+))?"                     
        r"(?:.*?,\s+(?P<interface>[A-Za-z0-9/\.\-]+))?"          
    )

    routes_found = 0
    
    # 4. DUYỆT TỪNG DÒNG TEXT VÀ BÓC TÁCH
    for line in raw_text.splitlines():
        line = line.strip()
        # Bỏ qua dòng trống, header hoặc gateway of last resort
        if not line or line.startswith("Codes:") or line.startswith("Gateway"):
            continue
            
        match = route_pattern.search(line)
        if match:
            route_dict = match.groupdict()
            
            protocol_code = route_dict['protocol'].strip()
            protocol_name = PROTOCOL_MAP.get(protocol_code, 'Unknown')
            
            # Ép kiểu dữ liệu an toàn. Nếu không có prefix (như O 2.2.2.2), tự động điền 32
            destination = route_dict['network']
            prefix_length = int(route_dict['prefix']) if route_dict['prefix'] else 32
            ad = int(route_dict['ad']) if route_dict['ad'] else None
            metric = int(route_dict['metric']) if route_dict['metric'] else None
            next_hop = route_dict['nexthop']
            route_age = route_dict['age']
            exit_interface = route_dict['interface']
            
            # 5. GHI VÀO DB THÔNG QUA CON TRỎ CỦA MAIN
            db_cursor.execute(f"""
                INSERT INTO {target_table} (
                    host, protocol_code, protocol_name, destination, prefix_length,
                    administrative_distance, metric, next_hop, route_age, exit_interface, raw_line
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                host, 
                protocol_code, 
                protocol_name, 
                destination, 
                prefix_length,
                ad, 
                metric, 
                next_hop, 
                route_age, 
                exit_interface, 
                line
            ))
            routes_found += 1

    print(f"      [+] Worker Routing: Đã băm và nạp thành công {routes_found} routes cho {host}.")
    return True