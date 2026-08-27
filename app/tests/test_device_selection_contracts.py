from __future__ import annotations

from pathlib import Path
import unittest


class DeviceSelectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.panel = (root / "UI/qml/panels/DevicesPanel.qml").read_text(encoding="utf-8")
        cls.section = (root / "UI/qml/sidebar/devices/DeviceSection.qml").read_text(encoding="utf-8")
        cls.item = (root / "UI/qml/sidebar/devices/DeviceItem.qml").read_text(encoding="utf-8")
        cls.menu = (root / "UI/qml/sidebar/devices/DeviceContextMenu.qml").read_text(encoding="utf-8")
        cls.syslog_panel = (root / "UI/qml/panels/SyslogDevicesPanel.qml").read_text(encoding="utf-8")
        cls.syslog_item = (root / "UI/qml/sidebar/syslog/SyslogDeviceItem.qml").read_text(encoding="utf-8")
        cls.syslog_menu = (root / "UI/qml/sidebar/syslog/SyslogDeviceContextMenu.qml").read_text(encoding="utf-8")
        cls.tabs = (root / "UI/qml/devices/DeviceTabs.qml").read_text(encoding="utf-8")

    def test_business_selection_is_host_based(self) -> None:
        self.assertIn('property string activeHost: ""', self.panel)
        self.assertIn("property var selectedHosts: ({})", self.panel)
        self.assertNotIn("property int selectedSection", self.panel)
        self.assertNotIn("property int selectedIndex", self.panel)
        self.assertIn("signal deviceActivated(string host)", self.section)
        self.assertIn("modelData.ip", self.section)
        self.assertNotIn("CheckBox {", self.panel + self.section)
        self.assertIn("DeviceBatchActionBar", self.panel)
        self.assertIn('property bool multiSelectMode: false', self.panel)
        self.assertIn("function startMultipleSelection(host)", self.panel)
        self.assertIn('text: "Select multiple"', self.menu)
        self.assertIn("if (multiSelectMode)", self.panel)
        self.assertIn(
            "activeBatchExitsMultipleSelection = multiSelectMode",
            self.panel,
        )
        self.assertIn(
            "if (exitMultipleSelection)",
            self.panel,
        )
        self.assertIn(
            "enabled: deviceItem.selectionMode || !deviceItem.blockedByStatus",
            self.item,
        )
        self.assertIn("acceptedModifiers: Qt.ControlModifier", self.item)
        self.assertIn("acceptedModifiers: Qt.ShiftModifier", self.item)
        self.assertIn("function selectRangeTo(host)", self.panel)
        self.assertIn("function eligibleHosts(operation, hosts)", self.panel)
        self.assertIn("handleToggleHostSelection(host)", self.panel)
        self.assertIn(
            "if (multiSelectMode && selectedHosts[contextTargetHost] !== true)\n"
            "            clearSelection()",
            self.panel,
        )
        self.assertIn('text: "Right-click for batch actions"', (
            Path(__file__).resolve().parents[1]
            / "UI/qml/sidebar/devices/DeviceBatchActionBar.qml"
        ).read_text(encoding="utf-8"))

    def test_context_target_is_snapshotted_and_tabs_do_not_close_sessions(self) -> None:
        self.assertIn("function openForHost(host, status, selectedHosts, statuses, x, y)", self.menu)
        self.assertIn("targetHost = String(host || \"\")", self.menu)
        self.assertIn('text: "Connect waiting ("', self.menu)
        self.assertIn('text: "Get configs from connected ("', self.menu)
        self.assertIn('text: "Disconnect connected ("', self.menu)
        self.assertIn('text: "Switch to Live Connection"', self.menu)
        self.assertIn("contextMenu.targetIsDevelopment", self.menu)
        self.assertNotIn('text: "Down (Dev)"', self.menu)
        self.assertNotIn("closeSessionForTab", self.tabs)
        self.assertNotIn("cli.closeDeviceSession", self.tabs)

    def test_unfinished_scp_running_config_is_hidden_from_device_menu(self) -> None:
        self.assertIn('text: "Get running-config via SCP"', self.menu)
        marker = self.menu.index('text: "Get running-config via SCP"')
        item_start = self.menu.rfind("ContextMenuItem {", 0, marker)
        item_end = self.menu.index("ContextMenuItem {", marker)
        item = self.menu[item_start:item_end]
        self.assertIn("visible: false", item)
        self.assertIn(
            "chuc nang chua phat trien xong, khong tam quan tam nieu viet bao cao",
            item,
        )

    def test_syslog_hosts_support_practical_group_selection(self) -> None:
        self.assertIn("DeviceBatchActionBar {", self.syslog_panel)
        self.assertIn("function selectRangeTo(host)", self.syslog_panel)
        self.assertIn("SyslogDeviceContextMenu {", self.syslog_panel)
        self.assertIn("groupDialog.openFor(root, hosts)", self.syslog_panel)
        self.assertIn("acceptedModifiers: Qt.ControlModifier", self.syslog_item)
        self.assertIn("acceptedModifiers: Qt.ShiftModifier", self.syslog_item)
        self.assertIn('text: "Configure as Syslog Group ("', self.syslog_menu)
        self.assertIn("root.batchHosts.length >= 2", self.syslog_menu)
        self.assertIn("root.batchHosts.length <= 5", self.syslog_menu)


if __name__ == "__main__":
    unittest.main()
