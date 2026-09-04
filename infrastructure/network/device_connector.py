"""
Device connector module for SSH/Telnet CLI access using Netmiko
"""
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException, ConnectionException
from infrastructure.network.netmiko_factory import connect_device
from infrastructure.network.ssh_algorithms import classify_ssh_error
import os
import re
import shlex
import sys


DEFAULT_NETWORK_TIMEOUT = 15
PROMPT_NOISE_RE = re.compile(r"(?:\x00|\^@)+$")
VALID_PROMPT_RE = re.compile(r"^[^\r\n]*[>#]$")


def load_default_db_path():
    """Load the canonical application database path."""
    from infrastructure.database.paths import DEVICE_NETWORK_DB

    return str(DEVICE_NETWORK_DB)

class DeviceConnector:
    """Manages connection and interactive CLI to network devices"""
    
    def __init__(
        self,
        host,
        method,
        port,
        username,
        password,
        device_type='cisco_ios',
        start_config_mode=False,
        db_path=None,
        timeout=DEFAULT_NETWORK_TIMEOUT,
    ):
        """Initialize device connector parameters"""
        self.host = host
        self.method = method.lower()
        self.port = int(port)
        self.username = username if username else ''
        self.password = password if password else ''
        self.device_type = device_type
        self.start_config_mode = start_config_mode
        self.db_path = db_path or load_default_db_path()
        self.timeout = int(timeout or DEFAULT_NETWORK_TIMEOUT)
        self.connection = None
        self.connected = False
        self.last_error = ""
        self.last_sync_error = ""
        self.last_sync_summary = {}
    
    def connect(self):
        """Establish connection to the device"""
        self.last_error = ""
        try:
            # Prepare device parameters
            device_params = {
                'device_type': self.device_type,
                'host': self.host,
                'port': self.port,
                'username': self.username,
                'password': self.password,
                'secret': self.password,
                'conn_timeout': self.timeout,
                'auth_timeout': self.timeout,
                'banner_timeout': self.timeout,
                'blocking_timeout': self.timeout,
                'session_timeout': self.timeout,
                'timeout': self.timeout,
            }
            
            # Adjust device type for telnet
            if self.method == 'telnet':
                device_params['device_type'] = f"{self.device_type}_telnet"
            
            print(f"\n[INFO] Connecting to {self.host} ({self.method.upper()})...")
            self.connection = connect_device(
                {**device_params, "method": self.method},
                self.db_path,
            )
            self.connected = True
            print(f"[SUCCESS] Successfully connected to {self.host}\n")
            if self.start_config_mode:
                self.enter_config_mode()
            return True
            
        except NetmikoTimeoutException as exc:
            detail = str(exc or "").strip()
            self.last_error = "CONNECTION_TIMEOUT"
            if detail:
                self.last_error = f"{self.last_error}: {detail}"
            print(f"\n[ERROR] Connection timeout to {self.host}: {detail}\n")
            self.disconnect()
            return False
        except NetmikoAuthenticationException:
            self.last_error = "authentication failed (invalid credentials)"
            print(f"\n[ERROR] Authentication failed for {self.host} (invalid credentials)\n")
            return False
        except ConnectionException as e:
            self.last_error = f"{classify_ssh_error(e)}: {e}"
            print(f"\n[ERROR] Connection error: {e}\n")
            return False
        except Exception as e:
            self.last_error = f"{classify_ssh_error(e)}: {e}"
            print(f"\n[ERROR] Unexpected error: {e}\n")
            return False

    def enter_config_mode(self):
        """Enter global configuration mode on the connected device."""
        if not self.connected or not self.connection:
            print("[ERROR] Not connected to device\n")
            return False

        try:
            if hasattr(self.connection, "check_enable_mode") and not self.connection.check_enable_mode():
                self.connection.enable()

            if not self.connection.check_config_mode():
                self.connection.config_mode()

            if not self.connection.check_config_mode():
                print("[ERROR] Could not enter configuration mode: prompt is not in config mode\n")
                return False

            print("[SUCCESS] Entered configuration terminal mode\n")
            return True
        except Exception as e:
            print(f"[ERROR] Could not enter configuration mode: {e}\n")
            return False
    
    def disconnect(self):
        """Close connection to device"""
        if self.connection:
            try:
                self.connection.disconnect()
                self.connected = False
                print(f"\n[SUCCESS] Disconnected from {self.host}\n")
            except Exception as e:
                print(f"[ERROR] Error disconnecting: {e}\n")
    
    def send_command(self, command):
        """Send command and return output without requiring the device to echo it."""
        if not self.connected or not self.connection:
            print("[ERROR] Not connected to device\n")
            return None
        
        try:
            # Some IOS consoles (notably virtual labs) suppress or alter command
            # echo or append NUL/"^@" noise to find_prompt().  Avoid both the
            # command-echo check and Netmiko's polluted automatic prompt pattern.
            prompt = str(self.connection.find_prompt() or "").strip()
            clean_prompt = PROMPT_NOISE_RE.sub("", prompt).rstrip()
            # find_prompt() can occasionally consume a partial command echo on
            # noisy console sessions.  Only trust values that actually look
            # like an IOS prompt; otherwise wait for any prompt-terminated line.
            if VALID_PROMPT_RE.fullmatch(clean_prompt):
                expect_string = (
                    rf"(?m)^{re.escape(clean_prompt)}"
                    r"[ \t]*(?:\x00|\^@)*[ \t\r]*$"
                )
            else:
                expect_string = r"(?m)^[^\r\n]*[>#][ \t]*(?:\x00|\^@)*[ \t\r]*$"
            output = self.connection.send_command(
                command,
                read_timeout=self.timeout,
                cmd_verify=False,
                expect_string=expect_string,
            )
            return output
        except Exception as e:
            print(f"[ERROR] Error executing command: {e}\n")
            return None

    def collect_running_config(self):
        """Collect running-config and interface output without choosing storage policy."""
        if not self.connected or not self.connection:
            return {"ok": False, "running_config": "", "interface_brief": ""}
        try:
            from infrastructure.network.running_config_collector import RunningConfigCollector

            output = RunningConfigCollector(
                self.connection,
                read_timeout=self.timeout,
            ).collect()
        except Exception as exc:
            self.last_error = str(exc)
            return {"ok": False, "running_config": "", "interface_brief": ""}
        in_config_mode = bool(
            callable(getattr(self.connection, "check_config_mode", None))
            and self.connection.check_config_mode()
        )
        brief_command = (
            "do show ip interface brief"
            if in_config_mode
            else "show ip interface brief"
        )
        brief_output = self.send_command(brief_command) or ""
        return {
            "ok": True,
            "running_config": str(output),
            "interface_brief": str(brief_output),
        }

    def collect_switch_state(self, state_keys=None):
        """Collect the bounded show-command set used by switch synchronization."""
        commands = {
            "vlan_brief": "show vlan brief",
            "interfaces_status": "show interfaces status",
            "interfaces_trunk": "show interfaces trunk",
            "etherchannel_summary": "show etherchannel summary",
            "vtp_status": "show vtp status",
        }
        requested = tuple(commands) if state_keys is None else tuple(state_keys)
        unsupported = [key for key in requested if key not in commands]
        if unsupported:
            return {
                "ok": False,
                "message": "Unsupported switch state key(s): " + ", ".join(unsupported),
                "outputs": {},
            }
        outputs = {}
        for key in requested:
            command = commands[key]
            value = self.send_command(command)
            if value is None:
                return {
                    "ok": False,
                    "message": f"Switch state collection failed while running: {command}",
                    "outputs": outputs,
                }
            if self._is_invalid_command_output(value):
                return {
                    "ok": False,
                    "message": f"Switch does not support state command: {command}",
                    "outputs": outputs,
                }
            outputs[key] = str(value)
        return {"ok": True, "outputs": outputs}

    @staticmethod
    def _is_invalid_command_output(output):
        text = str(output or "").lower()
        return "% invalid input" in text or "invalid input detected" in text

    def save_running_config(self, file_path):
        """Legacy adapter that collects, writes a text file, then synchronizes state."""
        if not file_path:
            print("[ERROR] Missing file path. Usage: output rcfg <file_path>\n")
            return False

        snapshot = self.collect_running_config()
        if not snapshot.get("ok"):
            return False
        output = snapshot["running_config"]
        brief_output = snapshot["interface_brief"]

        try:
            file_path = os.path.expanduser(file_path.strip().strip('"'))
            if os.path.isdir(file_path) or file_path.endswith(("\\", "/")):
                safe_host = self.host.replace(":", "_").replace("/", "_").replace("\\", "_")
                file_path = os.path.join(file_path, f"{safe_host}_running-config.txt")

            parent_dir = os.path.dirname(os.path.abspath(file_path))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(output)
                if not output.endswith("\n"):
                    f.write("\n")

            print(f"[SUCCESS] Running-config saved to {os.path.abspath(file_path)}\n")
            self.sync_collected_state(output, brief_output)
            return True
        except Exception as e:
            print(f"[ERROR] Could not save running-config: {e}\n")
            return False

    def sync_collected_state(self, running_config, interface_brief=""):
        """Replace DB snapshot for this host with data collected from the device."""
        self.last_sync_error = ""
        self.last_sync_summary = {}
        if not self.db_path:
            self.last_sync_error = "database path is not configured"
            print("[WARNING] Could not sync collected state: database path is not configured.\n")
            return False

        try:
            from features.devices.sync_state import sync_device_state

            self.last_sync_summary = sync_device_state(
                self.db_path,
                self.host,
                running_config or "",
                interface_brief or "",
            )
            print(
                "[SUCCESS] Synced collected state: "
                f"{self.last_sync_summary.get('interfaces', 0)} interface(s), "
                f"{self.last_sync_summary.get('static_routes', 0)} static route(s), "
                f"{self.last_sync_summary.get('default_routes', 0)} default route(s), "
                f"{self.last_sync_summary.get('ospf_processes', 0)} OSPF process(es).\n"
            )
            if self.last_sync_summary.get("conflicts"):
                print(
                    "[WARNING] Sync preserved pending module(s): "
                    + ", ".join(self.last_sync_summary["conflicts"])
                    + ".\n"
                )
            return True
        except Exception as e:
            self.last_sync_error = str(e)
            print(f"[WARNING] Could not sync collected state: {e}\n")
            return False

    def handle_local_command(self, cmd):
        """Handle local helper commands before sending input to the device."""
        lowered = cmd.lower()
        for prefix in ("ouput rcfg ", "output rcfg "):
            if lowered.startswith(prefix):
                file_path = cmd[len(prefix):].strip()
                self.save_running_config(file_path)
                return True

        if lowered in ("ouput rcfg", "output rcfg"):
            print("[ERROR] Missing file path. Usage: output rcfg <file_path>\n")
            return True

        if lowered == "ospf help":
            self.show_ospf_help()
            return True

        if lowered == "ospf list":
            self.handle_ospf_list()
            return True

        if lowered.startswith("ospf "):
            self.handle_ospf_command(cmd)
            return True

        return False

    def _ospf_api(self):
        """Tạo OSPF API helper dựa trên DB path và kết nối hiện tại."""
        if not self.db_path:
            print("[ERROR] OSPF DB commands are only available when logged in from database.\n")
            return None

        try:
            from routing.ospf_api import OspfApi
            return OspfApi(self.db_path, self.host, self.connection)
        except Exception as e:
            print(f"[ERROR] Could not load OSPF API: {e}\n")
            return None

    def show_ospf_help(self):
        """In các lệnh OSPF hỗ trợ trong interactive CLI."""
        print("\nOSPF commands:")
        print("  ospf list")
        print("  ospf pending [process_id]")
        print("  ospf apply [process_id]\n")
        print("OSPF data must be created/edited by the Qt app in device_network.db.")

    def handle_ospf_list(self):
        """Đọc DB và in danh sách OSPF process của thiết bị hiện tại."""
        api = self._ospf_api()
        if not api:
            return

        try:
            rows = api.list_processes()
        except Exception as e:
            print(f"[ERROR] Could not list OSPF data: {e}\n")
            return

        if not rows:
            print("[INFO] No OSPF process found for this host.\n")
            return

        print("\nOSPF processes:")
        for row in rows:
            print(
                f"  process={row['process_id']} router_id={row['router_id'] or '-'} "
                f"ref_bw={row['reference_bandwidth'] or '-'} networks={row['network_count']} "
                f"areas={row['area_count']} passive={row['passive_count']} "
                f"sync_status={row['sync_status']}"
            )
        print()

    def handle_ospf_command(self, cmd):
        """Xử lý các lệnh OSPF pending/apply/list từ CLI nội bộ."""
        api = self._ospf_api()
        if not api:
            return

        try:
            parts = shlex.split(cmd)
            if len(parts) < 2:
                self.show_ospf_help()
                return

            action = parts[1].lower()

            if action == "list" and len(parts) == 2:
                self.handle_ospf_list()
                return

            if action == "pending" and len(parts) in (2, 3):
                process_id = int(parts[2]) if len(parts) == 3 else None
                commands, _ = api.build_pending_commands(process_id)
                if not commands:
                    print("No pending OSPF changes.\n")
                    return
                print("\nPending OSPF commands:")
                for command in commands:
                    print(f"  {command}")
                print()
                return

            if action == "apply" and len(parts) in (2, 3):
                process_id = int(parts[2]) if len(parts) == 3 else None
                print("[INFO] Applying pending OSPF changes...")
                output = api.apply_pending(process_id)
                print(f"\n{output}\n")
                return

            self.show_ospf_help()
        except Exception as e:
            print(f"[ERROR] OSPF command failed: {e}\n")
    
    def interactive_cli(self):
        """Interactive CLI mode"""
        if not self.connected:
            print("[ERROR] Not connected to device\n")
            return
        
        print("="*60)
        print(f" Connected to: {self.host}")
        print(f" Type 'exit' to disconnect or 'quit' for help")
        print("="*60 + "\n")
        
        try:
            while self.connected:
                try:
                    # Custom prompt with host
                    cmd = input(f">>({self.host})> ").strip()
                    
                    if not cmd:
                        continue
                    
                    if cmd.lower() == 'exit':
                        print("[INFO] Exiting interactive CLI...")
                        break
                    
                    if cmd.lower() == 'quit':
                        print("\nAvailable commands:")
                        print("  - Any CLI command for the device")
                        print("  - ouput rcfg <file_path> to save 'do show running-config'")
                        print("  - ospf help for DB-backed OSPF apply")
                        print("  - 'exit' to disconnect and return to main menu\n")
                        continue

                    if self.handle_local_command(cmd):
                        continue
                    
                    # Send command to device
                    print(f"\n[INFO] Executing: {cmd}")
                    output = self.send_command(cmd)
                    
                    if output is not None:
                        print(f"\n{output}\n")
                    
                except KeyboardInterrupt:
                    print("\n[INFO] Interrupted by user")
                    break
                except EOFError:
                    print("\n[*] Connection closed")
                    break
        
        except Exception as e:
            print(f"\n[ERROR] CLI Error: {e}\n")
        
        finally:
            self.disconnect()


def login_device(host, method, port, username, password, device_type='cisco_ios', start_config_mode=False, db_path=None):
    """Đăng nhập thiết bị và mở interactive CLI dựa trên tham số đã nhận."""
    connector = DeviceConnector(
        host,
        method,
        port,
        username,
        password,
        device_type,
        start_config_mode=start_config_mode,
        db_path=db_path,
    )
    
    if connector.connect():
        connector.interactive_cli()
        return True
    
    return False


# Example usage
if __name__ == "__main__":
    # Test parameters
    test_host = "192.168.1.1"
    test_method = "ssh"
    test_port = "22"
    test_user = "admin"
    test_pass = "cisco123"
    
    login_device(test_host, test_method, test_port, test_user, test_pass)
