from fastapi import FastAPI, BackgroundTasks
import uvicorn
import sys
import os

# 1. KẾT NỐI API VỚI THƯ MỤC BACKEND
from backend.PyCode.router_layer3.routing.main import routing_dispatcher 
from backend.PyCode.router_layer3.interface.main import interface_dispatcher
from backend.PyCode.router_layer3.service.dhcp.main import main as dhcp_dispatcher
# BỔ SUNG IMPORT CHO MODULE SECURITY (ACL)

from backend.PyCode.security.main import security_dispatcher

# BỔ SUNG IMPORT CHO MODULE INFO (GIÁM SÁT)
from backend.PyCode.info.main import info_collect_dispatcher, info_sync_dispatcher


#import nat
from backend.PyCode.router_layer3.service.nat.main import nat_dispatcher

#Import module Sync
from backend.PyCode.sync.sync_manager import SyncManager
#Import module Switch Layer 2
from backend.PyCode.switch_layer2.main import l2_dispatcher
#Import module Switch Layer 2 & Layer 3
from backend.PyCode.switch_layer2.main import l2_dispatcher, l3_dispatcher

app = FastAPI(
    title="Network Master API",
    description="Trung tâm quản lý toàn bộ URL kết nối với Frontend"
)
sync_engine = SyncManager()
# =====================================================================
# 📍 KHU VỰC QUẢN LÝ URL (chỉ cần bảo trì chỗ này)
# =====================================================================



