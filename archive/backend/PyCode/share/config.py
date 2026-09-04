import os
import sys
from dotenv import load_dotenv, find_dotenv

# =========================================================
# 1. RADAR TỰ ĐỘNG MÒ TÌM GỐC DỰ ÁN QUA FILE .env
# =========================================================
env_path = find_dotenv()
if not env_path:
    raise Exception("[-] LỖI CRITICAL: Không tìm thấy file .env! Vui lòng tạo file .env ở gốc dự án.")

load_dotenv(env_path)

# PROJECT_ROOT đang là thư mục CAMS (chứa file .env)
PROJECT_ROOT = os.path.dirname(env_path)

# Gán các thư mục gốc để code bên dưới ngắn gọn và đồng bộ hơn
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
PYCODE_DIR = os.path.join(BACKEND_DIR, "PyCode")

# Ép hệ thống nhận diện thư mục backend để import chéo mượt mà
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# =========================================================
# 2. QUY HOẠCH ĐƯỜNG DẪN DATABASE & FILE TẠM (GLOBAL)
# =========================================================
db_rel_path = os.getenv("DB_RELATIVE_PATH", "backend/PyCode/share/database/device_network.db")

# Bí danh DB_PATH (Dùng chung cho toàn bộ dự án)
DB_PATH = os.path.join(PROJECT_ROOT, *db_rel_path.split("/"))
DB_DEVICE_NETWORK = DB_PATH 

BACKUP_DIR = os.path.join(PROJECT_ROOT, "app", "backup")
TMP_DIR = os.path.join(BACKEND_DIR, "Tmp")

os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

DEFAULT_SSH_TIMEOUT = 60


# Thư mục chứa Snapshot (ảnh chụp trạng thái cấu hình của Switch)
STATE_DIR = os.path.join(TMP_DIR, "states")
os.makedirs(STATE_DIR, exist_ok=True)
# =====================================================================
# 3. QUY HOẠCH GIAO TIẾP JSON (I/O) GIỮA FRONTEND VÀ BACKEND
# =====================================================================
INTERFACE_INPUT = os.path.join(TMP_DIR, "interface_input.json")
INTERFACE_OUTPUT = os.path.join(TMP_DIR, "interface_output.json")
DHCP_INPUT = os.path.join(TMP_DIR, "dhcp_input.json")
DHCP_OUTPUT = os.path.join(TMP_DIR, "dhcp_output.json")
ROUTE_INPUT = os.path.join(TMP_DIR, "route_input.json")
ROUTE_OUTPUT = os.path.join(TMP_DIR, "route_output.json")
SECURITY_INPUT = os.path.join(TMP_DIR, "security_input.json")
SECURITY_OUTPUT = os.path.join(TMP_DIR, "security_output.json")
FILE_LOGIN_EXPORT = os.path.join(TMP_DIR, "login_output.json")

# =========================================================
# 4. QUY HOẠCH THƯ MỤC TEMPLATE (JINJA2)
# =========================================================
# --- Nhóm Security (ACL, DHCP) ---
SECURITY_DIR = os.path.join(PYCODE_DIR, "security")
ACL_TEMPLATE_DIR = os.path.join(SECURITY_DIR, "ACL", "Templates")
DHCP_TEMPLATE_DIR = os.path.join(SECURITY_DIR, "DHCP", "Templates")

# --- Nhóm Router Layer 3 ---
ROUTER_LAYER3_DIR = os.path.join(PYCODE_DIR, "router_layer3")

# Module Routing
ROUTING_DIR = os.path.join(ROUTER_LAYER3_DIR, "routing")
ROUTING_TEMPLATE_DIR = os.path.join(ROUTING_DIR, "templates")

# Module Interface
INTERFACE_DIR = os.path.join(ROUTER_LAYER3_DIR, "interface")
INTERFACE_TEMPLATE_DIR = os.path.join(INTERFACE_DIR, "templates")

# (Khai báo sẵn đường dẫn cho 2 module đang thiết kế)
ROUTER_CONFIG_DIR = os.path.join(ROUTER_LAYER3_DIR, "router_config")
SERVICE_DIR = os.path.join(ROUTER_LAYER3_DIR, "service")

# --- Nhóm Switch Layer 2 ---
SWITCH_LAYER2_DIR = os.path.join(PYCODE_DIR, "switch_layer2")
L2_TEMPLATE_DIR = os.path.join(SWITCH_LAYER2_DIR, "templates")


#-----------SWITCH----------------
L2_BACKUP_DIR = os.path.join(PROJECT_ROOT,"backend","PyCode", "switch_layer2", "backup", "layer2_state")
os.makedirs(L2_BACKUP_DIR, exist_ok=True)
L3_BACKUP_DIR = os.path.join(PROJECT_ROOT, "backend", "PyCode", "switch_layer2", "backup", "layer3_state")
os.makedirs(L3_BACKUP_DIR, exist_ok=True)
#---------------------------------------------



