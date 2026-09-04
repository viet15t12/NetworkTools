from __future__ import annotations

import sqlite3
import json
import tempfile
import unittest
from pathlib import Path

from features.routing.static_default import get_default_routes, replace_default_route, save_default_routes


class _Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _as_list(value):
        return json.loads(value) if isinstance(value, str) else list(value or [])

    @staticmethod
    def _as_dict(value):
        return dict(value)

    @staticmethod
    def _int_or_none(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class StaticDefaultRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE t04_static_default_routes (
                id INTEGER PRIMARY KEY,
                host TEXT NOT NULL,
                next_hop_ip TEXT NOT NULL,
                sync_status TEXT
            )
            """
        )

    def tearDown(self) -> None:
        self.connection.close()

    def test_unchanged_route_is_not_deleted_and_reinserted(self) -> None:
        self.connection.execute(
            """
            INSERT INTO t04_static_default_routes
                (host, next_hop_ip, sync_status)
            VALUES ('192.168.122.101', '192.168.122.1', 'synchronized')
            """
        )

        replace_default_route(
            self.connection, "192.168.122.101", "192.168.122.1"
        )

        rows = self.connection.execute(
            """
            SELECT next_hop_ip, sync_status
            FROM t04_static_default_routes
            WHERE host = '192.168.122.101'
            """
        ).fetchall()
        self.assertEqual(
            [(row["next_hop_ip"], row["sync_status"]) for row in rows],
            [("192.168.122.1", "synchronized")],
        )

    def test_changed_route_still_creates_delete_and_apply_operations(self) -> None:
        self.connection.execute(
            """
            INSERT INTO t04_static_default_routes
                (host, next_hop_ip, sync_status)
            VALUES ('router-1', '192.0.2.1', 'synchronized')
            """
        )

        replace_default_route(self.connection, "router-1", "192.0.2.2")

        rows = self.connection.execute(
            """
            SELECT next_hop_ip, sync_status
            FROM t04_static_default_routes
            WHERE host = 'router-1'
            ORDER BY id
            """
        ).fetchall()
        self.assertEqual(
            [(row["next_hop_ip"], row["sync_status"]) for row in rows],
            [
                ("192.0.2.1", "pending_delete"),
                ("192.0.2.2", "pending_apply"),
            ],
        )

    def test_unchanged_route_repairs_previous_apply_delete_pair(self) -> None:
        self.connection.executemany(
            """
            INSERT INTO t04_static_default_routes
                (host, next_hop_ip, sync_status)
            VALUES ('router-1', '192.0.2.1', ?)
            """,
            [("pending_delete",), ("pending_apply",)],
        )

        replace_default_route(self.connection, "router-1", "192.0.2.1")

        rows = self.connection.execute(
            """
            SELECT next_hop_ip, sync_status
            FROM t04_static_default_routes
            WHERE host = 'router-1'
            """
        ).fetchall()
        self.assertEqual(
            [(row["next_hop_ip"], row["sync_status"]) for row in rows],
            [("192.0.2.1", "synchronized")],
        )


class DefaultRouteListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "routes.db"
        self.db = _Database(self.path)
        with self.db._connect() as connection:
            connection.execute(
                """
                CREATE TABLE t04_static_default_routes (
                    id INTEGER PRIMARY KEY,
                    host TEXT NOT NULL,
                    next_hop_ip TEXT NOT NULL,
                    sync_status TEXT NOT NULL
                )
                """
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_one_host_can_save_multiple_default_routes(self) -> None:
        self.assertTrue(
            save_default_routes(
                self.db,
                "router-1",
                json.dumps([
                    {"id": 0, "nexthop": "192.0.2.1"},
                    {"id": 0, "nexthop": "198.51.100.1"},
                ]),
            )
        )

        result = get_default_routes(self.db, "router-1")
        self.assertTrue(result["ok"])
        self.assertEqual(
            [route["nexthop"] for route in result["routes"]],
            ["192.0.2.1", "198.51.100.1"],
        )

    def test_removing_one_default_preserves_the_other(self) -> None:
        save_default_routes(
            self.db,
            "router-1",
            [{"nexthop": "192.0.2.1"}, {"nexthop": "198.51.100.1"}],
        )
        routes = get_default_routes(self.db, "router-1")["routes"]

        self.assertTrue(save_default_routes(self.db, "router-1", [routes[1]]))

        active = get_default_routes(self.db, "router-1")["routes"]
        self.assertEqual([route["nexthop"] for route in active], ["198.51.100.1"])
        with self.db._connect() as connection:
            deleted = connection.execute(
                "SELECT next_hop_ip FROM t04_static_default_routes WHERE sync_status='pending_delete'"
            ).fetchall()
        self.assertEqual([row[0] for row in deleted], ["192.0.2.1"])

    def test_list_save_repairs_legacy_contradictory_pair(self) -> None:
        with self.db._connect() as connection:
            deleted_id = connection.execute(
                "INSERT INTO t04_static_default_routes(host,next_hop_ip,sync_status) VALUES('router-1','192.0.2.1','pending_delete')"
            ).lastrowid
            applied_id = connection.execute(
                "INSERT INTO t04_static_default_routes(host,next_hop_ip,sync_status) VALUES('router-1','192.0.2.1','pending_apply')"
            ).lastrowid

        self.assertTrue(
            save_default_routes(
                self.db, "router-1", [{"id": applied_id, "nexthop": "192.0.2.1"}]
            )
        )

        with self.db._connect() as connection:
            rows = connection.execute(
                "SELECT id,next_hop_ip,sync_status FROM t04_static_default_routes WHERE host='router-1'"
            ).fetchall()
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows],
            [(deleted_id, "192.0.2.1", "synchronized")],
        )


if __name__ == "__main__":
    unittest.main()
