import yaml
import json
import time
import os
import re
import socket  # <--- Thư viện mới để check port
from napalm import get_network_driver

# --- CẤU HÌNH ---
INPUT_FILE = 'input_topology.yaml'       
XML_OUTPUT_FILE = 'reports/network_topology.drawio.xml'
SCAN_DB_FILE = 'reports/Thong_tin_loai_thiet_bi.json' 

# --- STYLE DRAW.IO ---
STYLE_ROUTER = "shape=ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=2;fontStyle=1;"
STYLE_SWITCH = "shape=rect;whiteSpace=wrap;html=1;rounded=1;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;fontStyle=1;"
STYLE_LINK = "endArrow=none;html=1;rounded=0;strokeWidth=2;strokeColor=#333333;"

def load_scan_database():
    db = {}
    if os.path.exists(SCAN_DB_FILE):
        try:
            with open(SCAN_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        hostname = item.get('hostname', '')
                        ip = item.get('ip') or item.get('management_ip')
                        if hostname and ip:
                            db[hostname] = ip
                            db[hostname.split('.')[0]] = ip 
        except: pass
    return db

# --- HÀM MỚI: KIỂM TRA THIẾT BỊ CÓ SỐNG KHÔNG ---
def is_host_alive(ip, port=22, timeout=1):
    """
    Thử kết nối đến cổng SSH (22) của thiết bị.
    Nếu kết nối được -> Thiết bị đang bật (Alive).
    Nếu không -> Thiết bị đã tắt (Dead).
    """
    if not ip: return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0 # 0 nghĩa là mở (Open)
    except:
        return False

def save_drawio_xml(nodes, edges):
    print(f"\n🎨 Đang vẽ file Draw.io XML (Chế độ Real-time)...")
    os.makedirs(os.path.dirname(XML_OUTPUT_FILE) if os.path.dirname(XML_OUTPUT_FILE) else '.', exist_ok=True)

    # Phân loại Node còn sống để vẽ
    layer_1_routers = [n for n in nodes if n['id'].upper().startswith("R") or "ROUTER" in n['label'].upper()]
    layer_3_access = [n for n in nodes if n not in layer_1_routers]
    
    layer_1_routers.sort(key=lambda x: x['id'])
    layer_3_access.sort(key=lambda x: x['id'])

    xml_content = [
        '<mxfile host="app.diagrams.net" type="device">',
        '  <diagram name="Network Topology" id="network-diagram">',
        '    <mxGraphModel dx="1200" dy="1200" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">',
        '      <root>',
        '        <mxCell id="0" />',
        '        <mxCell id="1" parent="0" />'
    ]

    def escape_xml(text):
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    
    node_map = {}

    def draw_layer(node_list, start_y, spacing_x=250):
        total_width = len(node_list) * spacing_x
        start_x = (1000 - total_width) / 2 
        for i, node in enumerate(node_list):
            node_id = node['id']
            label = escape_xml(f"{node['label']}\n({node['ip']})")
            style = STYLE_ROUTER if node_id.upper().startswith("R") else STYLE_SWITCH
            w, h = (80, 80) if node_id.upper().startswith("R") else (120, 60)
            x = start_x + (i * spacing_x)
            
            xml_node = f'        <mxCell id="{node_id}" value="{label}" style="{style}" vertex="1" parent="1">'
            xml_geo = f'          <mxGeometry x="{x}" y="{start_y}" width="{w}" height="{h}" as="geometry" />'
            xml_content.append(xml_node + '\n' + xml_geo + '\n        </mxCell>')
            node_map[node_id] = True

    draw_layer(layer_1_routers, 50, 300)
    if len(layer_3_access) > 6:
        mid = len(layer_3_access) // 2
        draw_layer(layer_3_access[:mid], 300, 200)
        draw_layer(layer_3_access[mid:], 500, 200)
    else:
        draw_layer(layer_3_access, 350, 220)

    for i, edge in enumerate(edges):
        src, dst = edge['source'], edge['target']
        label = escape_xml(edge.get('label', '').replace('\n', ' / '))
        if src in node_map and dst in node_map:
            edge_id = f"edge_{i}"
            xml_edge = f'        <mxCell id="{edge_id}" value="{label}" style="{STYLE_LINK};edgeStyle=orthogonalEdgeStyle;curved=1;" edge="1" parent="1" source="{src}" target="{dst}">'
            xml_geo = '          <mxGeometry relative="1" as="geometry" />'
            xml_content.append(xml_edge + '\n' + xml_geo + '\n        </mxCell>')

    xml_content.append('      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>')
    with open(XML_OUTPUT_FILE, 'w', encoding='utf-8') as f: f.write("\n".join(xml_content))
    print(f"✅ Đã xuất file XML tại: {XML_OUTPUT_FILE}")

def parse_cdp_raw(raw_output):
    neighbors = []
    chunks = raw_output.split('-------------------------')
    for chunk in chunks:
        if not chunk.strip(): continue
        try:
            name_match = re.search(r'Device ID: ([\w\.-]+)', chunk)
            local_match = re.search(r'Interface: ([\w\/\s]+),', chunk)
            remote_port_match = re.search(r'Port ID \(outgoing port\): ([\w\/\s]+)', chunk)
            ip_match = re.search(r'IP.*address: ([\d\.]+)', chunk, re.IGNORECASE)
            
            if name_match:
                neighbors.append({
                    'remote_host': name_match.group(1),
                    'remote_ip': ip_match.group(1) if ip_match else None,
                    'local_port': local_match.group(1).strip() if local_match else "Fa0/0",
                    'remote_port': remote_port_match.group(1).strip() if remote_port_match else "Fa0/0"
                })
        except: continue
    return neighbors

def recursive_discovery():
    print("\n--- 🕵️ WORKER TOPOLOGY: REAL-TIME MONITORING ---")
    if not os.path.exists(INPUT_FILE): return
    with open(INPUT_FILE, 'r', encoding='utf-8') as f: config = yaml.safe_load(f)
    
    seed = config.get('seed_device', {})
    queue = [seed.get('ip')]
    username, password = config.get('username'), config.get('password')
    driver_type = seed.get('platform', 'ios')
    
    visited_ips, visited_hostnames = set(), set()
    nodes, links, processed_links = [], [], set()
    ip_database = load_scan_database()

    netmiko_args = {"global_delay_factor": 2, "transport_options": {"key_types": ["ssh-rsa"]}}

    while queue:
        current_ip = queue.pop(0).strip()
        if current_ip in visited_ips or not current_ip: continue
        
        print(f"👉 Quét: {current_ip}...", end=" ", flush=True)
        
        # --- CHECK 1: Thiết bị hiện tại có sống không? ---
        if not is_host_alive(current_ip):
            print(f"❌ DEAD (Không phản hồi SSH). Bỏ qua.")
            visited_ips.add(current_ip)
            continue
        # -----------------------------------------------

        try:
            driver = get_network_driver(driver_type)
            device = driver(current_ip, username, password, optional_args=netmiko_args)
            device.open()
            
            facts = device.get_facts()
            short_hostname = facts['hostname'].split('.')[0].lower()
            
            if short_hostname in visited_hostnames:
                device.close(); visited_ips.add(current_ip); print("🔁 Loop!"); continue
            
            visited_hostnames.add(short_hostname)
            nodes.append({"id": short_hostname.upper(), "label": facts['hostname'], "ip": current_ip})
            print(f"✅ OK ({short_hostname})")

            # Lấy CDP/LLDP
            neighbors = parse_cdp_raw(device.cli(['show cdp neighbors detail']).get('show cdp neighbors detail', ''))
            
            for n in neighbors:
                remote_short = n['remote_host'].split('.')[0].lower()
                next_ip = n['remote_ip'] or ip_database.get(n['remote_host']) or ip_database.get(remote_short)

                # --- CHECK 2: Hàng xóm có sống không? (QUAN TRỌNG) ---
                # Nếu hàng xóm có IP, tool sẽ thử "Ping" nhẹ (check port 22)
                # Nếu không phản hồi -> Coi như dây đứt hoặc máy tắt -> KHÔNG VẼ
                if next_ip:
                    # Bỏ check alive nếu đó là Router/Switch đang quét (để tránh tự check mình)
                    if next_ip not in visited_ips and next_ip != current_ip:
                        if not is_host_alive(next_ip, timeout=0.5):
                            print(f"      ⚠️  Phát hiện 'Bóng ma' {remote_short.upper()} ({next_ip}) -> Đã tắt. Không vẽ!")
                            continue # <--- BỎ QUA KHÔNG VẼ DÂY NÀY
                # -----------------------------------------------------

                link_id = "-".join(sorted([short_hostname.upper(), remote_short.upper()]))
                
                if link_id not in processed_links:
                    links.append({
                        "source": short_hostname.upper(), "target": remote_short.upper(),
                        "label": f"{n['local_port']} <-> {n['remote_port']}"
                    })
                    processed_links.add(link_id)
                
                if next_ip and next_ip not in visited_ips and next_ip not in queue:
                    queue.append(next_ip)

            device.close()
        except Exception as e: print(f"❌ Lỗi {current_ip}: {e}")
        visited_ips.add(current_ip)

    save_drawio_xml(nodes, links)
    print(f"🏁 GIÁM SÁT HOÀN TẤT! Sơ đồ chỉ hiện thị thiết bị ĐANG ONLINE.")

if __name__ == "__main__":
    recursive_discovery()