def get_acl_template_path(os_folder):
    return os.path.join(ACL_TEMPLATE_DIR, os_folder)

# =========================================================
# 5. SINGLE SOURCE OF TRUTH: QUY HOẠCH CÁC TÊN BẢNG DATABASE
# =========================================================
DB_TABLES = {
    "device_info": {
        "main": "t01_devices"  
    },
    "routing_ospf": {     
        "processes": "t04_ospf_processes",  
        "networks": "t04_ospf_networks",  
        "distance": "t04_ospf_distance",  
        "areas": "t04_ospf_areas",  
        "area_ranges": "t04_ospf_area_ranges",  
        "redistribute": "t04_ospf_redistribute",  
        "passive_interfaces": "t04_ospf_passive_interfaces",  
        "tuning": "t04_ospf_tuning",  
        "interface_settings": "t04_router_iface_ospf"  
    },
    "routing_eigrp": {     
        "processes": "t04_eigrp_processes",  
        "networks": "t04_eigrp_networks",  
        "interface_settings": "t04_router_iface_eigrp",  
        "passive_interfaces": "t04_eigrp_passive_interfaces",  
        "distribute_lists": "t04_eigrp_distribute_lists",  
        "offset_lists": "t04_eigrp_offset_lists",  
        "redistribute": "t04_eigrp_redistribute",  
        "key_chains": "t04_eigrp_key_chains"  
    },
    "routing_static": {   
        "default": "t04_static_default_routes",  
        "routes": "t04_static_routes"  
    },
    "acl": {   
        "main": "t05_ACL_DB",  
        "extended": "t05_extended_acl_rules",  
        "standard": "t05_standard_acl_rules",  
        "mac": "t05_mac_acl_rules",  
        "reflexive": "t05_reflexive_acl_rules",  
        "dynamic": "t05_dynamic_acl_rules",
        "router_iface": "t05_router_iface_acl"   
    },
    "interfaces": {
        "main": "t02_interface_name"  
    },
    "nat_acl": {
        "main": "t05_NAT_ACL_DB",  
        "standard": "t05_nat_standard_acl_rules",  
        "extended": "t05_nat_extended_acl_rules"  
    },
    "nat": {
        "main": "t05_NAT_DB",  
        "interfaces": "t05_router_iface_nat",  
        "pools": "t05_nat_pools",  
        "static_mappings": "t05_nat_static_mappings",  
        "dynamic_rules": "t05_nat_dynamic_rules",  
        "overload_rules": "t05_nat_overload_interface_rules",  
        "exempt_rules": "t05_nat_exempt_rules"  
    },
    "route_map": {
        "main": "t05_route_map_db", 
        "entries": "t05_route_map_entries" 
    },
    "dhcp": {
        "pools": "t03_dhcp_pool", 
        "excluded": "t03_excluded_address", 
        "helper": "t03_router_iface_helper"
    },


    #Bảng vlan L2
    "l2_vlan": {
        "main": "t06_vlan_db"
    },
    # --- BỔ SUNG KHAI BÁO BẢNG L2 INTERFACE & ETHERCHANNEL ---
    "l2_interfaces": {
        "main": "t06_interface_l2",
        "access": "t06_iface_access",
        "trunk": "t06_iface_trunk"
    },
    "l2_etherchannel": {
        "main": "t06_etherchannel"
    },
    "l2_stp": {
        "global": "t06_stp_config",
        "interface": "t06_iface_stp"
    },
    "l2_vtp": {
        "domains": "t09_vtp_domains",
        "switches": "t09_vtp_switches",
        "modes": "t09_vtp_database_modes"
    },
    "l2_security": {
        "global": "t06_security_l2",
        "dhcp_trust": "t06_dhcp_trust_ports",
        "port_sec": "t06_iface_port_security",
        "mac_table": "t06_iface_mac_table"
    },
    "l2_traffic_control": {
    "storm_control": "t06_iface_storm_control",
    "qos": "t06_iface_qos"
    },

    # --- BỔ SUNG BẢNG L3 SWITCH (SVI & ROUTING) ---
    "l3_switch": {
        "global": "t06_switch_l3_config",
        "svi": "t06_svi_interface"
    }
}

# =========================================================
# 6. TRUNG TÂM CẤP PHÁT KẾT NỐI DATABASE (GLOBAL CONNECTION)
# =========================================================
import sqlite3

def get_db_connection():
    """
    Hàm duy nhất trong toàn dự án được phép mở kết nối tới Database Letos.
    Bọn Worker chỉ việc gọi hàm này để dùng, cấm tự kết nối!
    """
    conn = sqlite3.connect(DB_PATH)
    # Bật khóa ngoại (Foreign Keys) cho toàn dự án để SQLite cascade chuẩn
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn