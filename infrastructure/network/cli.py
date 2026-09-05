import os
from infrastructure.database import sqlcipher as sqlite3
import json
import sys

from infrastructure.security import decrypt_device_password

# Try to import readline for command history (up/down arrows)
try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False

# Define paths relative to this script so the tool works after CMake copies it.
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(WORKSPACE_ROOT, "database_paths.json")


def load_database_paths():
    """Load DB paths created by the PyQt app."""
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        db_file = data.get("device_network_db")
        if db_file:
            data["device_network_db"] = os.path.abspath(os.path.expanduser(db_file))
        return data
    except Exception as e:
        return {"error": str(e)}


def get_db_file():
    """Lấy đường dẫn database chính từ file database_paths.json."""
    data = load_database_paths()
    return data.get("device_network_db")

def show_all_paths():
    """Display all paths used in the application."""
    print("\n" + "="*50)
    print("WORKSPACE PATHS")
    print("="*50)
    print(f"Workspace Root: {WORKSPACE_ROOT}")
    print(f"JSON File:      {JSON_FILE}")
    data = load_database_paths()
    if data.get("main_sql"):
        print(f"Main SQL File:  {data['main_sql']}")
    if data.get("device_network_db"):
        print(f"Database File:  {data['device_network_db']}")
    if data.get("error"):
        print(f"JSON Error:     {data['error']}")
    print("="*50 + "\n")

def show_json_content():
    """Display the content of the JSON file containing paths."""
    if not os.path.exists(JSON_FILE):
        print(f"\nWarning: {JSON_FILE} does not exist. Start the PyQt app first so it can initialize DB paths.\n")
        return
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("\n" + "="*50)
        print("JSON PATHS CONTENT")
        print("="*50)
        for key, value in data.items():
            print(f"{key}: {value}")
        print("="*50 + "\n")
    except Exception as e:
        print(f"\nError reading JSON file: {e}\n")

def normalize_device_type(os_name):
    """Convert the t01_devices.os value to a Netmiko device_type."""
    if not os_name:
        return "cisco_ios"

    normalized = os_name.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "ios": "cisco_ios",
        "cisco_ios": "cisco_ios",
        "ios_xe": "cisco_xe",
        "cisco_xe": "cisco_xe",
        "nxos": "cisco_nxos",
        "cisco_nxos": "cisco_nxos",
        "asa": "cisco_asa",
        "cisco_asa": "cisco_asa",
    }
    return aliases.get(normalized, normalized)

def get_device_from_db(host):
    """Load login details for a host from the t01_devices table."""
    db_file = get_db_file()
    if not db_file or not os.path.exists(db_file):
        print(f"\n[ERROR] Database file not found from {JSON_FILE}")
        print("        Start the PyQt app first so it can create/update the DB and write database_paths.json.\n")
        return None

    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT host, method, portnumber, username, password, os
            FROM t01_devices
            WHERE host = ?
            """,
            (host,),
        ).fetchone()
        conn.close()
    except sqlite3.Error as e:
        print(f"\n[ERROR] Could not read t01_devices table: {e}\n")
        return None

    if row is None:
        print(f"\n[ERROR] Device '{host}' was not found in t01_devices table.")
        print("        Add it to device_network.db or use:")
        print("        login <host> <method> <port> <user> <pass>\n")
        return None

    method = (row["method"] or "ssh").strip().lower()
    port = row["portnumber"] or (23 if method == "telnet" else 22)
    return {
        "host": row["host"],
        "method": method,
        "port": port,
        "username": row["username"] or "",
        "password": decrypt_device_password(row["password"]),
        "device_type": normalize_device_type(row["os"]),
    }

def handle_login(args):
    """Handle login commands using direct arguments or t01_devices table rows."""
    if len(args) == 1:
        device = get_device_from_db(args[0])
        if device is None:
            return
        start_config_mode = True
        db_path = get_db_file()
    elif len(args) == 2 and args[0].lower() == "db":
        device = get_device_from_db(args[1])
        if device is None:
            return
        start_config_mode = True
        db_path = get_db_file()
    elif len(args) >= 5:
        device = {
            "host": args[0],
            "method": args[1],
            "port": args[2],
            "username": args[3],
            "password": args[4],
            "device_type": "cisco_ios",
        }
        start_config_mode = False
        db_path = None
    else:
        print("\n[ERROR] Invalid login command format")
        print("    Usage: login <host>                         # load from t01_devices table")
        print("    Usage: login db <host>                      # load from t01_devices table")
        print("    Usage: login <host> <method> <port> <user> <pass>")
        print("    Example: login 192.168.1.1")
        print("    Example: login 192.168.1.1 ssh 22 admin cisco123\n")
        return

    # Import lazily so database bootstrap can run without Netmiko installed.
    from infrastructure.network.device_connector import login_device

    login_device(
        device["host"],
        device["method"],
        device["port"],
        device["username"],
        device["password"],
        device_type=device["device_type"],
        start_config_mode=start_config_mode,
        db_path=db_path,
    )

def get_input_with_history(prompt):
    """Get user input with history support if readline is available."""
    if HAS_READLINE:
        try:
            return input(prompt).strip()
        except EOFError:
            return "exit"
    else:
        return input(prompt).strip()

def main():
    """Main CLI loop."""
    print("\n" + "="*60)
    print(" NETWORK DATABASE MANAGER")
    print("="*60)
    print("\n[Commands]:")
    print("  - login <host>    - Login using device_network.db t01_devices table")
    print("  - login db <host> - Login using device_network.db t01_devices table")
    print("  - login <h> <m> <p> <u> <pass> - Login to device (h=host, m=method, p=port, u=user)")
    print("  - info paths      - Show all system paths")
    print("  - info json       - Show JSON file content")
    print("  - exit            - Exit application")
    if HAS_READLINE:
        print("\n[Tip]: Use up/down arrow keys for command history")
    else:
        print("\n[!] Note: Command history (up/down arrows) not available.")
        print("    To enable: pip install pyreadline (on Windows)")
    print("\n" + "="*60 + "\n")
    while True:
        try:
            cmd = get_input_with_history(">> ")
            if HAS_READLINE:
                readline.add_history(cmd)  # Add to history for arrow keys
            
            # Parse command and arguments
            parts = cmd.split()
            if not parts:
                continue
            
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if command == "login":
                handle_login(args)
            elif command == "info" and len(parts) > 1:
                subcommand = parts[1].lower()
                if subcommand == "paths":
                    show_all_paths()
                elif subcommand == "json":
                    show_json_content()
                else:
                    print(f"[ERROR] Unknown info subcommand: {subcommand}")
            elif command == "exit":
                print("[*] Exiting...")
                break
            else:
                print("[ERROR] Unknown command. Type 'help' or see menu above.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")

def print_help():
    """In hướng dẫn sử dụng CLI network-code."""
    print("CAMS network-code CLI")
    print()
    print("Database creation is handled by the PyQt app.")
    print(f"This CLI reads DB paths from: {JSON_FILE}")
    print()
    print("Run without arguments for interactive commands:")
    print("  login <host>")
    print("  login db <host>")
    print("  login <host> <method> <port> <user> <pass>")
    print("  info paths")
    print("  info json")
    print("  exit")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] in ("-h", "--help"):
            print_help()
            sys.exit(0)
        print("[ERROR] Non-interactive DB creation was removed. Start without arguments and use the interactive CLI.")
        sys.exit(1)
    main()
