from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import select
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from features.syslog.native import NativeSyslogCollector
from features.syslog.qt.manager import SyslogManager
from infrastructure.database.paths import DEVICE_NETWORK_DB, INFO_COLLECTED_DB


APP_DIR = Path(__file__).resolve().parents[2]
COLLECTOR = APP_DIR / "bin" / "networktools-syslog-collector"


class NativeCollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _event(self, process: subprocess.Popen[str], timeout: float = 3.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([process.stdout], [], [], 0.1)
            if not ready:
                continue
            line = process.stdout.readline()
            if line:
                return json.loads(line)
            break
        self.fail("Native collector did not emit an event")

    @unittest.skipUnless(COLLECTOR.is_file(), "native collector is not built")
    def test_udp_and_tcp_are_persisted_and_published(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info_db = root / "info.db"
            device_db = root / "device.db"
            shutil.copy2(INFO_COLLECTED_DB, info_db)
            shutil.copy2(DEVICE_NETWORK_DB, device_db)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = int(probe.getsockname()[1])
            settings = root / "syslog.json"
            settings.write_text(json.dumps({
                "bind_ip": "127.0.0.1",
                "port": port,
                "max_message_bytes": 16384,
                "max_tcp_clients": 8,
            }), encoding="utf-8")
            process = subprocess.Popen(
                [
                    str(COLLECTOR), "--settings", str(settings),
                    "--info-db", str(info_db), "--device-db", str(device_db),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                ready = self._event(process)
                self.assertEqual(ready["type"], "ready")

                payload = b"<36>*Aug 23 04:29:20.262: %SYS-5-CONFIG_I: Native UDP"
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                    udp.sendto(payload, ("127.0.0.1", port))
                udp_event = self._event(process)
                self.assertEqual(udp_event["type"], "message")
                self.assertEqual(udp_event["row"]["protocol"], "udp")
                self.assertEqual(udp_event["row"]["cisco_facility"], "SYS")
                self.assertEqual(udp_event["row"]["severity"], 5)

                with socket.create_connection(("127.0.0.1", port), timeout=2) as tcp:
                    tcp.sendall(b"<37>Aug 23 04:29:21.000: %SYS-5-CONFIG_I: Native TCP\n")
                tcp_event = self._event(process)
                self.assertEqual(tcp_event["row"]["protocol"], "tcp")

                with closing(sqlite3.connect(info_db)) as connection:
                    rows = connection.execute(
                        "SELECT protocol, message FROM t12_syslog_messages "
                        "WHERE message IN ('Native UDP', 'Native TCP') ORDER BY id"
                    ).fetchall()
                self.assertEqual(rows, [("udp", "Native UDP"), ("tcp", "Native TCP")])
            finally:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()

    @unittest.skipUnless(COLLECTOR.is_file(), "native collector is not built")
    def test_qprocess_bridge_publishes_inserted_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info_db = root / "info.db"
            device_db = root / "device.db"
            shutil.copy2(INFO_COLLECTED_DB, info_db)
            shutil.copy2(DEVICE_NETWORK_DB, device_db)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = int(probe.getsockname()[1])
            settings = root / "syslog.json"
            settings.write_text(json.dumps({
                "bind_ip": "127.0.0.1", "port": port,
                "max_message_bytes": 16384, "max_tcp_clients": 8,
            }), encoding="utf-8")

            bridge = NativeSyslogCollector()
            rows: list[dict] = []
            bridge.messageInserted.connect(lambda row: rows.append(dict(row)))
            try:
                bridge.start(settings, info_db, device_db)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                    udp.sendto(
                        b"<36>Aug 23 04:29:22.000: %SYS-5-CONFIG_I: Qt bridge",
                        ("127.0.0.1", port),
                    )
                deadline = time.monotonic() + 3
                while not rows and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["message"], "Qt bridge")
            finally:
                bridge.stop()

    @unittest.skipUnless(COLLECTOR.is_file(), "native collector is not built")
    def test_manager_emits_rows_for_qml_from_native_collector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info_db = root / "info.db"
            device_db = root / "device.db"
            shutil.copy2(INFO_COLLECTED_DB, info_db)
            shutil.copy2(DEVICE_NETWORK_DB, device_db)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = int(probe.getsockname()[1])
            settings = root / "syslog.json"
            settings.write_text(json.dumps({
                "enabled_on_startup": False,
                "protocol": "both",
                "bind_ip": "127.0.0.1",
                "advertised_ip": "127.0.0.1",
                "port": port,
                "retention_days": 30,
                "max_message_bytes": 16384,
                "max_tcp_clients": 8,
            }), encoding="utf-8")

            with patch.dict("os.environ", {"NETWORKTOOLS_SYSLOG_SETTINGS": str(settings)}):
                manager = SyslogManager()
            rows: list[dict] = []
            manager.messagesInserted.connect(
                lambda batch: rows.extend(dict(row) for row in batch)
            )
            try:
                manager.set_database_paths(info_db, device_db)
                result = manager.startServer()
                self.assertTrue(result["ok"], result)
                self.assertEqual(manager.listenerState, "listening")
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                    udp.sendto(
                        b"<36>Aug 23 04:29:23.000: %SYS-5-CONFIG_I: Manager signal",
                        ("127.0.0.1", port),
                    )
                deadline = time.monotonic() + 3
                while not rows and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertEqual(rows[0]["message"], "Manager signal")
                self.assertEqual(manager.receivedCount, 1)
            finally:
                manager.shutdown()


if __name__ == "__main__":
    unittest.main()
