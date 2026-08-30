from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main as _main_bootstrap  # noqa: F401 - configures PyQt DLL/QML paths
from PyQt6.QtCore import (
    Q_ARG,
    QCoreApplication,
    QMetaObject,
    QObject,
    QPoint,
    QPointF,
    QSettings,
    Qt,
    QUrl,
    pyqtSlot,
    qInstallMessageHandler,
)
from PyQt6.QtGui import QColor, QWheelEvent
from PyQt6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlEngine, QQmlExpression
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app_facade import (
    AppPaths,
    DatabaseManager,
    ExternalToolsManager,
    LanguageSettings,
    MenuPresentationController,
    NetworkMonitor,
    StatusBarSettings,
    SystemAppearance,
    TerminalHelper,
    ThemeSettings,
    WindowSettings,
)
from features.config_backup import ConfigBackupService
from features.sftp import SftpController
from infrastructure.system.virtual_lab import VirtualLabInfo
from infrastructure.system.desktop_environment import DesktopEnvironmentDetector
from core.welcome import WelcomeController
from core.workspace_save import WorkspaceSaveController


APP_DIR = Path(__file__).resolve().parents[1]


class QmlSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(str(APP_DIR))
        self.warnings: list[str] = []
        self.engine.warnings.connect(
            lambda warnings: self.warnings.extend(warning.toString() for warning in warnings)
        )
        welcome_controller = WelcomeController()
        workspace_save_controller = WorkspaceSaveController(welcome_controller)
        self.context_objects = {
            "dbManager": DatabaseManager(),
            "cli": TerminalHelper(),
            "networkMonitor": NetworkMonitor(),
            "statusBarSettings": StatusBarSettings(),
            "themeSettings": ThemeSettings(),
            "languageSettings": LanguageSettings(),
            "windowSettings": WindowSettings(),
            "workspaceSaveController": workspace_save_controller,
            "welcomeController": welcome_controller,
            "AppPaths": AppPaths(),
            "externalTools": ExternalToolsManager(),
        }
        context = self.engine.rootContext()
        for name, value in self.context_objects.items():
            context.setContextProperty(name, value)

    def tearDown(self) -> None:
        for root in self.engine.rootObjects():
            close = getattr(root, "close", None)
            if callable(close):
                close()
            root.deleteLater()
        for value in self.context_objects.values():
            shutdown = getattr(value, "shutdown", None)
            if callable(shutdown):
                shutdown()
        self.engine.clearComponentCache()
        self.engine.deleteLater()
        self.app.processEvents()

    def _create(self, relative_path: str):
        component = QQmlComponent(
            self.engine,
            QUrl.fromLocalFile(str((APP_DIR / relative_path).resolve())),
        )
        instance = component.create()
        self.app.processEvents()
        self.assertTrue(instance, [error.toString() for error in component.errors()])
        return instance

    def _create_with_properties(self, relative_path: str, properties: dict):
        component = QQmlComponent(
            self.engine,
            QUrl.fromLocalFile(str((APP_DIR / relative_path).resolve())),
        )
        instance = component.createWithInitialProperties(properties)
        self.app.processEvents()
        self.assertTrue(instance, [error.toString() for error in component.errors()])
        return instance

    def _wait_until(self, predicate, timeout_ms: int = 5000) -> bool:
        deadline = time.perf_counter() + timeout_ms / 1000
        while time.perf_counter() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            QTest.qWait(5)
        self.app.processEvents()
        return bool(predicate())

    def test_network_prefix_harness(self) -> None:
        harness = self._create("tests/qml/NetworkFieldHarness.qml")
        self.assertEqual(harness.property("subnetResult"), "255.255.255.0")
        self.assertEqual(harness.property("wildcardResult"), "0.0.0.255")
        self.assertEqual(self.warnings, [])

    def test_ospf_process_preserves_numeric_area_zero_from_database(self) -> None:
        card = self._create_with_properties(
            "UI/qml/features/routing/ospf/OspfProcessCard.qml",
            {
                "processIndex": 1,
                "payload": {
                    "process_id": 1,
                    "networks": [
                        {
                            "network": "10.0.0.0",
                            "wildcard": "0.0.0.255",
                            "area": 0,
                        },
                        {
                            "network": "10.0.1.0",
                            "wildcard": "0.0.0.255",
                            "area": "",
                        },
                    ],
                },
            },
        )

        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(card), card, "validate(true)"
        ).evaluate()

        self.assertFalse(is_undefined)
        result_map = result.toVariant()
        self.assertTrue(result_map["ok"], result_map)
        area, area_is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(card), card, "networks.get(0).area"
        ).evaluate()
        self.assertFalse(area_is_undefined)
        self.assertEqual(area, "0")
        defaulted_area, defaulted_area_is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(card), card,
            "snapshotForSave().networks[1].area"
        ).evaluate()
        self.assertFalse(defaulted_area_is_undefined)
        self.assertEqual(defaulted_area, "0")

    def test_routing_group_reads_and_updates_nested_network_models(self) -> None:
        dialog = self._create("UI/qml/features/routing/RoutingGroupDialog.qml")
        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(dialog),
            dialog,
            """
            populateTargets([{
                host: "192.168.122.102",
                device_name: "R2",
                networks: [{
                    network: "10.1.12.0",
                    wildcard: "0.0.0.3",
                    prefix_length: 30,
                    interfaces: [{interface_name: "GigabitEthernet0/1"}]
                }]
            }, {
                host: "192.168.122.103",
                device_name: "R3",
                networks: [{
                    network: "10.1.13.0",
                    wildcard: "0.0.0.255",
                    prefix_length: 24,
                    interfaces: [{interface_name: "GigabitEthernet0/2"}]
                }]
            }]);
            updateSelected(0, true);
            updateSelected(1, true);
            updateNetwork(0, 0, "selected", true);
            updateNetwork(0, 0, "area", "7");
            updateNetwork(1, 0, "selected", true);
            stepIndex = 3;
            ({targets: selectedTargets(), valid: stepValid(), error: errorText})
            """,
        ).evaluate()

        self.assertFalse(is_undefined)
        result_map = result.toVariant()
        self.assertTrue(result_map["valid"], result_map["error"])
        targets = result_map["targets"]
        self.assertEqual(
            targets[0]["networks"],
            [{"network": "10.1.12.0", "wildcard": "0.0.0.3", "area": "7"}],
        )
        self.assertEqual(
            targets[1]["networks"],
            [{"network": "10.1.13.0", "wildcard": "0.0.0.255", "area": "0"}],
        )
        self.assertFalse(
            any("is not a function" in warning for warning in self.warnings),
            self.warnings,
        )

        limit_result, limit_is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(dialog),
            dialog,
            """
            populateTargets([
                {host: "r1", networks: []}, {host: "r2", networks: []},
                {host: "r3", networks: []}, {host: "r4", networks: []},
                {host: "r5", networks: []}, {host: "r6", networks: []}
            ]);
            for (let i = 0; i < 6; i++)
                updateSelected(i, true);
            ({count: selectedCount, targets: selectedTargets().length, error: errorText})
            """,
        ).evaluate()

        self.assertFalse(limit_is_undefined)
        limit_map = limit_result.toVariant()
        self.assertEqual(limit_map["count"], 5)
        self.assertEqual(limit_map["targets"], 5)
        self.assertIn("at most 5 hosts", limit_map["error"])

    def test_view_push_polling_stops_when_database_manager_shuts_down(self) -> None:
        button = self._create_with_properties(
            "UI/qml/shared/ViewPushButton.qml",
            {"hostIp": "", "controllerName": "routing", "moduleName": "ospf"},
        )
        manager = self.context_objects["dbManager"]

        class ViewPushFactoryProbe:
            called = False

            def get(self, controller_name):
                self.called = True
                return None

        probe = ViewPushFactoryProbe()
        manager._view_push = probe

        self.assertFalse(button.property("backendShuttingDown"))
        manager.shutdown()
        self.app.processEvents()

        self.assertTrue(manager.shuttingDown)
        self.assertTrue(button.property("backendShuttingDown"))
        self.assertFalse(
            manager.hasPendingViewPush("routing", "192.168.122.103", "ospf")
        )
        button.setProperty("hostIp", "192.168.122.103")
        self.app.processEvents()
        self.assertFalse(probe.called)

    def test_view_push_button_tolerates_a_temporarily_null_backend(self) -> None:
        context = self.engine.rootContext()
        manager = self.context_objects["dbManager"]
        context.setContextProperty("dbManager", None)
        try:
            button = self._create_with_properties(
                "UI/qml/shared/ViewPushButton.qml",
                {"hostIp": "192.0.2.10", "controllerName": "switching"},
            )
            self.assertFalse(button.property("backendAvailable"))
            self.assertFalse(button.property("hasPendingConfig"))
            self.assertEqual(self.warnings, [])
        finally:
            context.setContextProperty("dbManager", manager)

    def test_switch_port_model_normalizes_nullable_roles(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/switching/interfaces/SwitchPortsPage.qml",
            {"host": "192.0.2.253", "width": 1100, "height": 720},
        )
        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            allRows = [
                {id: 1, if_name: "GigabitEthernet0/1", mode: "access"},
                {id: 2, if_name: "GigabitEthernet0/2", mode: "trunk",
                 allowed_vlans: "10,20", voice_vlan: 20, sticky: 1}
            ];
            rebuildVisibleRows();
            ({count: allRows.length, selected: selectedIndex})
            """,
        ).evaluate()
        self.assertFalse(is_undefined)
        self.assertEqual(result.toVariant(), {"count": 2, "selected": 0})
        self.assertEqual(self.warnings, [])

    def test_switch_port_mode_change_replaces_draft_for_reactive_access_trunk_form(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/switching/interfaces/SwitchPortsPage.qml",
            {"host": "192.0.2.253", "width": 1100, "height": 720},
        )
        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            draftData = defaultDraft();
            const accessDraft = draftData;
            updateField("mode", "trunk");
            ({mode: draftData.mode, replaced: accessDraft !== draftData})
            """,
        ).evaluate()

        self.assertFalse(is_undefined)
        self.assertEqual(result.toVariant(), {"mode": "trunk", "replaced": True})
        self.assertEqual(self.warnings, [])

    def test_switch_ports_have_all_access_and_trunk_child_tabs(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/switching/interfaces/SwitchPortsPage.qml",
            {"host": "192.0.2.253", "width": 1100, "height": 720},
        )
        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            allRows = [
                {id: 1, if_name: "GigabitEthernet0/1", mode: "access"},
                {id: 2, if_name: "GigabitEthernet0/2", mode: "trunk"},
                {id: 3, if_name: "GigabitEthernet0/3", mode: "access"}
            ];
            activePortTab = "Port Status";
            rebuildVisibleRows();
            const allCount = interfaceModel.count;
            beginCreate();
            const statusFormMode = formMode;
            activatePortTab("Access");
            const accessCount = interfaceModel.count;
            beginCreate();
            const accessDraftMode = draftData.mode;
            cancel();
            activatePortTab("Trunk");
            const trunkCount = interfaceModel.count;
            beginCreate();
            ({allCount: allCount,
              accessCount: accessCount,
              trunkCount: trunkCount,
              statusFormMode: statusFormMode,
              accessDraftMode: accessDraftMode,
              trunkDraftMode: draftData.mode})
            """,
        ).evaluate()

        self.assertFalse(is_undefined)
        self.assertEqual(
            result.toVariant(),
            {
                "allCount": 3,
                "accessCount": 2,
                "trunkCount": 1,
                "statusFormMode": 0,
                "accessDraftMode": "access",
                "trunkDraftMode": "trunk",
            },
        )
        self.assertIsNotNone(page.findChild(QObject, "switchPortModeTabs"))
        self.assertEqual(self.warnings, [])

    def test_port_status_is_mode_only_and_advanced_tabs_lock_their_mode(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/switching/interfaces/SwitchPortsPage.qml",
            {"host": "192.0.2.253", "width": 1100, "height": 720},
        )
        inspector = page.findChild(QObject, "switchPortInspector")
        self.assertIsNotNone(inspector)
        self.assertTrue(inspector.property("modeOnly"))
        self.assertTrue(inspector.property("allowModeChange"))

        expression = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            'activatePortTab("Access"); activePortTab',
        )
        result, is_undefined = expression.evaluate()
        self.assertFalse(is_undefined)
        self.assertEqual(result, "Access")
        self.app.processEvents()

        self.assertFalse(inspector.property("modeOnly"))
        self.assertFalse(inspector.property("allowModeChange"))
        self.assertEqual(self.warnings, [])

    def test_trunk_vlan_checkboxes_build_allowed_vlan_expression(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/switching/interfaces/SwitchPortsPage.qml",
            {"host": "192.0.2.253", "width": 1100, "height": 720},
        )
        setup = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            vlanOptions = [
                {vlan_id: 10, vlan_name: "users", state: "active"},
                {vlan_id: 20, vlan_name: "voice", state: "active"},
                {vlan_id: 30, vlan_name: "servers", state: "active"}
            ];
            activatePortTab("Trunk");
            beginCreate();
            draftData.allowed_vlans
            """,
        )
        result, is_undefined = setup.evaluate()
        self.assertFalse(is_undefined)
        self.assertEqual(result, "all")

        inspector = page.findChild(QObject, "switchPortInspector")
        self.assertIsNotNone(inspector)
        expression = QQmlExpression(
            QQmlEngine.contextForObject(inspector),
            inspector,
            """
            toggleAllVlans(false);
            toggleAllowedVlan(10, true);
            toggleAllowedVlan(30, true);
            allowedExpression()
            """,
        )
        result, is_undefined = expression.evaluate()
        self.assertFalse(is_undefined)
        self.assertEqual(result, "10,30")
        self.assertEqual(
            page.property("draftData").toVariant()["allowed_vlans"], "10,30"
        )
        self.assertIsNotNone(page.findChild(QObject, "trunkAllVlansCheckbox"))
        self.assertEqual(self.warnings, [])

    def test_switch_monitoring_model_normalizes_missing_counter_roles(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/switching/monitoring/SwitchMonitoringPage.qml",
            {
                "host": "192.0.2.254",
                "viewName": "portCounters",
                "width": 1100,
                "height": 720,
            },
        )
        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            allRows = [
                {if_name: "GigabitEthernet0/1", oper_status: "up"},
                {if_name: "GigabitEthernet0/2", oper_status: "down",
                 in_octets: 1024, out_errors: 2}
            ];
            rebuildVisibleRows();
            ({count: rowsModel.count,
              firstIn: rowsModel.get(0).in_octets,
              firstPolled: rowsModel.get(0).polled_at,
              secondOutErrors: rowsModel.get(1).out_errors})
            """,
        ).evaluate()
        self.assertFalse(is_undefined)
        self.assertEqual(
            result.toVariant(),
            {"count": 2, "firstIn": 0, "firstPolled": "", "secondOutErrors": 2},
        )
        self.assertEqual(self.warnings, [])

    def test_l2_security_trusted_uplink_options_refresh_reactively(self) -> None:
        """Interface inventory must reach the ComboBox without reopening the page."""
        page = self._create_with_properties(
            "UI/qml/features/switching/security/L2SecurityPage.qml",
            {"host": "192.0.2.248", "width": 1100, "height": 720},
        )
        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            section = "trust";
            interfaceOptions = [
                {id: 1, if_name: "GigabitEthernet0/1", mode: "trunk",
                 oper_status: "up"},
                {id: 2, if_name: "GigabitEthernet0/2", mode: "access",
                 oper_status: "down"}
            ];
            dataRevision += 1;
            ({values: availableTrustInterfaces(),
              labels: availableTrustInterfaceLabels()})
            """,
        ).evaluate()

        self.assertFalse(is_undefined)
        self.assertEqual(
            result.toVariant(),
            {
                "values": ["GigabitEthernet0/1", "GigabitEthernet0/2"],
                "labels": [
                    "GigabitEthernet0/1  —  trunk · up",
                    "GigabitEthernet0/2  —  access · down",
                ],
            },
        )
        self.app.processEvents()
        combo = page.findChild(QObject, "trustInterfaceCombo")
        self.assertIsNotNone(combo)
        self.assertEqual(combo.property("currentValue"), "GigabitEthernet0/1")
        self.assertEqual(self.warnings, [])

    def test_vtp_saved_domain_can_be_loaded_back_into_the_editor(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/switching/switching/VtpPage.qml",
            {"host": "192.0.2.255", "width": 1100, "height": 760},
        )
        expression = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            groupModel.clear();
            groupModel.append(normalizedGroup({
                vtp_domain_id: 7,
                domain_name: "CAMPUS",
                version: 3,
                description: null,
                members: [
                    {host: "sw1.local", mode: "server", pruning: 1},
                    {host: "sw2.local", mode: "client", pruning: 0}
                ]
            }));
            loadGroup(0);
            ({domain: domainField.text,
              version: Number(versionCombo.currentValue),
              members: memberModel.count,
              firstMode: memberModel.get(0).vtpMode,
              selected: selectedGroupIndex})
            """,
        )
        result, is_undefined = expression.evaluate()
        self.assertFalse(is_undefined, expression.error().toString())
        self.assertEqual(
            result.toVariant(),
            {
                "domain": "CAMPUS",
                "version": 3,
                "members": 2,
                "firstMode": "server",
                "selected": 0,
            },
        )
        self.assertEqual(self.warnings, [])

    def test_etherchannel_quick_select_excludes_members_used_elsewhere(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/switching/switching/EtherChannelPage.qml",
            {"host": "192.0.2.249", "width": 1100, "height": 760},
        )
        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            interfaceOptions = [
                {if_name: "GigabitEthernet0/1", mode: "access"},
                {if_name: "GigabitEthernet0/2", mode: "trunk"},
                {if_name: "GigabitEthernet0/3", mode: "routed"},
                {if_name: "Port-channel9", mode: "trunk"}
            ];
            allRows = [{id: 8, member_ports: "GigabitEthernet0/2"}];
            draftData = {id: 0, member_ports: ""};
            toggleMember("GigabitEthernet0/1", true);
            ({available: availableMemberInterfaces(), members: draftData.member_ports})
            """,
        ).evaluate()
        self.assertFalse(is_undefined)
        self.assertEqual(
            result.toVariant(),
            {"available": ["GigabitEthernet0/1"], "members": "GigabitEthernet0/1"},
        )
        self.assertEqual(self.warnings, [])

    def test_interface_view_tolerates_a_null_selection_and_exposes_reload(self) -> None:
        view = self._create_with_properties(
            "UI/qml/features/interfaces/InterfaceView.qml",
            {"width": 900, "height": 700},
        )
        view.setProperty("selectedInterface", None)
        self.app.processEvents()

        self.assertFalse(view.property("selectedCanDelete"))
        self.assertIsNotNone(view.findChild(QObject, "interfaceReloadButton"))
        selection_warnings = [
            warning for warning in self.warnings
            if "selectedInterface" in warning or "could not be converted" in warning
        ]
        self.assertEqual(selection_warnings, [])

    def test_fhrp_protocol_page_uses_responsive_operations_workspace(self) -> None:
        page = self._create_with_properties(
            "UI/qml/features/fhrp/FhrpProtocolPage.qml",
            {"protocol": "hsrp", "width": 1100, "height": 760},
        )

        result, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(page),
            page,
            """
            toggleHost("192.0.2.1", true);
            toggleHost("192.0.2.2", true);
            matchingInterfaces = [{
                iface_id: 1,
                host: "192.0.2.1",
                interface_name: "GigabitEthernet0/1",
                ip_address: "192.168.4.1",
                network: "192.168.4.0/24"
            }, {
                iface_id: 2,
                host: "192.0.2.2",
                interface_name: "GigabitEthernet0/1",
                ip_address: "192.168.4.2",
                network: "192.168.4.0/24"
            }];
            groupAuthType = "md5-key";
            groupAuthSecret = "secret";
            updateProtocolOption("version", 1);
            updateProtocolOption("hello_ms", 2000);
            updateProtocolOption("hold_ms", 7000);
            updateMember(0, "preemptDelayMinSec", 15);
            updateMember(0, "preemptDelayReloadSec", 30);
            updateMember(0, "tracks", [{
                track_object: "GigabitEthernet0/2",
                decrement_value: 25
            }]);
            savedGroupModel.append({
                fhrp_id: 1,
                protocol: "hsrp",
                group_number: 1,
                virtual_ip: "192.168.4.10",
                address_family: "ipv4",
                description: "",
                updated_at: "",
                members: [{host: "192.0.2.1", sync_status: "pending_apply"},
                          {host: "192.0.2.2", sync_status: "synchronized"}]
            });
            refreshPendingPushHosts();
            ({matched: matchedHostCount(), payload: memberPayload(),
              pendingHosts: pendingPushHosts, groupRange: groupRange,
              authType: groupAuthType})
            """,
        ).evaluate()
        self.app.processEvents()

        self.assertFalse(page.property("compactLayout"))
        form_pane = page.findChild(QObject, "fhrpFormPane")
        self.assertIsNotNone(form_pane)
        pane_scroll = form_pane.findChild(QObject, "splitFormPaneScroll")
        self.assertIsNotNone(pane_scroll)
        self.assertGreater(float(form_pane.property("height")), 0)
        self.assertTrue(form_pane.property("contentOverflow"))
        self.assertGreater(
            float(form_pane.property("scrollContentHeight")),
            float(form_pane.property("viewportHeight")),
        )
        self.assertGreater(
            float(pane_scroll.property("contentHeight")),
            float(pane_scroll.property("availableHeight")),
        )
        self.assertIsNotNone(page.findChild(QObject, "fhrpSummaryGrid"))
        self.assertIsNotNone(page.findChild(QObject, "fhrpHostPicker"))
        self.assertIsNotNone(page.findChild(QObject, "fhrpSavedGroupsPanel"))
        self.assertIsNotNone(page.findChild(QObject, "fhrpProtocolOptionsEditor"))
        reload_button = page.findChild(QObject, "fhrpReloadButton")
        self.assertIsNotNone(reload_button)
        self.assertEqual(reload_button.property("text"), "Reload UI")
        self.assertFalse(reload_button.property("autoCompact"))
        self.assertGreaterEqual(
            float(reload_button.property("width")) + 0.5,
            float(reload_button.property("expandedImplicitWidth")),
        )
        save_button = page.findChild(QObject, "fhrpSaveButton")
        view_push_button = page.findChild(QObject, "fhrpViewPushButton")
        self.assertIsNotNone(save_button)
        self.assertIsNotNone(view_push_button)
        self.assertIsNone(page.findChild(QObject, "fhrpSavePushButton"))
        self.assertTrue(save_button.property("enabled"))
        self.assertTrue(view_push_button.property("enabled"))
        page.setProperty("operationBusy", True)
        self.app.processEvents()
        self.assertFalse(save_button.property("enabled"))
        self.assertFalse(view_push_button.property("enabled"))
        page.setProperty("operationBusy", False)
        self.app.processEvents()
        self.assertTrue(save_button.property("enabled"))
        self.assertTrue(view_push_button.property("enabled"))
        self.assertFalse(is_undefined)
        result_map = result.toVariant()
        self.assertEqual(result_map["matched"], 2)
        self.assertEqual(len(result_map["payload"]), 2)
        self.assertEqual(result_map["pendingHosts"], ["192.0.2.1"])
        self.assertEqual(result_map["groupRange"], "0–255")
        self.assertEqual(result_map["authType"], "none")
        first_member = result_map["payload"][0]
        self.assertEqual(first_member["version"], 1)
        self.assertEqual(first_member["hello_ms"], 2000)
        self.assertEqual(first_member["hold_ms"], 7000)
        self.assertEqual(first_member["preempt_delay_min_sec"], 15)
        self.assertEqual(first_member["preempt_delay_reload_sec"], 30)
        self.assertEqual(
            first_member["tracks"],
            [{"track_object": "GigabitEthernet0/2", "decrement_value": 25}],
        )

        page.setProperty("width", 600)
        self.app.processEvents()
        self.assertTrue(page.property("compactLayout"))
        self.assertGreater(float(form_pane.property("width")), 0)
        self.assertGreater(float(form_pane.property("height")), 0)
        self.assertEqual(self.warnings, [])

    def test_fhrp_vrrp_and_glbp_specific_options_reach_member_payload(self) -> None:
        cases = (
            (
                "vrrp",
                """
                updateProtocolOption("advertisement_ms", 750);
                toggleHost("192.0.2.1", true);
                memberPayload()[0]
                """,
                {"version": 2, "advertisement_ms": 750},
            ),
            (
                "glbp",
                """
                updateProtocolOption("hello_ms", 1500);
                updateProtocolOption("hold_ms", 6000);
                updateProtocolOption("load_balancing", "weighted");
                toggleHost("192.0.2.1", true);
                updateMember(0, "weightingMax", 120);
                updateMember(0, "weightingLower", 80);
                updateMember(0, "weightingUpper", 110);
                updateMember(0, "forwarderPreempt", false);
                updateMember(0, "forwarderPreemptDelaySec", 10);
                memberPayload()[0]
                """,
                {
                    "hello_ms": 1500,
                    "hold_ms": 6000,
                    "load_balancing": "weighted",
                    "weighting_max": 120,
                    "weighting_lower": 80,
                    "weighting_upper": 110,
                    "forwarder_preempt": False,
                    "forwarder_preempt_delay_sec": 10,
                },
            ),
        )

        for protocol, expression, expected in cases:
            with self.subTest(protocol=protocol):
                page = self._create_with_properties(
                    "UI/qml/features/fhrp/FhrpProtocolPage.qml",
                    {"protocol": protocol, "width": 1100, "height": 760},
                )
                result, is_undefined = QQmlExpression(
                    QQmlEngine.contextForObject(page), page, expression
                ).evaluate()
                self.assertFalse(is_undefined)
                payload = result.toVariant()
                for field, value in expected.items():
                    self.assertEqual(payload[field], value)

        self.assertEqual(self.warnings, [])

    def test_nqv_easter_egg_switches_brand_logo_to_hidden_asset(self) -> None:
        self.engine.rootContext().setContextProperty("nqvEasterEggEnabled", True)
        harness = self._create("tests/qml/EasterEggAssetHarness.qml")
        self.assertTrue(str(harness.property("activeLogo").toString()).startswith(
            "data:image/svg+xml;base64,"
        ))

    def test_ptit_easter_egg_switches_brand_logo_to_hidden_asset(self) -> None:
        self.engine.rootContext().setContextProperty("ptitEasterEggEnabled", True)
        harness = self._create("tests/qml/EasterEggAssetHarness.qml")
        active_url = harness.property("activeLogo").toString()
        self.assertTrue(str(active_url).startswith("data:image/svg+xml;base64,"))
        self.assertEqual(active_url, self.context_objects["AppPaths"].hiddenPtitLogo().toString())

    def test_settings_sidebar_cards_grow_to_fit_wrapped_descriptions(self) -> None:
        harness = self._create("tests/qml/SettingsPanelHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
        panel = harness.findChild(QObject, "settingsPanelUnderTest")
        self.assertIsNotNone(panel)
        filtered_count = QQmlExpression(
            QQmlEngine.contextForObject(panel),
            panel,
            "filteredItems.length",
        ).evaluate()[0]
        self.assertEqual(filtered_count, 5)
        self.assertTrue(
            self._wait_until(lambda: panel.property("renderedCardCount") == 5)
        )

        cards = [
            QQmlExpression(
                QQmlEngine.contextForObject(panel),
                panel,
                f"cardAt({index})",
            ).evaluate()[0]
            for index in range(5)
        ]
        self.assertTrue(all(card is not None for card in cards))

        for index, card in enumerate(cards):
            with self.subTest(card=index):
                self.assertGreaterEqual(
                    float(card.property("height")) + 0.5,
                    max(
                        72.0,
                        float(card.property("contentImplicitHeight")) + 24.0,
                    ),
                )
        self.assertTrue(any(float(card.property("height")) > 72 for card in cards))
        self.assertEqual(self.warnings, [])

    def test_language_selector_updates_and_persists_vietnamese(self) -> None:
        backend = self.context_objects["languageSettings"]
        backend.setLanguage("en")
        view = self._create("UI/qml/content/SettingsView.qml")
        view.setProperty("activeSettingKey", "language")
        combo = view.findChild(QObject, "applicationLanguageCombo")
        self.assertIsNotNone(combo)
        self.assertEqual(combo.property("currentIndex"), 0)

        QMetaObject.invokeMethod(combo, "activated", Q_ARG(int, 1))
        self.app.processEvents()

        self.assertEqual(backend.language, "vi")
        self.assertEqual(combo.property("currentIndex"), 1)
        restored = LanguageSettings()
        self.assertEqual(restored.language, "vi")
        backend.setLanguage("en")
        self.assertEqual(self.warnings, [])

    def test_appearance_menu_style_override_updates_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "menu-style.ini"),
                QSettings.Format.IniFormat,
            )
            controller = MenuPresentationController(
                detector=DesktopEnvironmentDetector(
                    platform_id="darwin",
                    environ={},
                    qt_platform_plugin="cocoa",
                ),
                settings=settings,
            )
            self.context_objects["menuPresentation"] = controller
            self.engine.rootContext().setContextProperty(
                "menuPresentation", controller
            )

            view = self._create("UI/qml/content/SettingsView.qml")
            combo = view.findChild(QObject, "menuStyleCombo")
            self.assertIsNotNone(combo)
            self.assertEqual(combo.property("currentIndex"), 0)

            QMetaObject.invokeMethod(combo, "activated", Q_ARG(int, 1))
            self.app.processEvents()

            self.assertEqual(controller.configuredStyle, "custom")
            self.assertTrue(controller.restartRequired)
            self.assertEqual(combo.property("currentIndex"), 1)
            self.assertEqual(self.warnings, [])

    def test_native_menu_is_created_with_its_owner_window(self) -> None:
        harness = self._create("tests/qml/NativeMenuHostHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
        self.assertTrue(
            self._wait_until(lambda: harness.property("nativeMenuReady"))
        )
        self.assertFalse(harness.property("nativeMenuFailed"))
        self.assertTrue(harness.property("nativeMenuHasOwner"))
        self.assertEqual(self.warnings, [])

    def test_network_shorthand_normalizes_on_focus_transfer_without_ghost_caret(
        self,
    ) -> None:
        harness = self._create("tests/qml/NetworkFieldFocusHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))

        fields = [
            harness.findChild(QObject, object_name)
            for object_name in (
                "networkFocusSubnetField",
                "networkFocusWildcardField",
                "networkFocusNextField",
            )
        ]
        self.assertTrue(all(field is not None for field in fields))

        def text_input(field):
            return next(
                child
                for child in field.findChildren(QObject)
                if child.metaObject().indexOfProperty("cursorVisible") >= 0
            )

        inputs = [text_input(field) for field in fields]

        def center_point(item) -> QPoint:
            mapped = QQmlExpression(
                QQmlEngine.contextForObject(item),
                item,
                "mapToItem(null, width / 2, height / 2)",
            ).evaluate()[0]
            return QPoint(round(mapped.x()), round(mapped.y()))

        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            center_point(inputs[0]),
        )
        for key in (Qt.Key.Key_Slash, Qt.Key.Key_2, Qt.Key.Key_4):
            QTest.keyClick(harness, key)

        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            center_point(inputs[1]),
        )
        self.app.processEvents()
        self.assertEqual(harness.property("subnetText"), "255.255.255.0")
        self.assertFalse(inputs[0].property("activeFocus"))
        self.assertFalse(inputs[0].property("cursorVisible"))

        for key in (Qt.Key.Key_Minus, Qt.Key.Key_Slash, Qt.Key.Key_2, Qt.Key.Key_4):
            QTest.keyClick(harness, key)
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            center_point(inputs[2]),
        )
        self.app.processEvents()
        self.assertEqual(harness.property("wildcardText"), "0.0.0.255")
        self.assertEqual(
            sum(bool(item.property("cursorVisible")) for item in inputs),
            1,
        )
        self.assertTrue(inputs[2].property("cursorVisible"))

        # Reproduce Qt's problematic late cursorVisible=true write, then
        # verify the inactive-field guard used by the deferred focus cleanup.
        inputs[1].setProperty("cursorVisible", True)
        self.assertTrue(inputs[1].property("cursorVisible"))
        QMetaObject.invokeMethod(inputs[1], "hideCursorAfterFocusOut")
        self.assertFalse(inputs[1].property("cursorVisible"))
        self.assertTrue(inputs[2].property("cursorVisible"))
        self.assertEqual(self.warnings, [])

    def test_file_type_icons_cover_names_extensions_and_fallback(self) -> None:
        harness = self._create("tests/qml/FileTypeIconHarness.qml")
        expected_suffixes = {
            "dockerIcon": "/resources/files/types/docker.svg",
            "environmentIcon": "/resources/files/types/tune.svg",
            "licenseIcon": "/resources/files/types/license.svg",
            "pythonIcon": "/resources/files/types/python.svg",
            "packetCaptureIcon": "/resources/files/types/hex.svg",
            "reactTypeScriptIcon": "/resources/files/types/react_ts.svg",
            "spreadsheetIcon": "/resources/files/types/table.svg",
            "textIcon": "/resources/files/types/document.svg",
        }

        for property_name, suffix in expected_suffixes.items():
            with self.subTest(property=property_name):
                icon_url = harness.property(property_name)
                self.assertIsInstance(icon_url, QUrl)
                self.assertTrue(icon_url.toString().endswith(suffix))
        unknown_url = harness.property("unknownIcon")
        self.assertIsInstance(unknown_url, QUrl)
        self.assertTrue(unknown_url.isEmpty())
        self.assertEqual(self.warnings, [])

    def test_standard_button_tab_focus_uses_accent_ring_and_text_underline(self) -> None:
        harness = self._create("tests/qml/ButtonFocusHarness.qml")
        cancel_label = harness.findChild(QObject, "testCancelChangesButtonLabel")

        self.assertIsNotNone(cancel_label)
        self.assertFalse(harness.property("cancelVisualFocus"))
        self.assertEqual(harness.property("cancelBorderWidth"), 0)

        QMetaObject.invokeMethod(harness, "focusCancelWithTabReason")
        self.app.processEvents()

        self.assertTrue(harness.property("cancelVisualFocus"))
        self.assertGreater(harness.property("cancelBorderWidth"), 0)
        self.assertEqual(harness.property("cancelBorderColor"), harness.property("accentColor"))
        self.assertFalse(cancel_label.property("font").bold())
        self.assertTrue(cancel_label.property("font").underline())
        self.assertEqual(self.warnings, [])

    def test_password_field_masks_by_default_and_preserves_cursor_on_toggle(self) -> None:
        harness = self._create("tests/qml/PasswordFieldHarness.qml")
        reveal_button = harness.findChild(QObject, "passwordRevealButton")

        self.assertIsNotNone(reveal_button)
        self.assertFalse(harness.property("passwordVisible"))
        self.assertNotEqual(harness.property("displayText"), "secret-value")
        self.assertEqual(harness.property("cursorPosition"), 4)
        self.assertTrue(harness.property("inputHasFocus"))
        self.assertTrue(
            str(reveal_button.property("iconSource")).endswith(
                "/resources/actions/visibility-on.svg"
            )
        )

        QMetaObject.invokeMethod(harness, "togglePassword")
        self.app.processEvents()

        self.assertTrue(harness.property("passwordVisible"))
        self.assertEqual(harness.property("displayText"), "secret-value")
        self.assertEqual(harness.property("cursorPosition"), 4)
        self.assertTrue(harness.property("inputHasFocus"))
        self.assertTrue(
            str(reveal_button.property("iconSource")).endswith(
                "/resources/actions/visibility-off.svg"
            )
        )

        QMetaObject.invokeMethod(harness, "togglePassword")
        self.app.processEvents()
        self.assertFalse(harness.property("passwordVisible"))
        self.assertNotEqual(harness.property("displayText"), "secret-value")
        self.assertEqual(self.warnings, [])

    def test_standard_spin_box_does_not_double_its_left_inset(self) -> None:
        spin_box = self._create("UI/components/standard/StandardSpinBox.qml")
        spin_box.setProperty("width", 240)
        control = spin_box.findChild(QObject, "standardSpinBoxControl")
        text_input = spin_box.findChild(QObject, "standardSpinBoxInput")

        self.assertIsNotNone(control)
        self.assertIsNotNone(text_input)
        self.assertEqual(control.property("leftPadding"), 0)
        self.assertEqual(control.property("rightPadding"), 0)
        self.assertEqual(text_input.property("x"), 0)
        self.assertGreater(text_input.property("leftPadding"), 0)
        self.assertLessEqual(text_input.property("leftPadding"), 16)
        self.assertEqual(self.warnings, [])

    def test_standard_spin_box_indicator_buttons_change_and_clamp_value(self) -> None:
        harness = self._create("tests/qml/SpinBoxHarness.qml")
        control = harness.findChild(QObject, "standardSpinBoxControl")
        self.assertIsNotNone(control)

        def indicator_point(vertical_fraction: float) -> QPoint:
            mapped = QQmlExpression(
                QQmlEngine.contextForObject(control),
                control,
                f"mapToItem(null, width - 14, height * {vertical_fraction})",
            ).evaluate()[0]
            return QPoint(round(mapped.x()), round(mapped.y()))

        up_point = indicator_point(0.25)
        down_point = indicator_point(0.75)

        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            up_point,
        )
        self.app.processEvents()
        self.assertEqual(control.property("value"), 60)

        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            down_point,
        )
        self.app.processEvents()
        self.assertEqual(control.property("value"), 50)

        control.setProperty("value", 100)
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            up_point,
        )
        self.assertEqual(control.property("value"), 100)

        control.setProperty("value", 0)
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            down_point,
        )
        self.assertEqual(control.property("value"), 0)
        self.assertEqual(self.warnings, [])

    def test_selection_tokens_keep_text_contrast_across_themes_and_accents(self) -> None:
        harness = self._create("tests/qml/SelectionThemeHarness.qml")

        def relative_luminance(color: QColor) -> float:
            channels = (color.redF(), color.greenF(), color.blueF())
            linear = [
                channel / 12.92
                if channel <= 0.04045
                else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast_ratio(first: QColor, second: QColor) -> float:
            first_luminance = relative_luminance(first)
            second_luminance = relative_luminance(second)
            return (max(first_luminance, second_luminance) + 0.05) / (
                min(first_luminance, second_luminance) + 0.05
            )

        for theme_mode in (1, 2, 3, 4):
            for custom_accent in ("#000000", "#FFFFFF", "#FFD400", "#777777", "#356FD6"):
                with self.subTest(theme_mode=theme_mode, accent=custom_accent):
                    QMetaObject.invokeMethod(
                        harness,
                        "setSelectionContext",
                        Q_ARG("QVariant", theme_mode),
                        Q_ARG("QVariant", custom_accent),
                    )
                    self.app.processEvents()
                    background = harness.property("selectionBackground")
                    foreground = harness.property("selectionForeground")
                    self.assertIsInstance(background, QColor)
                    self.assertIsInstance(foreground, QColor)
                    self.assertGreaterEqual(contrast_ratio(background, foreground), 4.5)

        self.assertEqual(self.warnings, [])

    def test_system_accent_and_status_starting_color_follow_theme_contract(self) -> None:
        harness = self._create("tests/qml/SelectionThemeHarness.qml")

        QMetaObject.invokeMethod(harness, "setSystemAccentContext")
        self.app.processEvents()
        self.assertEqual(harness.property("currentAccentName"), "System")
        self.assertEqual(
            harness.property("currentAccentColor"),
            harness.property("systemAccentColor"),
        )

        for index in range(12):
            with self.subTest(preset=index):
                QMetaObject.invokeMethod(
                    harness,
                    "setPresetStatusContext",
                    Q_ARG("QVariant", index),
                )
                self.app.processEvents()
                self.assertGreaterEqual(
                    float(harness.property("statusBarWarningContrast")),
                    4.5,
                )

        for accent in ("#000000", "#FFFFFF", "#FFD400", "#777777", "#356FD6"):
            with self.subTest(custom=accent):
                QMetaObject.invokeMethod(
                    harness,
                    "setCustomStatusContext",
                    Q_ARG("QVariant", accent),
                )
                self.app.processEvents()
                self.assertGreaterEqual(
                    float(harness.property("statusBarWarningContrast")),
                    4.5,
                )

        self.assertEqual(self.warnings, [])

    def test_high_contrast_toggle_combines_with_light_and_dark_modes(self) -> None:
        harness = self._create("tests/qml/SelectionThemeHarness.qml")
        for base_mode, high_contrast, expected_mode in (
            (1, False, 1),
            (1, True, 3),
            (2, False, 2),
            (2, True, 4),
        ):
            with self.subTest(base_mode=base_mode, high_contrast=high_contrast):
                QMetaObject.invokeMethod(
                    harness,
                    "setThemeContext",
                    Q_ARG("QVariant", base_mode),
                    Q_ARG("QVariant", high_contrast),
                )
                self.app.processEvents()
                self.assertEqual(harness.property("effectiveThemeMode"), expected_mode)
                self.assertEqual(harness.property("highContrastEnabled"), high_contrast)

        QMetaObject.invokeMethod(
            harness,
            "setThemeContext",
            Q_ARG("QVariant", 0),
            Q_ARG("QVariant", True),
        )
        self.app.processEvents()
        self.assertIn(harness.property("effectiveThemeMode"), (3, 4))
        self.assertTrue(harness.property("highContrastEnabled"))

    def test_system_theme_tracks_linux_appearance_backend_changes(self) -> None:
        with patch.object(
            SystemAppearance,
            "_detect_color_scheme",
            return_value=SystemAppearance.DARK,
        ):
            appearance = SystemAppearance(poll_interval_ms=60_000)
        self.context_objects["systemAppearance"] = appearance
        self.engine.rootContext().setContextProperty(
            "systemAppearance",
            appearance,
        )
        harness = self._create("tests/qml/SelectionThemeHarness.qml")
        QMetaObject.invokeMethod(
            harness,
            "setThemeContext",
            Q_ARG("QVariant", 0),
            Q_ARG("QVariant", False),
        )
        self.app.processEvents()
        self.assertEqual(harness.property("effectiveThemeMode"), 2)

        with patch.object(
            appearance,
            "_detect_color_scheme",
            return_value=SystemAppearance.LIGHT,
        ):
            appearance.refresh()
        self.app.processEvents()
        self.assertEqual(harness.property("effectiveThemeMode"), 1)

    def test_config_text_viewer_search_zoom_and_line_selection(self) -> None:
        viewer = self._create("UI/components/standard/ConfigTextViewer.qml")
        viewer.setProperty("width", 900)
        viewer.setProperty("height", 560)
        viewer.setProperty("highlightingChunkLineCount", 1)
        viewer.setProperty(
            "text",
            "interface GigabitEthernet0/0\n ip address 10.0.0.1 255.255.255.0\n permit inside 2026-07-14 12:30:00\ninterface Loopback0",
        )
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        self.assertTrue(viewer.property("highlightingInProgress"))
        self.assertFalse(viewer.property("highlightingReady"))
        for _ in range(8):
            if not viewer.property("highlightingInProgress"):
                break
            QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        self.app.processEvents()

        self.assertTrue(viewer.property("highlightingReady"))
        self.assertTrue(viewer.property("syntaxHighlightingActive"))
        self.assertIn("<span", viewer.property("highlightedText"))
        self.assertIn("GigabitEthernet0/0", viewer.property("highlightedText"))
        self.assertIn("font-weight:600", viewer.property("highlightedText"))
        light_highlighted_text = viewer.property("highlightedText")

        theme_harness = self._create("tests/qml/SelectionThemeHarness.qml")
        QMetaObject.invokeMethod(
            theme_harness,
            "setSelectionContext",
            Q_ARG("QVariant", 2),
            Q_ARG("QVariant", "#356FD6"),
        )
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        for _ in range(8):
            if not viewer.property("highlightingInProgress"):
                break
            QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        self.app.processEvents()
        self.assertNotEqual(viewer.property("highlightedText"), light_highlighted_text)

        viewer.setProperty("searchText", "interface")
        QMetaObject.invokeMethod(viewer, "runSearchNow")
        self.app.processEvents()

        self.assertEqual(viewer.property("lineCount"), 4)
        self.assertEqual(viewer.property("matchCount"), 2)
        self.assertEqual(viewer.property("currentMatchIndex"), -1)

        search_field = viewer.findChild(QObject, "configViewerSearchField")
        content = viewer.findChild(QObject, "configViewerContent")
        bottom_toolbar = viewer.findChild(QObject, "configViewerBottomToolbar")
        zoom_out_button = viewer.findChild(QObject, "configViewerZoomOutButton")
        zoom_in_button = viewer.findChild(QObject, "configViewerZoomInButton")
        zoom_percent_button = viewer.findChild(QObject, "configViewerZoomPercentButton")
        line_selection_margin = viewer.findChild(QObject, "configViewerLineSelectionMargin")
        line_selection_mouse_area = viewer.findChild(
            QObject, "configViewerLineSelectionMouseArea"
        )
        context_menu = viewer.findChild(QObject, "configViewerContextMenu")
        context_copy_item = viewer.findChild(QObject, "configViewerContextCopyItem")
        context_find_item = viewer.findChild(QObject, "configViewerContextFindItem")
        occurrence_repeater = viewer.findChild(QObject, "configViewerOccurrenceRepeater")
        text_area = viewer.findChild(QObject, "configViewerTextArea")
        self.assertIsNotNone(search_field)
        self.assertIsNotNone(content)
        self.assertIsNotNone(bottom_toolbar)
        self.assertIsNotNone(zoom_out_button)
        self.assertIsNotNone(zoom_in_button)
        self.assertIsNotNone(zoom_percent_button)
        self.assertIsNone(viewer.findChild(QObject, "configViewerResetZoomButton"))
        self.assertIsNone(viewer.findChild(QObject, "configViewerZoomSpinBox"))
        self.assertIsNotNone(line_selection_margin)
        self.assertIsNotNone(line_selection_mouse_area)
        self.assertIsNotNone(context_menu)
        self.assertIsNotNone(context_copy_item)
        self.assertIsNotNone(context_find_item)
        self.assertIsNotNone(occurrence_repeater)
        self.assertIsNotNone(text_area)
        self.assertGreater(bottom_toolbar.property("y"), content.property("y"))
        self.assertLess(line_selection_margin.property("width"), 24)
        margin_frame_x_expression = QQmlExpression(
            QQmlEngine.contextForObject(viewer),
            viewer,
            "lineSelectionMargin.mapToItem(textFrame, 0, 0).x",
        )
        self.assertLess(margin_frame_x_expression.evaluate()[0], 0)
        self.assertIsNone(viewer.findChild(QObject, "configViewerLineNumbers"))

        second_line_y_expression = QQmlExpression(
            QQmlEngine.contextForObject(viewer),
            viewer,
            "selectionMarginYForLine(1)",
        )
        second_line_y = second_line_y_expression.evaluate()[0]
        self.assertGreater(second_line_y, 0)
        QMetaObject.invokeMethod(
            viewer,
            "selectLineAtSelectionMarginY",
            Q_ARG("QVariant", second_line_y),
            Q_ARG("QVariant", False),
        )
        self.app.processEvents()
        self.assertEqual(
            viewer.property("selectedText"),
            " ip address 10.0.0.1 255.255.255.0",
        )

        QMetaObject.invokeMethod(viewer, "focusSearch")
        self.app.processEvents()

        focus_harness = self._create("tests/qml/ConfigTextViewerHarness.qml")
        focus_harness.setProperty("configText", viewer.property("text"))
        QTest.qWait(100)
        self.app.processEvents()
        self.assertTrue(focus_harness.property("highlightingReady"))
        self.assertTrue(focus_harness.property("syntaxHighlightingActive"))
        self.assertIn("<span", focus_harness.property("highlightedText"))
        QTest.keyClick(
            focus_harness,
            Qt.Key.Key_F,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertTrue(focus_harness.property("searchHasFocus"))

        # Enter must compute fresh matches synchronously even when the 180 ms
        # typing debounce has not fired yet. Shift+Enter navigates backwards.
        for character in "interface":
            QTest.keyClick(
                focus_harness,
                getattr(Qt.Key, f"Key_{character.upper()}"),
            )
        QTest.keyClick(focus_harness, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(focus_harness.property("matchCount"), 2)
        self.assertEqual(focus_harness.property("currentMatchIndex"), 0)
        QTest.keyClick(focus_harness, Qt.Key.Key_Return)
        self.assertEqual(focus_harness.property("currentMatchIndex"), 1)
        QTest.keyClick(
            focus_harness,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
        )
        self.assertEqual(focus_harness.property("currentMatchIndex"), 0)

        wheel_font_size = focus_harness.property("fontPixelSize")
        self.assertEqual(focus_harness.property("zoomPercent"), 100)
        wheel_event = QWheelEvent(
            QPointF(450, 250),
            QPointF(450, 250),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QCoreApplication.sendEvent(focus_harness, wheel_event)
        self.app.processEvents()
        self.assertEqual(focus_harness.property("zoomPercent"), 110)
        self.assertEqual(focus_harness.property("fontPixelSize"), wheel_font_size + 1)

        QTest.keyClick(
            focus_harness,
            Qt.Key.Key_Equal,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(focus_harness.property("zoomPercent"), 125)
        self.assertEqual(focus_harness.property("fontPixelSize"), 16)
        QTest.keyClick(
            focus_harness,
            Qt.Key.Key_Minus,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(focus_harness.property("zoomPercent"), 110)
        self.assertEqual(focus_harness.property("fontPixelSize"), wheel_font_size + 1)

        focus_harness.setProperty(
            "configText",
            "\n".join(f"interface Loopback{index}" for index in range(100)),
        )
        QTest.qWait(50)
        self.app.processEvents()
        line_height = focus_harness.property("codeLineHeight")
        self.assertGreater(line_height, 0)
        self.assertTrue(
            self._wait_until(
                lambda: focus_harness.property("maximumScrollY") >= line_height * 2,
                timeout_ms=2000,
            )
        )

        QMetaObject.invokeMethod(
            focus_harness,
            "setScrollContentY",
            Q_ARG("QVariant", line_height * 2 + line_height * 0.4),
        )
        self.app.processEvents()
        aligned_second_line_expression = QQmlExpression(
            QQmlEngine.contextForObject(focus_harness),
            focus_harness,
            "viewer.verticalScrollPositionForLine(2)",
        )
        aligned_second_line = aligned_second_line_expression.evaluate()[0]
        self.assertAlmostEqual(
            focus_harness.property("scrollContentY"),
            aligned_second_line,
            delta=0.01,
        )

        line_scroll_event = QWheelEvent(
            QPointF(450, 250),
            QPointF(450, 250),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QCoreApplication.sendEvent(focus_harness, line_scroll_event)
        self.app.processEvents()
        aligned_fifth_line_expression = QQmlExpression(
            QQmlEngine.contextForObject(focus_harness),
            focus_harness,
            "viewer.verticalScrollPositionForLine(5)",
        )
        aligned_fifth_line = aligned_fifth_line_expression.evaluate()[0]
        self.assertAlmostEqual(
            focus_harness.property("scrollContentY"),
            aligned_fifth_line,
            delta=0.01,
        )

        focus_viewer = focus_harness.findChild(QObject, "testConfigTextViewer")
        self.assertIsNotNone(focus_viewer)
        sixth_line_y_expression = QQmlExpression(
            QQmlEngine.contextForObject(focus_viewer),
            focus_viewer,
            "selectionMarginYForLine(5)",
        )
        sixth_line_y = sixth_line_y_expression.evaluate()[0]
        self.assertGreaterEqual(sixth_line_y, 0)
        QMetaObject.invokeMethod(
            focus_viewer,
            "selectLineAtSelectionMarginY",
            Q_ARG("QVariant", sixth_line_y),
            Q_ARG("QVariant", False),
        )
        self.app.processEvents()
        self.assertEqual(focus_viewer.property("selectedText"), "interface Loopback5")

        QApplication.clipboard().clear()
        QTest.keyClick(
            focus_harness,
            Qt.Key.Key_C,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(QApplication.clipboard().text(), "interface Loopback5")

        QTest.keyClick(
            focus_harness,
            Qt.Key.Key_F,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(focus_harness.property("searchText"), "interface Loopback5")
        self.assertTrue(focus_harness.property("searchHasFocus"))
        focus_harness.setProperty("visible", False)

        QMetaObject.invokeMethod(search_field, "accepted")
        self.app.processEvents()
        self.assertEqual(viewer.property("currentMatchIndex"), 0)
        self.assertEqual(viewer.property("selectedText"), "interface")

        QMetaObject.invokeMethod(search_field, "accepted")
        QMetaObject.invokeMethod(search_field, "reverseAccepted")
        self.app.processEvents()
        self.assertEqual(viewer.property("currentMatchIndex"), 0)

        default_font_size = viewer.property("defaultFontPixelSize")
        self.assertEqual(default_font_size, 13)
        self.assertEqual(viewer.property("zoomPercent"), 100)
        QMetaObject.invokeMethod(zoom_in_button, "clicked")
        self.assertEqual(viewer.property("zoomPercent"), 110)
        self.assertEqual(viewer.property("fontPixelSize"), default_font_size + 1)
        QMetaObject.invokeMethod(zoom_out_button, "clicked")
        self.assertEqual(viewer.property("zoomPercent"), 100)
        self.assertEqual(viewer.property("fontPixelSize"), default_font_size)
        QMetaObject.invokeMethod(zoom_in_button, "clicked")
        QMetaObject.invokeMethod(zoom_percent_button, "clicked")
        self.assertEqual(viewer.property("fontPixelSize"), default_font_size)
        self.assertLessEqual(zoom_percent_button.property("width"), 64)
        QMetaObject.invokeMethod(
            viewer,
            "setZoomPercent",
            Q_ARG("QVariant", 76),
        )
        self.app.processEvents()
        self.assertEqual(viewer.property("zoomPercent"), 75)
        self.assertEqual(viewer.property("fontPixelSize"), 10)
        QMetaObject.invokeMethod(
            viewer,
            "setZoomPercent",
            Q_ARG("QVariant", 199),
        )
        self.app.processEvents()
        self.assertEqual(viewer.property("zoomPercent"), 200)
        self.assertEqual(viewer.property("fontPixelSize"), 26)
        self.assertEqual(zoom_percent_button.property("text"), "200%")
        QMetaObject.invokeMethod(zoom_percent_button, "clicked")
        self.assertEqual(viewer.property("zoomPercent"), 100)
        QMetaObject.invokeMethod(
            viewer,
            "setZoomPercent",
            Q_ARG("QVariant", 999),
        )
        self.app.processEvents()
        self.assertEqual(viewer.property("zoomPercent"), 500)
        self.assertEqual(viewer.property("fontPixelSize"), 65)
        QMetaObject.invokeMethod(zoom_percent_button, "clicked")
        for _ in range(20):
            QMetaObject.invokeMethod(zoom_in_button, "clicked")
        self.app.processEvents()
        self.assertEqual(viewer.property("zoomPercent"), 500)
        self.assertEqual(viewer.property("fontPixelSize"), 65)

        zoomed_second_line_y = second_line_y_expression.evaluate()[0]
        QMetaObject.invokeMethod(
            viewer,
            "selectLineAtSelectionMarginY",
            Q_ARG("QVariant", zoomed_second_line_y),
            Q_ARG("QVariant", False),
        )
        self.app.processEvents()
        self.assertEqual(
            viewer.property("selectedText"),
            " ip address 10.0.0.1 255.255.255.0",
        )
        QMetaObject.invokeMethod(zoom_percent_button, "clicked")

        QApplication.clipboard().clear()
        QMetaObject.invokeMethod(viewer, "copyAll")
        self.app.processEvents()
        self.assertEqual(QApplication.clipboard().text(), viewer.property("text"))
        self.assertTrue(viewer.property("copyFeedbackVisible"))

        QMetaObject.invokeMethod(viewer, "selectLine", Q_ARG("QVariant", 1))
        self.app.processEvents()
        self.assertEqual(
            viewer.property("selectedText"),
            " ip address 10.0.0.1 255.255.255.0",
        )

        QApplication.clipboard().clear()
        QMetaObject.invokeMethod(viewer, "copySelection")
        self.app.processEvents()
        self.assertEqual(
            QApplication.clipboard().text(),
            " ip address 10.0.0.1 255.255.255.0",
        )
        self.assertTrue(context_copy_item.property("enabled"))
        self.assertTrue(context_find_item.property("enabled"))

        QMetaObject.invokeMethod(viewer, "findSelectedText")
        self.app.processEvents()
        self.assertEqual(
            viewer.property("searchText"),
            " ip address 10.0.0.1 255.255.255.0",
        )
        self.assertEqual(viewer.property("currentMatchIndex"), 0)

        QMetaObject.invokeMethod(
            context_menu,
            "openAt",
            Q_ARG("QVariant", 100),
            Q_ARG("QVariant", 100),
        )
        self.app.processEvents()
        self.assertTrue(viewer.property("contextMenuVisible"))
        QMetaObject.invokeMethod(context_menu, "close")
        self.assertFalse(viewer.property("contextMenuVisible"))

        viewer.setProperty("syntaxHighlightCharacterLimit", 1_000_000)
        viewer.setProperty(
            "text",
            "IOSv active\nIOSv standby\nseparator\nIOSv active",
        )
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        for _ in range(8):
            if not viewer.property("highlightingInProgress"):
                break
            QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        viewer.setProperty("searchText", "IOSv")
        QMetaObject.invokeMethod(viewer, "runSearchNow")
        QMetaObject.invokeMethod(viewer, "findNext")
        QTest.qWait(100)
        self.app.processEvents()
        self.assertEqual(viewer.property("matchCount"), 3)
        self.assertEqual(viewer.property("occurrenceCount"), 2)
        occurrence_marker_count_expression = QQmlExpression(
            QQmlEngine.contextForObject(viewer),
            viewer,
            "selectionOccurrenceRepeater.count",
        )
        self.assertEqual(occurrence_marker_count_expression.evaluate()[0], 2)
        for marker_index in range(2):
            marker_width_expression = QQmlExpression(
                QQmlEngine.contextForObject(viewer),
                viewer,
                f"selectionOccurrenceRepeater.itemAt({marker_index}).width",
            )
            marker_height_expression = QQmlExpression(
                QQmlEngine.contextForObject(viewer),
                viewer,
                f"selectionOccurrenceRepeater.itemAt({marker_index}).height",
            )
            self.assertGreater(marker_width_expression.evaluate()[0], 2)
            self.assertGreater(marker_height_expression.evaluate()[0], 0)

        repeated_block = "alpha one\nbeta two"
        viewer.setProperty(
            "text",
            repeated_block + "\nseparator\n" + repeated_block,
        )
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        for _ in range(8):
            if not viewer.property("highlightingInProgress"):
                break
            QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        QMetaObject.invokeMethod(
            viewer,
            "selectLineRange",
            Q_ARG("QVariant", 0),
            Q_ARG("QVariant", 1),
        )
        QMetaObject.invokeMethod(viewer, "findSelectedText")
        self.app.processEvents()
        self.assertEqual(viewer.property("searchText"), repeated_block)
        self.assertEqual(viewer.property("matchCount"), 2)
        self.assertEqual(viewer.property("currentMatchIndex"), 0)
        QMetaObject.invokeMethod(viewer, "findNext")
        self.app.processEvents()
        self.assertEqual(viewer.property("currentMatchIndex"), 1)
        self.assertEqual(
            str(viewer.property("selectedText")).replace("\u2029", "\n"),
            repeated_block,
        )

        viewer.setProperty("syntaxHighlightCharacterLimit", 8)
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        self.assertTrue(viewer.property("highlightingSkippedForLargeText"))
        self.assertFalse(viewer.property("syntaxHighlightingActive"))
        QMetaObject.invokeMethod(
            theme_harness,
            "setSelectionContext",
            Q_ARG("QVariant", 1),
            Q_ARG("QVariant", "#356FD6"),
        )
        self.assertEqual(self.warnings, [])

    def test_config_text_viewer_wraps_long_lines_when_requested(self) -> None:
        viewer = self._create("UI/components/standard/ConfigTextViewer.qml")
        viewer.setProperty("width", 420)
        viewer.setProperty("height", 300)
        viewer.setProperty("wrapLongLines", True)
        viewer.setProperty("smoothVerticalScrolling", True)
        viewer.setProperty(
            "text",
            "access-list 199 permit tcp host 192.0.2.10 host 198.51.100.20 eq 443 "
            * 12,
        )
        self.assertTrue(
            self._wait_until(lambda: not viewer.property("highlightingInProgress"))
        )

        area = viewer.findChild(QObject, "configViewerTextArea")
        line_scroll = viewer.findChild(QObject, "configViewerLineScrollWheelHandler")
        self.assertIsNotNone(area)
        self.assertIsNotNone(line_scroll)
        wraps = QQmlExpression(
            QQmlEngine.contextForObject(area),
            area,
            "positionToRectangle(length - 1).y > positionToRectangle(0).y",
        ).evaluate()[0]
        self.assertTrue(wraps)
        self.assertFalse(line_scroll.property("enabled"))
        self.assertEqual(self.warnings, [])

    def test_config_text_viewer_uses_distinct_semantic_highlight_colors(self) -> None:
        viewer = self._create("UI/components/standard/ConfigTextViewer.qml")
        viewer.setProperty("width", 900)
        viewer.setProperty("height", 560)
        viewer.setProperty(
            "text",
            "\n".join(
                (
                    "ip address 192.168.1.1 255.255.255.0",
                    "network 10.0.0.0 0.0.0.255 area 1",
                    "route 10.0.0.0/24",
                    "interface GigabitEthernet0/0",
                    "metric 42 yes 2026-07-14 12:30:00",
                    "permit deny inside outside",
                    "! comment",
                )
            ),
        )
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        for _ in range(8):
            if not viewer.property("highlightingInProgress"):
                break
            QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        self.app.processEvents()

        palette_properties = (
            "syntaxIpAddressColor",
            "syntaxPrefixColor",
            "syntaxMaskColor",
            "syntaxWildcardColor",
            "syntaxInterfaceColor",
            "syntaxNumberColor",
            "syntaxBooleanColor",
            "syntaxDateTimeColor",
            "syntaxPermitColor",
            "syntaxDenyColor",
            "syntaxInsideColor",
            "syntaxOutsideColor",
            "syntaxCommentColor",
        )
        palette = [viewer.property(name).name().lower() for name in palette_properties]
        highlighted_text = viewer.property("highlightedText").lower()
        self.assertEqual(len(set(palette)), len(palette))
        for color in palette:
            with self.subTest(color=color):
                self.assertIn(f"color:{color}", highlighted_text)

        viewer.setProperty("text", "interface Loopback0\n")
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        for _ in range(4):
            if not viewer.property("highlightingInProgress"):
                break
            QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        self.app.processEvents()
        self.assertEqual(viewer.property("lineCount"), 2)
        self.assertIn("&#8203;", viewer.property("highlightedText"))

        viewer.setProperty("syntaxMode", "diff")
        viewer.setProperty(
            "text",
            "--- running-config@aaaaaaa\n"
            "+++ running-config@bbbbbbb\n"
            "@@ -1 +1 @@\n"
            "-hostname old\n"
            "+hostname new\n",
        )
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        for _ in range(8):
            if not viewer.property("highlightingInProgress"):
                break
            QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        self.app.processEvents()
        diff_highlighted_text = viewer.property("highlightedText").lower()
        for color_property in ("diffAdditionColor", "diffDeletionColor", "diffHunkColor"):
            color = viewer.property(color_property).name().lower()
            with self.subTest(diff_color=color_property):
                self.assertIn(f"color:{color}", diff_highlighted_text)
        self.assertEqual(self.warnings, [])

    def test_config_text_viewer_keeps_edge_lines_inside_viewport_at_zoom_steps(self) -> None:
        """Long lines remain whole at both viewport edges for every representative zoom."""
        viewer = self._create("UI/components/standard/ConfigTextViewer.qml")
        viewer.setProperty("width", 900)
        viewer.setProperty("height", 560)
        viewer.setProperty(
            "text",
            "\n".join(
                f"interface Loopback{index} description {'x' * 180}"
                for index in range(200)
            ),
        )
        self.assertTrue(self._wait_until(lambda: viewer.property("highlightingReady")))

        for zoom_level in (25, 100, 200, 500):
            with self.subTest(zoom=zoom_level):
                QMetaObject.invokeMethod(
                    viewer,
                    "setZoomPercent",
                    Q_ARG("QVariant", zoom_level),
                )
                QTest.qWait(30)
                self.app.processEvents()
                capacity = viewer.property("visibleWholeLineCapacity")
                first_line = 20
                last_line = first_line + capacity - 1
                scroll_position = QQmlExpression(
                    QQmlEngine.contextForObject(viewer),
                    viewer,
                    f"verticalScrollPositionForLine({first_line})",
                ).evaluate()[0]
                QMetaObject.invokeMethod(
                    viewer,
                    "setVerticalScrollPosition",
                    Q_ARG("QVariant", scroll_position),
                )
                self.app.processEvents()

                first_top = QQmlExpression(
                    QQmlEngine.contextForObject(viewer),
                    viewer,
                    f"configTextArea.positionToRectangle(lineStarts[{first_line}]).y - verticalScrollContentY",
                ).evaluate()[0]
                last_bottom = QQmlExpression(
                    QQmlEngine.contextForObject(viewer),
                    viewer,
                    f"configTextArea.positionToRectangle(lineStarts[{last_line}]).y"
                    f" + configTextArea.positionToRectangle(lineStarts[{last_line}]).height"
                    " - verticalScrollContentY",
                ).evaluate()[0]
                viewport_height = viewer.property("codeViewportHeight")
                line_height = viewer.property("codeLineHeight")

                self.assertGreaterEqual(first_top, -0.01)
                self.assertLessEqual(last_bottom, viewport_height + 0.51)
                self.assertLess(viewport_height - last_bottom, line_height)

        self.assertEqual(self.warnings, [])

    def test_config_text_viewer_does_not_reuse_stale_cursor_positions(self) -> None:
        """Replacing a long selected document must not address the old QTextDocument."""
        cursor_messages: list[str] = []
        previous_handler = qInstallMessageHandler(
            lambda _message_type, _context, message: cursor_messages.append(message)
        )
        try:
            viewer = self._create("UI/components/standard/ConfigTextViewer.qml")
            viewer.setProperty("width", 900)
            viewer.setProperty("height", 560)
            viewer.setProperty(
                "text",
                "\n".join(
                    f"interface Loopback{index} description repeated interface marker"
                    for index in range(240)
                ),
            )
            self.assertTrue(self._wait_until(lambda: viewer.property("highlightingReady")))
            text_area = viewer.findChild(QObject, "configViewerTextArea")
            self.assertIsNotNone(text_area)
            self.assertTrue(
                self._wait_until(
                    lambda: text_area.property("length") == len(viewer.property("text"))
                )
            )
            QTest.qWait(30)
            self.app.processEvents()
            viewer.setProperty("searchText", "interface")
            QMetaObject.invokeMethod(viewer, "runSearchNow")
            QMetaObject.invokeMethod(viewer, "selectMatch", Q_ARG("QVariant", 0))
            self.assertTrue(
                self._wait_until(lambda: viewer.property("occurrenceCount") > 100),
                (
                    viewer.property("selectedText"),
                    text_area.property("length"),
                    len(viewer.property("text")),
                    viewer.property("highlightingReady"),
                ),
            )

            viewer.setProperty("text", "hostname short\n")
            self.assertTrue(self._wait_until(lambda: viewer.property("highlightingReady")))
            viewer.setProperty("syntaxMode", "diff")
            viewer.setProperty(
                "text",
                "--- running-config@old\n+++ running-config@new\n@@ -1 +1 @@\n-old\n+new\n",
            )
            self.assertTrue(self._wait_until(lambda: viewer.property("highlightingReady")))
        finally:
            qInstallMessageHandler(previous_handler)

        out_of_range = [
            message
            for message in cursor_messages
            if "QTextCursor::setPosition" in message and "out of range" in message
        ]
        self.assertEqual(out_of_range, [])

    def test_config_text_viewer_highlights_ten_thousand_lines_in_chunks(self) -> None:
        viewer = self._create("UI/components/standard/ConfigTextViewer.qml")
        viewer.setProperty("width", 900)
        viewer.setProperty("height", 560)
        viewer.setProperty("highlightingChunkLineCount", 250)
        large_config = "\n".join(
            f"interface GigabitEthernet0/{index} ip address 10.0.0.1 255.255.255.0 permit inside"
            for index in range(10_000)
        )

        started_at = time.perf_counter()
        viewer.setProperty("text", large_config)
        QMetaObject.invokeMethod(viewer, "startHighlighting")
        self.assertTrue(viewer.property("highlightingInProgress"))
        for _ in range(50):
            if not viewer.property("highlightingInProgress"):
                break
            QMetaObject.invokeMethod(viewer, "processHighlightChunk")
        elapsed = time.perf_counter() - started_at

        self.assertFalse(viewer.property("highlightingInProgress"))
        self.assertTrue(viewer.property("highlightingReady"))
        self.assertEqual(viewer.property("lineCount"), 10_000)
        self.assertLess(elapsed, 8.0)
        self.assertEqual(self.warnings, [])

    def test_information_reload_tracks_activation_and_running_command(self) -> None:
        information = self._create("UI/qml/content/InformationView.qml")
        information.setProperty("width", 900)
        information.setProperty("height", 560)
        information.setProperty("currentHostIp", "192.0.2.10")
        self.app.processEvents()

        reload_button = information.findChild(QObject, "informationReloadButton")
        copy_button = information.findChild(QObject, "informationCopyAllButton")
        self.assertIsNotNone(reload_button)
        self.assertIsNotNone(copy_button)
        self.assertEqual(copy_button.property("y"), reload_button.property("y"))
        self.assertEqual(copy_button.property("height"), reload_button.property("height"))

        self.assertEqual(information.property("lastLoadedHost"), "192.0.2.10")
        self.assertEqual(information.property("lastReloadReason"), "manual")
        QMetaObject.invokeMethod(
            information,
            "reloadData",
            Q_ARG("QVariant", "activation"),
        )
        self.app.processEvents()
        self.assertEqual(information.property("lastReloadReason"), "activation")

        cli = self.context_objects["cli"]
        cli.runningConfigFinished.emit("192.0.2.11", True, "ignored host")
        self.app.processEvents()
        self.assertEqual(information.property("lastReloadReason"), "activation")
        cli.runningConfigFinished.emit("192.0.2.10", True, "backup complete")
        self.app.processEvents()
        self.assertEqual(information.property("lastReloadReason"), "manual")
        self.assertEqual(information.property("lastLoadedHost"), "192.0.2.10")
        db_manager = self.context_objects["dbManager"]
        db_manager.runningConfigUpdated.emit("192.0.2.10")
        self.app.processEvents()
        self.assertEqual(information.property("lastLoadedHost"), "192.0.2.10")
        self.assertEqual(self.warnings, [])

    def test_activity_bar_hides_unavailable_tools_and_keeps_operational_tools_active(self) -> None:
        activity_bar = self._create("UI/qml/layout/ActivityBar.qml")
        activity_bar.setProperty("width", 48)
        activity_bar.setProperty("height", 480)
        self.app.processEvents()

        console_item = activity_bar.findChild(QObject, "consoleSerialActivityItem")
        self.assertIsNone(console_item)
        activity_source = (
            Path(__file__).resolve().parents[1]
            / "UI/qml/layout/ActivityBar.qml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("navigationTopology", activity_source)
        self.assertNotIn("navigationConsoleSerial", activity_source)

        sftp_item = activity_bar.findChild(QObject, "sftpActivityItem")
        self.assertIsNotNone(sftp_item)
        self.assertTrue(sftp_item.property("visible"))
        self.assertTrue(sftp_item.property("enabled"))
        self.assertAlmostEqual(sftp_item.property("opacity"), 1.0)
        self.assertEqual(sftp_item.parent().objectName(), "activityTopGroup")

        syslog_item = activity_bar.findChild(QObject, "syslogActivityItem")
        self.assertIsNotNone(syslog_item)
        self.assertTrue(syslog_item.property("visible"))
        self.assertTrue(syslog_item.property("enabled"))
        self.assertAlmostEqual(syslog_item.property("opacity"), 1.0)
        self.assertEqual(syslog_item.parent().objectName(), "activityTopGroup")

        database_item = activity_bar.findChild(QObject, "databaseActivityItem")
        settings_item = activity_bar.findChild(QObject, "settingsActivityItem")
        self.assertIsNotNone(database_item)
        self.assertIsNotNone(settings_item)
        self.assertEqual(database_item.parent().objectName(), "activityBottomGroup")
        self.assertEqual(settings_item.parent().objectName(), "activityBottomGroup")
        self.assertLess(database_item.property("y"), settings_item.property("y"))
        self.assertEqual(activity_bar.property("activeIndex"), 0)
        self.assertEqual(activity_bar.property("appMode"), "devices")
        self.assertEqual(self.warnings, [])

    def test_database_sidebar_groups_tables_with_semantic_icons(self) -> None:
        panel = self._create("UI/qml/panels/DatabaseTablesPanel.qml")
        panel.setProperty("width", 320)
        panel.setProperty("height", 720)
        self.app.processEvents()

        header = panel.findChild(QObject, "databasePanelHeaderTitle")
        reload_button = panel.findChild(QObject, "databasePanelReloadButton")
        self.assertIsNotNone(header)
        self.assertIsNotNone(reload_button)
        self.assertEqual(header.property("text"), "TABLE")
        self.assertGreater(len(panel.property("tables")), 0, panel.property("tableGroups"))
        groups_value = panel.property("tableGroups")
        groups = groups_value.toVariant() if hasattr(groups_value, "toVariant") else groups_value
        self.assertEqual(len(groups), 9, (groups, self.warnings))
        self.assertEqual({group["key"] for group in groups}, {
            "01", "02", "03", "04", "05", "06", "08", "09", "10"
        })
        self.assertIn("02 - Router Interface", {group["title"] for group in groups})
        self.assertIn("10 - Syslog Configuration", {group["title"] for group in groups})
        domain_colors = {group["color"].name() for group in groups}
        self.assertGreaterEqual(len(domain_colors), 6)

        group_repeater = panel.findChild(QObject, "databaseGroupRepeater")
        self.assertIsNotNone(group_repeater)
        self.assertEqual(group_repeater.property("count"), 9)

        database_item = self._create_with_properties(
            "UI/qml/panels/DatabaseTableItem.qml",
            {
                "tableName": "t05_NAT_DB",
                "groupKey": "05",
                "domainColor": groups[4]["color"],
                "domainIcon": groups[4]["icon"],
            },
        )
        icon_source = database_item.property("tableIconSource")
        icon_text = icon_source.toString() if hasattr(icon_source, "toString") else str(icon_source)
        self.assertIn("vpn.svg", icon_text)
        database_item_source = (APP_DIR / "UI/qml/panels/DatabaseTableItem.qml").read_text(encoding="utf-8")
        database_section_source = (APP_DIR / "UI/qml/panels/DatabaseTableSection.qml").read_text(encoding="utf-8")
        self.assertEqual(database_section_source.count("ThemedIcon {"), 1)
        self.assertIn("AppAssets.navigationChevronDown", database_section_source)
        self.assertIn("AppAssets.navigationChevronRight", database_section_source)
        self.assertNotIn("iconSource: root.groupIcon", database_section_source)
        device_item_source = (APP_DIR / "UI/qml/sidebar/devices/DeviceItem.qml").read_text(encoding="utf-8")
        device_section_source = (APP_DIR / "UI/qml/sidebar/devices/DeviceSection.qml").read_text(encoding="utf-8")
        for source in (
            database_item_source,
            database_section_source,
            device_item_source,
            device_section_source,
        ):
            self.assertIn("height:Theme.listItemHeight", "".join(source.split()))
        self.assertEqual(self.warnings, [])

    def test_database_group_context_menu_collapses_and_expands_every_group(self) -> None:
        harness = self._create("tests/qml/DatabaseGroupsHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))

        panel = harness.findChild(QObject, "databaseGroupsPanel")
        repeater = harness.findChild(QObject, "databaseGroupRepeater")
        menu = harness.findChild(QObject, "panelGroupContextMenu")
        collapse_all = harness.findChild(QObject, "panelGroupCollapseAll")
        expand_all = harness.findChild(QObject, "panelGroupExpandAll")
        self.assertTrue(all((panel, repeater, menu, collapse_all, expand_all)))
        self.assertGreater(repeater.property("count"), 1)

        first_group = QQmlExpression(
            QQmlEngine.contextForObject(repeater),
            repeater,
            "itemAt(0)",
        ).evaluate()[0]
        self.assertIsNotNone(first_group)

        def click_group_header(button: Qt.MouseButton) -> None:
            point = QQmlExpression(
                QQmlEngine.contextForObject(first_group),
                first_group,
                "mapToItem(null, width / 2, Theme.listItemHeight / 2)",
            ).evaluate()[0]
            QTest.mouseClick(
                harness,
                button,
                Qt.KeyboardModifier.NoModifier,
                QPoint(round(point.x()), round(point.y())),
            )
            self.app.processEvents()
            if button == Qt.MouseButton.RightButton:
                QTest.qWait(150)

        def click_menu_item(item: QObject) -> None:
            point = QQmlExpression(
                QQmlEngine.contextForObject(item),
                item,
                "mapToItem(null, width / 2, height / 2)",
            ).evaluate()[0]
            QTest.mouseClick(
                harness,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                QPoint(round(point.x()), round(point.y())),
            )
            self.app.processEvents()

        click_group_header(Qt.MouseButton.RightButton)
        self.assertTrue(menu.property("visible"))
        click_menu_item(collapse_all)
        self.assertTrue(panel.property("allDatabaseGroupsCollapsed"))
        for index in range(repeater.property("count")):
            group = QQmlExpression(
                QQmlEngine.contextForObject(repeater),
                repeater,
                f"itemAt({index})",
            ).evaluate()[0]
            self.assertFalse(group.property("expanded"))

        click_group_header(Qt.MouseButton.LeftButton)
        self.assertTrue(first_group.property("expanded"))
        self.assertFalse(panel.property("allDatabaseGroupsCollapsed"))

        click_group_header(Qt.MouseButton.RightButton)
        self.assertTrue(menu.property("visible"))
        click_menu_item(expand_all)
        self.assertTrue(panel.property("allDatabaseGroupsExpanded"))
        for index in range(repeater.property("count")):
            group = QQmlExpression(
                QQmlEngine.contextForObject(repeater),
                repeater,
                f"itemAt({index})",
            ).evaluate()[0]
            self.assertTrue(group.property("expanded"))

        self.assertEqual(self.warnings, [])

    def test_database_browser_nested_cells_keep_bound_row_scope(self) -> None:
        browser = self._create("UI/qml/content/DatabaseBrowserView.qml")
        browser.setProperty("width", 900)
        browser.setProperty("height", 560)
        self.warnings.clear()
        browser.setProperty("tableData", {
            "columns": ["id", "host", "username", "password", "connection_status"],
            "rows": [{
                "__rowid__": 1,
                "id": 7,
                "host": "192.0.2.10",
                "username": "admin",
                "password": "secret",
                "connection_status": "connected",
            }],
            "editable": True,
            "message": "Loaded test row",
        })
        self.app.processEvents()
        browser.setProperty("editMode", True)
        self.app.processEvents()
        browser.setProperty("editMode", False)
        self.app.processEvents()

        scope_errors = [
            warning for warning in self.warnings
            if "Cannot read property" in warning or "TypeError" in warning
        ]
        self.assertEqual(scope_errors, [], self.warnings)

    def test_syslog_workspace_uses_shared_surfaces_and_handles_missing_backend(self) -> None:
        self.engine.rootContext().setContextProperty("syslogManager", None)
        workspace = self._create("UI/qml/features/syslog/SyslogWorkspace.qml")
        workspace.setProperty("width", 1100)
        workspace.setProperty("height", 760)
        self.app.processEvents()

        self.assertIsNone(workspace.property("backend"))
        self.assertIsNotNone(workspace.findChild(QObject, "syslogControlBar"))
        self.assertIsNotNone(workspace.findChild(QObject, "syslogFilterBar"))
        self.assertIsNotNone(workspace.findChild(QObject, "syslogLogTable"))

    def test_syslog_settings_exposes_safe_log_reset_controls(self) -> None:
        self.engine.rootContext().setContextProperty("syslogManager", None)
        self.engine.rootContext().setContextProperty("syslogSettings", None)
        settings = self._create("UI/qml/features/syslog/SyslogServerSettings.qml")
        self.assertIsNotNone(settings.findChild(QObject, "syslogResetScope"))
        self.assertIsNotNone(settings.findChild(QObject, "syslogResetExportButton"))
        self.assertIsNotNone(settings.findChild(QObject, "syslogResetDataButton"))
        self.assertIsNotNone(
            settings.findChild(QObject, "syslogResetConfirmationDialog")
        )
        self.assertEqual(self.warnings, [])

    def test_sftp_workspace_loads_with_serialized_backend(self) -> None:
        controller = SftpController()
        self.engine.rootContext().setContextProperty("sftpController", controller)
        try:
            workspace = self._create("UI/qml/sftp/SftpView.qml")
            workspace.setProperty("width", 1100)
            workspace.setProperty("height", 760)
            self.assertTrue(
                self._wait_until(lambda: not controller.busy, timeout_ms=5000)
            )
            self.assertIsNotNone(workspace.findChild(QObject, "sftpLocalPanel"))
            self.assertIsNotNone(workspace.findChild(QObject, "sftpRemotePanel"))
            self.assertEqual(controller._pool.maxThreadCount(), 1)

            self.engine.rootContext().setContextProperty("sftpController", None)
            self.app.processEvents()
            self.assertIsNone(workspace.property("backend"))
            self.assertEqual(self.warnings, [])
        finally:
            self.engine.rootContext().setContextProperty("sftpController", None)
            controller.shutdown()

    def test_sftp_mouse_back_and_forward_follow_active_panel_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            second = Path(temp) / "second"
            first.mkdir()
            second.mkdir()
            controller = SftpController()
            self.engine.rootContext().setContextProperty("sftpController", controller)
            try:
                harness = self._create("tests/qml/SftpNavigationHarness.qml")
                self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
                workspace = harness.findChild(QObject, "sftpNavigationWorkspace")
                local_path_field = harness.findChild(QObject, "sftpLocalPathField")
                self.assertIsNotNone(workspace)
                self.assertIsNotNone(local_path_field)

                controller.openLocalDirectory(str(first))
                self.assertTrue(self._wait_until(lambda: not controller.busy))
                controller.openLocalDirectory(str(second))
                self.assertTrue(self._wait_until(lambda: not controller.busy))
                self.assertEqual(Path(controller.localPath), second)
                QMetaObject.invokeMethod(local_path_field, "forceActiveFocus")
                self.app.processEvents()
                self.assertTrue(workspace.property("textInputActive"))

                center = QPoint(
                    round(harness.width() / 2),
                    round(harness.height() / 2),
                )
                QTest.mouseClick(
                    harness,
                    Qt.MouseButton.BackButton,
                    Qt.KeyboardModifier.NoModifier,
                    center,
                )
                self.app.processEvents()
                self.assertEqual(Path(controller.localPath), first)

                QTest.mouseClick(
                    harness,
                    Qt.MouseButton.ForwardButton,
                    Qt.KeyboardModifier.NoModifier,
                    center,
                )
                self.app.processEvents()
                self.assertEqual(Path(controller.localPath), second)
                self.assertEqual(self.warnings, [])
            finally:
                self.engine.rootContext().setContextProperty("sftpController", None)
                controller.shutdown()

    def test_sftp_file_panel_supports_explorer_style_multi_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("alpha.txt", "bravo.txt", "charlie.txt", "delta.txt", "echo.txt"):
                (root / name).write_text(name, encoding="utf-8")

            controller = SftpController()
            self.engine.rootContext().setContextProperty("sftpController", controller)
            try:
                harness = self._create("tests/qml/SftpNavigationHarness.qml")
                self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
                controller.openLocalDirectory(temp)
                self.assertTrue(self._wait_until(lambda: not controller.busy))

                panel = harness.findChild(QObject, "sftpLocalPanel")
                file_list = harness.findChild(QObject, "sftpLocalFileList")
                self.assertIsNotNone(panel)
                self.assertIsNotNone(file_list)
                self.assertTrue(self._wait_until(lambda: file_list.property("count") == 5))

                def click_row(index, modifiers=Qt.KeyboardModifier.NoModifier):
                    row = QQmlExpression(
                        QQmlEngine.contextForObject(file_list),
                        file_list,
                        f"itemAtIndex({index})",
                    ).evaluate()[0]
                    self.assertIsNotNone(row)
                    mapped = QQmlExpression(
                        QQmlEngine.contextForObject(row),
                        row,
                        "mapToItem(null, width / 2, height / 2)",
                    ).evaluate()[0]
                    QTest.mouseClick(
                        harness,
                        Qt.MouseButton.LeftButton,
                        modifiers,
                        QPoint(round(mapped.x()), round(mapped.y())),
                    )
                    self.app.processEvents()

                def selected_rows():
                    value = panel.property("selectedIndices")
                    return value.toVariant() if hasattr(value, "toVariant") else value

                click_row(0)
                self.assertEqual(selected_rows(), [0])
                click_row(2, Qt.KeyboardModifier.ControlModifier)
                self.assertEqual(selected_rows(), [0, 2])
                click_row(4, Qt.KeyboardModifier.ShiftModifier)
                self.assertEqual(selected_rows(), [2, 3, 4])

                QTest.keyClick(
                    harness,
                    Qt.Key.Key_A,
                    Qt.KeyboardModifier.ControlModifier,
                )
                self.app.processEvents()
                self.assertEqual(selected_rows(), [0, 1, 2, 3, 4])
                self.assertEqual(panel.property("selectedCount"), 5)
                self.assertEqual(self.warnings, [])
            finally:
                self.engine.rootContext().setContextProperty("sftpController", None)
                controller.shutdown()

    def test_sftp_right_click_preserves_selection_and_opens_file_menu(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("alpha.txt", "bravo.txt", "charlie.txt"):
                (root / name).write_text(name, encoding="utf-8")

            controller = SftpController()
            self.engine.rootContext().setContextProperty("sftpController", controller)
            try:
                harness = self._create("tests/qml/SftpNavigationHarness.qml")
                self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
                controller.openLocalDirectory(temp)
                self.assertTrue(self._wait_until(lambda: not controller.busy))

                panel = harness.findChild(QObject, "sftpLocalPanel")
                file_list = harness.findChild(QObject, "sftpLocalFileList")
                menu = harness.findChild(QObject, "sftpLocalFileContextMenu")
                self.assertIsNotNone(panel)
                self.assertIsNotNone(file_list)
                self.assertIsNotNone(menu)
                self.assertTrue(self._wait_until(lambda: file_list.property("count") == 3))

                def click_row(index, button, modifiers=Qt.KeyboardModifier.NoModifier):
                    row = QQmlExpression(
                        QQmlEngine.contextForObject(file_list),
                        file_list,
                        f"itemAtIndex({index})",
                    ).evaluate()[0]
                    mapped = QQmlExpression(
                        QQmlEngine.contextForObject(row),
                        row,
                        "mapToItem(null, width / 2, height / 2)",
                    ).evaluate()[0]
                    QTest.mouseClick(
                        harness,
                        button,
                        modifiers,
                        QPoint(round(mapped.x()), round(mapped.y())),
                    )
                    self.app.processEvents()

                def selected_rows():
                    value = panel.property("selectedIndices")
                    return value.toVariant() if hasattr(value, "toVariant") else value

                click_row(0, Qt.MouseButton.LeftButton)
                click_row(
                    2,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.ControlModifier,
                )
                click_row(2, Qt.MouseButton.RightButton)
                self.assertTrue(menu.property("visible"))
                menu_lock = QQmlExpression(
                    QQmlEngine.contextForObject(menu),
                    menu,
                    "UiState.windowLock",
                ).evaluate()[0]
                self.assertFalse(menu_lock)
                self.assertEqual(selected_rows(), [0, 2])
                self.assertEqual(menu.property("selectedCount"), 2)
                rename_item = menu.findChild(QObject, "sftpContextRename")
                delete_item = menu.findChild(QObject, "sftpContextDelete")
                self.assertFalse(rename_item.property("enabled"))
                self.assertTrue(delete_item.property("enabled"))

                QMetaObject.invokeMethod(menu, "close")
                self.app.processEvents()
                click_row(1, Qt.MouseButton.RightButton)
                self.assertEqual(selected_rows(), [1])
                self.assertTrue(rename_item.property("enabled"))
                self.assertEqual(self.warnings, [])
            finally:
                self.engine.rootContext().setContextProperty("sftpController", None)
                controller.shutdown()

    def test_sftp_shortcuts_do_not_conflict_with_hidden_device_commands(self) -> None:
        controller = SftpController()
        self.engine.rootContext().setContextProperty("sftpController", controller)
        try:
            harness = self._create("tests/qml/SftpShortcutConflictHarness.qml")
            self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
            workspace = harness.findChild(QObject, "sftpShortcutWorkspace")
            local_panel = harness.findChild(QObject, "sftpLocalPanel")
            entry_dialog = harness.findChild(QObject, "sftpLocalEntryDialog")
            self.assertIsNotNone(workspace)
            self.assertIsNotNone(local_panel)
            self.assertIsNotNone(entry_dialog)
            self.assertFalse(entry_dialog.property("visible"))

            QTest.keyClick(
                harness,
                Qt.Key.Key_N,
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.ShiftModifier,
            )
            self.assertTrue(
                self._wait_until(lambda: entry_dialog.property("visible"))
            )
            self.assertEqual(local_panel.property("editMode"), "create")

            QMetaObject.invokeMethod(entry_dialog, "reject")
            self.assertTrue(
                self._wait_until(lambda: not entry_dialog.property("visible"))
            )

            QTest.keyClick(
                harness,
                Qt.Key.Key_R,
                Qt.KeyboardModifier.ControlModifier,
            )
            self.app.processEvents()
            self.assertEqual(harness.property("reloadCount"), 1)
            self.assertEqual(self.warnings, [])
        finally:
            self.engine.rootContext().setContextProperty("sftpController", None)
            controller.shutdown()

    def test_sftp_profile_dialog_only_saves_password_after_explicit_opt_in(self) -> None:
        class MemoryCredentialStore:
            available = True

            def __init__(self):
                self.values = {}

            def has(self, profile_id):
                return profile_id in self.values

            def read(self, profile_id):
                return self.values.get(profile_id, "")

            def write(self, profile_id, password):
                self.values[profile_id] = password

            def delete(self, profile_id):
                self.values.pop(profile_id, None)

        with tempfile.TemporaryDirectory() as temp:
            store = MemoryCredentialStore()
            controller = SftpController(
                settings=QSettings(
                    str(Path(temp) / "dialog.ini"), QSettings.Format.IniFormat
                ),
                credential_store=store,
            )
            self.engine.rootContext().setContextProperty("sftpController", controller)
            try:
                harness = self._create("tests/qml/SftpConnectionDialogHarness.qml")
                self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
                dialog = harness.findChild(
                    QObject, "sftpConnectionDialogHarnessDialog"
                )
                host_field = harness.findChild(QObject, "sftpProfileHostField")
                user_field = harness.findChild(QObject, "sftpProfileUserField")
                password_field = harness.findChild(
                    QObject, "sftpProfilePasswordField"
                )
                save_password = harness.findChild(
                    QObject, "sftpSavePasswordCheck"
                )
                save_button = harness.findChild(QObject, "sftpProfileSaveButton")
                for item in (
                    dialog,
                    host_field,
                    user_field,
                    password_field,
                    save_password,
                    save_button,
                ):
                    self.assertIsNotNone(item)

                QMetaObject.invokeMethod(dialog, "open")
                host_field.setProperty("text", "192.0.2.45")
                user_field.setProperty("text", "operator")
                save_password.setProperty("checked", True)
                password_field.setProperty("text", "dialog-secret")
                self.app.processEvents()

                mapped = QQmlExpression(
                    QQmlEngine.contextForObject(save_button),
                    save_button,
                    "mapToItem(null, width / 2, height / 2)",
                ).evaluate()[0]
                QTest.mouseClick(
                    harness,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                    QPoint(round(mapped.x()), round(mapped.y())),
                )
                self.app.processEvents()

                self.assertEqual(len(controller.savedConnections), 1)
                profile = controller.savedConnections[0]
                self.assertTrue(profile["passwordSaved"])
                self.assertEqual(store.read(profile["id"]), "dialog-secret")
                self.assertNotIn("password", profile)
                self.assertEqual(self.warnings, [])
            finally:
                self.engine.rootContext().setContextProperty("sftpController", None)
                controller.shutdown()

    def test_sftp_sidebar_and_settings_load_with_shared_backend(self) -> None:
        controller = SftpController()
        self.engine.rootContext().setContextProperty("sftpController", controller)
        try:
            sidebar = self._create("UI/qml/panels/PanelSideBar.qml")
            sidebar.setProperty("width", 300)
            sidebar.setProperty("height", 720)
            sidebar.setProperty("appMode", "sftp")

            settings = self._create("UI/qml/content/SettingsView.qml")
            settings.setProperty("width", 1000)
            settings.setProperty("height", 720)
            settings.setProperty("activeSettingKey", "sftp")
            self.app.processEvents()

            self.assertEqual(sidebar.property("appMode"), "sftp")
            self.assertIsNotNone(settings.findChild(QObject, "sftpSettings"))
            self.assertEqual(self.warnings, [])
        finally:
            self.engine.rootContext().setContextProperty("sftpController", None)
            controller.shutdown()

    def test_external_tool_catalog_loads_as_a_read_only_vendor_catalog(self) -> None:
        catalog = self._create(
            "UI/qml/content/ExternalToolCatalogSettings.qml"
        )
        catalog.setProperty("width", 1100)
        catalog.setProperty("height", 760)
        self.app.processEvents()

        self.assertEqual(catalog.property("objectName"), "externalToolCatalogSettings")
        self.assertGreater(len(catalog.property("catalog")), 0)
        application_rows = catalog.property("applicationRows")
        if hasattr(application_rows, "toVariant"):
            application_rows = application_rows.toVariant()
        self.assertGreater(len(application_rows), 0)
        for object_name in (
            "externalToolCatalogSplit",
            "externalToolCatalogCategoryList",
            "externalToolCatalogApplicationList",
            "externalToolCatalogSearchField",
        ):
            with self.subTest(object_name=object_name):
                self.assertIsNotNone(catalog.findChild(QObject, object_name))
        self.assertEqual(self.warnings, [])

    def test_notification_center_copy_layout_and_dnd_controls(self) -> None:
        copy_button = self._create("UI/components/standard/CopyButton.qml")
        message = "Device R1 configuration completed"
        copy_button.setProperty("textToCopy", message)
        QApplication.clipboard().clear()

        QMetaObject.invokeMethod(copy_button, "copyText")
        self.app.processEvents()

        self.assertEqual(QApplication.clipboard().text(), message)
        self.assertTrue(copy_button.property("copied"))

        notification_harness = self._create("tests/qml/NotificationCopyHarness.qml")
        toast_manager = notification_harness.findChild(QObject, "testToastManager")
        notification_center = notification_harness.findChild(QObject, "testNotificationCenter")
        dnd_button = notification_harness.findChild(QObject, "notificationDndButton")
        dnd_icon = notification_harness.findChild(QObject, "notificationDndButtonIcon")
        header_text = notification_harness.findChild(QObject, "notificationHeaderText")

        self.assertIsNotNone(toast_manager)
        self.assertIsNotNone(notification_center)
        self.assertIsNotNone(dnd_button)
        self.assertIsNotNone(dnd_icon)
        self.assertIsNotNone(header_text)
        self.assertIsNone(notification_harness.findChild(QObject, "toastCopyButton"))

        icon_parent = dnd_icon.parent()
        self.assertAlmostEqual(
            dnd_icon.property("x") + dnd_icon.property("width") / 2,
            icon_parent.property("width") / 2,
        )
        self.assertAlmostEqual(
            dnd_icon.property("y") + dnd_icon.property("height") / 2,
            icon_parent.property("height") / 2,
        )

        populated_height = notification_harness.property("notificationPanelHeight")
        self.assertGreater(populated_height, 96)
        self.assertLessEqual(populated_height, 400)

        QMetaObject.invokeMethod(notification_harness, "clearHistory")
        self.app.processEvents()
        self.assertEqual(notification_harness.property("notificationPanelHeight"), 44)
        self.assertEqual(header_text.property("text"), "No New Notifications")
        self.assertIsNone(notification_harness.findChild(QObject, "emptyNotificationText"))

        for index in range(12):
            QMetaObject.invokeMethod(
                notification_harness,
                "addHistory",
                Q_ARG("QVariant", f"Notification {index + 1} with enough content to verify scrolling."),
                Q_ARG("QVariant", "warning" if index % 3 == 0 else "info"),
            )
        self.app.processEvents()
        self.assertEqual(notification_center.property("notificationCount"), 12)
        self.assertEqual(header_text.property("text"), "Notifications")
        self.assertEqual(notification_harness.property("notificationPanelHeight"), 400)
        self.assertTrue(notification_center.property("hasScrollableOverflow"))

        QMetaObject.invokeMethod(notification_harness, "clearHistory")
        QMetaObject.invokeMethod(
            notification_harness,
            "addActionHistory",
            Q_ARG("QVariant", "External Tools needs configuration."),
        )
        self.app.processEvents()
        QMetaObject.invokeMethod(
            notification_center,
            "triggerActionAt",
            Q_ARG("QVariant", 0),
        )
        self.app.processEvents()
        self.assertEqual(notification_harness.property("lastActionId"), "open-settings")
        self.assertEqual(
            notification_harness.property("lastActionData"),
            "external_tools",
        )
        self.assertEqual(notification_center.property("notificationCount"), 0)

        for message in ("First dismissible notification", "Second notification"):
            QMetaObject.invokeMethod(
                notification_harness,
                "addHistory",
                Q_ARG("QVariant", message),
                Q_ARG("QVariant", "info"),
            )
        QMetaObject.invokeMethod(
            notification_center,
            "dismissAt",
            Q_ARG("QVariant", 0),
        )
        self.app.processEvents()
        self.assertEqual(notification_center.property("notificationCount"), 1)

        QMetaObject.invokeMethod(dnd_button, "clicked")
        self.app.processEvents()
        self.assertTrue(notification_harness.property("doNotDisturb"))
        self.assertFalse(dnd_button.property("checked"))
        self.assertFalse(dnd_button.property("_selected"))

        notification_harness.setProperty("visible", False)
        self.assertEqual(self.warnings, [])

    def test_status_bar_dnd_indicator_blinks_only_for_unread(self) -> None:
        status_bar = self._create("UI/qml/layout/StatusBar.qml")
        notification_button = status_bar.findChild(QObject, "statusBarNotificationButton")
        self.assertIsNotNone(notification_button)

        status_bar.setProperty("isDND", True)
        status_bar.setProperty("unreadCount", 1)
        status_bar.setProperty("isNotificationOpen", False)
        self.app.processEvents()

        self.assertTrue(status_bar.property("notificationShouldBlink"))
        self.assertTrue(
            str(notification_button.property("iconSource")).endswith(
                "/resources/status/do-not-disturb.svg"
            )
        )

        status_bar.setProperty("isNotificationOpen", True)
        self.app.processEvents()
        self.assertFalse(status_bar.property("notificationShouldBlink"))
        self.assertEqual(self.warnings, [])

    def test_status_bar_task_progress_supports_indeterminate_and_measured_work(self) -> None:
        status_bar = self._create("UI/qml/layout/StatusBar.qml")
        progress = status_bar.findChild(QObject, "statusBarTaskProgress")
        self.assertIsNotNone(progress)

        status_bar.setProperty("taskVisible", True)
        status_bar.setProperty("taskBusy", True)
        status_bar.setProperty("taskProgress", -1.0)
        self.app.processEvents()
        self.assertTrue(progress.property("indeterminate"))

        status_bar.setProperty("taskProgress", 0.5)
        self.app.processEvents()
        self.assertFalse(progress.property("indeterminate"))
        self.assertAlmostEqual(progress.property("value"), 0.5)

        status_bar.setProperty("taskBusy", False)
        status_bar.setProperty("taskProgress", 1.0)
        self.app.processEvents()
        self.assertFalse(progress.property("indeterminate"))
        self.assertAlmostEqual(progress.property("value"), 1.0)
        self.assertEqual(self.warnings, [])

    def test_device_operation_badge_only_shows_known_transient_states(self) -> None:
        badge = self._create("UI/qml/sidebar/devices/DeviceOperationBadge.qml")

        self.assertFalse(badge.property("knownState"))
        for state, symbol in (
            ("queued", "…"),
            ("running", "↻"),
            ("success", "✓"),
            ("warning", "!"),
            ("error", "×"),
            ("cancelled", "–"),
        ):
            badge.setProperty("state", state)
            self.app.processEvents()
            self.assertTrue(badge.property("knownState"), state)
            self.assertEqual(badge.property("symbol"), symbol)

        badge.setProperty("state", "unexpected")
        self.app.processEvents()
        self.assertFalse(badge.property("knownState"))
        self.assertEqual(self.warnings, [])

    def test_action_icon_dialogs_and_menu_load(self) -> None:
        for relative_path in (
            "UI/qml/sidebar/new_device/NewDevice.qml",
            "UI/qml/sidebar/new_device/BatchNewDevice.qml",
            "UI/qml/sidebar/devices/DeviceContextMenu.qml",
            "UI/components/standard/ConfigTextContextMenu.qml",
            "UI/qml/shared/ViewPushDialog.qml",
        ):
            with self.subTest(qml=relative_path):
                component = self._create(relative_path)
                component.setProperty("visible", False)
                self.app.processEvents()
        self.assertEqual(self.warnings, [])

    def test_view_push_long_failure_output_stays_in_scrollable_preview(self) -> None:
        dialog = self._create("UI/qml/shared/ViewPushDialog.qml")
        long_output = "ACL push failed:\n" + "\n".join(
            f"R4(config-ext-nacl)#no {index}" for index in range(300)
        )
        expression = QQmlExpression(
            QQmlEngine.contextForObject(dialog),
            dialog,
            f"finishPush(false, {json.dumps(long_output)})",
        )
        expression.evaluate()
        self.app.processEvents()

        self.assertFalse(expression.hasError(), expression.error().toString())
        self.assertEqual(dialog.property("previewText"), long_output)
        self.assertEqual(
            dialog.property("messageText"),
            "Configuration push failed. Review the device output below.",
        )
        status = dialog.findChild(QObject, "viewPushStatusMessage")
        self.assertIsNotNone(status)
        self.assertLessEqual(status.property("lineCount"), 3)
        self.assertEqual(self.warnings, [])

    def test_multi_host_view_push_tracks_progress_and_locks_actions(self) -> None:
        dialog = self._create("UI/qml/shared/MultiHostViewPushDialog.qml")
        expression = QQmlExpression(
            QQmlEngine.contextForObject(dialog),
            dialog,
            """
            hosts = ["r1", "r2", "r3"];
            pendingPreviews = ({r1: true, r2: true, r3: true});
            recordPreview("r1", true, "Ready", "show running-config");
            pushTargetCount = 3;
            pendingHosts = ({r1: true, r2: true, r3: true});
            isPushing = true;
            recordResult("r1", true, "Done");
            """,
        )
        expression.evaluate()
        self.app.processEvents()

        self.assertFalse(expression.hasError(), expression.error().toString())
        progress = dialog.findChild(QObject, "multiHostViewPushProgress")
        push_button = dialog.findChild(QObject, "multiHostViewPushPushButton")
        close_button = dialog.findChild(QObject, "multiHostViewPushCloseButton")
        self.assertIsNotNone(progress)
        self.assertIsNotNone(push_button)
        self.assertIsNotNone(close_button)
        self.assertEqual(progress.property("value"), 1)
        self.assertEqual(progress.property("to"), 3)
        self.assertFalse(push_button.property("enabled"))
        self.assertFalse(close_button.property("enabled"))
        self.assertEqual(self.warnings, [])

    def test_main_module_loads(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        self.assertEqual(len(self.engine.rootObjects()), 1)
        window = self.engine.rootObjects()[0]
        self.assertEqual(window.property("workspaceDisplayName"), "")
        self.assertEqual(window.property("title"), "NetworkTools")
        self.assertEqual(self.warnings, [])

    def test_welcome_module_loads_as_independent_entry_window(self) -> None:
        self.engine.loadFromModule("UI", "Welcome")
        self.app.processEvents()

        self.assertEqual(len(self.engine.rootObjects()), 1)
        window = self.engine.rootObjects()[0]
        self.assertEqual(window.objectName(), "welcomeWindow")
        self.assertIsNotNone(window.findChild(QObject, "welcomeCreateProjectButton"))
        self.assertIsNotNone(window.findChild(QObject, "welcomeOpenProjectButton"))
        self.assertIsNotNone(window.findChild(QObject, "welcomeSettingsButton"))
        self.assertIsNotNone(window.findChild(QObject, "welcomeRecentProjectList"))
        self.assertIsNotNone(window.findChild(QObject, "welcomeCommandRegistry"))
        self.assertIsNotNone(window.findChild(QObject, "welcomeProjectLocationField"))
        self.assertIsNotNone(
            window.findChild(QObject, "welcomeProjectLocationBrowseButton")
        )
        self.assertIsNotNone(
            window.findChild(QObject, "welcomeSetDefaultProjectLocationCheck")
        )
        self.assertEqual(self.warnings, [])

    def test_main_window_exposes_modern_menu_bar(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()

        window = self.engine.rootObjects()[0]
        self.assertTrue(window.flags() & Qt.WindowType.FramelessWindowHint)
        self.assertIsNotNone(window.findChild(QObject, "workspaceTitleBar"))
        self.assertIsNotNone(window.findChild(QObject, "modernMenuBar"))
        self.assertIsNotNone(window.findChild(QObject, "windowMinimizeButton"))
        self.assertIsNotNone(window.findChild(QObject, "windowMaximizeButton"))
        self.assertIsNotNone(window.findChild(QObject, "windowCloseButton"))
        self.assertEqual(self.warnings, [])

    def test_main_sidebar_snaps_closed_and_open_at_vscode_threshold(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        self.assertEqual(len(self.engine.rootObjects()), 1)
        window = self.engine.rootObjects()[0]
        self.assertTrue(QTest.qWaitForWindowExposed(window, 1000))

        resize_area = window.findChild(QObject, "sidebarResizeArea")
        sidebar = window.findChild(QObject, "mainPanelSideBar")
        title_bar = window.findChild(QObject, "workspaceTitleBar")
        self.assertIsNotNone(resize_area)
        self.assertIsNotNone(sidebar)
        self.assertIsNotNone(title_bar)
        self.assertGreaterEqual(
            float(resize_area.property("y")),
            float(title_bar.property("height")),
        )

        def center_point() -> QPoint:
            mapped = QQmlExpression(
                QQmlEngine.contextForObject(resize_area),
                resize_area,
                "mapToItem(null, width / 2, height / 2)",
            ).evaluate()[0]
            return QPoint(round(mapped.x()), round(mapped.y()))

        minimum = float(window.property("minSidebarWidth"))
        threshold = float(window.property("sidebarSnapThreshold"))
        self.assertEqual(minimum, 170)
        self.assertEqual(threshold, minimum / 2)

        start = center_point()
        initial_width = float(sidebar.property("width"))
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            start,
        )
        collapse_point = QPoint(
            round(start.x() - initial_width + threshold - 1),
            start.y(),
        )
        QTest.mouseMove(window, collapse_point, 10)
        self.app.processEvents()
        self.assertFalse(window.property("sidebarVisible"))
        self.assertEqual(sidebar.property("width"), 0)
        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            collapse_point,
        )

        collapsed = center_point()
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            collapsed,
        )
        restore_point = QPoint(round(collapsed.x() + threshold), collapsed.y())
        QTest.mouseMove(window, restore_point, 10)
        self.app.processEvents()
        self.assertTrue(window.property("sidebarVisible"))
        self.assertEqual(sidebar.property("width"), minimum)
        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            restore_point,
        )
        self.app.processEvents()
        self.assertEqual(window.property("savedSidebarWidth"), minimum)
        self.assertEqual(self.warnings, [])

    def test_main_sidebar_reserves_the_minimum_workspace_width(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        self.assertEqual(len(self.engine.rootObjects()), 1)
        window = self.engine.rootObjects()[0]
        self.assertTrue(QTest.qWaitForWindowExposed(window, 1000))
        window.showNormal()
        window.setProperty("width", 1024)
        window.setProperty("height", 700)
        window.setProperty("savedSidebarWidth", 600)
        QQmlExpression(
            QQmlEngine.contextForObject(window),
            window,
            "showSidebar()",
        ).evaluate()
        self.assertTrue(
            self._wait_until(
                lambda: abs(float(window.property("width")) - 1024) < 0.5
            )
        )
        self.assertEqual(float(window.property("effectiveMaxSidebarWidth")), 335)
        self.assertEqual(float(window.property("sidebarWidth")), 335)
        self.assertGreaterEqual(
            float(window.property("workspaceContentWidth")),
            640,
        )

        window.setProperty("width", 1440)
        self.assertTrue(
            self._wait_until(
                lambda: float(window.property("sidebarWidth")) == 600
            )
        )
        self.assertGreaterEqual(
            float(window.property("workspaceContentWidth")),
            640,
        )
        self.assertEqual(self.warnings, [])

    def test_responsive_controls_wrap_compact_and_keep_inputs_usable(self) -> None:
        harness = self._create("tests/qml/ResponsiveControlsHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))

        button = harness.findChild(QObject, "responsiveCompactButton")
        label = harness.findChild(QObject, "responsiveCompactButtonLabel")
        control_bar = harness.findChild(QObject, "responsiveSyslogControlBar")
        control_layout = harness.findChild(QObject, "syslogControlLayout")
        filter_bar = harness.findChild(QObject, "responsiveSyslogFilterBar")
        filter_layout = harness.findChild(QObject, "syslogFilterLayout")
        search = harness.findChild(QObject, "syslogMessageSearch")
        severity = harness.findChild(QObject, "syslogSeverityFilter")
        protocol = harness.findChild(QObject, "syslogProtocolFilter")
        self.assertTrue(all((
            button,
            label,
            control_bar,
            control_layout,
            filter_bar,
            filter_layout,
            search,
            severity,
            protocol,
        )))

        self.assertTrue(button.property("compactContent"))
        self.assertFalse(label.property("visible"))
        self.assertEqual(float(button.property("width")), 34)
        self.assertGreaterEqual(
            float(control_bar.property("height")),
            float(control_layout.property("implicitHeight")) + 24,
        )
        self.assertGreaterEqual(
            float(filter_bar.property("height")),
            float(filter_layout.property("implicitHeight")) + 24,
        )
        self.assertGreaterEqual(float(search.property("width")), 120)
        self.assertGreaterEqual(float(severity.property("width")), 120)
        self.assertGreaterEqual(float(protocol.property("width")), 120)

        for object_name in (
            "syslogListenerButton",
            "syslogMessageSearch",
            "syslogSeverityFilter",
            "syslogProtocolFilter",
            "syslogHostFilterChip",
            "syslogResetFiltersButton",
        ):
            item = harness.findChild(QObject, object_name)
            self.assertIsNotNone(item)
            contained = QQmlExpression(
                QQmlEngine.contextForObject(item),
                item,
                "x >= -0.5 && x + width <= parent.width + 0.5",
            ).evaluate()[0]
            with self.subTest(item=object_name):
                self.assertTrue(contained)
                self.assertGreater(float(item.property("width")), 0)
        self.assertEqual(self.warnings, [])

    def test_sftp_toolbar_keeps_full_labels_when_workspace_is_wide(self) -> None:
        harness = self._create("tests/qml/SftpNavigationHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))

        for object_name in (
            "sftpLocalNewFolderButton",
            "sftpLocalRenameButton",
            "sftpLocalDeleteButton",
            "sftpLocalTransferButton",
            "sftpRemoteNewFolderButton",
            "sftpRemoteRenameButton",
            "sftpRemoteDeleteButton",
            "sftpRemoteTransferButton",
        ):
            button = harness.findChild(QObject, object_name)
            label = harness.findChild(QObject, object_name + "Label")
            self.assertIsNotNone(button, object_name)
            self.assertIsNotNone(label, object_name + "Label")
            with self.subTest(button=object_name):
                self.assertFalse(button.property("compactContent"))
                self.assertTrue(label.property("visible"))
                self.assertGreaterEqual(
                    float(button.property("width")) + 0.5,
                    float(button.property("expandedImplicitWidth")),
                )
                self.assertGreaterEqual(
                    float(label.property("width")) + 0.5,
                    float(label.property("contentWidth")),
                )

        self.assertEqual(self.warnings, [])

    def test_open_editors_stays_below_devices_and_group_menu_controls_all(self) -> None:
        harness = self._create("tests/qml/DeviceGroupsHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))

        panel = harness.findChild(QObject, "deviceGroupsPanel")
        device_scroll = harness.findChild(QObject, "deviceGroupScrollView")
        open_editors = harness.findChild(QObject, "openEditorsSection")
        connected = harness.findChild(QObject, "connectedDeviceGroup")
        menu = harness.findChild(QObject, "panelGroupContextMenu")
        collapse_all = harness.findChild(QObject, "panelGroupCollapseAll")
        expand_all = harness.findChild(QObject, "panelGroupExpandAll")
        self.assertTrue(
            all(
                (
                    panel,
                    device_scroll,
                    open_editors,
                    connected,
                    menu,
                    collapse_all,
                    expand_all,
                )
            )
        )
        self.assertGreaterEqual(
            float(open_editors.property("y")) + 0.5,
            float(device_scroll.property("y")) + float(device_scroll.property("height")),
        )
        self.assertAlmostEqual(
            float(open_editors.property("y")) + float(open_editors.property("height")),
            float(panel.property("height")),
            delta=1.0,
        )

        header_point = QQmlExpression(
            QQmlEngine.contextForObject(connected),
            connected,
            "mapToItem(null, width / 2, Theme.listItemHeight / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(header_point.x()), round(header_point.y())),
        )
        self.app.processEvents()
        self.assertTrue(menu.property("visible"))

        collapse_point = QQmlExpression(
            QQmlEngine.contextForObject(collapse_all),
            collapse_all,
            "mapToItem(null, width / 2, height / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(collapse_point.x()), round(collapse_point.y())),
        )
        self.app.processEvents()
        self.assertTrue(panel.property("allDeviceGroupsCollapsed"))

        header_point = QQmlExpression(
            QQmlEngine.contextForObject(connected),
            connected,
            "mapToItem(null, width / 2, Theme.listItemHeight / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(header_point.x()), round(header_point.y())),
        )
        self.app.processEvents()
        self.assertTrue(menu.property("visible"))

        expand_point = QQmlExpression(
            QQmlEngine.contextForObject(expand_all),
            expand_all,
            "mapToItem(null, width / 2, height / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(expand_point.x()), round(expand_point.y())),
        )
        self.app.processEvents()
        self.assertTrue(panel.property("allDeviceGroupsExpanded"))
        self.assertEqual(self.warnings, [])

    def test_information_and_split_forms_adapt_at_compact_width(self) -> None:
        information = self._create("tests/qml/InformationResponsiveHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(information, 1000))
        view = information.findChild(QObject, "informationView")
        card = information.findChild(QObject, "informationVersionCard")
        controls = information.findChild(QObject, "informationVersionControls")
        commit_combo = information.findChild(
            QObject,
            "informationCommitHistoryComboBox",
        )
        self.assertTrue(all((view, card, controls, commit_combo)))
        self.assertTrue(view.property("compactLayout"))
        self.assertGreaterEqual(
            float(card.property("height")),
            float(controls.property("implicitHeight")) + 16,
        )
        combo_contained = QQmlExpression(
            QQmlEngine.contextForObject(commit_combo),
            commit_combo,
            "x >= -0.5 && x + width <= parent.width + 0.5",
        ).evaluate()[0]
        self.assertTrue(combo_contained)
        self.assertGreaterEqual(float(commit_combo.property("width")), 120)

        responsive_forms = (
            ("UI/qml/features/acl/AclForm.qml", "aclResponsiveSplit"),
            (
                "UI/qml/features/interfaces/InterfaceView.qml",
                "interfaceResponsiveSplit",
            ),
            (
                "UI/qml/features/dhcp/DhcpPoolForm.qml",
                "dhcpPoolResponsiveSplit",
            ),
            (
                "UI/qml/features/nat/NatStaticForm.qml",
                "natStaticResponsiveSplit",
            ),
        )
        for relative_path, split_name in responsive_forms:
            form = self._create_with_properties(
                relative_path,
                {"width": 640, "height": 700},
            )
            split = form.findChild(QObject, split_name)
            with self.subTest(qml=relative_path):
                self.assertTrue(form.property("compactLayout"))
                self.assertIsNotNone(split)
                self.assertEqual(
                    split.property("orientation"),
                    Qt.Orientation.Vertical,
                )

        scroll_harness = self._create("tests/qml/SplitFormPaneScrollHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(scroll_harness, 1000))
        split_pane = scroll_harness.findChild(QObject, "splitFormPaneUnderTest")
        pane_scroll = scroll_harness.findChild(QObject, "splitFormPaneScroll")
        self.assertIsNotNone(split_pane)
        self.assertIsNotNone(pane_scroll)
        self.assertTrue(split_pane.property("contentOverflow"))
        self.assertGreater(
            float(split_pane.property("scrollContentHeight")),
            float(split_pane.property("viewportHeight")),
        )
        self.assertEqual(self.warnings, [])

    def test_feature_dropdown_bound_delegate_has_no_modeldata_errors(self) -> None:
        harness = self._create("tests/qml/FeatureDropdownHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
        dropdown = harness.findChild(QObject, "featureDropdownUnderTest")
        self.assertIsNotNone(dropdown)
        self.assertTrue(dropdown.property("visible"))
        self.assertFalse(
            any("modelData is not defined" in warning for warning in self.warnings)
        )
        self.assertEqual(self.warnings, [])

    def test_command_registry_dispatches_only_available_context(self) -> None:
        harness = self._create("tests/qml/CommandRegistryHarness.qml")

        for key, modifiers, counter in (
            (
                Qt.Key.Key_O,
                Qt.KeyboardModifier.ControlModifier,
                "openProjectCount",
            ),
            (Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier, "saveCount"),
            (
                Qt.Key.Key_B,
                Qt.KeyboardModifier.ControlModifier,
                "sidebarToggleCount",
            ),
        ):
            QTest.keyClick(harness, key, modifiers)
            self.app.processEvents()
            self.assertEqual(harness.property(counter), 1)

        QTest.keyClick(
            harness,
            Qt.Key.Key_R,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(harness.property("reloadCount"), 1)

        for key, counter in (
            (Qt.Key.Key_D, "dashboardCount"),
            (Qt.Key.Key_F, "sftpCount"),
            (Qt.Key.Key_L, "systemLogsCount"),
            (Qt.Key.Key_B, "databaseCount"),
        ):
            QTest.keyClick(
                harness,
                key,
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier,
            )
            self.app.processEvents()
            self.assertEqual(harness.property(counter), 1)

        QTest.keyClick(
            harness,
            Qt.Key.Key_Comma,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(harness.property("settingsCount"), 1)

        QTest.keyClick(
            harness,
            Qt.Key.Key_K,
            Qt.KeyboardModifier.ControlModifier,
        )
        QTest.keyClick(
            harness,
            Qt.Key.Key_S,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(harness.property("shortcutGuideCount"), 1)

        harness.setProperty("inputFocusActive", True)
        QTest.keyClick(harness, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(
            harness,
            Qt.Key.Key_D,
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier,
        )
        QTest.keyClick(
            harness,
            Qt.Key.Key_Comma,
            Qt.KeyboardModifier.ControlModifier,
        )
        QTest.keyClick(
            harness,
            Qt.Key.Key_K,
            Qt.KeyboardModifier.ControlModifier,
        )
        QTest.keyClick(
            harness,
            Qt.Key.Key_S,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(harness.property("reloadCount"), 1)
        self.assertEqual(harness.property("dashboardCount"), 1)
        self.assertEqual(harness.property("settingsCount"), 2)
        self.assertEqual(harness.property("shortcutGuideCount"), 2)

        harness.setProperty("inputFocusActive", False)
        harness.setProperty("reloadAvailable", False)
        harness.setProperty("databaseAvailable", False)
        QTest.keyClick(harness, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(
            harness,
            Qt.Key.Key_B,
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier,
        )
        self.app.processEvents()
        self.assertEqual(harness.property("reloadCount"), 1)
        self.assertEqual(harness.property("databaseCount"), 1)

        harness.setProperty("reloadAvailable", True)
        harness.setProperty("shortcutDispatchEnabled", False)
        QTest.keyClick(harness, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
        self.app.processEvents()
        self.assertEqual(harness.property("reloadCount"), 1)

        harness.setProperty("shortcutDispatchEnabled", True)
        harness.setProperty("shortcutContextActive", False)
        QTest.keyClick(harness, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
        self.app.processEvents()
        self.assertEqual(harness.property("saveCount"), 1)

        harness.setProperty("shortcutContextActive", True)
        harness.setProperty("navigationCommandsVisible", False)
        QTest.keyClick(
            harness,
            Qt.Key.Key_D,
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier,
        )
        self.app.processEvents()
        self.assertEqual(harness.property("dashboardCount"), 1)
        self.assertEqual(self.warnings, [])

    def test_command_registry_exposes_complete_nonvisual_action_model(self) -> None:
        harness = self._create("tests/qml/CommandRegistryHarness.qml")
        registry = harness.findChild(QObject, "testCommandRegistry")
        save_command = harness.findChild(QObject, "commandWorkspaceSave")
        settings_command = harness.findChild(QObject, "commandSettingsOpen")
        about_command = harness.findChild(QObject, "commandAppAbout")

        self.assertIsNotNone(registry)
        self.assertEqual(harness.property("commandCount"), 16)
        self.assertEqual(save_command.property("commandId"), "workspace.save")
        self.assertEqual(save_command.property("text"), "Save Workspace")
        icon_source = save_command.property("iconSource")
        self.assertTrue(icon_source.toString().endswith("save.svg"))
        self.assertEqual(save_command.property("shortcut"), "Ctrl+S")
        self.assertTrue(save_command.property("enabled"))
        self.assertEqual(settings_command.property("nativeRole"), "preferences")
        self.assertEqual(about_command.property("nativeRole"), "about")

        QMetaObject.invokeMethod(registry, "triggerSave")
        QMetaObject.invokeMethod(registry, "triggerAbout")
        self.assertEqual(harness.property("saveCount"), 1)
        self.assertEqual(harness.property("aboutCount"), 1)

        harness.setProperty("saveAvailable", False)
        QMetaObject.invokeMethod(registry, "triggerSave")
        self.assertEqual(harness.property("saveCount"), 1)
        self.assertFalse(save_command.property("enabled"))
        self.assertEqual(self.warnings, [])

    def test_modern_menu_binds_registry_state_and_invokes_commands(self) -> None:
        harness = self._create("tests/qml/ModernMenuBarHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))

        def find_item(item, object_name):
            if item.objectName() == object_name:
                return item
            for child in item.childItems():
                found = find_item(child, object_name)
                if found is not None:
                    return found
            return None

        menu_bar = harness.findChild(QQuickItem, "modernMenuBar")
        file_button = find_item(menu_bar, "modernMenuButtonFile")
        file_popup = file_button.findChild(QObject, "modernMenuPopupFile")
        focus_probe = harness.findChild(QObject, "modernMenuFocusProbe")

        self.assertIsNotNone(menu_bar)
        self.assertIsNotNone(file_button)
        self.assertIsNotNone(file_popup)
        self.assertIsNotNone(focus_probe)

        menu_bar.setProperty("acceleratorsEnabled", True)
        QMetaObject.invokeMethod(harness, "focusContent")
        self.assertTrue(
            self._wait_until(
                lambda: bool(focus_probe.property("activeFocus")), 200
            )
        )
        QTest.keyClick(
            harness,
            Qt.Key.Key_F,
            Qt.KeyboardModifier.AltModifier,
        )
        self.assertTrue(
            self._wait_until(lambda: bool(file_popup.property("opened")), 500)
        )
        save_item = find_item(harness.contentItem(), "modernMenuItemWorkspaceSave")
        self.assertIsNotNone(save_item)
        self.assertEqual(save_item.property("shortcutText"), "Ctrl+S")
        self.assertTrue(save_item.property("enabled"))
        self.assertEqual(harness.property("activeMenuIndex"), 0)

        QMetaObject.invokeMethod(save_item, "activate")
        self.app.processEvents()
        self.assertEqual(harness.property("saveCount"), 1)
        self.assertFalse(file_popup.property("opened"))
        self.assertTrue(
            self._wait_until(
                lambda: bool(focus_probe.property("activeFocus")), 200
            )
        )

        harness.setProperty("saveAvailable", False)
        QTest.keyClick(
            harness,
            Qt.Key.Key_F,
            Qt.KeyboardModifier.AltModifier,
        )
        self.assertTrue(
            self._wait_until(lambda: bool(file_popup.property("opened")), 500)
        )
        save_item = find_item(harness.contentItem(), "modernMenuItemWorkspaceSave")
        self.assertIsNotNone(save_item)
        self.assertFalse(save_item.property("enabled"))
        QMetaObject.invokeMethod(save_item, "activate")
        self.assertEqual(harness.property("saveCount"), 1)
        QMetaObject.invokeMethod(file_popup, "dismissToOpener")

        self.assertTrue(
            self._wait_until(lambda: not bool(file_popup.property("visible")), 500)
        )

        QTest.keyClick(
            harness,
            Qt.Key.Key_V,
            Qt.KeyboardModifier.AltModifier,
        )
        self.app.processEvents()
        settings_item = find_item(harness.contentItem(), "modernMenuItemSettingsOpen")
        self.assertIsNotNone(settings_item)
        self.assertEqual(harness.property("activeMenuIndex"), 1)
        QMetaObject.invokeMethod(settings_item, "activate")
        self.assertEqual(harness.property("settingsCount"), 1)
        self.assertEqual(self.warnings, [])

    def test_main_keyboard_shortcut_reference_opens_from_registry(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        root = self.engine.rootObjects()[0]
        registry = root.findChild(QObject, "appCommandRegistry")
        dialog = root.findChild(QObject, "shortcutReferenceDialog")
        self.assertIsNotNone(registry)
        self.assertIsNotNone(dialog)
        self.assertGreaterEqual(dialog.property("entryCount"), 30)
        self.assertFalse(dialog.property("visible"))

        QMetaObject.invokeMethod(registry, "triggerShortcutGuide")
        self.assertTrue(self._wait_until(lambda: dialog.property("visible")))
        QMetaObject.invokeMethod(dialog, "reject")
        self.assertTrue(self._wait_until(lambda: not dialog.property("visible")))
        self.assertEqual(self.warnings, [])

    def test_main_about_opens_as_an_independent_window(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        root = self.engine.rootObjects()[0]
        registry = root.findChild(QObject, "appCommandRegistry")
        about = root.findChild(QObject, "aboutWindow")
        self.assertIsNotNone(registry)
        self.assertIsNotNone(about)
        self.assertFalse(about.property("visible"))

        QMetaObject.invokeMethod(registry, "triggerAbout")
        self.assertTrue(self._wait_until(lambda: about.property("visible")))
        self.assertTrue(root.property("visible"))
        QMetaObject.invokeMethod(about, "close")
        self.assertTrue(self._wait_until(lambda: not about.property("visible")))
        self.assertTrue(root.property("visible"))
        self.assertEqual(self.warnings, [])

    def test_main_dnd_archives_notification_without_showing_toast(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        root = self.engine.rootObjects()[0]
        toast_manager = root.findChild(QObject, "mainToastManager")
        notification_center = root.findChild(QObject, "notificationCenter")

        self.assertIsNotNone(toast_manager)
        self.assertIsNotNone(notification_center)
        initial_count = root.property("notificationHistoryCount")

        QMetaObject.invokeMethod(root, "setDoNotDisturb", Q_ARG("QVariant", True))
        QMetaObject.invokeMethod(
            root,
            "recordNotification",
            Q_ARG("QVariant", "DND archived notification"),
            Q_ARG("QVariant", "warning"),
            Q_ARG("QVariant", True),
        )
        self.app.processEvents()

        self.assertTrue(root.property("isDoNotDisturb"))
        self.assertEqual(toast_manager.property("toastCount"), 0)
        self.assertEqual(root.property("notificationHistoryCount"), initial_count + 1)
        self.assertEqual(root.property("unreadNotifications"), 1)

        notification_center.setProperty("visible", True)
        self.app.processEvents()
        self.assertEqual(
            notification_center.property("notificationCount"),
            root.property("notificationHistoryCount"),
        )
        self.assertEqual(root.property("unreadNotifications"), 0)
        self.assertEqual(self.warnings, [])

    def test_main_translates_notifications_at_the_shared_boundary(self) -> None:
        language = self.context_objects["languageSettings"]
        language.setLanguage("vi")
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        root = self.engine.rootObjects()[0]

        QMetaObject.invokeMethod(
            root,
            "recordNotification",
            Q_ARG("QVariant", "Connecting to router-01..."),
            Q_ARG("QVariant", "info"),
            Q_ARG("QVariant", False),
        )
        translated, is_undefined = QQmlExpression(
            QQmlEngine.contextForObject(root),
            root,
            "notificationHistoryModel.get(0).msgText",
        ).evaluate()

        self.assertFalse(is_undefined)
        self.assertEqual(translated, "Đang kết nối tới router-01...")
        language.setLanguage("en")
        self.assertEqual(self.warnings, [])

    def test_main_notification_toggle_clears_and_deduplicates_toasts(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        root = self.engine.rootObjects()[0]
        toast_manager = root.findChild(QObject, "mainToastManager")
        notification_center = root.findChild(QObject, "notificationCenter")
        notification_button = root.findChild(QObject, "statusBarNotificationButton")

        self.assertIsNotNone(toast_manager)
        self.assertIsNotNone(notification_center)
        self.assertIsNotNone(notification_button)
        initial_history_count = root.property("notificationHistoryCount")

        for _ in range(2):
            QMetaObject.invokeMethod(
                root,
                "recordNotification",
                Q_ARG("QVariant", "Added a new EIGRP process card."),
                Q_ARG("QVariant", "info"),
                Q_ARG("QVariant", True),
            )
        self.app.processEvents()

        # Duplicate events remain auditable in history but share one popup.
        self.assertEqual(root.property("notificationHistoryCount"), initial_history_count + 2)
        self.assertEqual(toast_manager.property("toastCount"), 1)

        # The short suppression window still applies if the first popup was
        # dismissed before the immediately repeated event arrives.
        QMetaObject.invokeMethod(toast_manager, "clearToasts")
        QMetaObject.invokeMethod(
            root,
            "recordNotification",
            Q_ARG("QVariant", "Added a new EIGRP process card."),
            Q_ARG("QVariant", "info"),
            Q_ARG("QVariant", True),
        )
        self.app.processEvents()
        self.assertEqual(root.property("notificationHistoryCount"), initial_history_count + 3)
        self.assertEqual(toast_manager.property("toastCount"), 0)

        QMetaObject.invokeMethod(
            root,
            "recordNotification",
            Q_ARG("QVariant", "A distinct notification"),
            Q_ARG("QVariant", "info"),
            Q_ARG("QVariant", True),
        )
        self.app.processEvents()
        self.assertEqual(toast_manager.property("toastCount"), 1)

        QMetaObject.invokeMethod(notification_button, "clicked")
        self.app.processEvents()
        self.assertTrue(notification_center.property("visible"))
        self.assertEqual(toast_manager.property("toastCount"), 0)

        # Notifications arriving while the Center is open go to history only.
        QMetaObject.invokeMethod(
            root,
            "recordNotification",
            Q_ARG("QVariant", "Notification while Center is open"),
            Q_ARG("QVariant", "warning"),
            Q_ARG("QVariant", True),
        )
        self.app.processEvents()
        self.assertEqual(root.property("notificationHistoryCount"), initial_history_count + 5)
        self.assertEqual(toast_manager.property("toastCount"), 0)

        QMetaObject.invokeMethod(notification_button, "clicked")
        self.app.processEvents()
        self.assertFalse(notification_center.property("visible"))
        self.assertEqual(self.warnings, [])

    def test_actionable_external_tools_toast_opens_the_target_settings(self) -> None:
        self.engine.loadFromModule("UI", "Main")
        self.app.processEvents()
        root = self.engine.rootObjects()[0]
        toast_manager = root.findChild(QObject, "mainToastManager")
        panel_sidebar = root.findChild(QObject, "mainPanelSideBar")

        self.assertIsNotNone(toast_manager)
        self.assertIsNotNone(panel_sidebar)
        QMetaObject.invokeMethod(toast_manager, "clearToasts")
        initial_history_count = root.property("notificationHistoryCount")

        QMetaObject.invokeMethod(
            root,
            "showExternalToolsConfigurationNotification",
            Q_ARG("QVariant", "No active SSH Client configured in External Tools."),
            Q_ARG("QVariant", "error"),
        )
        self.app.processEvents()

        self.assertEqual(
            toast_manager.property("latestActionLabel"),
            "Open External Tools",
        )
        self.assertEqual(toast_manager.property("toastCount"), 1)
        self.assertEqual(
            root.property("notificationHistoryCount"),
            initial_history_count + 1,
        )

        QMetaObject.invokeMethod(toast_manager, "triggerLatestAction")
        self.assertTrue(
            self._wait_until(
                lambda: root.property("activeSettingKey") == "external_tools"
            )
        )
        self.assertEqual(panel_sidebar.property("appMode"), "settings")
        self.assertEqual(toast_manager.property("toastCount"), 0)
        self.assertEqual(
            root.property("notificationHistoryCount"),
            initial_history_count,
        )

        for index in range(5):
            QMetaObject.invokeMethod(
                toast_manager,
                "showToast",
                Q_ARG("QVariant", f"Stack notification {index}"),
                Q_ARG("QVariant", "info"),
                Q_ARG("QVariant", False),
            )
        self.app.processEvents()
        self.assertEqual(toast_manager.property("toastCount"), 3)
        self.assertEqual(self.warnings, [])

    def test_content_area_loads_every_feature_and_mode(self) -> None:
        content = self._create("UI/qml/content/ContentArea.qml")
        content.setProperty("tabCount", 1)

        for feature_index, object_name in (
            (0, "loadedRoutingView"),
            (2, "loadedDhcpView"),
            (3, "loadedAclView"),
            (5, "loadedNatView"),
        ):
            content.setProperty("activeTextFeature", feature_index)
            self.assertTrue(content.property("activeViewLoading"))
            self.assertTrue(self._wait_until(lambda name=object_name: content.findChild(QObject, name) is not None))
            self.assertTrue(self._wait_until(lambda: not content.property("activeViewLoading")))

        self.assertIsNotNone(content.findChild(QObject, "dhcpLoader"))
        self.assertIsNotNone(content.findChild(QObject, "loadedDhcpView"))

        content.setProperty("activeTextFeature", -1)
        content.setProperty("currentHostIp", "192.0.2.10")
        for feature_index, object_name in ((2, "loadedInterfaceView"), (0, "loadedInformationView")):
            content.setProperty("activeMainFeature", feature_index)
            self.assertTrue(content.property("activeViewLoading"))
            self.assertTrue(self._wait_until(lambda name=object_name: content.findChild(QObject, name) is not None))

        self.assertIsNotNone(content.findChild(QObject, "informationLoader"))
        loaded_information = content.findChild(QObject, "loadedInformationView")
        self.assertIsNotNone(loaded_information)
        self.assertTrue(self._wait_until(lambda: content.property("effectiveHostIp") == "192.0.2.10"))
        self.assertEqual(content.property("informationHostIp"), "192.0.2.10")
        for inactive_host_property in (
            "routingHostIp",
            "dhcpHostIp",
            "aclHostIp",
            "natHostIp",
        ):
            with self.subTest(inactive_host=inactive_host_property):
                self.assertEqual(content.property(inactive_host_property), "")
        self.assertTrue(self._wait_until(lambda: content.property("reloadCommandEnabled")))
        self.assertTrue(content.property("reloadCommandEnabled"))
        QMetaObject.invokeMethod(content, "triggerReloadCommand")
        self.app.processEvents()
        self.assertEqual(loaded_information.property("lastReloadReason"), "shortcut")

        content.setProperty("deviceRole", "sw2")
        content.setProperty("activeMainFeature", -1)
        content.setProperty("activeTextFeature", 16)
        self.assertTrue(
            self._wait_until(
                lambda: content.findChild(QObject, "loadedSwitchWorkspace") is not None
            )
        )
        switch_sub_bar = content.findChild(QObject, "switchSubFeatureBar")
        self.assertIsNotNone(switch_sub_bar)
        self.assertEqual(switch_sub_bar.property("activeTab"), "L2 Security")
        self.assertEqual(
            switch_sub_bar.property("tabs").toVariant(),
            ["L2 Security", "Port Security"],
        )

        content.setProperty("activeTextFeature", 14)
        self.assertTrue(
            self._wait_until(
                lambda: switch_sub_bar.property("activeTab") == "VLAN"
            )
        )
        self.assertTrue(switch_sub_bar.property("visible"))
        self.assertEqual(
            switch_sub_bar.property("tabs").toVariant(),
            ["VLAN", "EtherChannel", "STP", "VTP"],
        )

        content.setProperty("activeTextFeature", 19)
        self.assertTrue(
            self._wait_until(
                lambda: content.findChild(QObject, "loadedSyslogDeviceConfigPage")
                is not None
            )
        )
        syslog_config = content.findChild(QObject, "loadedSyslogDeviceConfigPage")
        self.assertEqual(syslog_config.property("host"), "192.0.2.10")
        self.assertIsNotNone(syslog_config.findChild(QObject, "syslogGroupButton"))
        self.assertIsNotNone(syslog_config.findChild(QObject, "syslogViewPushButton"))
        self.assertIsNotNone(syslog_config.findChild(QObject, "syslogCrudActions"))

        content.setProperty("appMode", "settings")
        self.assertTrue(self._wait_until(lambda: content.findChild(QObject, "loadedSettingsView") is not None))
        content.setProperty("appMode", "database")
        self.assertTrue(self._wait_until(lambda: content.findChild(QObject, "loadedDatabaseView") is not None))
        content.setProperty("appMode", "devices")
        self.app.processEvents()

        flags = (
            "routingViewLoaded",
            "dhcpViewLoaded",
            "aclViewLoaded",
            "natViewLoaded",
            "interfaceViewLoaded",
            "informationViewLoaded",
            "switchWorkspaceLoaded",
            "settingsViewLoaded",
            "databaseViewLoaded",
        )
        self.assertTrue(all(content.property(flag) for flag in flags))
        self.assertEqual(self.warnings, [])

    def test_information_view_loads_empty_version_history_without_warnings(self) -> None:
        """Information history controls remain stable when a host has no backup yet."""
        information = self._create_with_properties(
            "UI/qml/content/InformationView.qml",
            {"currentHostIp": "192.0.2.254", "width": 1000, "height": 700},
        )
        self.assertTrue(self._wait_until(lambda: not information.property("isViewLoading")))
        history = information.property("commitHistory")
        self.assertEqual(history.toVariant() if hasattr(history, "toVariant") else history, [])
        self.assertEqual(information.property("configText"), "")
        self.assertIsNotNone(information.findChild(QObject, "informationCommitHistoryComboBox"))
        viewer = information.findChild(QObject, "informationConfigViewer")
        self.assertIsNotNone(viewer)
        self.assertTrue(viewer.property("wrapLongLines"))
        self.assertTrue(viewer.property("smoothVerticalScrolling"))
        self.assertEqual(self.warnings, [])

    def test_status_bar_renders_each_virtual_lab_without_inline_ip(self) -> None:
        monitor = self.context_objects["networkMonitor"]
        monitor._apply_virtual_labs(
            (
                VirtualLabInfo(
                    state="online",
                    platform="EVE-NG",
                    server_ip="192.0.2.10",
                    server_url="http://192.0.2.10",
                ),
                VirtualLabInfo(
                    state="active",
                    platform="PNETLab",
                    server_ip="192.0.2.11",
                    server_url="http://192.0.2.11",
                    lab_name="OSPF Practice",
                    running_node_count=2,
                ),
            )
        )
        status_bar = self._create("UI/qml/layout/StatusBar.qml")
        repeater = status_bar.findChild(QObject, "virtualLabRepeater")

        self.assertEqual(status_bar.property("virtualLabCount"), 2)
        self.assertIsNotNone(repeater)
        self.assertEqual(repeater.property("count"), 2)
        first_delegate = QQmlExpression(
            QQmlEngine.contextForObject(repeater), repeater, "itemAt(0)"
        ).evaluate()[0]
        second_delegate = QQmlExpression(
            QQmlEngine.contextForObject(repeater), repeater, "itemAt(1)"
        ).evaluate()[0]
        first = first_delegate.findChild(QObject, "virtualLabIndicatorText0")
        second = second_delegate.findChild(QObject, "virtualLabIndicatorText1")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.property("text"), "EVE-NG · Online")
        self.assertEqual(second.property("text"), "PNETLab · OSPF Practice · 2 running")
        self.assertNotIn("192.0.2.", first.property("text"))
        self.assertNotIn("192.0.2.", second.property("text"))
        self.assertEqual(self.warnings, [])

    def test_information_view_compares_adjacent_and_multi_version_git_ranges(self) -> None:
        """Information exposes cumulative Diff ranges and returns to snapshot mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ConfigBackupService(Path(temp_dir) / "backup")
            host = "192.0.2.253"
            service.save_snapshot(host, "hostname edge\ndescription first\n")
            service.save_snapshot(host, "hostname edge\ndescription middle\n")
            service.save_snapshot(host, "hostname edge-new\ndescription current\n")
            manager = DatabaseManager(config_backup_service=service)
            self.context_objects["dbManager"] = manager
            self.engine.rootContext().setContextProperty("dbManager", manager)

            information = self._create_with_properties(
                "UI/qml/content/InformationView.qml",
                {"currentHostIp": host, "width": 1200, "height": 760},
            )
            self.assertTrue(self._wait_until(lambda: not information.property("isViewLoading")))
            compare_button = information.findChild(QObject, "informationCompareModeButton")
            snapshot_button = information.findChild(QObject, "informationSnapshotModeButton")
            base_combo = information.findChild(QObject, "informationDiffBaseComboBox")
            target_combo = information.findChild(QObject, "informationDiffTargetComboBox")
            viewer = information.findChild(QObject, "informationConfigViewer")
            self.assertIsNotNone(compare_button)
            self.assertIsNotNone(snapshot_button)
            self.assertIsNotNone(base_combo)
            self.assertIsNotNone(target_combo)
            self.assertIsNotNone(viewer)

            QMetaObject.invokeMethod(compare_button, "clicked")
            self.assertTrue(self._wait_until(lambda: not information.property("isViewLoading")))
            self.assertEqual(information.property("viewMode"), "diff")
            self.assertEqual(information.property("diffVersionSpan"), 2)
            self.assertIn("-description middle", information.property("diffText"))
            self.assertIn("+description current", information.property("diffText"))
            self.assertEqual(viewer.property("syntaxMode"), "diff")

            base_combo.setProperty("currentIndex", 2)
            QMetaObject.invokeMethod(information, "loadDiff")
            self.assertTrue(self._wait_until(lambda: not information.property("isViewLoading")))
            self.assertEqual(information.property("diffVersionSpan"), 3)
            self.assertIn("-hostname edge", information.property("diffText"))
            self.assertIn("+hostname edge-new", information.property("diffText"))

            QMetaObject.invokeMethod(snapshot_button, "clicked")
            self.app.processEvents()
            self.assertEqual(information.property("viewMode"), "snapshot")
            self.assertEqual(viewer.property("syntaxMode"), "configuration")
            self.assertIn("hostname edge-new", information.property("configText"))
            self.assertEqual(self.warnings, [])

    def test_every_switch_table_page_loads_without_qml_warnings(self) -> None:
        pages = (
            ("UI/qml/features/switching/interfaces/SwitchPortsPage.qml", {"host": "192.0.2.250"}),
            ("UI/qml/features/switching/interfaces/SviPage.qml", {"host": "192.0.2.250"}),
            ("UI/qml/features/switching/switching/VlanPage.qml", {"host": "192.0.2.250"}),
            ("UI/qml/features/switching/switching/EtherChannelPage.qml", {"host": "192.0.2.250"}),
            ("UI/qml/features/switching/switching/StpPage.qml", {"host": "192.0.2.250"}),
            ("UI/qml/features/switching/switching/VtpPage.qml", {"host": "192.0.2.250"}),
            ("UI/qml/features/switching/security/L2SecurityPage.qml", {"host": "192.0.2.250"}),
            (
                "UI/qml/features/switching/monitoring/SwitchMonitoringPage.qml",
                {"host": "192.0.2.250", "viewName": "portCounters"},
            ),
            (
                "UI/qml/features/switching/monitoring/SwitchMonitoringPage.qml",
                {"host": "192.0.2.250", "viewName": "macTable"},
            ),
        )
        instances = []
        for relative_path, properties in pages:
            with self.subTest(qml=relative_path, view=properties.get("viewName", "")):
                instances.append(self._create_with_properties(relative_path, properties))
        self.app.processEvents()
        self.assertEqual(self.warnings, [])

    def test_switch_configuration_pages_adapt_at_workspace_breakpoint(self) -> None:
        pages = (
            "UI/qml/features/switching/interfaces/SwitchPortsPage.qml",
            "UI/qml/features/switching/interfaces/SviPage.qml",
            "UI/qml/features/switching/switching/VlanPage.qml",
            "UI/qml/features/switching/switching/EtherChannelPage.qml",
            "UI/qml/features/switching/switching/StpPage.qml",
            "UI/qml/features/switching/switching/VtpPage.qml",
            "UI/qml/features/switching/security/L2SecurityPage.qml",
        )
        instances = []
        for relative_path in pages:
            with self.subTest(qml=relative_path):
                page = self._create_with_properties(
                    relative_path,
                    {"host": "192.0.2.251", "width": 1200, "height": 720},
                )
                instances.append(page)
                self.assertFalse(page.property("compactLayout"))
                page.setProperty("width", 760)
                self.app.processEvents()
                self.assertTrue(page.property("compactLayout"))
        self.assertEqual(self.warnings, [])

    def test_switch_edit_actions_keep_the_full_label_in_compact_layout(self) -> None:
        pages = (
            "UI/qml/features/switching/interfaces/SwitchPortsPage.qml",
            "UI/qml/features/switching/interfaces/SviPage.qml",
            "UI/qml/features/switching/switching/VlanPage.qml",
            "UI/qml/features/switching/switching/EtherChannelPage.qml",
            "UI/qml/features/switching/switching/StpPage.qml",
        )
        instances = []
        for relative_path in pages:
            with self.subTest(qml=relative_path):
                page = self._create_with_properties(
                    relative_path,
                    {"host": "192.0.2.251", "width": 760, "height": 720},
                )
                instances.append(page)
                edit_buttons = [
                    item
                    for item in page.findChildren(QObject, "crudEditButton")
                    if item.property("visible")
                ]
                self.assertTrue(edit_buttons)
                edit_button = edit_buttons[0]
                edit_label = edit_button.findChild(QObject, "crudEditButtonLabel")
                action_flow = page.findChild(QObject, "workspaceHeaderActions")
                self.assertEqual(edit_button.property("text"), "Edit")
                self.assertFalse(edit_button.property("compactContent"))
                self.assertIsNotNone(edit_label)
                self.assertTrue(edit_label.property("visible"))
                self.assertEqual(edit_label.property("text"), "Edit")
                self.assertGreaterEqual(
                    edit_button.property("width") + 0.5,
                    edit_button.property("expandedImplicitWidth"),
                )
                self.assertIsNotNone(action_flow)
                for action in action_flow.findChildren(QObject):
                    if action.parent() != action_flow or not action.property("visible"):
                        continue
                    self.assertGreaterEqual(action.property("x"), -0.5)
                    self.assertLessEqual(
                        action.property("x") + action.property("width"),
                        action_flow.property("width") + 0.5,
                    )
        self.assertEqual(self.warnings, [])

    def test_switch_editor_forms_expose_working_cancel_actions(self) -> None:
        pages = (
            (
                "UI/qml/features/switching/interfaces/SwitchPortsPage.qml",
                'activatePortTab("Access"); beginCreate();',
                "switchPortEditorActions",
            ),
            (
                "UI/qml/features/switching/interfaces/SviPage.qml",
                "beginCreate();",
                "sviEditorActions",
            ),
            (
                "UI/qml/features/switching/switching/VlanPage.qml",
                "beginCreate();",
                "vlanEditorActions",
            ),
            (
                "UI/qml/features/switching/switching/EtherChannelPage.qml",
                "beginCreate();",
                "etherChannelEditorActions",
            ),
            (
                "UI/qml/features/switching/switching/StpPage.qml",
                "beginCreate();",
                "stpEditorActions",
            ),
        )
        instances = []
        for relative_path, setup, action_name in pages:
            with self.subTest(qml=relative_path):
                page = self._create_with_properties(
                    relative_path,
                    {"host": "192.0.2.254", "width": 1100, "height": 720},
                )
                instances.append(page)
                result, is_undefined = QQmlExpression(
                    QQmlEngine.contextForObject(page), page, setup + " formMode"
                ).evaluate()
                self.assertFalse(is_undefined)
                self.assertNotEqual(result, 0)
                self.app.processEvents()

                actions = page.findChild(QObject, action_name)
                self.assertIsNotNone(actions)
                self.assertTrue(actions.property("visible"))
                QMetaObject.invokeMethod(actions, "cancelRequested")
                self.app.processEvents()
                self.assertEqual(page.property("formMode"), 0)
        self.assertEqual(self.warnings, [])

    def test_switch_workspace_caches_each_feature_after_first_visit(self) -> None:
        workspace = self._create_with_properties(
            "UI/qml/features/switching/SwitchWorkspace.qml",
            {
                "host": "192.0.2.252",
                "deviceRole": "sw2",
                "feature": "interfaces",
                "width": 1200,
                "height": 720,
            },
        )
        self.assertTrue(self._wait_until(lambda: workspace.property("switchPortsLoaded")))

        for feature, flag in (
            ("switching", "vlanLoaded"),
            ("security", "l2SecurityLoaded"),
            ("monitoring", "portCountersLoaded"),
        ):
            workspace.setProperty("feature", feature)
            self.assertTrue(self._wait_until(lambda name=flag: workspace.property(name)))
            self.assertTrue(workspace.property("switchPortsLoaded"))

        workspace.setProperty("feature", "switching")
        self.app.processEvents()
        workspace.setProperty("subFeature", "vtp")
        self.assertTrue(self._wait_until(lambda: workspace.property("vtpLoaded")))

        workspace.setProperty("subFeature", "etherChannel")
        self.assertTrue(self._wait_until(lambda: workspace.property("etherChannelLoaded")))

        workspace.setProperty("subFeature", "stp")
        self.assertTrue(self._wait_until(lambda: workspace.property("stpLoaded")))

        workspace.setProperty("feature", "security")
        workspace.setProperty("subFeature", "portSecurity")
        self.assertTrue(self._wait_until(lambda: workspace.property("portSecurityLoaded")))

        self.assertTrue(self._wait_until(lambda: not workspace.property("isViewLoading")))
        self.assertEqual(self.warnings, [])

    def test_every_saved_table_form_loads_without_qml_warnings(self) -> None:
        table_forms = (
            "UI/qml/features/dhcp/DhcpPoolList.qml",
            "UI/qml/features/dhcp/DhcpExcludedForm.qml",
            "UI/qml/features/dhcp/DhcpHelperForm.qml",
            "UI/qml/features/nat/NatInterfaceForm.qml",
            "UI/qml/features/nat/NatStaticForm.qml",
            "UI/qml/features/nat/NatDynamicForm.qml",
            "UI/qml/features/nat/NatPatForm.qml",
            "UI/qml/features/nat/NatAclForm.qml",
            "UI/qml/features/nat/NatRouteMapForm.qml",
        )
        instances = []
        for relative_path in table_forms:
            with self.subTest(qml=relative_path):
                instances.append(self._create(relative_path))
        self.app.processEvents()
        self.assertEqual(self.warnings, [])

    def test_device_tab_spinner_replaces_icon_only_while_loading(self) -> None:
        harness = self._create("tests/qml/DeviceTabsLoadingHarness.qml")
        self.assertTrue(self._wait_until(lambda: harness.property("tabCount") == 1))
        self.assertTrue(
            self._wait_until(
                lambda: harness.findChild(QObject, "deviceTabLoadingSpinner") is not None
            )
        )

        spinner = harness.findChild(QObject, "deviceTabLoadingSpinner")
        device_icon = harness.findChild(QObject, "deviceTabDeviceIcon")
        self.assertIsNotNone(spinner)
        self.assertIsNotNone(device_icon)
        self.assertFalse(spinner.property("running"))
        self.assertTrue(device_icon.property("visible"))
        self.assertIs(spinner.parent(), device_icon.parent())
        self.assertEqual(spinner.property("width"), device_icon.property("width"))
        self.assertEqual(spinner.property("height"), device_icon.property("height"))
        self.assertAlmostEqual(
            spinner.property("x") + spinner.property("width") / 2,
            device_icon.property("x") + device_icon.property("width") / 2,
        )
        self.assertAlmostEqual(
            spinner.property("y") + spinner.property("height") / 2,
            device_icon.property("y") + device_icon.property("height") / 2,
        )

        harness.setProperty("activeContentLoading", True)
        self.assertTrue(self._wait_until(lambda: spinner.property("running")))
        self.assertTrue(spinner.property("visible"))
        self.assertFalse(device_icon.property("visible"))

        harness.setProperty("activeContentLoading", False)
        self.assertTrue(self._wait_until(lambda: not spinner.property("running")))
        self.assertFalse(spinner.property("visible"))
        self.assertTrue(device_icon.property("visible"))
        self.assertEqual(self.warnings, [])

    def test_device_tab_context_menu_closes_tabs_to_the_right(self) -> None:
        harness = self._create("tests/qml/DeviceTabsContextHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
        tabs = harness.findChild(QObject, "deviceTabsContextTarget")
        tab_list = harness.findChild(QObject, "deviceTabList")
        menu = harness.findChild(QObject, "deviceTabContextMenu")
        self.assertIsNotNone(tabs)
        self.assertIsNotNone(tab_list)
        self.assertIsNotNone(menu)
        self.assertTrue(self._wait_until(lambda: tabs.property("tabCount") == 3))

        QTest.keyClick(
            harness,
            Qt.Key.Key_1,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(tabs.property("activeUid"), "192.0.2.1")
        QTest.keyClick(
            harness,
            Qt.Key.Key_9,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.app.processEvents()
        self.assertEqual(tabs.property("activeUid"), "192.0.2.3")

        second_tab = QQmlExpression(
            QQmlEngine.contextForObject(tab_list),
            tab_list,
            "itemAtIndex(1)",
        ).evaluate()[0]
        mapped = QQmlExpression(
            QQmlEngine.contextForObject(second_tab),
            second_tab,
            "mapToItem(null, width / 2, height / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(mapped.x()), round(mapped.y())),
        )
        self.app.processEvents()
        self.assertTrue(menu.property("visible"))
        self.assertEqual(tabs.property("contextTargetIndex"), 1)
        close_right = menu.findChild(QObject, "deviceTabContextCloseRight")
        self.assertTrue(close_right.property("enabled"))

        close_point = QQmlExpression(
            QQmlEngine.contextForObject(close_right),
            close_right,
            "mapToItem(null, width / 2, height / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(close_point.x()), round(close_point.y())),
        )
        self.app.processEvents()
        self.assertEqual(tabs.property("tabCount"), 2)
        self.assertEqual(tabs.property("activeUid"), "192.0.2.2")
        self.assertEqual(self.warnings, [])

    def test_each_device_tab_keeps_feature_bar_and_content_state_in_sync(self) -> None:
        harness = self._create("tests/qml/DeviceFeatureStateHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))

        QMetaObject.invokeMethod(harness, "openFirstHost")
        self.app.processEvents()
        self.assertEqual(harness.property("activeHost"), "192.0.2.1")
        self.assertEqual(harness.property("selectedMainFeature"), 0)
        self.assertEqual(harness.property("selectedTextFeature"), -1)

        QMetaObject.invokeMethod(harness, "selectNat")
        self.app.processEvents()
        self.assertEqual(harness.property("selectedMainFeature"), -1)
        self.assertEqual(harness.property("selectedTextFeature"), 5)
        self.assertEqual(harness.property("contentMainFeature"), -1)
        self.assertEqual(harness.property("contentTextFeature"), 5)

        QMetaObject.invokeMethod(harness, "openSecondHost")
        self.app.processEvents()
        self.assertEqual(harness.property("activeHost"), "192.0.2.2")
        self.assertEqual(harness.property("selectedMainFeature"), 0)
        self.assertEqual(harness.property("selectedTextFeature"), -1)
        self.assertEqual(harness.property("contentMainFeature"), 0)
        self.assertEqual(harness.property("contentTextFeature"), -1)

        QMetaObject.invokeMethod(harness, "selectFirstHost")
        self.app.processEvents()
        self.assertEqual(harness.property("activeHost"), "192.0.2.1")
        self.assertEqual(harness.property("selectedMainFeature"), -1)
        self.assertEqual(harness.property("selectedTextFeature"), 5)
        self.assertEqual(harness.property("contentMainFeature"), -1)
        self.assertEqual(harness.property("contentTextFeature"), 5)
        self.assertEqual(self.warnings, [])

    def test_open_editors_tracks_selects_and_closes_device_tabs(self) -> None:
        harness = self._create("tests/qml/OpenEditorsHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
        tabs = harness.findChild(QObject, "openEditorsDeviceTabs")
        section = harness.findChild(QObject, "openEditorsTestSection")
        editor_list = harness.findChild(QObject, "openEditorsList")
        self.assertIsNotNone(tabs)
        self.assertIsNotNone(section)
        self.assertIsNotNone(editor_list)
        self.assertTrue(self._wait_until(lambda: tabs.property("tabCount") == 3))
        self.assertEqual(section.property("editorCount"), 3)
        self.assertEqual(tabs.property("activeUid"), "192.0.2.3")
        self.assertEqual(editor_list.property("currentIndex"), 2)
        self.assertEqual(section.property("height"), 4 * 28)

        first_row = QQmlExpression(
            QQmlEngine.contextForObject(editor_list),
            editor_list,
            "itemAtIndex(0)",
        ).evaluate()[0]
        self.assertIsNotNone(first_row)
        first_point = QQmlExpression(
            QQmlEngine.contextForObject(first_row),
            first_row,
            "mapToItem(null, width / 2, height / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(first_point.x()), round(first_point.y())),
        )
        self.assertTrue(
            self._wait_until(lambda: tabs.property("activeUid") == "192.0.2.1")
        )
        self.assertEqual(editor_list.property("currentIndex"), 0)

        first_row = QQmlExpression(
            QQmlEngine.contextForObject(editor_list),
            editor_list,
            "itemAtIndex(0)",
        ).evaluate()[0]
        self.assertIsNotNone(first_row)
        close_first = first_row.findChild(QObject, "openEditorCloseButton0")
        self.assertIsNotNone(close_first)
        self.assertTrue(close_first.property("visible"))
        close_point = QQmlExpression(
            QQmlEngine.contextForObject(close_first),
            close_first,
            "mapToItem(null, width / 2, height / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(close_point.x()), round(close_point.y())),
        )
        self.assertTrue(self._wait_until(lambda: tabs.property("tabCount") == 2))
        self.assertEqual(section.property("editorCount"), 2)

        close_all = harness.findChild(QObject, "openEditorsCloseAllButton")
        self.assertIsNotNone(close_all)
        close_all_point = QQmlExpression(
            QQmlEngine.contextForObject(close_all),
            close_all,
            "mapToItem(null, width / 2, height / 2)",
        ).evaluate()[0]
        QTest.mouseClick(
            harness,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(round(close_all_point.x()), round(close_all_point.y())),
        )
        self.assertTrue(self._wait_until(lambda: tabs.property("tabCount") == 0))
        self.assertEqual(section.property("editorCount"), 0)
        self.assertEqual(tabs.property("activeUid"), "")
        self.assertEqual(self.warnings, [])

    def test_interface_row_context_menu_edits_and_deletes_target(self) -> None:
        class InterfaceBackend(QObject):
            def __init__(self):
                super().__init__()
                self.rows = [
                    {
                        "iface_id": 1,
                        "interface_name": "GigabitEthernet0/0",
                        "interface_kind": "L3",
                        "interface_type": "physical",
                        "can_delete": False,
                        "ip_address": "192.0.2.1",
                        "subnet_mask": "255.255.255.0",
                    },
                    {
                        "iface_id": 2,
                        "interface_name": "Loopback0",
                        "interface_kind": "L3",
                        "interface_type": "loopback",
                        "can_delete": True,
                        "ip_address": "198.51.100.1",
                        "subnet_mask": "255.255.255.255",
                    },
                ]
                self.deleted = []

            @pyqtSlot(str, result="QVariantList")
            def getRouterInterfaces(self, host):
                return [dict(row) for row in self.rows]

            @pyqtSlot(str, str, str, result=bool)
            def hasPendingViewPush(self, controller, host, module):
                return False

            @pyqtSlot(int, result=bool)
            def deleteRouterInterface(self, iface_id):
                self.deleted.append(iface_id)
                self.rows = [
                    row for row in self.rows if row["iface_id"] != iface_id
                ]
                return True

        backend = InterfaceBackend()
        self.engine.rootContext().setContextProperty("dbManager", backend)
        harness = self._create("tests/qml/InterfaceContextHarness.qml")
        self.assertTrue(QTest.qWaitForWindowExposed(harness, 1000))
        view = harness.findChild(QObject, "interfaceContextTarget")
        interface_list = harness.findChild(QObject, "interfaceSavedList")
        menu = harness.findChild(QObject, "interfaceContextMenu")
        self.assertIsNotNone(view)
        self.assertIsNotNone(interface_list)
        self.assertIsNotNone(menu)
        self.assertTrue(
            self._wait_until(lambda: interface_list.property("count") == 1)
        )

        def right_click_row(index):
            row = QQmlExpression(
                QQmlEngine.contextForObject(interface_list),
                interface_list,
                f"itemAtIndex({index})",
            ).evaluate()[0]
            point = QQmlExpression(
                QQmlEngine.contextForObject(row),
                row,
                "mapToItem(null, width / 2, height / 2)",
            ).evaluate()[0]
            QTest.mouseClick(
                harness,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
                QPoint(round(point.x()), round(point.y())),
            )
            self.app.processEvents()

        def click_menu_item(object_name):
            item = menu.findChild(QObject, object_name)
            point = QQmlExpression(
                QQmlEngine.contextForObject(item),
                item,
                "mapToItem(null, width / 2, height / 2)",
            ).evaluate()[0]
            QTest.mouseClick(
                harness,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                QPoint(round(point.x()), round(point.y())),
            )
            self.app.processEvents()

        right_click_row(0)
        self.assertTrue(menu.property("visible"))
        click_menu_item("interfaceContextEdit")
        self.assertEqual(view.property("selectedIfaceId"), 1)

        QMetaObject.invokeMethod(
            view,
            "activateTab",
            Q_ARG("QVariant", "Loopback"),
        )
        self.assertTrue(self._wait_until(lambda: view.property("currentTab") == "Loopback"))
        QTest.qWait(30)
        self.assertTrue(
            self._wait_until(lambda: interface_list.property("count") == 1)
        )
        right_click_row(0)
        self.assertTrue(menu.property("visible"))
        click_menu_item("interfaceContextDelete")
        self.assertEqual(backend.deleted, [2])
        self.assertTrue(
            self._wait_until(lambda: interface_list.property("count") == 0)
        )
        self.assertEqual(self.warnings, [])
        self.engine.rootContext().setContextProperty(
            "dbManager", self.context_objects["dbManager"]
        )

    def test_external_tools_master_detail_loads_and_enters_new_tool_mode(self) -> None:
        settings = self._create("UI/qml/content/ExternalToolsSettings.qml")
        settings.setProperty("width", 1200)
        settings.setProperty("height", 760)
        self.assertTrue(self._wait_until(lambda: not settings.property("discoveryPending")))

        for object_name in (
            "externalToolsScanButton",
            "externalToolsNewButton",
            "externalToolsFeatureBar",
            "externalToolCategoryList",
            "externalToolsApplicationList",
            "externalToolsMainSplit",
            "externalToolAppName",
            "externalToolExecutable",
            "externalToolArguments",
            "externalToolSaveButton",
        ):
            with self.subTest(object_name=object_name):
                self.assertIsNotNone(settings.findChild(QObject, object_name))

        self.assertFalse(settings.property("compactLayout"))
        settings.setProperty("width", 800)
        self.app.processEvents()
        self.assertTrue(settings.property("compactLayout"))

        QMetaObject.invokeMethod(settings, "clearForm")
        self.app.processEvents()
        self.assertEqual(settings.property("editorMode"), "custom")
        self.assertFalse(settings.property("formValid"))
        self.assertFalse(settings.findChild(QObject, "externalToolSaveButton").property("enabled"))
        self.app.processEvents()
        self.assertEqual(self.warnings, [])

    def test_rapid_feature_switch_only_incubates_final_view(self) -> None:
        content = self._create("UI/qml/content/ContentArea.qml")
        content.setProperty("tabCount", 1)

        # These changes happen in one event-loop turn. The dispatch timer must
        # coalesce them so an obsolete heavy screen does not consume CPU.
        content.setProperty("activeTextFeature", 0)  # Routing
        content.setProperty("activeTextFeature", 3)  # ACL
        content.setProperty("activeTextFeature", 2)  # DHCP

        self.assertTrue(content.property("activeViewLoading"))
        self.assertTrue(
            self._wait_until(
                lambda: content.findChild(QObject, "loadedDhcpView") is not None
            )
        )
        self.assertTrue(self._wait_until(lambda: not content.property("activeViewLoading")))
        self.assertTrue(content.property("dhcpViewLoaded"))
        self.assertFalse(content.property("routingViewLoaded"))
        self.assertFalse(content.property("aclViewLoaded"))
        self.assertIsNone(content.findChild(QObject, "loadedRoutingView"))
        self.assertIsNone(content.findChild(QObject, "loadedAclView"))
        self.assertEqual(self.warnings, [])

    def test_heavy_feature_tabs_load_on_first_visit(self) -> None:
        routing = self._create("UI/qml/features/routing/RoutingView.qml")
        for tab in ("Static", "Default", "OSPF", "EIGRP", "Info"):
            routing.setProperty("currentTab", tab)
            self.app.processEvents()
        self.assertTrue(all(routing.property(name) for name in ("infoLoaded", "staticLoaded", "ospfLoaded", "eigrpLoaded")))

        dhcp = self._create("UI/qml/features/dhcp/DhcpView.qml")
        for tab in ("Excluded", "Helper", "Pool"):
            dhcp.setProperty("currentTab", tab)
            self.app.processEvents()
        self.assertTrue(all(dhcp.property(name) for name in ("poolLoaded", "excludedLoaded", "helperLoaded")))

        nat = self._create("UI/qml/features/nat/NatView.qml")
        for tab in ("Dynamic", "PAT", "Interfaces", "ACL", "Route Map", "Static"):
            nat.setProperty("currentTab", tab)
            self.app.processEvents()
        nat_flags = ("staticLoaded", "dynamicLoaded", "patLoaded", "interfacesLoaded", "aclLoaded", "routeMapLoaded")
        self.assertTrue(all(nat.property(name) for name in nat_flags))
        self.assertEqual(self.warnings, [])


if __name__ == "__main__":
    unittest.main()
