import unittest
from pathlib import Path

from PyQt6.QtCore import QMetaObject, QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtQml import QQmlApplicationEngine, QQmlComponent
from PyQt6.QtWidgets import QApplication

from features.syslog.qt.manager import _variant_dict
from features.syslog.settings import SyslogSettings


APP_DIR = Path(__file__).resolve().parents[2]


class _DeviceConfigBackend(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.deleted_payload = None

    @pyqtSlot(str, result="QVariant")
    def getDeviceConfigurations(self, host: str):
        return [{
            "device_host": host,
            "server_ip": "192.168.122.1",
            "protocol": "udp",
            "port": 5514,
            "source_interface": "GigabitEthernet0/0",
            "trap_severity": 4,
            "timestamps": False,
            "sequence_numbers": False,
            "configured": True,
            "sync_status": "synchronized",
        }]

    @pyqtSlot(str, "QVariant", result="QVariant")
    def deleteDeviceConfiguration(self, host: str, payload):
        self.deleted_payload = _variant_dict(payload)
        return {"ok": True, "message": "staged"}


class _InterfaceInventoryBackend(QObject):
    runningConfigUpdated = pyqtSignal(str)

    @pyqtSlot(str, result="QVariant")
    def getRouterInterfaces(self, _host: str):
        return [
            {"interface_name": "Loopback0"},
            {"interface_name": "GigabitEthernet0/0"},
        ]

    @pyqtSlot(str, result="QVariant")
    def getSwitchInterfaces(self, _host: str):
        return [{"if_name": "GigabitEthernet0/1"}]

    @pyqtSlot(str, result="QVariant")
    def getSwitchSvis(self, _host: str):
        return [{"vlan_id": 10}]

    @pyqtSlot(str, result="QVariant")
    def getSwitchEtherChannels(self, _host: str):
        return [{"po_number": 1}]

    @pyqtSlot(str, str, str, result=bool)
    def hasPendingViewPush(self, _controller: str, _host: str, _module: str):
        return False


class SyslogQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _create(
        self, relative_path: str, context: dict | None = None,
        properties: dict | None = None,
    ):
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(APP_DIR))
        for name, value in (context or {}).items():
            engine.rootContext().setContextProperty(name, value)
        warnings: list[str] = []
        engine.warnings.connect(
            lambda rows: warnings.extend(row.toString() for row in rows)
        )
        component = QQmlComponent(
            engine,
            QUrl.fromLocalFile(str(APP_DIR / relative_path)),
        )
        instance = component.createWithInitialProperties(properties or {})
        self.app.processEvents()
        self.assertIsNotNone(
            instance,
            [error.toString() for error in component.errors()],
        )
        return engine, instance, warnings

    def test_syslog_table_renders_list_model_without_warnings(self) -> None:
        engine, instance, warnings = self._create(
            "tests/qml/SyslogTableHarness.qml"
        )
        try:
            self.assertEqual(warnings, [])
        finally:
            instance.deleteLater()
            engine.deleteLater()

    def test_syslog_table_recycles_rows_without_null_model_warnings(self) -> None:
        engine, instance, warnings = self._create(
            "tests/qml/SyslogTableHarness.qml"
        )
        try:
            QMetaObject.invokeMethod(instance, "churnRows")
            QMetaObject.invokeMethod(instance, "exerciseNullRow")
            for _ in range(4):
                self.app.processEvents()
            relevant = [
                item for item in warnings
                if "SyslogLogRow.qml" in item
                or "SyslogMessageDetails.qml" in item
                or "undefined member" in item
                or "Cannot read property" in item
            ]
            self.assertEqual(relevant, [], warnings)
        finally:
            instance.deleteLater()
            engine.deleteLater()

    def test_syslog_device_item_combines_name_and_host(self) -> None:
        cases = (
            ({"host": "192.168.122.10", "device_name": "Core-R1"},
             "Core-R1(192.168.122.10)"),
            ({"host": "192.168.122.11", "device_name": "   "},
             "192.168.122.11"),
        )
        for device_data, expected in cases:
            with self.subTest(device_data=device_data):
                engine, instance, warnings = self._create(
                    "UI/qml/sidebar/syslog/SyslogDeviceItem.qml",
                    properties={"deviceData": device_data},
                )
                try:
                    self.assertEqual(instance.property("displayLabel"), expected)
                    self.assertEqual(warnings, [])
                finally:
                    instance.deleteLater()
                    engine.deleteLater()

    def test_syslog_settings_spinboxes_do_not_create_binding_loops(self) -> None:
        settings = SyslogSettings()
        engine, instance, warnings = self._create(
            "UI/qml/features/syslog/SyslogServerSettings.qml",
            {"syslogSettings": settings, "syslogManager": None},
        )
        try:
            self.assertFalse(
                any("Binding loop" in warning for warning in warnings),
                warnings,
            )
        finally:
            instance.deleteLater()
            engine.deleteLater()

    def test_device_config_delete_sends_plain_mapping_to_backend(self) -> None:
        backend = _DeviceConfigBackend()
        engine, instance, warnings = self._create(
            "UI/qml/features/syslog/SyslogDeviceConfigPage.qml",
            {"syslogManager": backend, "dbManager": None},
            {"host": "192.168.122.102"},
        )
        try:
            self.assertEqual(instance.property("selectedIndex"), 0)
            QMetaObject.invokeMethod(instance, "deleteSelected")
            self.app.processEvents()
            self.assertIsInstance(backend.deleted_payload, dict)
            self.assertEqual(backend.deleted_payload["server_ip"], "192.168.122.1")
            self.assertEqual(backend.deleted_payload["port"], 5514)
            self.assertFalse(any("Syslog data must" in item for item in warnings), warnings)
        finally:
            instance.deleteLater()
            engine.deleteLater()

    def test_device_config_source_interface_uses_inventory_combo_box(self) -> None:
        backend = _DeviceConfigBackend()
        inventory = _InterfaceInventoryBackend()
        engine, instance, warnings = self._create(
            "UI/qml/features/syslog/SyslogDeviceConfigPage.qml",
            {"syslogManager": backend, "dbManager": inventory},
            {"host": "192.168.122.102"},
        )
        try:
            self.assertEqual(
                instance.property("sourceInterfaceOptions").toVariant(),
                [
                    "GigabitEthernet0/0",
                    "GigabitEthernet0/1",
                    "Loopback0",
                    "Port-channel1",
                    "Vlan10",
                ],
            )
            combo = instance.findChild(QObject, "syslogSourceInterfaceCombo")
            self.assertIsNotNone(combo)
            QMetaObject.invokeMethod(instance, "beginEdit")
            self.app.processEvents()
            self.assertEqual(combo.property("currentText"), "GigabitEthernet0/0")
            self.assertEqual(warnings, [])
        finally:
            instance.deleteLater()
            engine.deleteLater()


if __name__ == "__main__":
    unittest.main()