# =============== API CỦA MODULE DHCP ========================
@app.post("/api/v1/network/dhcp")
def trigger_dhcp(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình DHCP xuống thiết bị (Đẩy từ DB) """
    if bg_tasks:
        # Cần modify lại hàm main() của DHCP để nhận tham số target nếu cần
        bg_tasks.add_task(dhcp_dispatcher) 
    else:
        dhcp_dispatcher()
        
    return {"status": "success", "message": f"Đang đẩy lệnh DHCP xuống {target}..."}


# =============== API CỦA MODULE ĐỒNG BỘ (SYNC) ========================
@app.post("/api/v1/network/sync")
def trigger_sync_api(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt đồng bộ cấu hình từ file backup vào Database Letos """
    if bg_tasks:
        bg_tasks.add_task(sync_engine.trigger_sync, target)
    else:
        sync_engine.trigger_sync(target)
        
    msg = f"Đang băm và đồng bộ toàn bộ file config trong backup..." if target.lower() == "all" else f"Đang băm file config và đẩy vào DB cho {target}..."
    return {"status": "success", "message": msg}

#============= API CỦA MODULE INTERFACE ROUTER LAYER 3=========================
@app.post("/api/v1/network/interfaces")
def trigger_interface(target: str = "all", bg_tasks: BackgroundTasks = None):
    """Nhận request API và kích hoạt push cấu hình Interface."""
    if bg_tasks:
        bg_tasks.add_task(interface_dispatcher, target)
    else:
        interface_dispatcher(target)
    return {"status": "success", "message": f"Đang đẩy lệnh Interface xuống {target}..."}


#=============== API CỦA MODULE ROUTING LAYER 3 ========================
@app.post("/api/v1/network/ospf")
def trigger_ospf(target: str = "all", bg_tasks: BackgroundTasks = None):
    if bg_tasks:
        bg_tasks.add_task(routing_dispatcher, target, "ospf")
    else:
        routing_dispatcher(target, "ospf")
    return {"status": "success", "message": f"Đang đẩy lệnh OSPF xuống {target}..."}

@app.post("/api/v1/network/eigrp")
def trigger_eigrp(target: str = "all", bg_tasks: BackgroundTasks = None):
    if bg_tasks:
        bg_tasks.add_task(routing_dispatcher, target, "eigrp")
    else:
        routing_dispatcher(target, "eigrp")
    return {"status": "success", "message": f"Đang đẩy lệnh EIGRP xuống {target}..."}

@app.post("/api/v1/network/static")
def trigger_static(target: str = "all", bg_tasks: BackgroundTasks = None):
    if bg_tasks:
        bg_tasks.add_task(routing_dispatcher, target, "static")
    else:
        routing_dispatcher(target, "static")
    return {"status": "success", "message": f"Đang đẩy lệnh Static Route xuống {target}..."}


#=============== API CỦA MODULE SECURITY (ACL) ========================
@app.post("/api/v1/network/acl")
def trigger_acl(target: str = "all", acl_id: int = None, bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình ACL (Có thể gọi đích danh ID hoặc quét toàn bộ) """
    if bg_tasks:
        # Truyền thêm tham số "acl" và acl_id vào hàm điều phối
        bg_tasks.add_task(security_dispatcher, target, "acl", acl_id)
    else:
        security_dispatcher(target, "acl", acl_id)
        
    msg = f"Đang đẩy lệnh ACL (ID: {acl_id}) xuống {target}..." if acl_id else f"Đang quét và đẩy toàn bộ ACL chờ xử lý xuống {target}..."
    return {"status": "success", "message": msg}

#=============== API CỦA MODULE NAT ========================
@app.post("/api/v1/network/nat")
def trigger_nat(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình toàn bộ khối NAT (NAT ACL & NAT Engine) """
    if bg_tasks:
        bg_tasks.add_task(nat_dispatcher, target)
    else:
        nat_dispatcher(target)
        
    return {"status": "success", "message": f"Đang quét và đẩy lệnh NAT xuống {target}..."}
# =============== API CỦA MODULE SWITCH LAYER 2 (VLAN)========================
@app.post("/api/v1/network/switch-l2/vlan")
def trigger_vlan(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình VLAN xuống thiết bị Switch (Lấy từ DB) """
    if bg_tasks:
        bg_tasks.add_task(l2_dispatcher, target, "vlan")
    else:
        l2_dispatcher(target, "vlan")
        
    return {"status": "success", "message": f"Đang gom cấu hình VLAN và đẩy xuống {target}..."}
# =============== API CỦA MODULE SWITCH LAYER 2 (INTERFACE) ========================
@app.post("/api/v1/network/switch-l2/interface")
def trigger_interface_l2(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình Interface L2 (Vật lý & EtherChannel) xuống Switch """
    if bg_tasks:
        bg_tasks.add_task(l2_dispatcher, target, "interface")
    else:
        l2_dispatcher(target, "interface")
        
    return {"status": "success", "message": f"Đang gom cấu hình Interface L2 và đẩy xuống {target}..."}

# =============== API CỦA MODULE SWITCH LAYER 2 (STP) ========================
@app.post("/api/v1/network/switch-l2/stp")
def trigger_stp(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình Spanning Tree Protocol (STP) xuống Switch """
    if bg_tasks:
        bg_tasks.add_task(l2_dispatcher, target, "stp")
    else:
        l2_dispatcher(target, "stp")
        
    return {"status": "success", "message": f"Đang gom cấu hình STP và đẩy xuống {target}..."}

# =============== API CỦA MODULE SWITCH LAYER 2 (VTP) ========================
@app.post("/api/v1/network/switch-l2/vtp")
def trigger_vtp(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình VTP (VLAN Trunking Protocol) xuống Switch """
    if bg_tasks:
        bg_tasks.add_task(l2_dispatcher, target, "vtp")
    else:
        l2_dispatcher(target, "vtp")
        
    return {"status": "success", "message": f"Đang gom cấu hình VTP và đẩy xuống {target}..."}
# =============== API CỦA MODULE SWITCH LAYER 2 (SECURITY) ========================
@app.post("/api/v1/network/switch-l2/security")
def trigger_security_l2(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình L2 Security (DHCP Snooping, DAI, Port Security) xuống Switch """
    if bg_tasks:
        bg_tasks.add_task(l2_dispatcher, target, "security")
    else:
        l2_dispatcher(target, "security")
        
    return {"status": "success", "message": f"Đang gom cấu hình L2 Security và đẩy xuống {target}..."}
#==========================================================================================================
# =============== API CỦA MODULE SWITCH LAYER 3 (SVI & IP ROUTING) ========================
@app.post("/api/v1/network/switch-l3/svi")
def trigger_svi(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ API kích hoạt cấu hình IP Routing và SVI xuống Switch Core """
    if bg_tasks:
        bg_tasks.add_task(l3_dispatcher, target, "svi")
    else:
        l3_dispatcher(target, "svi")
        
    return {"status": "success", "message": f"Đang gom cấu hình SVI/L3 và đẩy xuống {target}..."}


#=========================================================================================



# =====================================================================
# =============== API CỦA MODULE INFO (GIÁM SÁT - TELEMETRY) ==========
# =====================================================================

# [TRIGGER 1] - CHỈ ĐI KÉO FILE VỀ
@app.post("/api/v1/network/info/collect")
def trigger_info_collect(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ Kích hoạt Nornir SSH kéo running-config (hoặc lệnh show) về lưu file text """
    if bg_tasks:
        bg_tasks.add_task(info_collect_dispatcher, target)
    else:
        info_collect_dispatcher(target)
        
    msg = "Đang càn quét và lưu file cấu hình..." if target.lower() == "all" else f"Đang kéo file từ {target}..."
    return {"status": "success", "message": msg}

# [TRIGGER 2] - CHỈ ĐỌC FILE VÀ CẬP NHẬT DATABASE
@app.post("/api/v1/network/info/sync-db")
def trigger_info_sync(target: str = "all", bg_tasks: BackgroundTasks = None):
    """ Kích hoạt băm file text trong STATE_DIR và đẩy vào info_collected.db """
    if bg_tasks:
        bg_tasks.add_task(info_sync_dispatcher, target)
    else:
        info_sync_dispatcher(target)
        
    msg = "Đang đọc file và đẩy vào Database..." if target.lower() == "all" else f"Đang xử lý dữ liệu cho {target}..."
    return {"status": "success", "message": msg}

if __name__ == "__main__":
    print(">>> API Server đã khởi động thành công: Đang lắng nghe tại http://127.0.0.1:8000")
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)
