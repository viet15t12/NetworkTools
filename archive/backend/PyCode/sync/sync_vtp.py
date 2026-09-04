import os
import re
import json
import yaml
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from backend.PyCode.share.config import get_db_connection, DB_TABLES, TMP_DIR, L2_BACKUP_DIR, STATE_DIR

TBL_DOMAINS = DB_TABLES["l2_vtp"]["domains"]
TBL_SWITCHES = DB_TABLES["l2_vtp"]["switches"]
TBL_MODES = DB_TABLES["l2_vtp"]["modes"]
TBL_DEVICES = DB_TABLES["device_info"]["main"]

# =====================================================================
# 1. PARSER OUTPUT TỪ SHOW VTP
# =====================================================================
def parse_vtp_output(status_output: str, password_output: str):
    """
    Parse dữ liệu thô từ 'show vtp status' và 'show vtp password'
    """
    # 1. Domain Name
    domain_match = re.search(r"VTP Domain Name\s*:\s*(\S+)", status_output)
    domain_name = domain_match.group(1).strip() if domain_match else ""
    if domain_name.lower() in ("null", "none", "(none)"):
        domain_name = ""

    # 2. VTP Version
    version_match = re.search(r"VTP version running\s*:\s*(\d+)", status_output) or \
                    re.search(r"VTP Operating Mode.*?Version\s*:\s*(\d+)", status_output) or \
                    re.search(r"VTP V2 Mode\s*:\s*(Enabled|Disabled)", status_output)
    
    version = 2
    if version_match:
        val = version_match.group(1)
        if val.isdigit():
            version = int(val)
        elif val.lower() == "enabled":
            version = 2
        elif val.lower() == "disabled":
            version = 1

    # 3. Operating Mode (VLAN mode)
    mode_match = re.search(r"VTP Operating Mode\s*:\s*(\w+)", status_output)
    mode = mode_match.group(1).strip().lower() if mode_match else "transparent"

    # 4. Pruning Mode
    pruning_match = re.search(r"VTP Pruning Mode\s*:\s*(\w+)", status_output)
    pruning = 1 if (pruning_match and pruning_match.group(1).strip().lower() == "enabled") else 0

    # 5. Primary Server (VTPv3)
    primary_server = 1 if re.search(r"VTP Primary Server\s*:\s*local", status_output, re.IGNORECASE) else 0

    # 6. Password
    pass_match = re.search(r"VTP Password:\s*(\S+)", password_output)
    password = pass_match.group(1).strip() if pass_match else ""
    if "not configured" in password_output.lower() or not password:
        password = ""

    return {
        "domain_name": domain_name,
        "version": version,
        "mode": mode,
        "pruning": pruning,
        "password": password,
        "primary_server": primary_server
    }


# =====================================================================
# 2. CẬP NHẬT DATABASE LETOS CHO 3 BẢNG VTP
# =====================================================================
def sync_vtp_record_to_db(host: str, parsed_data: dict):
    """
    Đồng bộ dữ liệu parsed vào:
      1. t09_vtp_domains
      2. t09_vtp_switches (Gán success = 1)
      3. t09_vtp_database_modes
    """
    domain_name = parsed_data["domain_name"] or "DEFAULT_DOMAIN"
    version = parsed_data["version"]
    raw_password = parsed_data["password"]
    mode = parsed_data["mode"]
    pruning = parsed_data["pruning"]
    primary_server = parsed_data.get("primary_server", 0)

    # --- XỬ LÝ CHUẨN RÀNG BUỘC CHECK CONSTRAINT ---
    # Nếu không có mật khẩu -> type = 'none' VÀ value = None (SQL NULL)
    # Nếu có mật khẩu -> type = 'plain' VÀ value = chuỗi mật khẩu
    if raw_password and len(raw_password.strip()) > 0:
        password_type = "plain"
        password_value = raw_password.strip()
    else:
        password_type = "none"
        password_value = None  # None trong Python sẽ chuyển thành NULL trong SQLite

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # --- BẢNG 1: t09_vtp_domains ---
        c.execute(f"SELECT vtp_domain_id FROM {TBL_DOMAINS} WHERE domain_name = ?", (domain_name,))
        dom_row = c.fetchone()
        if dom_row:
            domain_id = dom_row[0]
            c.execute(f"""
                UPDATE {TBL_DOMAINS}
                SET version = ?, password_value = ?, password_type = ?, updated_at = datetime('now', 'localtime')
                WHERE vtp_domain_id = ?
            """, (version, password_value, password_type, domain_id))
        else:
            c.execute(f"""
                INSERT INTO {TBL_DOMAINS} (domain_name, version, password_type, password_value)
                VALUES (?, ?, ?, ?)
            """, (domain_name, version, password_type, password_value))
            domain_id = c.lastrowid

        # --- BẢNG 2: t09_vtp_switches (GÁN CHUẨN SUCCESS = 1) ---
        c.execute(f"SELECT vtp_switch_id FROM {TBL_SWITCHES} WHERE TRIM(host) = TRIM(?)", (host,))
        sw_row = c.fetchone()
        if sw_row:
            switch_id = sw_row[0]
            c.execute(f"""
                UPDATE {TBL_SWITCHES}
                SET vtp_domain_id = ?, pruning = ?, success = 1
                WHERE vtp_switch_id = ?
            """, (domain_id, pruning, switch_id))
        else:
            c.execute(f"""
                INSERT INTO {TBL_SWITCHES} (host, vtp_domain_id, pruning, success)
                VALUES (?, ?, ?, 1)
            """, (host, domain_id, pruning))
            switch_id = c.lastrowid

        # --- BẢNG 3: t09_vtp_database_modes ---
        c.execute(f"SELECT vtp_mode_id FROM {TBL_MODES} WHERE vtp_switch_id = ? AND database_type = 'vlan'", (switch_id,))
        mode_row = c.fetchone()
        if mode_row:
            c.execute(f"""
                UPDATE {TBL_MODES}
                SET mode = ?, primary_server = ?
                WHERE vtp_mode_id = ?
            """, (mode, primary_server, mode_row[0]))
        else:
            c.execute(f"""
                INSERT INTO {TBL_MODES} (vtp_switch_id, database_type, mode, primary_server)
                VALUES (?, 'vlan', ?, ?)
            """, (switch_id, mode, primary_server))

        conn.commit()

        # Cập nhật snapshot state JSON
        state_file = os.path.join(L2_BACKUP_DIR, f"{host}_vtp_state.json")
        current_state = {
            "domain_name": domain_name,
            "version": version,
            "password_type": password_type,
            "password_value": password_value or "",
            "pruning": pruning,
            "mode": mode,
            "primary_server": primary_server
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(current_state, f, indent=2)

        print(f"[+] [SYNC VTP] {host} -> Đồng bộ DB Letos thành công (Domain: {domain_name}, Mode: {mode}, Ver: {version})")

    except Exception as e:
        conn.rollback()
        print(f"[-] [SYNC VTP ERROR] Lỗi cập nhật DB cho {host}: {e}")
        raise e
    finally:
        conn.close()


# =====================================================================
# 3. WORKER ĐỒNG BỘ CHO SYNC_MANAGER (ĐỌC TỪ FILE RUNNING)
# =====================================================================
def sync_l2_vtp_worker(host_ip: str):
    """Bóc tách từ file _running.txt"""
    config_file = os.path.join(STATE_DIR, f"{host_ip}_running.txt")
    if not os.path.exists(config_file):
        return False

    with open(config_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    status_match = re.search(r"={5,}\s*\[\s*SHOW VTP STATUS\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
    pass_match = re.search(r"={5,}\s*\[\s*SHOW VTP PASSWORD\s*\]\s*={5,}\n(.*?)(?=\n={5,}|\Z)", raw_text, re.DOTALL | re.IGNORECASE)

    status_raw = status_match.group(1).strip() if status_match else ""
    pass_raw = pass_match.group(1).strip() if pass_match else ""

    if not status_raw:
        print(f"[-] [SYNC VTP] Không tìm thấy dữ liệu SHOW VTP STATUS trong file của {host_ip}")
        return False

    parsed = parse_vtp_output(status_raw, pass_raw)
    sync_vtp_record_to_db(host_ip, parsed)
    return True