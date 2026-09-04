from __future__ import annotations

import importlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
worker_routing = importlib.import_module("features.routing.worker")
worker_dhcp = importlib.import_module("features.dhcp.worker")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


routing_main = importlib.import_module("features.routing.dispatcher")
dhcp_main = importlib.import_module("features.dhcp.dispatcher")


def _task(host: str) -> dict:
    return {
        "module": "test",
        "type": "test",
        "target": {"ip": host},
        "config": [],
    }


class DevModeWorkerTests(unittest.TestCase):
    workers = (
        ("routing", worker_routing.run_routing_config),
        ("dhcp", worker_dhcp.run_dhcp_config),
    )

    def _database(self, root: Path, include_dev: bool = True) -> Path:
        db_path = root / "device_network.db"
        with closing(sqlite3.connect(db_path)) as connection:
            dev_column = ", dev INTEGER DEFAULT 0" if include_dev else ""
            connection.execute(
                f"CREATE TABLE t01_devices (host TEXT PRIMARY KEY{dev_column})"
            )
            connection.commit()
        return db_path

    def _set_devices(self, db_path: Path, devices: list[tuple[str, int]]) -> None:
        with closing(sqlite3.connect(db_path)) as connection:
            connection.executemany(
                "INSERT INTO t01_devices (host, dev) VALUES (?, ?)",
                devices,
            )
            connection.commit()

    def _run(self, worker, tasks, db_path: Path, output_path: Path, provider):
        worker(
            tasks,
            str(db_path),
            str(output_path),
            session_provider=provider,
        )
        return json.loads(output_path.read_text(encoding="utf-8"))

    def test_dev_host_never_requests_a_real_session(self):
        for worker_name, worker in self.workers:
            with self.subTest(worker=worker_name), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                db_path = self._database(root)
                self._set_devices(db_path, [("dev-host", 1)])

                def forbidden_provider(_host):
                    raise AssertionError("dev host attempted to open a real session")

                results = self._run(
                    worker,
                    [_task("dev-host")],
                    db_path,
                    root / f"{worker_name}.json",
                    forbidden_provider,
                )

                self.assertEqual(results[0]["target"], "dev-host")
                self.assertEqual(results[0]["status"], "success")
                self.assertIn("no device login or push", results[0]["message"])

    def test_mixed_targets_only_request_a_session_for_real_hosts(self):
        for worker_name, worker in self.workers:
            with self.subTest(worker=worker_name), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                db_path = self._database(root)
                self._set_devices(db_path, [("dev-host", 1), ("real-host", 0)])
                requested_hosts = []

                def provider(host):
                    requested_hosts.append(host)
                    return None

                results = self._run(
                    worker,
                    [_task("dev-host"), _task("real-host")],
                    db_path,
                    root / f"{worker_name}.json",
                    provider,
                )
                results_by_host = {item["target"]: item for item in results}

                self.assertEqual(requested_hosts, ["real-host"])
                self.assertEqual(results_by_host["dev-host"]["status"], "success")
                self.assertEqual(results_by_host["real-host"]["status"], "failed")

    def test_lookup_error_fails_closed_without_requesting_sessions(self):
        for worker_name, worker in self.workers:
            with self.subTest(worker=worker_name), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                db_path = self._database(root, include_dev=False)
                with closing(sqlite3.connect(db_path)) as connection:
                    connection.execute(
                        "INSERT INTO t01_devices (host) VALUES (?)",
                        ("unknown-host",),
                    )
                    connection.commit()
                requested_hosts = []

                def provider(host):
                    requested_hosts.append(host)
                    return None

                results = self._run(
                    worker,
                    [_task("unknown-host")],
                    db_path,
                    root / f"{worker_name}.json",
                    provider,
                )

                self.assertEqual(requested_hosts, [])
                self.assertEqual(results[0]["status"], "failed")
                self.assertIn("real", results[0]["message"].lower())
                self.assertIn("blocked", results[0]["message"].lower())


class DevModeDispatcherTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        db_path = root / "device_network.db"
        from scripts.build_databases import combine_sql

        schema = combine_sql(APP_DIR / "infrastructure" / "database" / "schemas" / "device_network")
        with closing(sqlite3.connect(db_path)) as connection:
            connection.executescript(schema)
            connection.execute(
                """
                INSERT INTO t01_devices
                    (host, device_name, method, portnumber, username, password, os, role, connection_status, dev)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("dev-host", "Dev Host", "SSH", 22, "user", "password", "cisco_ios", "router", "connected", 1),
            )
            connection.commit()
        return db_path

    def test_routing_dev_report_updates_and_deletes_pending_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = self._database(root)
            with closing(sqlite3.connect(db_path)) as connection:
                add_id = connection.execute(
                    """
                    INSERT INTO t04_static_routes
                        (host, network, subnet_mask, next_hop, ad, sync_status)
                    VALUES (?, ?, ?, ?, ?, 'pending_apply')
                    """,
                    ("dev-host", "10.10.0.0", "255.255.0.0", "192.0.2.1", 1),
                ).lastrowid
                delete_id = connection.execute(
                    """
                    INSERT INTO t04_static_routes
                        (host, network, subnet_mask, next_hop, ad, sync_status)
                    VALUES (?, ?, ?, ?, ?, 'pending_delete')
                    """,
                    ("dev-host", "10.20.0.0", "255.255.0.0", "192.0.2.2", 1),
                ).lastrowid
                connection.commit()

            routing_main.DB_PATH = str(db_path)
            routing_main.ROUTE_OUTPUT = str(root / "routing_output.json")
            routing_main.TMP_DIR = str(root)

            def forbidden_provider(_host):
                raise AssertionError("routing dev host attempted to open a real session")

            routing_main.routing_dispatcher(
                "dev-host",
                "static",
                session_provider=forbidden_provider,
            )

            self.assertTrue(
                (root / "routing_output_static_dev-host.json").is_file()
            )

            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT sync_status FROM t04_static_routes WHERE id = ?",
                        (add_id,),
                    ).fetchone()[0],
                    "synchronized",
                )
                self.assertIsNone(
                    connection.execute(
                        "SELECT 1 FROM t04_static_routes WHERE id = ?",
                        (delete_id,),
                    ).fetchone()
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT username, password, method, portnumber, dev FROM t01_devices WHERE host = ?",
                        ("dev-host",),
                    ).fetchone(),
                    ("user", "password", "SSH", 22, 1),
                )

    def test_dhcp_dev_report_updates_and_deletes_pending_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = self._database(root)
            with closing(sqlite3.connect(db_path)) as connection:
                add_id = connection.execute(
                    """
                    INSERT INTO t03_dhcp_pool
                        (host, pool, network, subnetmask, sync_status)
                    VALUES (?, ?, ?, ?, 'pending_apply')
                    """,
                    ("dev-host", "DEV_ADD", "10.30.0.0", "255.255.0.0"),
                ).lastrowid
                delete_id = connection.execute(
                    """
                    INSERT INTO t03_dhcp_pool
                        (host, pool, network, subnetmask, sync_status)
                    VALUES (?, ?, ?, ?, 'pending_delete')
                    """,
                    ("dev-host", "DEV_DELETE", "10.40.0.0", "255.255.0.0"),
                ).lastrowid
                connection.commit()

            dhcp_main.DB_PATH = str(db_path)
            dhcp_main.DHCP_OUTPUT = str(root / "dhcp_output.json")
            dhcp_main.TMP_DIR = str(root)
            original_builder = worker_dhcp.build_dhcp_inventory

            def forbidden_builder(_db_path, _tasks):
                raise AssertionError("DHCP dev host attempted to build a real inventory")

            worker_dhcp.build_dhcp_inventory = forbidden_builder
            try:
                dhcp_main.dhcp_dispatcher("dev-host")
            finally:
                worker_dhcp.build_dhcp_inventory = original_builder

            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT sync_status FROM t03_dhcp_pool WHERE dhcp_id = ?",
                        (add_id,),
                    ).fetchone()[0],
                    "synchronized",
                )
                self.assertIsNone(
                    connection.execute(
                        "SELECT 1 FROM t03_dhcp_pool WHERE dhcp_id = ?",
                        (delete_id,),
                    ).fetchone()
                )


if __name__ == "__main__":
    unittest.main()
