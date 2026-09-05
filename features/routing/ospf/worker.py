import os
from infrastructure.database import sqlcipher as sqlite3


PENDING_STATES = ("pending_apply", "pending_delete", None)


def is_pending(value):
    """Kiểm tra trạng thái DB có đang chờ xử lý hay không."""
    return value in PENDING_STATES


def is_remove(value):
    """Kiểm tra trạng thái DB có yêu cầu xóa cấu hình hay không."""
    return value == "pending_delete"


def is_enable(value):
    """Kiểm tra giá trị bật cấu hình theo kiểu boolean-like."""
    return value in (1, "1", True)


def is_disable(value):
    """Kiểm tra giá trị tắt cấu hình theo kiểu boolean-like."""
    return value in (0, "0", False)


def has_action_bit(value, index):
    """Treat legacy rows as fully selected and modern four-bit masks precisely."""
    mask = str(value or "")
    return len(mask) != 4 or (0 <= index < 4 and mask[index] == "1")


def _table_columns(cursor, table):
    return {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}


def _select_all_with_interface_alias(cursor, table):
    columns = _table_columns(cursor, table)
    if "interface_name" in columns:
        return "*"
    if "t02_interface_name" in columns:
        return "*, t02_interface_name AS interface_name"
    return "*"


class OspfApi:
    """Apply OSPF configuration from device_network.db to an active Netmiko session."""

    def __init__(self, db_path, host, connection):
        """Lưu DB path, host và session Netmiko đang mở."""
        self.db_path = db_path
        self.host = host
        self.connection = connection

    def _connect_db(self):
        """Mở kết nối SQLite để đọc/ghi trạng thái OSPF."""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def list_processes(self):
        """Liệt kê các OSPF process của host cùng số lượng cấu hình con."""
        with self._connect_db() as conn:
            return conn.execute(
                """
                SELECT p.ospf_id, p.process_id, p.router_id, p.reference_bandwidth,
                       p.passive_default, p.default_originate, p.default_originate_always,
                       p.sync_status,
                       COUNT(DISTINCT n.id) AS network_count,
                       COUNT(DISTINCT a.id) AS area_count,
                       COUNT(DISTINCT pi.id) AS passive_count
                FROM t04_ospf_processes p
                LEFT JOIN t04_ospf_networks n ON n.ospf_id = p.ospf_id
                LEFT JOIN t04_ospf_areas a ON a.ospf_id = p.ospf_id
                LEFT JOIN t04_ospf_passive_interfaces pi ON pi.ospf_id = p.ospf_id
                WHERE p.host = ?
                GROUP BY p.ospf_id
                ORDER BY p.process_id
                """,
                (self.host,),
            ).fetchall()

    def _pending_processes(self, process_id=None):
        """Đọc các OSPF process và row con đang pending trong DB."""
        with self._connect_db() as conn:
            cursor = conn.cursor()
            params = [self.host]
            filter_sql = ""
            if process_id is not None:
                filter_sql = " AND p.process_id = ?"
                params.append(process_id)

            processes = cursor.execute(
                f"""
                SELECT p.*
                FROM t04_ospf_processes p
                WHERE p.host = ?
                  {filter_sql}
                  AND (
                    p.sync_status IN ('pending_apply', 'pending_delete') OR p.sync_status IS NULL
                    OR EXISTS (
                        SELECT 1 FROM t04_ospf_networks n
                        WHERE n.ospf_id = p.ospf_id
                          AND (n.sync_status IN ('pending_apply', 'pending_delete') OR n.sync_status IS NULL)
                    )
                    OR EXISTS (
                        SELECT 1 FROM t04_ospf_areas a
                        WHERE a.ospf_id = p.ospf_id
                          AND (a.sync_status IN ('pending_apply', 'pending_delete') OR a.sync_status IS NULL)
                    )
                    OR EXISTS (
                        SELECT 1 FROM t04_ospf_area_ranges ar
                        JOIN t04_ospf_areas a ON a.id = ar.area_db_id
                        WHERE a.ospf_id = p.ospf_id
                          AND (ar.sync_status IN ('pending_apply', 'pending_delete') OR ar.sync_status IS NULL)
                    )
                    OR EXISTS (
                        SELECT 1 FROM t04_ospf_distance d
                        WHERE d.ospf_id = p.ospf_id
                          AND (d.sync_status IN ('pending_apply', 'pending_delete') OR d.sync_status IS NULL)
                    )
                    OR EXISTS (
                        SELECT 1 FROM t04_ospf_tuning t
                        WHERE t.ospf_id = p.ospf_id
                          AND (t.sync_status IN ('pending_apply', 'pending_delete') OR t.sync_status IS NULL)
                    )
                    OR EXISTS (
                        SELECT 1 FROM t04_ospf_redistribute r
                        WHERE r.ospf_id = p.ospf_id
                          AND (r.sync_status IN ('pending_apply', 'pending_delete') OR r.sync_status IS NULL)
                    )
                    OR EXISTS (
                        SELECT 1 FROM t04_ospf_passive_interfaces pi
                        WHERE pi.ospf_id = p.ospf_id
                          AND (pi.sync_status IN ('pending_apply', 'pending_delete') OR pi.sync_status IS NULL)
                    )
                    OR EXISTS (
                        SELECT 1 FROM t04_router_iface_ospf i
                        WHERE i.ospf_id = p.ospf_id
                          AND (i.sync_status IN ('pending_apply', 'pending_delete') OR i.sync_status IS NULL)
                    )
                  )
                ORDER BY p.process_id
                """,
                tuple(params),
            ).fetchall()

            items = []
            for process in processes:
                ospf_id = process["ospf_id"]
                item = {
                    "process": process,
                    "networks": self._fetch_child(cursor, "t04_ospf_networks", "ospf_id", ospf_id),
                    "areas": self._fetch_child(cursor, "t04_ospf_areas", "ospf_id", ospf_id),
                    "distance": self._fetch_child(cursor, "t04_ospf_distance", "ospf_id", ospf_id),
                    "tuning": self._fetch_child(cursor, "t04_ospf_tuning", "ospf_id", ospf_id),
                    "redistribute": self._fetch_child(cursor, "t04_ospf_redistribute", "ospf_id", ospf_id),
                    "passive_interfaces": self._fetch_child(cursor, "t04_ospf_passive_interfaces", "ospf_id", ospf_id),
                    "interfaces": self._fetch_child(cursor, "t04_router_iface_ospf", "ospf_id", ospf_id),
                    "area_ranges": cursor.execute(
                        """
                        SELECT ar.*, a.area_id
                        FROM t04_ospf_area_ranges ar
                        JOIN t04_ospf_areas a ON a.id = ar.area_db_id
                        WHERE a.ospf_id = ? AND (ar.sync_status IN ('pending_apply', 'pending_delete') OR ar.sync_status IS NULL)
                        ORDER BY ar.id
                        """,
                        (ospf_id,),
                    ).fetchall(),
                }
                items.append(item)

        return items

    def _fetch_child(self, cursor, table, key_column, key_value):
        """Đọc các row con pending của một bảng OSPF."""
        if table == "t04_router_iface_ospf":
            return [
                self._normalize_row(dict(row))
                for row in cursor.execute(
                    """
                    SELECT r.*, i.interface_name
                    FROM t04_router_iface_ospf AS r
                    JOIN t02_interface_name AS i ON i.iface_id = r.iface_id
                    WHERE r.ospf_id = ? AND (r.sync_status IN ('pending_apply', 'pending_delete') OR r.sync_status IS NULL)
                    ORDER BY r.id
                    """,
                    (key_value,),
                ).fetchall()
            ]
        select_columns = _select_all_with_interface_alias(cursor, table)
        rows = cursor.execute(
            f"""
            SELECT {select_columns}
            FROM {table}
            WHERE {key_column} = ? AND (sync_status IN ('pending_apply', 'pending_delete') OR sync_status IS NULL)
            ORDER BY id
            """,
            (key_value,),
        ).fetchall()
        return [self._normalize_row(dict(row)) for row in rows]

    def _normalize_row(self, row):
        """Chuẩn hóa tên cột interface legacy sang interface_name."""
        if "interface_name" not in row and "t02_interface_name" in row:
            row["interface_name"] = row["t02_interface_name"]
        return row

    def build_pending_commands(self, process_id=None):
        """Dựng danh sách lệnh CLI OSPF và tracking DB cần cập nhật."""
        commands = []
        tracking = []

        for item in self._pending_processes(process_id):
            process = item["process"]
            process_id_value = process["process_id"]

            if is_remove(process["sync_status"]):
                commands.append(f"no router ospf {process_id_value}")
                tracking.append({**item, "action": "delete_process"})
                continue

            router_commands = self._build_router_commands(item)
            interface_commands = self._build_interface_commands(process_id_value, item["interfaces"])
            if router_commands:
                commands.extend(router_commands)
            if interface_commands:
                commands.extend(interface_commands)
            tracking.append({**item, "action": "upsert"})

        return commands, tracking

    def _build_router_commands(self, item):
        """Dựng các lệnh trong router ospf cho một process."""
        process = item["process"]
        commands = [f"router ospf {process['process_id']}"]
        has_body = False

        if is_pending(process["sync_status"]):
            action_cfg = process["action_Cfg"] if "action_Cfg" in process.keys() else "1111"
            if has_action_bit(action_cfg, 0) and process["router_id"]:
                commands.append(f"router-id {process['router_id']}")
                has_body = True
            if has_action_bit(action_cfg, 1) and process["reference_bandwidth"]:
                commands.append(f"auto-cost reference-bandwidth {process['reference_bandwidth']}")
                has_body = True
            if has_action_bit(action_cfg, 2) and is_enable(process["passive_default"]):
                commands.append("passive-interface default")
                has_body = True
            elif has_action_bit(action_cfg, 2) and (is_disable(process["passive_default"]) or is_remove(process["passive_default"])):
                commands.append("no passive-interface default")
                has_body = True
            if has_action_bit(action_cfg, 3) and (is_enable(process["default_originate"]) or is_enable(process["default_originate_always"])):
                suffix = " always" if is_enable(process["default_originate_always"]) else ""
                commands.append(f"default-information originate{suffix}")
                has_body = True
            elif has_action_bit(action_cfg, 3) and (
                is_disable(process["default_originate"])
                or is_disable(process["default_originate_always"])
                or is_remove(process["default_originate"])
                or is_remove(process["default_originate_always"])
            ):
                commands.append("no default-information originate")
                has_body = True

        for network in item["networks"]:
            prefix = "no " if is_remove(network["sync_status"]) else ""
            commands.append(
                f"{prefix}network {network['network']} {network['wildcard']} area {network['area']}"
            )
            has_body = True

        for area in item["areas"]:
            if is_remove(area["sync_status"]):
                commands.append(f"no area {area['area_id']}")
                has_body = True
                continue
            if area["area_type"] and area["area_type"] != "normal":
                extra = " no-summary" if is_enable(area["no_summary"]) else ""
                commands.append(f"area {area['area_id']} {area['area_type']}{extra}")
                has_body = True
            if area["authentication"] == "message-digest":
                commands.append(f"area {area['area_id']} authentication message-digest")
                has_body = True
            elif area["authentication"] == "remove":
                commands.append(f"no area {area['area_id']} authentication")
                has_body = True

        for area_range in item["area_ranges"]:
            prefix = "no " if is_remove(area_range["sync_status"]) else ""
            suffix = ""
            if not prefix:
                if area_range["advertise"] == 0:
                    suffix += " not-advertise"
                if area_range["cost"]:
                    suffix += f" cost {area_range['cost']}"
            commands.append(
                f"{prefix}area {area_range['area_id']} range {area_range['ip']} {area_range['mask']}{suffix}"
            )
            has_body = True

        for distance in item["distance"]:
            if is_remove(distance["sync_status"]):
                commands.append("no distance ospf")
            else:
                parts = ["distance ospf"]
                if distance["external"]:
                    parts.extend(["external", str(distance["external"])])
                if distance["intra_area"]:
                    parts.extend(["intra-area", str(distance["intra_area"])])
                if distance["inter_area"]:
                    parts.extend(["inter-area", str(distance["inter_area"])])
                commands.append(" ".join(parts))
            has_body = True

        for tuning in item["tuning"]:
            if is_remove(tuning["sync_status"]):
                for command in ("no maximum-paths", "no max-lsa", "no timers throttle spf", "no timers throttle lsa all"):
                    commands.append(command)
                has_body = True
                continue
            if tuning["maximum_paths"]:
                commands.append(f"maximum-paths {tuning['maximum_paths']}")
                has_body = True
            if tuning["max_lsa"]:
                commands.append(f"max-lsa {tuning['max_lsa']}")
                has_body = True
            if tuning["spf_delay"] is not None and tuning["spf_min_delay"] is not None and tuning["spf_max_delay"] is not None:
                commands.append(
                    f"timers throttle spf {tuning['spf_delay']} {tuning['spf_min_delay']} {tuning['spf_max_delay']}"
                )
                has_body = True
            if tuning["lsa_delay"] is not None and tuning["lsa_min_delay"] is not None and tuning["lsa_max_delay"] is not None:
                commands.append(
                    f"timers throttle lsa all {tuning['lsa_delay']} {tuning['lsa_min_delay']} {tuning['lsa_max_delay']}"
                )
                has_body = True

        for redistribute in item["redistribute"]:
            parts = ["redistribute", redistribute["protocol"]]
            if redistribute["protocol"] in ("eigrp", "bgp") and redistribute["process_id"]:
                parts.append(str(redistribute["process_id"]))
            if is_remove(redistribute["sync_status"]):
                commands.append("no " + " ".join(parts))
                has_body = True
                continue
            if redistribute["metric"]:
                parts.extend(["metric", str(redistribute["metric"])])
            if redistribute["metric_type"]:
                parts.extend(["metric-type", str(redistribute["metric_type"])])
            if is_enable(redistribute["subnets"]):
                parts.append("subnets")
            if redistribute["route_map"]:
                parts.extend(["route-map", redistribute["route_map"]])
            commands.append(" ".join(parts))
            has_body = True

        for passive in item["passive_interfaces"]:
            if is_remove(passive["sync_status"]) or is_disable(passive["passive"]) or is_remove(passive["passive"]):
                commands.append(f"no passive-interface {passive['interface_name']}")
            else:
                commands.append(f"passive-interface {passive['interface_name']}")
            has_body = True

        if not has_body:
            return []
        commands.append("exit")
        return commands

    def _build_interface_commands(self, process_id, interfaces):
        """Dựng các lệnh interface-level OSPF."""
        commands = []
        for interface in interfaces:
            commands.append(f"interface {interface['interface_name']}")
            if is_remove(interface["sync_status"]):
                commands.append(f"no ip ospf {process_id} area {interface['area']}")
            else:
                commands.append(f"ip ospf {process_id} area {interface['area']}")
                if interface["cost"]:
                    commands.append(f"ip ospf cost {interface['cost']}")
                if interface["priority"] is not None:
                    commands.append(f"ip ospf priority {interface['priority']}")
                if interface["hello_interval"]:
                    commands.append(f"ip ospf hello-interval {interface['hello_interval']}")
                if interface["dead_interval"]:
                    commands.append(f"ip ospf dead-interval {interface['dead_interval']}")
                if is_enable(interface["mtu_ignore"]):
                    commands.append("ip ospf mtu-ignore")
                elif is_disable(interface["mtu_ignore"]) or is_remove(interface["mtu_ignore"]):
                    commands.append("no ip ospf mtu-ignore")
                if is_enable(interface["bfd"]):
                    commands.append("ip ospf bfd")
                elif is_disable(interface["bfd"]) or is_remove(interface["bfd"]):
                    commands.append("no ip ospf bfd")
                if interface["network_type"]:
                    commands.append(f"ip ospf network {interface['network_type']}")
                if interface["auth_type"] == "message-digest":
                    commands.append("ip ospf authentication message-digest")
                    if interface["auth_key"]:
                        commands.append(
                            f"ip ospf message-digest-key 1 md5 {interface['auth_key']}"
                        )
                elif interface["auth_type"] == "plain":
                    commands.append("ip ospf authentication")
                    if interface["auth_key"]:
                        commands.append(
                            f"ip ospf authentication-key {interface['auth_key']}"
                        )
                elif interface["auth_type"] == "remove":
                    commands.append("no ip ospf authentication")
            commands.append("exit")
        return commands

    def apply_pending(self, process_id=None):
        """Push các lệnh OSPF pending qua session hiện tại và mark DB."""
        commands, tracking = self.build_pending_commands(process_id)
        if not commands:
            return "No pending OSPF changes."

        result = self.connection.send_config_set(
            commands,
            read_timeout=60,
            cmd_verify=False,
        )

        self._mark_applied(tracking)
        return result

    def _mark_applied(self, tracking):
        """Cập nhật DB sau khi push OSPF thành công."""
        with self._connect_db() as conn:
            cursor = conn.cursor()
            for item in tracking:
                process = item["process"]
                if item["action"] == "delete_process":
                    cursor.execute("DELETE FROM t04_ospf_processes WHERE ospf_id = ?", (process["ospf_id"],))
                    continue

                if is_pending(process["sync_status"]):
                    cursor.execute(
                        "UPDATE t04_ospf_processes "
                        "SET sync_status = 'synchronized', action_Cfg = '0000' "
                        "WHERE ospf_id = ?",
                        (process["ospf_id"],),
                    )

                self._mark_child_rows(cursor, "t04_ospf_networks", item["networks"])
                self._mark_child_rows(cursor, "t04_ospf_areas", item["areas"])
                self._mark_child_rows(cursor, "t04_ospf_area_ranges", item["area_ranges"])
                self._mark_child_rows(cursor, "t04_ospf_distance", item["distance"])
                self._mark_child_rows(cursor, "t04_ospf_tuning", item["tuning"])
                self._mark_child_rows(cursor, "t04_ospf_redistribute", item["redistribute"])
                self._mark_child_rows(cursor, "t04_ospf_passive_interfaces", item["passive_interfaces"])
                self._mark_child_rows(cursor, "t04_router_iface_ospf", item["interfaces"])
            conn.commit()

    def _mark_child_rows(self, cursor, table, rows):
        """Mark hoặc xóa các row con OSPF sau khi push."""
        for row in rows:
            if is_remove(row["sync_status"]):
                cursor.execute(f"DELETE FROM {table} WHERE id = ?", (row["id"],))
            else:
                cursor.execute(f"UPDATE {table} SET sync_status = 'synchronized' WHERE id = ?", (row["id"],))
