from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from pathlib import Path
from unittest.mock import Mock, patch

import paramiko

from features.devices.ssh_algorithm_repository import (
    clear_ssh_algorithm_override,
    get_ssh_algorithm_override,
    save_ssh_algorithm_override,
)
from features.devices.login_service import DeviceLoginService
from features.devices.repository import DeviceRepository
from infrastructure.network.netmiko_factory import connect_device
from infrastructure.network.nornir_netmiko_plugin import CAMSNetmiko
from infrastructure.network.nornir_netmiko_plugin import register_networktools_netmiko
from infrastructure.network.nornir_netmiko_tasks import netmiko_send_config
from infrastructure.network.ssh_algorithms import (
    SshAlgorithmOverride,
    UnsupportedSshAlgorithm,
    make_transport_factory,
    merge_preferred,
    normalize_algorithm_list,
)
from scripts.build_databases import _repair_missing_objects, combine_sql


SCHEMA_DIR = (
    Path(__file__).resolve().parents[1]
    / "infrastructure"
    / "database"
    / "schemas"
    / "device_network"
)


class SshAlgorithmOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device.db"
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.executescript(combine_sql(SCHEMA_DIR))
            conn.execute("INSERT INTO t01_devices(host) VALUES ('r1')")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_schema_repository_normalization_and_cascade(self) -> None:
        result = save_ssh_algorithm_override(
            self.db_path,
            "r1",
            {
                "kex_algorithms": " diffie-hellman-group14-sha1, ,diffie-hellman-group14-sha1 ",
                "host_key_algorithms": "",
                "note": "legacy",
            },
        )
        self.assertTrue(result["ok"], result)
        override = get_ssh_algorithm_override(self.db_path, "r1")
        self.assertEqual(
            override.kex, ("diffie-hellman-group14-sha1",)
        )
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("UPDATE t01_devices SET host = 'r1-renamed' WHERE host = 'r1'")
            self.assertEqual(
                conn.execute("SELECT host FROM t01_ssh_algo").fetchone()[0],
                "r1-renamed",
            )
            conn.execute("DELETE FROM t01_devices WHERE host = 'r1-renamed'")
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t01_ssh_algo").fetchone()[0],
                0,
            )

    def test_login_payload_carries_per_device_terminal_algorithms(self) -> None:
        result = save_ssh_algorithm_override(
            self.db_path,
            "r1",
            {
                "kex_algorithms": "diffie-hellman-group14-sha1",
                "host_key_algorithms": "ssh-rsa",
            },
        )
        self.assertTrue(result["ok"], result)

        device = DeviceLoginService(DeviceRepository(self.db_path)).load("r1")

        self.assertIsNotNone(device)
        self.assertEqual(
            device["ssh_algorithms"]["kex"],
            ["diffie-hellman-group14-sha1"],
        )
        self.assertEqual(device["ssh_algorithms"]["key_types"], ["ssh-rsa"])

    def test_runtime_repair_restores_missing_table_without_data_loss(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("DROP TABLE t01_ssh_algo")
            conn.execute("UPDATE t01_devices SET device_name = 'Router 1' WHERE host = 'r1'")
        repaired = _repair_missing_objects(SCHEMA_DIR, self.db_path)
        self.assertIn("t01_ssh_algo", repaired)
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            self.assertEqual(
                conn.execute("SELECT device_name FROM t01_devices WHERE host = 'r1'").fetchone()[0],
                "Router 1",
            )

    def test_null_or_cleared_row_uses_default_path(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("INSERT INTO t01_ssh_algo(host) VALUES ('r1')")
        self.assertIsNone(get_ssh_algorithm_override(self.db_path, "r1"))
        self.assertTrue(clear_ssh_algorithm_override(self.db_path, "r1")["ok"])

    def test_missing_override_row_uses_plain_connect_handler(self) -> None:
        with patch(
            "infrastructure.network.netmiko_factory.ConnectHandler",
            return_value=Mock(),
        ) as handler:
            connect_device(
                {"host": "r1", "device_type": "cisco_ios"},
                self.db_path,
            )
        handler.assert_called_once()

    def test_normalization_and_merge_preserve_order(self) -> None:
        self.assertEqual(normalize_algorithm_list("a, b,a,,"), ("a", "b"))
        self.assertEqual(merge_preferred(("b", "a"), ("a", "c")), ("b", "a", "c"))

    def test_unsupported_algorithm_rejected_before_transport(self) -> None:
        with self.assertRaises(UnsupportedSshAlgorithm):
            make_transport_factory(SshAlgorithmOverride(kex=("not-real",)))

    def test_factory_does_not_mutate_paramiko_global_preferences(self) -> None:
        supported = next(iter(paramiko.Transport._kex_info))
        before = tuple(paramiko.Transport._preferred_kex)
        factory = make_transport_factory(SshAlgorithmOverride(kex=(supported,)))
        fake_transport = Mock()
        options = Mock()
        options.kex = ("default",)
        options.key_types = ()
        options.ciphers = ()
        options.digests = ()
        fake_transport.get_security_options.return_value = options
        with patch("infrastructure.network.ssh_algorithms.paramiko.Transport", return_value=fake_transport):
            self.assertIs(factory(Mock()), fake_transport)
        self.assertEqual(tuple(paramiko.Transport._preferred_kex), before)
        self.assertEqual(options.kex[0], supported)

    def test_parallel_factories_keep_overrides_isolated(self) -> None:
        supported = tuple(paramiko.Transport._kex_info)[:2]
        if len(supported) < 2:
            self.skipTest("Paramiko exposes fewer than two KEX algorithms")
        before = tuple(paramiko.Transport._preferred_kex)
        factories = {
            "r1": make_transport_factory(SshAlgorithmOverride(kex=(supported[0],))),
            "r2": make_transport_factory(SshAlgorithmOverride(kex=(supported[1],))),
        }
        captured: dict[str, tuple[str, ...]] = {}

        class FakeOptions:
            kex = ("default",)
            key_types = ()
            ciphers = ()
            digests = ()

        class FakeTransport:
            def __init__(self, sock, **_kwargs):
                self.sock = sock
                self.options = FakeOptions()

            def get_security_options(self):
                return self.options

        def run(name: str, algorithm: str) -> None:
            transport = factories[name](name)
            captured[name] = transport.options.kex

        with patch(
            "infrastructure.network.ssh_algorithms.paramiko.Transport",
            FakeTransport,
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda item: run(*item), (("r1", supported[0]), ("r2", supported[1]))))
        self.assertEqual(captured["r1"][0], supported[0])
        self.assertEqual(captured["r2"][0], supported[1])
        self.assertEqual(tuple(paramiko.Transport._preferred_kex), before)

    def test_transport_exception_does_not_change_global_preferences(self) -> None:
        supported = next(iter(paramiko.Transport._kex_info))
        factory = make_transport_factory(
            SshAlgorithmOverride(kex=(supported,))
        )
        before = tuple(paramiko.Transport._preferred_kex)
        with patch(
            "infrastructure.network.ssh_algorithms.paramiko.Transport",
            side_effect=RuntimeError("transport failed"),
        ):
            with self.assertRaises(RuntimeError):
                factory(Mock())
        self.assertEqual(tuple(paramiko.Transport._preferred_kex), before)

    def test_telnet_never_reads_override(self) -> None:
        params = {"host": "r1", "device_type": "cisco_ios_telnet", "method": "telnet"}
        with patch(
            "infrastructure.network.netmiko_factory.ConnectHandler",
            return_value=Mock(),
        ) as handler, patch(
            "infrastructure.network.netmiko_factory.get_ssh_algorithm_override"
        ) as repository:
            connect_device(params, self.db_path)
        handler.assert_called_once()
        repository.assert_not_called()

    def test_nornir_plugin_uses_the_same_connection_factory(self) -> None:
        plugin = CAMSNetmiko()
        connection = Mock()
        with patch(
            "infrastructure.network.nornir_netmiko_plugin.connect_device",
            return_value=connection,
        ) as factory:
            plugin.open(
                hostname="r1",
                username="admin",
                password="secret",
                port=22,
                platform="cisco_ios",
                extras={
                    "ssh_algorithm_db_path": str(self.db_path),
                    "banner_timeout": 15,
                },
            )
        self.assertIs(plugin.connection, connection)
        params, db_path = factory.call_args.args
        self.assertEqual(db_path, str(self.db_path))
        self.assertNotIn("ssh_algorithm_db_path", params)
        self.assertEqual(params["banner_timeout"], 15)

    def test_two_nornir_hosts_push_concurrently_through_shared_policy(self) -> None:
        from nornir.core import Nornir
        from nornir.core.configuration import Config
        from nornir.core.inventory import ConnectionOptions, Host, Hosts, Inventory
        from nornir.init_nornir import load_runner

        barrier = Barrier(2)
        pushed: list[str] = []

        class FakeConnection:
            def __init__(self, host: str) -> None:
                self.host = host

            def enable(self) -> None:
                return None

            def send_config_set(self, config_commands, **_kwargs):
                barrier.wait(timeout=2)
                pushed.append(self.host)
                return "\n".join(config_commands)

            def disconnect(self) -> None:
                return None

        hosts = {
            name: Host(
                name=name,
                hostname=name,
                username="admin",
                password="secret",
                port=22,
                platform="cisco_ios",
                connection_options={
                    "networktools_netmiko": ConnectionOptions(
                        extras={"ssh_algorithm_db_path": str(self.db_path)}
                    )
                },
            )
            for name in ("r1", "r2")
        }
        config = Config.from_dict(
            runner={"plugin": "threaded", "options": {"num_workers": 2}},
            logging={"enabled": False},
        )
        register_networktools_netmiko()
        nornir = Nornir(
            inventory=Inventory(hosts=Hosts(hosts)),
            runner=load_runner(config),
            config=config,
        )
        with patch(
            "infrastructure.network.nornir_netmiko_plugin.connect_device",
            side_effect=lambda params, _db_path: FakeConnection(params["host"]),
        ):
            results = nornir.run(
                task=netmiko_send_config,
                config_commands=["hostname TEST"],
            )
        self.assertFalse(results.failed)
        self.assertCountEqual(pushed, ["r1", "r2"])


if __name__ == "__main__":
    unittest.main()
