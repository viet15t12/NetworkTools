from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main as _main_bootstrap  # noqa: F401 - configures Qt paths
from PyQt6.QtCore import QObject, QUrl, pyqtSlot
from PyQt6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlEngine, QQmlExpression
from PyQt6.QtWidgets import QApplication

from core.database.conversion import ConversionMixin
from features.routing.ospf import get_ospf_routing, save_ospf_routing
from scripts.build_databases import combine_sql


APP_DIR = Path(__file__).resolve().parents[1]


class _OspfBridge(QObject, ConversionMixin):
    def __init__(self, database: Path) -> None:
        super().__init__()
        self.database = database
        self.error = ""

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _set_last_routing_error(self, value: str) -> None:
        self.error = value

    @pyqtSlot(str, result="QVariant")
    def getOspfRouting(self, host: str) -> dict[str, Any]:
        return get_ospf_routing(self, host)

    @pyqtSlot(str, "QVariant", result=bool)
    def saveOspfRouting(self, host: str, payload: Any) -> bool:
        return save_ospf_routing(self, host, payload)

    @pyqtSlot(result=str)
    def getLastRoutingError(self) -> str:
        return self.error

    @pyqtSlot(str, str, str, result=bool)
    def hasPendingViewPush(self, _controller: str, _host: str, _module: str) -> bool:
        return False


class OspfQmlDatabaseBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "device_network.db"
        schema = combine_sql(
            APP_DIR / "infrastructure" / "database" / "schemas" / "device_network"
        )
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(schema)
            connection.execute("INSERT INTO t01_devices (host) VALUES ('r1')")
            connection.execute(
                "INSERT INTO t02_interface_name (host, interface_name) "
                "VALUES ('r1', 'GigabitEthernet0/0')"
            )
            connection.commit()
        self.bridge = _OspfBridge(self.database)
        self.assertTrue(save_ospf_routing(self.bridge, "r1", [self._payload()]), self.bridge.error)
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(str(APP_DIR))
        self.engine.rootContext().setContextProperty("dbManager", self.bridge)
        self.warnings: list[str] = []
        self.engine.warnings.connect(
            lambda rows: self.warnings.extend(row.toString() for row in rows)
        )

    def tearDown(self) -> None:
        for root in self.engine.rootObjects():
            root.deleteLater()
        self.engine.clearComponentCache()
        self.engine.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    @staticmethod
    def _payload() -> dict[str, Any]:
        return {
            "process_id": 10,
            "router_id": "1.1.1.1",
            "reference_bandwidth": 1000,
            "default_originate": True,
            "default_originate_always": True,
            "networks": [{"network": "10.0.0.0", "wildcard": "0.0.0.255", "area": 0}],
            "distance": {"external": 111, "intra_area": 112, "inter_area": 113},
            "areas": [{
                "area_id": 0,
                "area_type": "normal",
                "no_summary": False,
                "authentication": "message-digest",
                "ranges": [{
                    "ip": "10.0.0.0", "mask": "255.255.0.0", "advertise": True,
                    "cost": 5,
                }],
            }],
            "redistribute": [{
                "protocol": "static", "subnets": True, "metric": 20, "metric_type": 2,
            }],
            "passive_interfaces": [{
                "interface_name": "GigabitEthernet0/0", "passive": True,
            }],
            "tuning": {
                "maximum_paths": 4, "max_lsa": 1000, "spf_delay": 5,
                "spf_min_delay": 10, "spf_max_delay": 20, "lsa_delay": 5,
                "lsa_min_delay": 10, "lsa_max_delay": 20,
            },
            "interface_settings": [{
                "interface_name": "GigabitEthernet0/0", "area": 0, "cost": 10,
                "priority": 0, "hello_interval": 10, "dead_interval": 40,
                "mtu_ignore": True, "bfd": True, "network_type": "broadcast",
                "auth_type": "message-digest", "auth_key": "secret",
            }],
        }

    def _create_form(self) -> QObject:
        component = QQmlComponent(
            self.engine,
            QUrl.fromLocalFile(str(APP_DIR / "UI/qml/features/routing/ospf/OspfRoutingForm.qml")),
        )
        form = component.createWithInitialProperties({
            "currentHostIp": "r1", "width": 1100, "height": 800,
        })
        for _ in range(30):
            self.app.processEvents()
        self.assertIsNotNone(form, [error.toString() for error in component.errors()])
        return form

    def test_qml_save_round_trip_preserves_every_child_table(self) -> None:
        form = self._create_form()
        result, undefined = QQmlExpression(
            QQmlEngine.contextForObject(form), form, "saveToDatabase()"
        ).evaluate()
        self.assertFalse(undefined)
        self.assertTrue(result)
        for _ in range(20):
            self.app.processEvents()

        loaded = get_ospf_routing(self.bridge, "r1")["processes"][0]
        self.assertEqual(len(loaded["areas"]), 1)
        self.assertEqual(len(loaded["areas"][0]["ranges"]), 1)
        self.assertEqual(len(loaded["redistribute"]), 1)
        self.assertEqual(len(loaded["passive_interfaces"]), 1)
        self.assertEqual(len(loaded["interface_settings"]), 1)
        self.assertEqual(loaded["process_id"], 10)
        self.assertEqual(loaded["reference_bandwidth"], 1000)
        self.assertEqual(loaded["networks"][0]["area"], 0)
        self.assertEqual(loaded["distance"]["external"], 111)
        self.assertEqual(loaded["distance"]["intra_area"], 112)
        self.assertEqual(loaded["distance"]["inter_area"], 113)
        self.assertEqual(loaded["areas"][0]["area_id"], 0)
        self.assertEqual(loaded["areas"][0]["ranges"][0]["cost"], 5)
        self.assertEqual(loaded["redistribute"][0]["metric"], 20)
        self.assertEqual(loaded["redistribute"][0]["metric_type"], 2)
        for key, value in self._payload()["tuning"].items():
            self.assertEqual(loaded["tuning"][key], value)
        self.assertEqual(loaded["interface_settings"][0]["area"], 0)
        self.assertEqual(loaded["interface_settings"][0]["cost"], 10)
        self.assertEqual(loaded["interface_settings"][0]["priority"], 0)
        self.assertEqual(loaded["interface_settings"][0]["hello_interval"], 10)
        self.assertEqual(loaded["interface_settings"][0]["dead_interval"], 40)
        self.assertEqual(self.warnings, [])

    def test_numeric_zero_is_not_replaced_by_default_or_empty_text(self) -> None:
        form = self._create_form()
        expression = QQmlExpression(
            QQmlEngine.contextForObject(form),
            form,
            """
            removeInterfaceSettingFromSelectedProcess(0);
            addInterfaceSettingToSelectedProcess(
                "GigabitEthernet0/0", 0, 10, 0, 10, 40,
                false, false, "broadcast", "", ""
            );
            setTuningForSelectedProcess(0, 0, 0, 0, 0, 0, 0, 0);
            removeAreaRangeFromSelectedArea(0);
            addAreaRangeToSelectedArea("10.1.0.0", "255.255.0.0", true, 0);
            addRedistributeToSelectedProcess("connected", "", true, 0, 1, "");
            saveToDatabase()
            """,
        )
        result, undefined = expression.evaluate()
        self.assertFalse(undefined, expression.error().toString())
        self.assertTrue(result, form.property("errorMessage"))

        loaded = get_ospf_routing(self.bridge, "r1")["processes"][0]
        interface = loaded["interface_settings"][0]
        self.assertEqual(interface["area"], 0)
        self.assertEqual(interface["priority"], 0)
        for key in self._payload()["tuning"]:
            self.assertEqual(loaded["tuning"][key], 0)
        self.assertEqual(
            [row["cost"] for row in loaded["areas"][0]["ranges"]], [0]
        )
        connected = next(
            row for row in loaded["redistribute"] if row["protocol"] == "connected"
        )
        self.assertEqual(connected["metric"], 0)
        self.assertEqual(self.warnings, [])

    def test_area_ids_round_trip_and_invalid_or_duplicate_ids_are_rejected(self) -> None:
        form = self._create_form()
        context = QQmlEngine.contextForObject(form)

        for area_id in ("123", "4294967295"):
            result, undefined = QQmlExpression(
                context, form,
                f'addAreaToSelectedProcess("{area_id}", "normal", false, "")',
            ).evaluate()
            self.assertFalse(undefined)
            self.assertTrue(result)

        for invalid_id in ("123oops", "4294967296", "000"):
            result, undefined = QQmlExpression(
                context, form,
                f'addAreaToSelectedProcess("{invalid_id}", "normal", false, "")',
            ).evaluate()
            self.assertFalse(undefined)
            self.assertFalse(result)

        result, undefined = QQmlExpression(context, form, "saveToDatabase()").evaluate()
        self.assertFalse(undefined)
        self.assertTrue(result, form.property("errorMessage"))
        loaded = get_ospf_routing(self.bridge, "r1")["processes"][0]
        self.assertEqual([row["area_id"] for row in loaded["areas"]], [0, 123, 4294967295])
        self.assertEqual(self.warnings, [])

    def test_invalid_optional_number_is_rejected_instead_of_truncated(self) -> None:
        form = self._create_form()
        result, undefined = QQmlExpression(
            QQmlEngine.contextForObject(form), form,
            'setTuningForSelectedProcess("4oops", "", "", "", "", "", "", ""); '
            'saveToDatabase()',
        ).evaluate()
        self.assertFalse(undefined)
        self.assertFalse(result)
        self.assertIn("maximum paths must be an integer", form.property("errorMessage"))
        loaded = get_ospf_routing(self.bridge, "r1")["processes"][0]
        self.assertEqual(loaded["tuning"]["maximum_paths"], 4)

    def test_invalid_process_id_is_rejected_instead_of_truncated(self) -> None:
        form = self._create_form()
        result, undefined = QQmlExpression(
            QQmlEngine.contextForObject(form),
            form,
            'processItems()[0].processId = "20oops"; saveToDatabase()',
        ).evaluate()
        self.assertFalse(undefined)
        self.assertFalse(result)
        self.assertIn("must be an integer", form.property("errorMessage"))
        loaded = get_ospf_routing(self.bridge, "r1")["processes"]
        self.assertEqual([row["process_id"] for row in loaded], [10])

    def test_invalid_reference_bandwidth_is_rejected_instead_of_truncated(self) -> None:
        form = self._create_form()
        result, undefined = QQmlExpression(
            QQmlEngine.contextForObject(form), form,
            'processItems()[0].referenceBandwidthText = "2000oops"; saveToDatabase()',
        ).evaluate()
        self.assertFalse(undefined)
        self.assertFalse(result)
        self.assertIn("positive integer", form.property("errorMessage"))
        loaded = get_ospf_routing(self.bridge, "r1")["processes"][0]
        self.assertEqual(loaded["reference_bandwidth"], 1000)

    def test_distance_and_tuning_fields_are_hydrated_from_database(self) -> None:
        form = self._create_form()
        self.assertEqual(
            form.findChild(QObject, "ospfDistanceExternalField").property("text"), "111"
        )
        self.assertEqual(
            form.findChild(QObject, "ospfDistanceIntraField").property("text"), "112"
        )
        self.assertEqual(
            form.findChild(QObject, "ospfTuningMaxPathsField").property("text"), "4"
        )
        self.assertEqual(
            form.findChild(QObject, "ospfTuningMaxLsaField").property("text"), "1000"
        )

    def test_qml_can_save_a_new_process_with_database_id_zero(self) -> None:
        form = self._create_form()
        result, undefined = QQmlExpression(
            QQmlEngine.contextForObject(form),
            form,
            """
            addEmptyProcess();
            processItems()[1].processId = "20";
            saveToDatabase()
            """,
        ).evaluate()
        self.assertFalse(undefined)
        self.assertTrue(result)
        for _ in range(20):
            self.app.processEvents()

        processes = get_ospf_routing(self.bridge, "r1")["processes"]
        self.assertEqual([row["process_id"] for row in processes], [10, 20])

    def test_missing_database_service_is_reported_without_qml_exception(self) -> None:
        self.engine.rootContext().setContextProperty("dbManager", None)
        form = self._create_form()

        self.assertEqual(
            form.property("errorMessage"), "OSPF database service is unavailable."
        )
        self.assertEqual(self.warnings, [])


if __name__ == "__main__":
    unittest.main()
