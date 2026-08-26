from __future__ import annotations

import inspect
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import ANY, patch

from PyQt6.QtCore import QCoreApplication, QSettings

from core.acl_slots import AclSlotsMixin
from core.nat_slots import NatSlotsMixin
from core.settings import ThemeSettings, WindowSettings


def _qml_component_blocks(source: str, component_name: str) -> list[str]:
    """Return balanced QML component blocks for small source-contract checks."""
    blocks: list[str] = []
    for match in re.finditer(rf"\b{re.escape(component_name)}\s*\{{", source):
        depth = 1
        cursor = match.end()
        while cursor < len(source) and depth:
            if source[cursor] == "{":
                depth += 1
            elif source[cursor] == "}":
                depth -= 1
            cursor += 1
        blocks.append(source[match.start() : cursor])
    return blocks


class WindowSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._settings_dir = tempfile.TemporaryDirectory()
        QCoreApplication.setOrganizationName("NetworkToolsTests")
        QCoreApplication.setApplicationName("UiContractTests")
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            cls._settings_dir.name,
        )
        QSettings().clear()

    @classmethod
    def tearDownClass(cls) -> None:
        QSettings().clear()
        cls._settings_dir.cleanup()

    def test_window_state_survives_a_new_backend_instance(self) -> None:
        first = WindowSettings()
        first.saveState(120, 80, 1440, 900, False)

        restored = WindowSettings()
        self.assertEqual(restored.savedX, 120)
        self.assertEqual(restored.savedY, 80)
        self.assertEqual(restored.savedWidth, 1440)
        self.assertEqual(restored.savedHeight, 900)
        self.assertFalse(restored.isMaximized)
        self.assertFalse(restored.isFirstLaunch)


class ThemeSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._settings_dir = tempfile.TemporaryDirectory()
        QCoreApplication.setOrganizationName("NetworkToolsThemeTests")
        QCoreApplication.setApplicationName("ThemeSettingsTests")
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            cls._settings_dir.name,
        )

    def setUp(self) -> None:
        QSettings().clear()

    @classmethod
    def tearDownClass(cls) -> None:
        QSettings().clear()
        cls._settings_dir.cleanup()

    def test_high_contrast_is_persisted_independently_from_base_mode(self) -> None:
        first = ThemeSettings()
        first.themeMode = 1
        first.highContrast = True

        restored = ThemeSettings()
        self.assertEqual(restored.themeMode, 1)
        self.assertTrue(restored.highContrast)

    def test_legacy_high_contrast_mode_is_migrated(self) -> None:
        settings = QSettings()
        settings.setValue("Theme/themeMode", 4)
        settings.sync()

        migrated = ThemeSettings()
        self.assertEqual(migrated.themeMode, 2)
        self.assertTrue(migrated.highContrast)
        self.assertEqual(QSettings().value("Theme/themeMode", type=int), 2)
        self.assertTrue(QSettings().value("Theme/highContrast", type=bool))

    def test_system_accent_preference_is_persisted(self) -> None:
        first = ThemeSettings()
        self.assertFalse(first.useSystemAccentColor)
        first.useSystemAccentColor = True

        restored = ThemeSettings()
        self.assertTrue(restored.useSystemAccentColor)
        self.assertTrue(
            QSettings().value("Theme/useSystemAccentColor", type=bool)
        )


class NatQmlBridgeContractTests(unittest.TestCase):
    def test_acl_slot_converts_qjsvalue_payload(self) -> None:
        expected = {"host": "10.0.0.1", "acl_name": "EDGE_IN"}

        class FakeQjsValue:
            def toVariant(self):
                return expected

        class Bridge(AclSlotsMixin):
            @staticmethod
            def _as_dict(value):
                if hasattr(value, "toVariant"):
                    value = value.toVariant()
                return value if isinstance(value, dict) else {}

        with patch("core.acl_slots.save_acl", return_value=True) as save:
            self.assertTrue(Bridge().saveAcl(FakeQjsValue()))
            save.assert_called_once_with(ANY, expected)

    def test_dynamic_nat_uses_acl_combo_and_nat_tabs_auto_reload(self) -> None:
        nat_dir = Path(__file__).resolve().parents[1] / "UI" / "qml" / "features" / "nat"
        dynamic_source = (nat_dir / "NatDynamicForm.qml").read_text(encoding="utf-8")
        route_map_source = (nat_dir / "NatRouteMapForm.qml").read_text(encoding="utf-8")
        view_source = (nat_dir / "NatView.qml").read_text(encoding="utf-8")

        self.assertIn("id: dynamicAclCombo", dynamic_source)
        self.assertIn("model: natDynamicForm.aclNames", dynamic_source)
        self.assertIn("dbManager.getNatAclNames(currentHostIp)", dynamic_source)
        self.assertNotIn("id:               aclNameField", dynamic_source)
        self.assertIn("id: routeMapAclCombo", route_map_source)
        self.assertIn("model: [\"No ACL\"].concat(routeMapForm.aclNames)", route_map_source)
        self.assertIn("dbManager.getNatAclNames(currentHostIp)", route_map_source)
        self.assertNotIn("id: aclNameField", route_map_source)
        self.assertIn("function reloadSelectedNatTab()", view_source)
        self.assertIn("dynamicLoader.item.reloadAclNames()", view_source)
        self.assertIn("dynamicLoader.item.reloadPools()", view_source)
        self.assertIn("patLoader.item.reloadAclNames()", view_source)
        self.assertIn("patLoader.item.reloadRules()", view_source)
        self.assertIn("routeMapLoader.item.reloadAclNames()", view_source)
        self.assertIn("routeMapLoader.item.reloadEntries()", view_source)

    def test_dhcp_forms_use_staged_save_and_cancel_contract(self) -> None:
        dhcp_dir = Path(__file__).resolve().parents[1] / "UI" / "qml" / "features" / "dhcp"
        for form_name in ("DhcpPoolForm.qml", "DhcpExcludedForm.qml", "DhcpHelperForm.qml"):
            source = (dhcp_dir / form_name).read_text(encoding="utf-8")
            with self.subTest(form=form_name):
                self.assertIn("property bool hasPendingLocalChanges", source)
                self.assertIn("function saveChanges()", source)
                self.assertIn("function cancelChanges()", source)
                self.assertIn('text: "Cancel Changes"', source)
                self.assertIn('text: "Save"', source)

    def test_acl_edit_change_cancel_and_module_size_contract(self) -> None:
        acl_dir = Path(__file__).resolve().parents[1] / "UI" / "qml" / "features" / "acl"
        editor = (acl_dir / "AclEditorPane.qml").read_text(encoding="utf-8")
        saved = (acl_dir / "AclSavedPanel.qml").read_text(encoding="utf-8")
        form = (acl_dir / "AclForm.qml").read_text(encoding="utf-8")
        self.assertIn('text: "View"', saved)
        self.assertIn('text: "Edit"', saved)
        self.assertIn('pane.viewing ? "Close View" : "Cancel"', editor)
        self.assertIn('text: pane.editing ? "Change ACL" : "Create ACL"', editor)
        self.assertIn("AclScrollablePane", editor)
        scroll_pane = (acl_dir / "AclScrollablePane.qml").read_text(encoding="utf-8")
        self.assertIn("ScrollBar.vertical", scroll_pane)
        self.assertIn("function viewAcl(index)", form)
        self.assertIn("function stageDeleteAcl(aclId)", form)
        self.assertIn("function savePendingDeletes()", form)
        self.assertIn("dbManager.deleteAcls(pendingDeleteIds)", form)
        self.assertIn('text: "Save"', form)
        self.assertIn('text: "Cancel Deletes"', form)
        bindings = (acl_dir / "AclBindingsEditor.qml").read_text(encoding="utf-8")
        binding_tab = (acl_dir / "AclBindingsTab.qml").read_text(encoding="utf-8")
        subbar = (acl_dir / "AclSubBar.qml").read_text(encoding="utf-8")
        self.assertIn("function addBinding()", bindings)
        self.assertIn('"Bindings"', subbar)
        self.assertIn("dbManager.saveAclBindings", binding_tab)
        self.assertNotIn("AclBindingsEditor", editor)

        feature_files = list(acl_dir.glob("*.qml"))
        feature_files += list((Path(__file__).resolve().parents[1] / "UI" / "qml" / "features" / "dhcp").glob("*.qml"))
        feature_files += list((Path(__file__).resolve().parents[1] / "features" / "acl").glob("*.py"))
        feature_files += list((Path(__file__).resolve().parents[1] / "features" / "dhcp").glob("*.py"))
        for path in feature_files:
            with self.subTest(path=path.name):
                self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 400)

    def test_acl_permit_deny_combo_uses_semantic_option_colors(self) -> None:
        ui_root = Path(__file__).resolve().parents[1] / "UI"
        combo = (
            ui_root / "components" / "standard" / "StandardComboBox.qml"
        ).read_text(encoding="utf-8")
        editor = (
            ui_root / "qml" / "features" / "acl" / "AclEditorPane.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("property var optionColors: []", combo)
        self.assertIn("property var optionBackgroundColors: []", combo)
        self.assertIn("root.optionColor(combo.currentIndex)", combo)
        self.assertIn("root.optionColor(del.index)", combo)
        self.assertIn('model: ["Permit", "Deny"]', editor)
        self.assertIn(
            "optionColors: [Theme.statusConnected, Theme.alertError]",
            editor,
        )
        self.assertIn(
            "optionBackgroundColors: [Theme.alertSuccessSubtle, Theme.alertErrorSubtle]",
            editor,
        )

    def test_every_nat_form_exposes_save_cancel_and_reload_actions(self) -> None:
        nat_dir = Path(__file__).resolve().parents[1] / "UI" / "qml" / "features" / "nat"
        form_names = (
            "NatStaticForm.qml",
            "NatDynamicForm.qml",
            "NatPatForm.qml",
            "NatInterfaceForm.qml",
            "NatAclForm.qml",
            "NatRouteMapForm.qml",
        )
        for form_name in form_names:
            source = (nat_dir / form_name).read_text(encoding="utf-8")
            with self.subTest(form=form_name):
                self.assertIn('text: "Save"', source)
                self.assertIn('text: "Cancel Changes"', source)
                self.assertIn('text: "Reload UI"', source)
                self.assertIn("property bool hasPendingLocalChanges", source)
                self.assertIn("function saveChanges()", source)

    def test_nat_add_slots_match_qml_positional_arity(self) -> None:
        # Expected counts include `self` and mirror the current QML form calls.
        expected_parameter_counts = {
            "addNatStaticEntry": 7,
            "addNatDynamicPool": 7,
            "addNatPatRule": 6,
            "addNatAcl": 6,
            "addNatRouteMapEntry": 7,
        }

        for method_name, expected_count in expected_parameter_counts.items():
            with self.subTest(method=method_name):
                method = getattr(NatSlotsMixin, method_name)
                self.assertEqual(len(inspect.signature(method).parameters), expected_count)


class SvgResourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_root = Path(__file__).resolve().parents[1] / "UI"
        cls.resources = cls.ui_root / "resources"
        cls.app_assets = cls.ui_root / "qml" / "shared" / "AppAssets.qml"

    def test_active_svg_paths_are_centralized_and_resolve(self) -> None:
        source = self.app_assets.read_text(encoding="utf-8")
        paths = re.findall(
            r'readonly property url \w+: resource\("([^"]+\.svg)"\)',
            source,
        )

        self.assertEqual(len(paths), 124)
        self.assertEqual(len(paths), len(set(paths)))
        for path in paths:
            with self.subTest(asset=path):
                self.assertTrue((self.ui_root / path).is_file())

        mapped = {path.removeprefix("resources/") for path in paths}
        active = {
            path.relative_to(self.resources).as_posix()
            for path in self.resources.rglob("*.svg")
        }
        self.assertEqual(active, mapped)

    def test_qml_consumers_use_semantic_app_assets_only(self) -> None:
        for path in self.ui_root.rglob("*.qml"):
            if path == self.app_assets:
                continue
            source = path.read_text(encoding="utf-8")
            with self.subTest(qml=path.relative_to(self.ui_root).as_posix()):
                self.assertNotRegex(source, r"resources/[A-Za-z0-9_./-]+\.svg")
                self.assertNotIn("AppAssets.resource(", source)

class ButtonIconContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_root = Path(__file__).resolve().parents[1] / "UI"
        cls.qml_files = tuple(cls.ui_root.rglob("*.qml"))
        cls.button_blocks = [
            (path, block)
            for path in cls.qml_files
            for block in _qml_component_blocks(path.read_text(encoding="utf-8"), "StandardButton")
        ]

    def test_button_action_assets_exist(self) -> None:
        asset_dir = self.ui_root / "resources" / "actions"
        for asset_name in (
            "backup.svg",
            "database-reload.svg",
            "push.svg",
            "save.svg",
        ):
            with self.subTest(asset=asset_name):
                self.assertTrue((asset_dir / asset_name).is_file())

    def test_reload_and_save_buttons_have_semantic_icons(self) -> None:
        reload_blocks = [
            block
            for _, block in self.button_blocks
            if re.search(r'text:\s*"Reload UI"', block)
        ]
        save_blocks = [
            block
            for _, block in self.button_blocks
            if re.search(r"^\s*text:.*\bSave(?:\s|\"|$)", block, flags=re.MULTILINE)
        ]

        self.assertEqual(len(reload_blocks), 23)
        self.assertTrue(
            all(
                "AppAssets.actionDatabaseReload" in block
                or "AppAssets.actionBackup" in block
                for block in reload_blocks
            )
        )
        self.assertTrue(all("autoCompact: false" in block for block in reload_blocks))
        self.assertTrue(
            all("Layout.minimumWidth: expandedImplicitWidth" in block
                for block in reload_blocks)
        )
        self.assertGreaterEqual(len(save_blocks), 17)
        self.assertTrue(all("AppAssets.actionSave" in block for block in save_blocks))

    def test_interface_row_actions_use_edit_and_delete_assets(self) -> None:
        source = (
            self.ui_root / "qml" / "features" / "interfaces" / "InterfaceView.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("iconSource: AppAssets.actionEdit", source)
        self.assertIn('tooltip: "Edit interface"', source)
        self.assertIn("iconSource: AppAssets.actionDelete", source)
        self.assertIn('tooltip: "Delete interface"', source)
        self.assertNotIn('glyph: "..."', source)
        self.assertNotIn('glyph: "X"', source)

    def test_view_push_and_running_config_backup_use_distinct_icons(self) -> None:
        view_push = (self.ui_root / "qml" / "shared" / "ViewPushButton.qml").read_text(
            encoding="utf-8"
        )
        dialog = (self.ui_root / "qml" / "shared" / "ViewPushDialog.qml").read_text(
            encoding="utf-8"
        )
        batch_dialog = (
            self.ui_root / "qml" / "shared" / "MultiHostViewPushDialog.qml"
        ).read_text(encoding="utf-8")
        preview_pane = (
            self.ui_root / "qml" / "shared" / "ConfigurationPreviewPane.qml"
        ).read_text(encoding="utf-8")
        standard_button = (
            self.ui_root / "components" / "standard" / "StandardButton.qml"
        ).read_text(encoding="utf-8")
        device_menu = (
            self.ui_root / "qml" / "sidebar" / "devices" / "DeviceContextMenu.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("AppAssets.actionPush", view_push)
        self.assertIn('type: "Primary"', view_push)
        self.assertIn("if (!root.enabled) return Theme.sideBarBackground", standard_button)
        self.assertIn("if (root.type === \"Primary\")", standard_button)
        self.assertIn("Theme.accentEmphasis", standard_button)
        self.assertIn("AppAssets.actionDatabaseReload", dialog)
        self.assertIn("AppAssets.actionPush", dialog)
        self.assertIn('objectName: "viewPushCancelButton"', dialog)
        self.assertIn('text: "Cancel"', dialog)
        self.assertIn("onClicked: dialog.reject()", dialog)
        self.assertIn("ConfigurationPreviewPane {", dialog)
        self.assertIn("ConfigurationPreviewPane {", batch_dialog)
        self.assertIn("ScrollBar.vertical: ScrollBar", preview_pane)
        self.assertIn("ScrollBar.horizontal: ScrollBar", preview_pane)
        self.assertGreaterEqual(preview_pane.count("policy: ScrollBar.AsNeeded"), 2)
        self.assertIn("onPreviewTextChanged: Qt.callLater(root.scrollToStart)", preview_pane)
        self.assertIn("AppAssets.actionBackup", device_menu)

        view_push_blocks = [
            (path, block)
            for path in self.qml_files
            for block in _qml_component_blocks(
                path.read_text(encoding="utf-8"), "ViewPushButton"
            )
        ]
        self.assertGreaterEqual(len(view_push_blocks), 12)
        for path, block in view_push_blocks:
            with self.subTest(qml=path.relative_to(self.ui_root).as_posix()):
                self.assertNotIn('type: "Secondary"', block)

    def test_documented_standard_button_icon_coverage(self) -> None:
        buttons_with_icons = [
            block for _, block in self.button_blocks if re.search(r"\bicon\.source\s*:", block)
        ]
        # Actionable notifications add two text-only actions; the SSH
        # compatibility dialog adds one themed Close action. The independent
        # Welcome flow adds Create/Cancel, a reusable theme choice, and Done.
        # Router Interface replaces its former hard-coded port-family action
        # with one text-only virtual-interface create action.
        # The per-device Syslog page adds nine icon-bearing CRUD/push actions.
        self.assertEqual(len(self.button_blocks), 237)
        self.assertEqual(len(buttons_with_icons), 95)
        self.assertEqual(len(self.button_blocks) - len(buttons_with_icons), 142)

    def test_routing_group_replaces_clone_workflow(self) -> None:
        routing_root = self.ui_root / "qml" / "features" / "routing"
        group = (routing_root / "RoutingGroupDialog.qml").read_text(encoding="utf-8")
        ospf = (routing_root / "ospf" / "OspfRoutingForm.qml").read_text(encoding="utf-8")
        eigrp = (routing_root / "eigrp" / "EigrpRoutingForm.qml").read_text(encoding="utf-8")

        self.assertIn('title: "Routing Group · "', group)
        self.assertIn('text: "Save"', group)
        self.assertIn('"Save & Push"', group)
        self.assertNotIn('text: "Clone"', ospf)
        self.assertNotIn('text: "Clone"', eigrp)
        self.assertNotIn('"Save & Push"', ospf)
        self.assertNotIn('"Save & Push"', eigrp)
        ospf_networks = (
            routing_root / "ospf" / "OspfNetworksSection.qml"
        ).read_text(encoding="utf-8")
        self.assertIn('id: ospfAreaField', ospf_networks)
        self.assertGreaterEqual(ospf_networks.count('ospfAreaField.text = "0"'), 2)

        batch = (
            self.ui_root / "qml" / "shared" / "MultiHostViewPushDialog.qml"
        ).read_text(encoding="utf-8")
        self.assertIn("pushViewPushBatchAsync", batch)
        self.assertNotIn("property var pushQueue", batch)
        self.assertNotIn("function pushNext()", batch)

    def test_fhrp_uses_protocol_subtabs_with_independent_pages(self) -> None:
        fhrp_root = self.ui_root / "qml" / "features" / "fhrp"
        view = (fhrp_root / "FhrpView.qml").read_text(encoding="utf-8")
        subbar = (fhrp_root / "FhrpSubBar.qml").read_text(encoding="utf-8")
        page = (fhrp_root / "FhrpProtocolPage.qml").read_text(encoding="utf-8")
        member = (fhrp_root / "FhrpMemberEditor.qml").read_text(encoding="utf-8")
        options = (fhrp_root / "FhrpProtocolOptionsEditor.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn('tabs: ["HSRP", "VRRP", "GLBP"]', subbar)
        self.assertEqual(view.count("FhrpProtocolPage {"), 3)
        self.assertIn('protocol: "hsrp"', view)
        self.assertIn('protocol: "vrrp"', view)
        self.assertIn('protocol: "glbp"', view)
        self.assertNotIn("protocolCombo", page)
        self.assertIn('objectName: "fhrpSummaryGrid"', page)
        self.assertIn('objectName: "fhrpHostPicker"', page)
        self.assertIn('title: "Member policy"', page)
        self.assertIn('title: "Group authentication"', page)
        self.assertIn("groupAuthType", page)
        self.assertNotIn('labelText: "Authentication"', member)
        self.assertIn('text: "Reset"', page)
        self.assertNotIn("ViewPushButton {", page)
        self.assertNotIn('text: "Save & Push"', page)
        self.assertEqual(page.count('text: "View & Push"'), 1)
        self.assertIn('objectName: "fhrpViewPushButton"', page)
        self.assertIn("batchDialog.openPreview(pendingPushHosts, protocol)", page)
        self.assertIn('objectName: "fhrpReloadButton"', page)
        self.assertIn('text: "Reload UI"', page)
        self.assertIn("autoCompact: false", page)
        self.assertIn("width: Math.ceil(expandedImplicitWidth)", page)
        self.assertIn("FhrpProtocolOptionsEditor {", page)
        self.assertIn("advertisement_ms: root.advertisementMs", page)
        self.assertIn("load_balancing: root.loadBalancing", page)
        self.assertIn("preempt_delay_min_sec:", page)
        self.assertIn("weighting_max:", page)
        self.assertIn("tracks: parseTracks(row.tracksJson)", page)
        self.assertIn('labelText: "HSRP version"', options)
        self.assertIn('labelText: "Advertisement interval (ms)"', options)
        self.assertIn('labelText: "Load balancing"', options)
        self.assertIn('labelText: "Preempt minimum delay (sec)"', member)
        self.assertIn('labelText: "Maximum weighting"', member)
        self.assertIn('text: "Add tracking object"', member)

    def test_sftp_assets_are_deduplicated_and_use_semantic_bindings(self) -> None:
        resources = self.ui_root / "resources"
        self.assertFalse((resources / "sftp_icons").exists())
        self.assertFalse((resources / "_unused").exists())
        self.assertIn(
            "Lucide Icons",
            (resources / "licenses" / "LUCIDE.txt").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "vscode-icons",
            (resources / "licenses" / "VSCODE-ICONS.txt").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "Material Extensions",
            (resources / "licenses" / "MATERIAL-ICON-THEME.txt").read_text(
                encoding="utf-8"
            ),
        )

        connection = (self.ui_root / "qml" / "sftp" / "SftpConnectionBar.qml").read_text(
            encoding="utf-8"
        )
        panel = (self.ui_root / "qml" / "sftp" / "SftpFilePanel.qml").read_text(
            encoding="utf-8"
        )
        file_menu = (
            self.ui_root / "qml" / "sftp" / "SftpFileContextMenu.qml"
        ).read_text(encoding="utf-8")
        queue = (self.ui_root / "qml" / "sftp" / "SftpTransferQueue.qml").read_text(
            encoding="utf-8"
        )
        log_panel = (self.ui_root / "qml" / "sftp" / "SftpLogPanel.qml").read_text(
            encoding="utf-8"
        )
        view = (self.ui_root / "qml" / "sftp" / "SftpView.qml").read_text(
            encoding="utf-8"
        )
        for relative_path in (
            "actions/connect.svg",
            "actions/disconnect.svg",
            "actions/upload.svg",
            "actions/download.svg",
            "actions/edit.svg",
            "actions/delete.svg",
            "actions/refresh.svg",
            "files/folder.svg",
            "files/file.svg",
            "files/types/docker.svg",
            "files/types/hex.svg",
            "files/types/python.svg",
        ):
            with self.subTest(asset=relative_path):
                self.assertTrue((resources / relative_path).is_file())
        self.assertIn("AppAssets.actionConnect", connection)
        self.assertIn("AppAssets.fileTypeIcon(name)", panel)
        self.assertIn("source: row.isDirectory", panel)
        self.assertIn('header: true; text: "Type"', panel)
        self.assertRegex(
            panel,
            r"text: row\.typeText\s+elide: Text\.ElideRight\s+color: Theme\.textSecondary",
        )
        self.assertNotIn("iconColor: root.selectedIndex === row.index", panel)
        self.assertNotIn("Theme.selectionForeground", panel)
        self.assertRegex(panel, r"text: row\.name\s+elide: Text\.ElideRight\s+color: Theme\.textPrimary")
        self.assertRegex(panel, r"text: row\.sizeText\s+color: Theme\.textSecondary")
        self.assertRegex(
            panel,
            r"text: row\.modified\s+elide: Text\.ElideRight\s+color: Theme\.textSecondary",
        )
        self.assertIn("AppAssets.actionUpload", panel)
        self.assertIn("AppAssets.actionDelete", queue)
        self.assertNotIn("AppAssets.resource", connection + panel + queue)
        self.assertIn("maximumEntries: 500", log_panel)
        self.assertIn("while (logModel.count >= root.maximumEntries)", log_panel)
        self.assertIn("SftpLogPanel {", view)
        self.assertIn("AppAssets.navigationChevronLeft", panel)
        self.assertIn("AppAssets.navigationChevronRight", panel)
        self.assertIn("AppAssets.navigationUp", panel)
        self.assertNotRegex(panel, r'text:\s*"(?:Back|Forward|Up|Refresh)"')
        self.assertIn('sequence: "Alt+Left"', view)
        self.assertIn('sequence: "Alt+Right"', view)
        self.assertIn("property var selectedIndices: []", panel)
        self.assertIn("mouse.modifiers", panel)
        self.assertIn("backend.deleteEntries", panel)
        self.assertIn("sequence: StandardKey.SelectAll", view)
        self.assertIn("Qt.LeftButton | Qt.RightButton", panel)
        self.assertIn("root.isSelected(row.index)", panel)
        self.assertIn('shortcutText: "F2"', file_menu)
        self.assertIn('shortcutText: "Ctrl+A"', file_menu)
        self.assertNotIn("UiState.windowLock", file_menu)
        self.assertIn('sequence: "Shift+F10"', view)
        self.assertIn('sequence: "Alt+Up"', view)
        self.assertIn("Qt.BackButton | Qt.ForwardButton", view)
        self.assertIn("activePane ? Theme.accentColor", panel)

        sidebar = (self.ui_root / "qml" / "panels" / "PanelSideBar.qml").read_text(
            encoding="utf-8"
        )
        settings_panel = (
            self.ui_root / "qml" / "panels" / "SettingsPanel.qml"
        ).read_text(encoding="utf-8")
        settings_view = (
            self.ui_root / "qml" / "content" / "SettingsView.qml"
        ).read_text(encoding="utf-8")
        self.assertIn('appMode === "sftp"', sidebar)
        self.assertIn("SftpConnectionsPanel {", sidebar)
        self.assertIn('"key": "sftp"', settings_panel)
        self.assertIn("SftpSettings {", settings_view)

    def test_sidebar_snap_and_network_focus_cleanup_are_explicit(self) -> None:
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(
            encoding="utf-8"
        )
        text_field = (
            self.ui_root / "components" / "standard" / "StandardTextField.qml"
        ).read_text(encoding="utf-8")
        network_field = (
            self.ui_root / "components" / "standard" / "StandardNetworkField.qml"
        ).read_text(encoding="utf-8")

        for contract in (
            "readonly property real minSidebarWidth: 170",
            "readonly property real sidebarSnapThreshold: minSidebarWidth / 2",
            "function applySidebarDragWidth(desiredWidth)",
            "desired < sidebarSnapThreshold",
            'objectName: "sidebarResizeArea"',
            "dragStartSidebarWidth",
        ):
            with self.subTest(sidebar_contract=contract):
                self.assertIn(contract, main)
        self.assertNotIn("SplitView {", main)
        self.assertIn("Qt.callLater(inputField.hideCursorAfterFocusOut)", text_field)
        self.assertIn("if (!activeFocus)", text_field)
        self.assertIn("onInputActiveFocusChanged", network_field)
        self.assertIn("if (!inputActiveFocus)", network_field)

    def test_responsive_workspace_contract_prevents_zero_width_and_overflow(self) -> None:
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(
            encoding="utf-8"
        )
        sizes = (
            self.ui_root / "theme" / "tokens" / "SizeTokens.qml"
        ).read_text(encoding="utf-8")
        theme = (self.ui_root / "theme" / "Theme.qml").read_text(encoding="utf-8")
        button = (
            self.ui_root / "components" / "standard" / "StandardButton.qml"
        ).read_text(encoding="utf-8")
        split_pane = (
            self.ui_root / "components" / "layout" / "SplitFormPane.qml"
        ).read_text(encoding="utf-8")
        control_bar = (
            self.ui_root / "qml" / "features" / "syslog" / "SyslogControlBar.qml"
        ).read_text(encoding="utf-8")
        filter_bar = (
            self.ui_root / "qml" / "features" / "syslog" / "SyslogFilterBar.qml"
        ).read_text(encoding="utf-8")
        log_table = (
            self.ui_root / "qml" / "features" / "syslog" / "SyslogLogTable.qml"
        ).read_text(encoding="utf-8")
        information = (
            self.ui_root / "qml" / "content" / "InformationView.qml"
        ).read_text(encoding="utf-8")
        dropdown = (
            self.ui_root / "qml" / "feature" / "FeatureDropdown.qml"
        ).read_text(encoding="utf-8")
        switch_monitoring = (
            self.ui_root
            / "qml"
            / "features"
            / "switching"
            / "monitoring"
            / "SwitchMonitoringPage.qml"
        ).read_text(encoding="utf-8")

        for contract in (
            "readonly property int windowMinWidth: 1024",
            "readonly property int windowMinHeight: 700",
            "readonly property int inputMinimumWidth: 120",
            "readonly property int minimumWorkspaceWidth: 640",
            "readonly property int compactWorkspaceBreakpoint: 640",
            "readonly property int largeWorkspaceBreakpoint: 1008",
        ):
            with self.subTest(size_contract=contract):
                self.assertIn(contract, sizes)
        for token in (
            "inputMinimumWidth",
            "minimumWorkspaceWidth",
            "compactWorkspaceBreakpoint",
            "largeWorkspaceBreakpoint",
        ):
            self.assertIn(f"SizeTokens.{token}", theme)

        self.assertIn("readonly property real effectiveMaxSidebarWidth", main)
        self.assertIn("- Theme.splitHandleWidth - Theme.minimumWorkspaceWidth", main)
        self.assertIn("onEffectiveMaxSidebarWidthChanged", main)
        self.assertIn("readonly property bool compactContent", button)
        self.assertIn("Layout.minimumWidth: minimumUsableWidth", button)
        self.assertIn("root.tooltip !== \"\" ? root.tooltip : root.text", button)

        for input_name in (
            "StandardTextField.qml",
            "StandardComboBox.qml",
            "StandardSpinBox.qml",
            "StandardPasswordField.qml",
        ):
            source = (
                self.ui_root / "components" / "standard" / input_name
            ).read_text(encoding="utf-8")
            with self.subTest(input=input_name):
                self.assertIn(
                    "Layout.minimumWidth: Theme.inputMinimumWidth",
                    source,
                )

        self.assertIn("ScrollView {", split_pane)
        self.assertIn('objectName: "splitFormPaneScroll"', split_pane)
        self.assertIn("paneLayout.implicitHeight", split_pane)
        self.assertIn("GridLayout {", control_bar)
        self.assertIn("controlLayout.implicitHeight + Theme.spacing24", control_bar)
        self.assertIn("GridLayout {", filter_bar)
        self.assertIn("filterLayout.implicitHeight + Theme.spacing24", filter_bar)
        self.assertIn("readonly property bool compactColumns", log_table)
        self.assertIn("visible: !root.compactColumns", log_table)
        self.assertIn("readonly property bool compactLayout", information)
        self.assertIn('objectName: "informationPrimaryVersionLayout"', information)
        self.assertIn("readonly property bool compactColumns", switch_monitoring)
        self.assertIn("&& !root.compactColumns", switch_monitoring)

        adaptive_splits = (
            "qml/features/acl/AclForm.qml",
            "qml/features/interfaces/InterfaceView.qml",
            "qml/features/dhcp/DhcpExcludedForm.qml",
            "qml/features/dhcp/DhcpHelperForm.qml",
            "qml/features/dhcp/DhcpPoolForm.qml",
            "qml/features/nat/NatStaticForm.qml",
            "qml/features/nat/NatDynamicForm.qml",
            "qml/features/nat/NatInterfaceForm.qml",
            "qml/features/nat/NatPatForm.qml",
            "qml/features/nat/NatRouteMapForm.qml",
            "qml/features/nat/NatAclForm.qml",
        )
        for relative_path in adaptive_splits:
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(adaptive_split=relative_path):
                self.assertIn(
                    "width < Theme.dataWorkspaceBreakpoint",
                    source,
                )
                self.assertRegex(
                    source,
                    r"orientation:\s+\w+\.compactLayout\s+\?\s+Qt\.Vertical",
                )

        self.assertIn("required property var modelData", dropdown)
        self.assertIn("dropdownRow.modelData", dropdown)

    def test_narrow_settings_cards_and_contextual_shortcuts_have_single_owners(
        self,
    ) -> None:
        settings_panel = (
            self.ui_root / "qml" / "panels" / "SettingsPanel.qml"
        ).read_text(encoding="utf-8")
        devices_panel = (
            self.ui_root / "qml" / "panels" / "DevicesPanel.qml"
        ).read_text(encoding="utf-8")
        sftp_view = (
            self.ui_root / "qml" / "sftp" / "SftpView.qml"
        ).read_text(encoding="utf-8")
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "implicitHeight: Math.max(72, contentImplicitHeight + 24)",
            settings_panel,
        )
        for shortcut in ('"Ctrl+N"', '"Ctrl+Alt+N"'):
            self.assertIn(
                f"Shortcut {{ sequence: {shortcut}; "
                "enabled: devicesPanel.deviceShortcutEnabled;",
                devices_panel,
            )
        self.assertIn('sequence: "Ctrl+Shift+N"', sftp_view)
        self.assertNotIn('sequence: "Ctrl+R"', sftp_view)
        self.assertIn(
            "reloadAvailable: root.isSftpMode || contentArea.reloadCommandEnabled",
            main,
        )

    def test_ospf_network_remove_action_uses_existing_standard_icon(self) -> None:
        source = (
            self.ui_root / "qml" / "features" / "routing" / "ospf" / "OspfNetworksSection.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("RemoveIconButton {", source)
        self.assertNotIn("AppAssets.resource", source)
        self.assertTrue((self.ui_root / "resources" / "actions" / "close.svg").is_file())

    def test_syslog_uses_current_workspace_table_and_resource_contracts(self) -> None:
        workspace = (self.ui_root / "qml" / "features" / "syslog" / "SyslogWorkspace.qml").read_text(
            encoding="utf-8"
        )
        table = (self.ui_root / "qml" / "features" / "syslog" / "SyslogLogTable.qml").read_text(
            encoding="utf-8"
        )
        row = (self.ui_root / "qml" / "features" / "syslog" / "SyslogLogRow.qml").read_text(
            encoding="utf-8"
        )
        settings = (
            self.ui_root / "qml" / "features" / "syslog" / "SyslogServerSettings.qml"
        ).read_text(encoding="utf-8")
        config_page = (
            self.ui_root / "qml" / "features" / "syslog" / "SyslogDeviceConfigPage.qml"
        ).read_text(encoding="utf-8")
        context_menu = (
            self.ui_root / "qml" / "sidebar" / "syslog" / "SyslogDeviceContextMenu.qml"
        ).read_text(encoding="utf-8")
        devices_panel = (
            self.ui_root / "qml" / "panels" / "SyslogDevicesPanel.qml"
        ).read_text(encoding="utf-8")
        activity_bar = (self.ui_root / "qml" / "layout" / "ActivityBar.qml").read_text(
            encoding="utf-8"
        )
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(encoding="utf-8")

        self.assertIn("WorkspaceHeader {", workspace)
        self.assertIn("maximumEntries: 2000", workspace)
        self.assertIn("function matchesFilters(row)", workspace)
        self.assertIn("DataTable {", table)
        self.assertIn("DataTableHeader {", table)
        self.assertIn("DataTableRow {", row)
        self.assertGreaterEqual(row.count("DataTableCell {"), 6)
        self.assertGreaterEqual(settings.count("FormSection {"), 3)
        self.assertIn('title: "Syslog Servers"', config_page)
        self.assertIn('controllerName: "syslog"', config_page)
        self.assertIn("CrudFormActions {", config_page)
        self.assertIn("getDeviceConfigurations(host)", config_page)
        self.assertIn("saveDeviceConfiguration(host, draftData)", config_page)
        self.assertIn("deleteDeviceConfiguration(host, clone(row))", config_page)
        self.assertIn("ContextMenuItem {", context_menu)
        self.assertIn("AppAssets.navigationSyslog", activity_bar)
        self.assertIn("id: syslogWorkspaceLoader", main)
        self.assertIn("asynchronous: true", main)
        self.assertIn('text: "HOSTS"', devices_panel)
        self.assertNotIn('text: "SYSTEM LOGS"', devices_panel)
        self.assertIn('objectName: "syslogPanelHostCountBadge"', devices_panel)
        self.assertIn("badgeColor: Theme.accentEmphasis", devices_panel)
        self.assertIn('objectName: "syslogPanelReloadButton"', devices_panel)
        self.assertIn('tooltip: root.busy ? "Refreshing Connected Hosts..."', devices_panel)
        self.assertNotIn("StandardButton {", devices_panel)
        self.assertNotIn("configureDevice(", devices_panel)
        self.assertNotIn("cancelDevice(", devices_panel)

    def test_add_and_new_buttons_do_not_use_add_icons(self) -> None:
        for path, block in self.button_blocks:
            with self.subTest(qml=path.name):
                self.assertNotIn("AppAssets.actionAdd", block)
                self.assertNotIn("AppAssets.actionListAdd", block)

    def test_cancel_changes_is_leftmost_text_action(self) -> None:
        cancel_consumers = []
        for path in self.qml_files:
            source = path.read_text(encoding="utf-8")
            if 'text: "Cancel Changes"' in source:
                cancel_consumers.append((path, source))

        self.assertEqual(len(cancel_consumers), 13)
        for path, source in cancel_consumers:
            cancel_blocks = [
                block
                for block in _qml_component_blocks(source, "StandardButton")
                if 'text: "Cancel Changes"' in block
            ]
            with self.subTest(qml=path.name):
                self.assertEqual(len(cancel_blocks), 1)
                self.assertIn('type: "Text"', cancel_blocks[0])
                if path.name == "ExternalToolsSettings.qml":
                    self.assertLess(
                        source.index('text: "Cancel Changes"'),
                        source.index('text: enabledToggle.checked ? "Use application" : "Save"'),
                    )
                elif path.name != "AclBindingsTab.qml":
                    self.assertLess(
                        source.index('text: "Cancel Changes"'),
                        source.index('text: "Reload UI"'),
                    )

    def test_every_cancel_action_uses_text_style(self) -> None:
        cancel_blocks = [
            (path, block)
            for path, block in self.button_blocks
            if re.search(r"\btext\s*:.*\"Cancel", block)
        ]

        # System Logs, Manual Sync, and Welcome project creation add
        # confirmation dialogs.
        self.assertEqual(len(cancel_blocks), 42)
        for path, block in cancel_blocks:
            with self.subTest(qml=path.name):
                self.assertIn('type: "Text"', block)

        edit_form_paths = (
            "qml/features/dhcp/DhcpPoolForm.qml",
            "qml/features/nat/NatStaticForm.qml",
            "qml/features/nat/NatDynamicForm.qml",
            "qml/features/nat/NatPatForm.qml",
            "qml/features/nat/NatInterfaceForm.qml",
            "qml/features/nat/NatAclForm.qml",
            "qml/features/nat/NatRouteMapForm.qml",
        )
        for relative_path in edit_form_paths:
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(order=relative_path):
                self.assertLess(
                    source.index('text: "Cancel"'),
                    source.index('? "Apply Edit" : "Add Locally"'),
                )

    def test_manual_sync_uses_the_correct_user_facing_name(self) -> None:
        context_menu = (
            self.ui_root / "qml" / "sidebar" / "devices" / "DeviceContextMenu.qml"
        ).read_text(encoding="utf-8")
        devices_panel = (
            self.ui_root / "qml" / "panels" / "DevicesPanel.qml"
        ).read_text(encoding="utf-8")

        self.assertIn('text: "Sync"', context_menu)
        self.assertNotIn('text: "Sys"', context_menu)
        self.assertIn("signal syncRequested(string ip)", context_menu)
        self.assertIn("signal sysSyncRequested(string ip)", context_menu)
        self.assertIn("onSyncRequested:", devices_panel)
        self.assertIn("cli.manualSyncAsync", devices_panel)
        self.assertIn("cli.applyManualSyncAsync", devices_panel)
        self.assertIn("Manual Sync started", devices_panel)
        self.assertIn('title: "Manual Sync conflict"', devices_panel)
        self.assertNotIn("Manual Sys", context_menu + devices_panel)

    def test_standard_button_has_keyboard_focus_ring_and_text_style(self) -> None:
        source = (
            self.ui_root / "components" / "standard" / "StandardButton.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("focusPolicy: Qt.StrongFocus", source)
        self.assertIn("if (root.visualFocus) return Theme.accentColor", source)
        self.assertIn('root.type === "Text" || root.type === "TextIcon"', source)
        self.assertIn('if (root.type === "TextIcon")', source)
        self.assertIn('font.bold: root.type === "Primary" || root.type === "Danger"', source)
        self.assertNotIn('root.type === "Danger" || root.type === "Text"', source)
        self.assertIn('root.type === "Text" && (hoverHandler.hovered || root.visualFocus)', source)


class QmlModuleContractTests(unittest.TestCase):
    def test_welcome_preserves_brand_colors_and_uses_contrast_safe_icons(self) -> None:
        ui_root = Path(__file__).resolve().parents[1] / "UI"
        welcome = (ui_root / "qml/app/Welcome.qml").read_text(encoding="utf-8")
        empty_workspace = (ui_root / "qml/content/WelcomeScreen.qml").read_text(
            encoding="utf-8"
        )
        action_card = (ui_root / "qml/welcome/WelcomeActionCard.qml").read_text(
            encoding="utf-8"
        )
        recent = (ui_root / "qml/welcome/RecentProjectDelegate.qml").read_text(
            encoding="utf-8"
        )
        project_icon = ET.parse(
            ui_root / "resources/brand/project-file-icon.svg"
        ).getroot()

        self.assertIn("preserveOriginalColors: true", welcome)
        self.assertIn("preserveOriginalColors: true", empty_workspace)
        self.assertIn("iconColor: Theme.selectionForeground", action_card)
        self.assertNotIn("brandProjectFileIcon", recent)
        svg_nodes = [
            node for node in project_icon.iter() if node.tag.endswith("}svg")
        ]
        self.assertEqual(len(svg_nodes), 1)

    def test_qmldir_exports_only_existing_qml_files(self) -> None:
        ui_root = Path(__file__).resolve().parents[1] / "UI"
        qmldir = (ui_root / "qmldir").read_text(encoding="utf-8")
        exports = 0
        for raw_line in qmldir.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", "module", "prefer")):
                continue
            candidate = line.split()[-1]
            if not candidate.endswith(".qml"):
                continue
            exports += 1
            with self.subTest(export=line.split()[0]):
                self.assertTrue((ui_root / candidate).is_file(), candidate)
        self.assertGreater(exports, 50)

    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_root = Path(__file__).resolve().parents[1] / "UI"

    def test_deprecated_base_components_are_removed_from_module(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        qml_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in self.ui_root.rglob("*.qml")
        )

        self.assertNotIn("BaseButton 1.0", qmldir)
        self.assertNotIn("BaseCard 1.0", qmldir)
        self.assertFalse((self.ui_root / "components" / "base" / "BaseButton.qml").exists())
        self.assertFalse((self.ui_root / "components" / "base" / "BaseCard.qml").exists())
        self.assertNotRegex(qml_source, r"\bBaseButton\s*\{")
        self.assertNotRegex(qml_source, r"\bBaseCard\s*\{")
        self.assertIn("ProcessCard 1.0 components/base/ProcessCard.qml", qmldir)

    def test_open_editors_sidebar_section_is_removed(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        devices = (
            self.ui_root / "qml" / "panels" / "DevicesPanel.qml"
        ).read_text(encoding="utf-8")
        sidebar = (
            self.ui_root / "qml" / "panels" / "PanelSideBar.qml"
        ).read_text(encoding="utf-8")
        tabs = (
            self.ui_root / "qml" / "devices" / "DeviceTabs.qml"
        ).read_text(encoding="utf-8")
        main = (
            self.ui_root / "qml" / "app" / "Main.qml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("OpenEditorsSection", qmldir + devices)
        self.assertFalse(
            (self.ui_root / "qml" / "panels" / "OpenEditorsSection.qml").exists()
        )
        self.assertNotIn("openEditors", sidebar)
        self.assertNotIn("openEditorsSnapshot", tabs)
        self.assertNotIn("onOpenEditorRequested", main)

    def test_panel_groups_expose_non_modal_collapse_expand_all_menu(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        devices = (
            self.ui_root / "qml" / "panels" / "DevicesPanel.qml"
        ).read_text(encoding="utf-8")
        section = (
            self.ui_root / "qml" / "sidebar" / "devices" / "DeviceSection.qml"
        ).read_text(encoding="utf-8")
        database = (
            self.ui_root / "qml" / "panels" / "DatabaseTablesPanel.qml"
        ).read_text(encoding="utf-8")
        database_section = (
            self.ui_root / "qml" / "panels" / "DatabaseTableSection.qml"
        ).read_text(encoding="utf-8")
        menu = (
            self.ui_root / "qml" / "panels" / "PanelGroupContextMenu.qml"
        ).read_text(encoding="utf-8")
        assets = (
            self.ui_root / "qml" / "shared" / "AppAssets.qml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "PanelGroupContextMenu 1.0 qml/panels/PanelGroupContextMenu.qml",
            qmldir,
        )
        self.assertIn("signal groupContextRequested", section)
        self.assertIn("acceptedButtons: Qt.RightButton", section)
        self.assertIn("function collapseAllDeviceGroups()", devices)
        self.assertIn("function expandAllDeviceGroups()", devices)
        self.assertIn("signal groupContextRequested", database_section)
        self.assertIn("acceptedButtons: Qt.RightButton", database_section)
        self.assertIn("function collapseAllDatabaseGroups()", database)
        self.assertIn("function expandAllDatabaseGroups()", database)
        self.assertIn("Object.assign({}, expandedGroups)", database)
        self.assertIn("PanelGroupContextMenu {", database)
        self.assertIn('text: "Collapse All"', menu)
        self.assertIn('text: "Expand All"', menu)
        self.assertNotIn("UiState.windowLock", menu)
        self.assertIn("AppAssets.navigationListCollapse", menu)
        self.assertIn("AppAssets.navigationListExpand", menu)
        self.assertIn("resources/navigation/list-collapse.svg", assets)
        self.assertIn("resources/navigation/list-expand.svg", assets)

    def test_system_accent_and_status_warning_use_shared_theme_pipeline(self) -> None:
        state = (
            self.ui_root / "theme" / "state" / "ThemeState.qml"
        ).read_text(encoding="utf-8")
        colors = (
            self.ui_root / "theme" / "tokens" / "ColorTokens.qml"
        ).read_text(encoding="utf-8")
        settings = (
            self.ui_root / "qml" / "content" / "SettingsView.qml"
        ).read_text(encoding="utf-8")
        status_bar = (
            self.ui_root / "qml" / "layout" / "StatusBar.qml"
        ).read_text(encoding="utf-8")
        main = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")

        self.assertIn("property SystemPalette systemPalette", state)
        self.assertIn("systemPalette.accent", state)
        self.assertIn("systemAppearanceBackend", state)
        self.assertIn("systemAppearanceBackend.prefersDark", state)
        self.assertIn(
            'context.setContextProperty("systemAppearance", system_appearance)',
            main,
        )
        self.assertIn("useSystemAccentColor", state)
        self.assertIn('objectName: "systemAccentCheckBox"', settings)
        self.assertIn("ThemeState.systemAccentColor", settings)
        self.assertIn("contrastRatio(statusBarBackground", colors)
        self.assertIn("Theme.statusBarWarningText", status_bar)

    def test_modal_dialogs_share_the_standard_surface_and_main_blur(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        standard = (
            self.ui_root / "components" / "standard" / "StandardDialog.qml"
        ).read_text(encoding="utf-8")
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(encoding="utf-8")

        self.assertIn(
            "StandardDialog 1.0 components/standard/StandardDialog.qml",
            qmldir,
        )
        for contract in (
            "parent: Overlay.overlay",
            "modal: true",
            "dim: true",
            "Overlay.modal: Rectangle",
            "DialogTitleBar {",
            "UiState.windowLock = true",
            "UiState.windowLock = false",
        ):
            with self.subTest(standard_dialog_contract=contract):
                self.assertIn(contract, standard)

        consumers = (
            "qml/sftp/SftpEntryDialog.qml",
            "qml/sftp/SftpMessageDialog.qml",
            "qml/sftp/SftpConnectionDialog.qml",
            "qml/sidebar/syslog/SyslogSourceInterfaceDialog.qml",
            "qml/features/syslog/SyslogMessageDetails.qml",
            "qml/content/ExternalToolsSettings.qml",
            "qml/shared/ViewPushDialog.qml",
        )
        for relative_path in consumers:
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(qml=relative_path):
                self.assertIn("StandardDialog {", source)

        self.assertIn("id: mainWorkspace", main)
        self.assertIn("layer.enabled: UiState.windowLock", main)
        self.assertIn("blurEnabled: true", main)
        self.assertIn("visible: UiState.windowLock && !root.active", main)

    def test_command_registry_owns_contextual_global_shortcuts(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        registry = (
            self.ui_root / "qml" / "shared" / "CommandRegistry.qml"
        ).read_text(encoding="utf-8")
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(encoding="utf-8")
        content = (
            self.ui_root / "qml" / "content" / "ContentArea.qml"
        ).read_text(encoding="utf-8")
        activity = (
            self.ui_root / "qml" / "layout" / "ActivityBar.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("CommandRegistry 1.0 qml/shared/CommandRegistry.qml", qmldir)
        self.assertIn("AppCommand 1.0 qml/shared/AppCommand.qml", qmldir)
        for command_id in (
            "project.new",
            "project.open",
            "workspace.save",
            "workspace.snapshot.create",
            "workspace.snapshot.history",
            "workspace.close",
            "app.quit",
            "view.reload",
            "view.sidebar.toggle",
            "view.dashboard",
            "view.sftp",
            "view.systemLogs",
            "view.database",
            "settings.open",
            "help.shortcuts",
            "app.about",
        ):
            with self.subTest(command_id=command_id):
                self.assertIn(f'commandId: "{command_id}"', registry)
        for contract in (
            'reloadShortcut: "Ctrl+R"',
            'dashboardShortcut: "Ctrl+Alt+D"',
            'sftpShortcut: "Ctrl+Alt+F"',
            'systemLogsShortcut: "Ctrl+Alt+L"',
            'databaseShortcut: "Ctrl+Alt+B"',
            'settingsShortcut: "Ctrl+,"',
            'shortcutGuideShortcut: "Ctrl+K, Ctrl+S"',
            "contextualCommandsEnabled: commandsEnabled && !inputFocusActive",
            "function triggerReload()",
            "function triggerDashboard()",
            "function triggerSftp()",
            "function triggerSystemLogs()",
            "function triggerDatabase()",
            "function triggerSettings()",
            "function triggerShortcutGuide()",
            "model: root.commands",
            "root.shortcutDispatchEnabled",
            "? Qt.ApplicationShortcut : Qt.WindowShortcut",
        ):
            with self.subTest(registry_contract=contract):
                self.assertIn(contract, registry)

        for contract in (
            'objectName: "appCommandRegistry"',
            "commandsEnabled: !UiState.windowLock",
            "inputFocusActive: root.textInputHasFocus",
            "reloadAvailable: root.isSftpMode || contentArea.reloadCommandEnabled",
            "databaseAvailable: activityBar.canActivateDatabase",
            "shortcutGuideHandler: function()",
            "ShortcutReferenceDialog {",
        ):
            with self.subTest(main_contract=contract):
                self.assertIn(contract, main)

        self.assertIn("readonly property bool reloadCommandEnabled", content)
        self.assertIn("function triggerReloadCommand()", content)
        self.assertIn('reloadData("shortcut", true)', content)
        self.assertIn("function activateDevices()", activity)
        self.assertIn("function activateSystemLogs()", activity)
        self.assertIn("function activateDatabase(toggleSidebarWhenActive)", activity)
        self.assertIn("function activateSettings()", activity)

        self.assertNotIn('saveShortcut: "Ctrl+S"', registry)
        self.assertNotIn('viewPushShortcut: "Ctrl+Shift+P"', registry)

        shortcut_dialog = (
            self.ui_root / "qml" / "shared" / "ShortcutReferenceDialog.qml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "ShortcutReferenceDialog 1.0 qml/shared/ShortcutReferenceDialog.qml",
            qmldir,
        )
        self.assertIn("StandardDialog {", shortcut_dialog)
        for section in (
            "Application",
            "General",
            "Activity Bar",
            "Devices",
            "Device tabs",
            "SFTP",
            "Interfaces",
            "Configuration viewer",
            "Dialogs",
        ):
            self.assertIn(f'sectionName: "{section}"', shortcut_dialog)

    def test_shortcut_map_reserves_number_keys_for_tabs_without_global_collisions(
        self,
    ) -> None:
        registry = (
            self.ui_root / "qml" / "shared" / "CommandRegistry.qml"
        ).read_text(encoding="utf-8")
        tabs = (
            self.ui_root / "qml" / "devices" / "DeviceTabs.qml"
        ).read_text(encoding="utf-8")

        global_shortcuts = re.findall(
            r'(?:shortcut|\w+Shortcut):\s*"([^"]+)"',
            registry,
        )
        self.assertEqual(len(global_shortcuts), len(set(global_shortcuts)))
        self.assertFalse(any(re.fullmatch(r"Ctrl\+[1-9]", key) for key in global_shortcuts))

        for number in range(1, 10):
            self.assertIn(f'sequence: "Ctrl+{number}"', tabs)
            self.assertIn(f"selectNumberedTab({number})", tabs)
        self.assertIn("number === 9 ? tabModel.count - 1", tabs)

    def test_about_is_an_independent_window_and_menu_icons_are_slightly_larger(
        self,
    ) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        about = (
            self.ui_root / "qml" / "app" / "AboutWindow.qml"
        ).read_text(encoding="utf-8")
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(
            encoding="utf-8"
        )
        registry = (
            self.ui_root / "qml" / "shared" / "CommandRegistry.qml"
        ).read_text(encoding="utf-8")
        modern_item = (
            self.ui_root / "qml" / "app" / "ModernMenuItem.qml"
        ).read_text(encoding="utf-8")
        context_item = (
            self.ui_root / "components" / "layout" / "ContextMenuItem.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("AboutWindow 1.0 qml/app/AboutWindow.qml", qmldir)
        self.assertIn("Window {", about)
        self.assertIn("modality: Qt.ApplicationModal", about)
        self.assertIn("flags: Qt.Dialog | Qt.FramelessWindowHint", about)
        self.assertIn("AboutWindow {", main)
        self.assertNotIn("id: aboutDialog", main)

        quit_block = next(
            block
            for block in _qml_component_blocks(registry, "AppCommand")
            if 'commandId: "app.quit"' in block
        )
        self.assertIn('shortcut: "Alt+F4"', quit_block)
        self.assertNotIn("iconSource:", quit_block)
        self.assertIn("iconSize: Theme.iconSizeNormal", modern_item)
        self.assertIn("property int iconSize: Theme.iconSizeNormal", context_item)

    def test_menu_presentation_backend_is_bridged(self) -> None:
        app_root = Path(__file__).resolve().parents[1]
        main = (app_root / "main.py").read_text(encoding="utf-8")
        facade = (app_root / "app_facade.py").read_text(encoding="utf-8")
        self.assertIn("MenuPresentationController", facade)
        self.assertIn("menu_presentation = MenuPresentationController()", main)
        self.assertIn(
            'context.setContextProperty("menuPresentation", menu_presentation)',
            main,
        )
        self.assertTrue(
            (app_root / "UI" / "qml" / "app" / "NativeGlobalMenuBar.qml").is_file()
        )

    def test_native_menu_is_lazy_and_uses_shared_command_contracts(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(
            encoding="utf-8"
        )
        native = (
            self.ui_root / "qml" / "app" / "NativeGlobalMenuBar.qml"
        ).read_text(encoding="utf-8")
        native_host = (
            self.ui_root / "qml" / "app" / "NativeMenuHost.qml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "NativeGlobalMenuBar 1.0 qml/app/NativeGlobalMenuBar.qml", qmldir
        )
        self.assertIn("NativeMenuHost 1.0 qml/app/NativeMenuHost.qml", qmldir)
        self.assertIn("import Qt.labs.platform 1.1 as Platform", native)
        self.assertIn("Platform.MenuBar {", native)
        self.assertIn("MenuDefinition.menus", native)
        self.assertIn("MenuDefinition.commandFor", native)
        self.assertIn("root.registry.trigger", native)
        self.assertIn("Platform.MenuItem.AboutRole", native)
        self.assertIn("Platform.MenuItem.PreferencesRole", native)
        self.assertIn("Platform.MenuItem.QuitRole", native)
        self.assertIn("nativeMenu.insertItem(index, object)", native)
        self.assertIn("root.insertMenu(index, object)", native)

        self.assertIn('objectName: "nativeMenuLoader"', native_host)
        self.assertIn(
            'Qt.resolvedUrl("NativeGlobalMenuBar.qml")', native_host
        )
        self.assertIn("nativeMenuLoader.setSource(", native_host)
        self.assertIn('"window": root.ownerWindow', native_host)
        self.assertIn("required property var registry", native)
        self.assertIn("active: root.useModernCustomMenu", main)
        self.assertNotIn("item.registry = root.registry", native_host)
        self.assertNotIn("item.window = root.ownerWindow", native_host)
        self.assertIn("shortcutDispatchEnabled: !root.nativeMenuOwnsShortcuts", main)

    def test_wayland_window_handoff_releases_input_focus_before_hide(self) -> None:
        app_root = Path(__file__).resolve().parents[1]
        main_py = (app_root / "main.py").read_text(encoding="utf-8")
        main_qml = (self.ui_root / "qml" / "app" / "Main.qml").read_text(
            encoding="utf-8"
        )
        welcome_qml = (
            self.ui_root / "qml" / "app" / "Welcome.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("def hide_window_safely", main_py)
        self.assertIn('QMetaObject.invokeMethod(window, "prepareForWindowHide")', main_py)
        self.assertIn("input_method.commit()", main_py)
        self.assertIn("input_method.reset()", main_py)
        self.assertIn("function prepareForWindowHide()", main_qml)
        self.assertIn("function prepareForWindowHide()", welcome_qml)

        open_workspace = main_py.index("def open_workspace")
        hide_welcome = main_py.index(
            "hide_window_safely(welcome_window)", open_workspace
        )
        load_workspace = main_py.index(
            'engine.loadFromModule("UI", "Main")', open_workspace
        )
        self.assertLess(hide_welcome, load_workspace)

    def test_modern_menu_uses_registry_and_theme_contracts(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(
            encoding="utf-8"
        )
        menu_bar = (self.ui_root / "qml" / "app" / "ModernMenuBar.qml").read_text(
            encoding="utf-8"
        )
        popup = (self.ui_root / "qml" / "app" / "ModernMenuPopup.qml").read_text(
            encoding="utf-8"
        )
        button = (
            self.ui_root / "qml" / "app" / "ModernMenuButton.qml"
        ).read_text(encoding="utf-8")
        item = (self.ui_root / "qml" / "app" / "ModernMenuItem.qml").read_text(
            encoding="utf-8"
        )

        for contract in (
            "ModernMenuBar 1.0 qml/app/ModernMenuBar.qml",
            "ModernMenuButton 1.0 qml/app/ModernMenuButton.qml",
            "ModernMenuPopup 1.0 qml/app/ModernMenuPopup.qml",
            "ModernMenuItem 1.0 qml/app/ModernMenuItem.qml",
            "ModernMenuSeparator 1.0 qml/app/ModernMenuSeparator.qml",
            "singleton MenuDefinition 1.0 qml/shared/MenuDefinition.qml",
        ):
            self.assertIn(contract, qmldir)

        self.assertIn("required property var registry", menu_bar)
        self.assertIn("MenuDefinition.menus", menu_bar)
        self.assertIn("registry: commandRegistry", main)
        self.assertIn("active: root.useModernCustomMenu", main)
        self.assertIn("Theme.contentSurface", popup)
        self.assertIn("MultiEffect", popup)
        self.assertIn("shadowColor: Theme.shadowColor", popup)
        self.assertIn("radius: Theme.radiusMedium", popup)
        self.assertIn("MenuDefinition.commandFor", popup)
        self.assertIn("root.registry.trigger", popup)
        self.assertIn("command.iconSource", item)
        self.assertIn("command.shortcut", item)
        self.assertIn("command.enabled", item)
        self.assertIn(
            "color: menuHover.hovered && !root.popupVisible", button
        )
        self.assertIn(
            "visible: root.popupVisible || root.activeFocus", button
        )
        self.assertNotIn("Behavior on color", button)
        self.assertNotIn("Behavior on color", item)
        self.assertNotIn("border.width: root.activeFocus", item)
        self.assertIn("font.weight: Font.Normal", item)

    def test_activity_bar_dims_only_unselected_icons(self) -> None:
        item = (
            self.ui_root / "qml" / "layout" / "ActivityBarItem.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("property real inactiveIconOpacity: 0.68", item)
        self.assertIn("id: activityIcon", item)
        self.assertIn(
            "opacity: !root.enabled || root.isActive || itemHover.hovered",
            item,
        )
        self.assertIn("root.inactiveIconOpacity", item)
        self.assertNotIn("opacity: root.isActive ? 1.0", item)

    def test_feature_and_subfeature_activation_reload_clean_cached_views(self) -> None:
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(encoding="utf-8")
        content = (
            self.ui_root / "qml" / "content" / "ContentArea.qml"
        ).read_text(encoding="utf-8")

        for contract in (
            "function activeFeatureLoader()",
            "function reloadActiveView(reason)",
            "function requestActivationReload(reason)",
            'requestActivationReload("feature-activated")',
            "id: featureActivationTimer",
        ):
            with self.subTest(content_contract=contract):
                self.assertIn(contract, content)
        self.assertIn('contentArea.requestActivationReload("feature-bar")', main)

        feature_roots = (
            "qml/features/routing/RoutingView.qml",
            "qml/features/dhcp/DhcpView.qml",
            "qml/features/nat/NatView.qml",
            "qml/features/acl/AclView.qml",
            "qml/features/interfaces/InterfaceView.qml",
            "qml/features/switching/SwitchWorkspace.qml",
        )
        for relative_path in feature_roots:
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(qml=relative_path):
                self.assertIn("function reloadData(reason)", source)

        dirty_safe_roots = feature_roots[:-1] + (feature_roots[-1],)
        for relative_path in dirty_safe_roots:
            if relative_path.endswith("InterfaceView.qml"):
                continue
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(dirty_guard=relative_path):
                self.assertIn("function hasUnsavedChanges(item)", source)

        nat = (self.ui_root / "qml" / "features" / "nat" / "NatView.qml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("dynamicLoader.item.clearForm()", nat)
        self.assertNotIn("patLoader.item.clearForm()", nat)
        self.assertNotIn("routeMapLoader.item.clearForm()", nat)

    def test_device_tab_loader_uses_async_cached_view_lifecycle(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        spinner = (
            self.ui_root / "components" / "base" / "LoadingSpinner.qml"
        ).read_text(encoding="utf-8")
        tab_item = (
            self.ui_root / "qml" / "devices" / "DeviceTabItem.qml"
        ).read_text(encoding="utf-8")
        tabs = (
            self.ui_root / "qml" / "devices" / "DeviceTabs.qml"
        ).read_text(encoding="utf-8")
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(encoding="utf-8")
        content = (
            self.ui_root / "qml" / "content" / "ContentArea.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("LoadingSpinner 1.0 components/base/LoadingSpinner.qml", qmldir)
        self.assertIn("RotationAnimator on rotation", spinner)
        self.assertIn("duration: Theme.loaderRotationDuration", spinner)
        self.assertIn('objectName: "deviceTabLoadingSpinner"', tab_item)
        self.assertIn("model.contentLoading === true", tab_item)
        self.assertIn("delegateRoot.hasDeviceIcon && !delegateRoot.isLoading", tab_item)
        self.assertIn("property bool activeContentLoading: false", tabs)
        self.assertIn("function syncActiveContentLoading()", tabs)
        self.assertIn("contentLoading: false", tabs)
        self.assertIn("activeContentLoading: contentArea.activeViewLoading", main)

        for contract in (
            "readonly property bool activeViewLoading",
            "function loaderIsBusy(loader)",
            "function cancelInactivePendingLoads()",
            "function scheduleActiveViewLoad()",
            "function syncHostToActiveView()",
            "property bool activeViewLoadPending: false",
            "property bool hostApplyPending: false",
            "id: hostApplyTimer",
            "interval: Theme.viewLoadDispatchDelay",
            "contentArea.effectiveHostIp = contentArea.pendingHostIp",
        ):
            with self.subTest(content_contract=contract):
                self.assertIn(contract, content)
        self.assertEqual(content.count("asynchronous: true"), 11)

        nested_loader_counts = {
            "qml/features/routing/RoutingView.qml": 5,
            "qml/features/dhcp/DhcpView.qml": 4,
            "qml/features/nat/NatView.qml": 7,
            "qml/features/acl/AclView.qml": 2,
        }
        for relative_path, expected_count in nested_loader_counts.items():
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(async_view=relative_path):
                self.assertEqual(source.count("asynchronous: true"), expected_count)
                self.assertIn("isViewLoading", source)
                self.assertIn("function syncHostToCurrentTab()", source)

    def test_collection_context_menus_match_visible_commands_and_shortcuts(self) -> None:
        tabs = (
            self.ui_root / "qml" / "devices" / "DeviceTabs.qml"
        ).read_text(encoding="utf-8")
        tab_item = (
            self.ui_root / "qml" / "devices" / "DeviceTabItem.qml"
        ).read_text(encoding="utf-8")
        tab_menu = (
            self.ui_root / "qml" / "devices" / "DeviceTabContextMenu.qml"
        ).read_text(encoding="utf-8")
        interface = (
            self.ui_root / "qml" / "features" / "interfaces" / "InterfaceView.qml"
        ).read_text(encoding="utf-8")
        interface_menu = (
            self.ui_root
            / "qml"
            / "features"
            / "interfaces"
            / "InterfaceContextMenu.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("contextMenuRequested", tab_item)
        for contract in (
            "function closeOtherTabs(idx)",
            "function closeTabsToRight(idx)",
            "function closeAllTabs()",
            'sequence: "Ctrl+F4"',
            'sequence: "Ctrl+K, Ctrl+W"',
            'sequence: "Shift+F10"',
            "function selectNumberedTab(number)",
            'sequence: "Ctrl+1"',
            'sequence: "Ctrl+9"',
        ):
            self.assertIn(contract, tabs)
        for label in (
            "Close Others",
            "Close to the Right",
            "Close All",
            "Reopen Closed",
        ):
            self.assertIn(f'text: "{label}"', tab_menu)

        self.assertIn("function selectInterfaceRow(index, row)", interface)
        self.assertIn("textInputActive", interface)
        for shortcut in ("F2", "Delete", "F5", "Shift+F10"):
            self.assertIn(f'sequence: "{shortcut}"', interface)
        for label in ("Edit", "Delete", "Refresh"):
            self.assertIn(f'text: "{label}"', interface_menu)

    def test_router_interfaces_use_routing_style_subfeatures(self) -> None:
        view = (
            self.ui_root / "qml/features/interfaces/InterfaceView.qml"
        ).read_text(encoding="utf-8")
        subbar = (
            self.ui_root / "qml/features/interfaces/InterfaceSubBar.qml"
        ).read_text(encoding="utf-8")
        editor = (
            self.ui_root / "qml/features/interfaces/InterfaceEditorPane.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("InterfaceSubBar {", view)
        self.assertIn('property string currentTab: "Physical"', view)
        self.assertIn('interfaceView.currentTab !== "Loopback"', view)
        self.assertIn('interfaceView.currentTab !== "Tunnel"', view)
        self.assertIn('objectName: "interfaceReloadButton"', view)
        self.assertIn("selectedCanDelete", view)
        self.assertIn(
            'tabs: ["Physical", "Loopback", "Tunnel", "Subinterface"]',
            subbar,
        )
        self.assertIn("activeInterfaceType", editor)
        self.assertNotIn("quickPorts", editor)
        self.assertNotIn("portFamilies", editor)
        self.assertIn("readOnly: true", editor)
        self.assertIn('"Create Loopback"', editor)
        self.assertIn('"Create Tunnel"', editor)
        self.assertIn('controllerName: "interface"', editor)
        self.assertIn('editor.selectedType === "loopback"', editor)
        self.assertIn('editor.selectedType === "tunnel"', editor)
        self.assertNotIn("reusableIfaceId", editor)
        self.assertIn("always start a distinct draft", editor)
        self.assertIn('"iface_id": selectedIfaceId', editor)

    def test_config_text_viewer_is_shared_by_both_config_surfaces(self) -> None:
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")
        viewer = (
            self.ui_root / "components" / "standard" / "ConfigTextViewer.qml"
        ).read_text(encoding="utf-8")
        context_menu = (
            self.ui_root / "components" / "standard" / "ConfigTextContextMenu.qml"
        ).read_text(encoding="utf-8")
        information = (
            self.ui_root / "qml" / "content" / "InformationView.qml"
        ).read_text(encoding="utf-8")
        routing = (
            self.ui_root / "qml" / "features" / "routing" / "info_routing.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("ConfigTextViewer 1.0 components/standard/ConfigTextViewer.qml", qmldir)
        self.assertIn("ConfigTextContextMenu 1.0 components/standard/ConfigTextContextMenu.qml", qmldir)
        self.assertEqual(information.count("ConfigTextViewer {"), 1)
        self.assertEqual(routing.count("ConfigTextViewer {"), 1)
        self.assertNotIn("TextArea {", information)
        self.assertEqual(routing.count("TextArea {"), 0)
        for contract in (
            'sequence: "Ctrl+F"',
            "function focusSearch()",
            "onAccepted: root.findNext()",
            "onReverseAccepted: root.findPrevious()",
            "function runSearchNow()",
            "function findNext()",
            "function findPrevious()",
            "function selectLine(lineIndex)",
            "function selectLineRange(firstLineIndex, lastLineIndex)",
            "function selectLineAtSelectionMarginY(viewportY, extendSelection)",
            "function zoomIn()",
            "function zoomOut()",
            "function setZoomPercent(percent)",
            "function resetZoom()",
            "function copySelection()",
            "function findSelectedText()",
            "function normalizeLineBreaks(value)",
            "function safeDocumentPosition(position)",
            "function rebuildSelectionOccurrences()",
            "CopyButton {",
            "maximumSearchMatches: 10000",
            "function highlightLine(line)",
            "function processHighlightChunk()",
            "highlightingChunkLineCount: 250",
            "syntaxHighlightCharacterLimit: 1000000",
            "highlightingSkippedForLargeText",
            "TextEdit.RichText",
            'objectName: "configViewerBottomToolbar"',
            'objectName: "configViewerZoomOutButton"',
            'objectName: "configViewerZoomInButton"',
            'objectName: "configViewerZoomPercentButton"',
            'objectName: "configViewerLineSelectionMargin"',
            'objectName: "configViewerOccurrenceRepeater"',
            'objectName: "configViewerOccurrenceMarker"',
            'objectName: "configViewerContextMenu"',
            'objectName: "configViewerZoomWheelHandler"',
            'objectName: "configViewerLineScrollWheelHandler"',
            "function lineAlignedContentY(value)",
            "function verticalScrollPositionForLine(lineIndex)",
            "function nearestVerticalScrollLine(value)",
            "function snapVerticalScroll()",
            "function scrollByLines(lineCount)",
            "acceptedModifiers: Qt.NoModifier",
            "defaultFontPixelSize: Theme.fontSizeNormal",
            "minimumZoomPercent: 25",
            "maximumZoomPercent: 500",
            "defaultZoomPercent: 100",
            "25, 33, 50, 67, 75, 80, 90, 100, 110",
            "Layout.maximumWidth: 64",
            "anchors.leftMargin: -18",
            "topPadding: root.codeVerticalPadding",
            "bottomPadding: root.codeVerticalPadding",
            "visibleWholeLineCapacity",
            "function nearestZoomLevel(percent)",
            "line-height:' + root.codeLineHeight",
            'const trailingLineKeeper = /\\n$/.test(root.pendingHighlightSource)',
            '";font-weight:600"',
            "function copyAll()",
            'sequence: "Ctrl+="',
            'sequence: "Ctrl+-"',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, viewer)

        self.assertNotIn("ListView {", viewer)
        self.assertNotIn('objectName: "configViewerLineNumbers"', viewer)
        self.assertNotIn("lineNumberText", viewer)
        self.assertNotIn("minimumFontPixelSize", viewer)
        self.assertNotIn("maximumFontPixelSize", viewer)
        self.assertNotIn('objectName: "configViewerResetZoomButton"', viewer)
        self.assertNotIn('objectName: "configViewerZoomSpinBox"', viewer)
        for contract in (
            "ContextMenuItem {",
            'text: "Copy"',
            'shortcutText: "Ctrl+C"',
            "AppAssets.actionCopy",
            'text: "Find"',
            'shortcutText: "Ctrl+F"',
            "AppAssets.actionSearch",
        ):
            with self.subTest(context_menu_contract=contract):
                self.assertIn(contract, context_menu)

        self.assertNotIn('sequence: "F3"', viewer)
        self.assertNotIn('sequence: "Shift+F3"', viewer)
        self.assertIn("function ensureSearchCurrent()", viewer)
        self.assertIn("root.ensureSearchCurrent()", viewer)
        self.assertIn("interval: 1", viewer)
        select_match = viewer[
            viewer.index("function selectMatch(index)") : viewer.index("function findNext()")
        ]
        self.assertNotIn("forceActiveFocus", select_match)
        self.assertLess(
            viewer.index('objectName: "configViewerContent"'),
            viewer.index('objectName: "configViewerBottomToolbar"'),
        )

        for source, button_name in (
            (information, "informationCopyAllButton"),
            (routing, "routingConfigCopyAllButton"),
        ):
            with self.subTest(copy_button=button_name):
                self.assertIn(f'objectName: "{button_name}"', source)
                viewer_id = "informationConfigViewer" if button_name.startswith("information") else "routingConfigViewer"
                self.assertIn(
                    f'text: {viewer_id}.copyFeedbackVisible ? "Copied" : "Copy All"',
                    source,
                )
                self.assertIn("AppAssets.actionCopy", source)

    def test_config_syntax_palette_exports_distinct_semantic_tokens(self) -> None:
        colors = (self.ui_root / "theme" / "tokens" / "ColorTokens.qml").read_text(
            encoding="utf-8"
        )
        theme = (self.ui_root / "theme" / "Theme.qml").read_text(encoding="utf-8")
        viewer = (
            self.ui_root / "components" / "standard" / "ConfigTextViewer.qml"
        ).read_text(encoding="utf-8")
        token_names = (
            "syntaxIpAddress",
            "syntaxPrefix",
            "syntaxMask",
            "syntaxWildcard",
            "syntaxInterface",
            "syntaxNumber",
            "syntaxBoolean",
            "syntaxDateTime",
            "syntaxPermit",
            "syntaxDeny",
            "syntaxInside",
            "syntaxOutside",
            "syntaxComment",
        )
        for token_name in token_names:
            with self.subTest(token=token_name):
                self.assertIn(f"property color {token_name}", colors)
                self.assertIn(f"ColorTokens.{token_name}", theme)
                self.assertIn(f"Theme.{token_name}", viewer)

    def test_information_activation_loads_versioned_backup_history(self) -> None:
        information = (
            self.ui_root / "qml" / "content" / "InformationView.qml"
        ).read_text(encoding="utf-8")
        content_area = (
            self.ui_root / "qml" / "content" / "ContentArea.qml"
        ).read_text(encoding="utf-8")

        for contract in (
            "function reloadData(reason)",
            "function loadCommit(commitId)",
            "dbManager.getRunningConfigHistory(host)",
            "dbManager.getRunningConfigAtCommit(host, requestedCommit)",
            "function loadDiff()",
            "dbManager.getRunningConfigDiff(host, baseCommit, targetCommit)",
            'objectName: "informationCommitHistoryComboBox"',
            'objectName: "informationSnapshotModeButton"',
            'objectName: "informationCompareModeButton"',
            'objectName: "informationDiffBaseComboBox"',
            'objectName: "informationDiffTargetComboBox"',
            "property var commitHistory: []",
            "function onRunningConfigFinished(host, ok, message)",
            "onCurrentHostIpChanged: reloadData()",
            "onClicked: root.reloadData()",
        ):
            with self.subTest(information_contract=contract):
                self.assertIn(contract, information)

        for contract in (
            "function scheduleInformationActivationReload()",
            "informationActivationTimer.restart()",
            'informationLoader.item.reloadData("activation")',
            'objectName: "informationLoader"',
            'objectName: "dhcpLoader"',
            'objectName: "loadedInformationView"',
            'objectName: "loadedDhcpView"',
        ):
            with self.subTest(content_contract=contract):
                self.assertIn(contract, content_area)

        dhcp_loader = content_area[
            content_area.index("id: dhcpLoader") : content_area.index("// ── ACL")
        ]
        information_loader = content_area[
            content_area.index("id: informationLoader") : content_area.index("// ── Các feature")
        ]
        self.assertIn("DhcpView {", dhcp_loader)
        self.assertNotIn("InformationView {", dhcp_loader)
        self.assertIn("InformationView {", information_loader)
        self.assertNotIn("DhcpView {", information_loader)

    def test_information_diff_uses_original_modified_picker_and_diff_stats(self) -> None:
        information = (
            self.ui_root / "qml" / "content" / "InformationView.qml"
        ).read_text(encoding="utf-8")

        for contract in (
            'objectName: "informationDiffRevisionPicker"',
            'labelText: "Original (older)"',
            'labelText: "Modified (newer)"',
            'objectName: "informationDiffAdditionsBadge"',
            'objectName: "informationDiffDeletionsBadge"',
            "color: Theme.alertSuccessSubtle",
            "color: Theme.alertErrorSubtle",
            'syntaxMode: root.viewMode === "diff" ? "diff" : "configuration"',
        ):
            with self.subTest(diff_ui_contract=contract):
                self.assertIn(contract, information)


class PasswordFieldContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_root = Path(__file__).resolve().parents[1] / "UI"

    def test_shared_password_field_is_masked_and_uses_existing_eye_assets(self) -> None:
        source = (
            self.ui_root / "components" / "standard" / "StandardPasswordField.qml"
        ).read_text(encoding="utf-8")
        qmldir = (self.ui_root / "qmldir").read_text(encoding="utf-8")

        self.assertIn("StandardPasswordField 1.0", qmldir)
        self.assertIn("property bool passwordVisible: false", source)
        self.assertIn("TextInput.Password", source)
        self.assertIn("AppAssets.actionVisibilityOn", source)
        self.assertIn("AppAssets.actionVisibilityOff", source)
        self.assertIn("function togglePasswordVisibility()", source)
        self.assertIn("inputField.forceActiveFocus()", source)

    def test_every_current_password_input_uses_shared_component(self) -> None:
        expected_consumers = {
            "qml/sidebar/new_device/NewDevice.qml": 1,
            "qml/sidebar/new_device/BatchNewDevice.qml": 1,
            "qml/features/interfaces/InterfaceView.qml": 1,
            "qml/sftp/SftpConnectionBar.qml": 1,
            "qml/sftp/SftpConnectionDialog.qml": 1,
        }
        for relative_path, expected_count in expected_consumers.items():
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(qml=relative_path):
                self.assertEqual(source.count("StandardPasswordField {"), expected_count)
                self.assertNotIn("echoMode: TextInput.Password", source)

    def test_sftp_password_storage_is_opt_in_protected_and_not_in_profile_maps(self) -> None:
        dialog = (
            self.ui_root / "qml" / "sftp" / "SftpConnectionDialog.qml"
        ).read_text(encoding="utf-8")
        bar = (
            self.ui_root / "qml" / "sftp" / "SftpConnectionBar.qml"
        ).read_text(encoding="utf-8")
        settings = (
            self.ui_root / "qml" / "content" / "SftpSettings.qml"
        ).read_text(encoding="utf-8")
        controller = (
            self.ui_root.parent / "features" / "sftp" / "controller.py"
        ).read_text(encoding="utf-8")
        credential_store = (
            self.ui_root.parent / "features" / "sftp" / "credential_store.py"
        ).read_text(encoding="utf-8")

        self.assertIn("savePasswordCheck.checked", dialog)
        self.assertIn("not recommended", dialog.lower())
        self.assertIn("passwordStorageAvailable", dialog)
        self.assertIn("Saved password will be used", bar)
        self.assertIn("sftpAutoSavePasswordCheck", settings)
        self.assertIn("setAutoSavePasswords", settings)
        self.assertIn("Off by default", settings)
        self.assertIn("CryptProtectData", credential_store)
        self.assertNotIn("CRYPTPROTECT_LOCAL_MACHINE", credential_store)
        self.assertIn('"passwordSaved"', controller)
        self.assertNotIn('profile["password"]', controller)


class SelectionTokenContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_root = Path(__file__).resolve().parents[1] / "UI"

    def test_theme_exports_contrast_aware_selection_tokens(self) -> None:
        colors = (self.ui_root / "theme" / "tokens" / "ColorTokens.qml").read_text(
            encoding="utf-8"
        )
        theme = (self.ui_root / "theme" / "Theme.qml").read_text(encoding="utf-8")

        self.assertIn("selectionBackground", colors)
        self.assertIn("selectionForeground", colors)
        self.assertIn("selectionForegroundFor", colors)
        self.assertIn("contrastRatio", colors)
        self.assertIn("ColorTokens.selectionBackground", theme)
        self.assertIn("ColorTokens.selectionForeground", theme)

    def test_text_input_consumers_use_shared_selection_tokens(self) -> None:
        consumers = (
            "components/standard/StandardTextField.qml",
            "components/standard/StandardPasswordField.qml",
            "components/standard/StandardSpinBox.qml",
            "components/standard/ConfigTextViewer.qml",
            "qml/content/DatabaseBrowserView.qml",
            "qml/shared/ConfigurationPreviewPane.qml",
        )
        for relative_path in consumers:
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(qml=relative_path):
                self.assertRegex(source, r"selectionColor:\s+Theme\.selectionBackground")
                self.assertRegex(source, r"selectedTextColor:\s+Theme\.selectionForeground")

    def test_standard_spin_box_uses_one_content_inset(self) -> None:
        spin_box = (
            self.ui_root / "components" / "standard" / "StandardSpinBox.qml"
        ).read_text(encoding="utf-8")

        self.assertIn('objectName: "standardSpinBoxControl"', spin_box)
        self.assertIn('objectName: "standardSpinBoxInput"', spin_box)
        self.assertIn("leftPadding: 0", spin_box)
        self.assertIn("rightPadding: 0", spin_box)
        self.assertIn("leftPadding: Theme.spacing12", spin_box)
        self.assertIn("property bool showIndicators: true", spin_box)

    def test_standard_spin_box_indicators_are_interactive_and_domain_bounded(self) -> None:
        spin_box = (
            self.ui_root / "components" / "standard" / "StandardSpinBox.qml"
        ).read_text(encoding="utf-8")
        for contract in (
            'objectName: "standardSpinBoxUpIndicator"',
            'objectName: "standardSpinBoxDownIndicator"',
            "onClicked: spinBox.increase()",
            "onClicked: spinBox.decrease()",
            "spinBox.value < spinBox.to",
            "spinBox.value > spinBox.from",
        ):
            with self.subTest(component_contract=contract):
                self.assertIn(contract, spin_box)

        consumers = {
            "qml/features/syslog/SyslogServerSettings.qml": (
                'labelText: "Listener port"',
                'labelText: "Retention period (days)"',
                "to: 65535",
                "to: 3650",
                "stepSize: 1",
            ),
            "qml/sftp/SftpConnectionDialog.qml": (
                'labelText: "Port"',
                "from: 1",
                "to: 65535",
                "stepSize: 1",
            ),
            "qml/sftp/SftpConnectionBar.qml": (
                'labelText: "Port"',
                "from: 1",
                "to: 65535",
                "stepSize: 1",
            ),
            "qml/content/SettingsView.qml": (
                'labelText: "Warning threshold (%)"',
                "from: 1",
                "to: 100",
                "stepSize: 5",
            ),
            "qml/features/nat/NatRouteMapForm.qml": (
                'labelText: "Sequence"',
                "from: 1",
                "to: 65535",
                "stepSize: 10",
            ),
            "qml/features/acl/AclRuleInputDynamic.qml": (
                'labelText: "Timeout (Minutes)"',
                "from: 1",
                "to: 9999",
                "value: 5",
                "stepSize: 1",
                "rule.timeout_seconds = timeoutSpinBox.value * 60",
            ),
            "qml/features/acl/AclRuleInputReflexive.qml": (
                'labelText: "Timeout (Seconds)"',
                "from: 30",
                "to: 2147483",
                "value: 300",
                "stepSize: 30",
            ),
        }
        for relative_path, contracts in consumers.items():
            source = (self.ui_root / relative_path).read_text(encoding="utf-8")
            for contract in contracts:
                with self.subTest(qml=relative_path, contract=contract):
                    self.assertIn(contract, source)


class DataTableUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_root = Path(__file__).resolve().parents[1] / "UI"

    def source(self, relative_path: str) -> str:
        return (self.ui_root / relative_path).read_text(encoding="utf-8")

    def test_shared_table_family_is_exported_and_tokenized(self) -> None:
        qmldir = self.source("qmldir")
        sizes = self.source("theme/tokens/SizeTokens.qml")
        for component in (
            "DataTable",
            "DataTableCell",
            "DataTableFrame",
            "DataTableHeader",
            "DataTableRow",
        ):
            with self.subTest(component=component):
                self.assertIn(f"{component} 1.0 components/table/{component}.qml", qmldir)
        self.assertIn("readonly property int tableHeaderHeight: 36", sizes)
        self.assertIn("readonly property int tableRowHeight: 40", sizes)
        self.assertIn("readonly property int dataWorkspaceBreakpoint: 920", sizes)

    def test_saved_list_family_cannot_overlap_header_and_content(self) -> None:
        panel = self.source("components/layout/SavedListPanel.qml")
        header = self.source("components/layout/SavedListHeader.qml")
        row = self.source("components/layout/SavedListRow.qml")
        acl_saved = self.source("qml/features/acl/AclSavedPanel.qml")
        acl_rules = self.source("qml/features/acl/AclRulesPanel.qml")

        self.assertIn("Layout.preferredHeight: active ? Theme.tableHeaderHeight : 0", panel)
        self.assertIn("visible: root.count > 0", panel)
        self.assertIn("DataTableHeader {", header)
        self.assertIn("DataTableRow {", row)
        self.assertIn("DataTableCell {", acl_saved)
        self.assertIn("DataTableCell {", acl_rules)
        self.assertNotIn("spacing: 2", acl_saved)
        self.assertNotIn("spacing: 2", acl_rules)

    def test_saved_table_consumers_share_responsive_columns_and_neutral_selection(self) -> None:
        row = self.source("components/table/DataTableRow.qml")
        colors = self.source("theme/tokens/ColorTokens.qml")
        saved_consumers = (
            "qml/features/dhcp/DhcpPoolList.qml",
            "qml/features/dhcp/DhcpExcludedForm.qml",
            "qml/features/dhcp/DhcpHelperForm.qml",
            "qml/features/nat/NatInterfaceForm.qml",
            "qml/features/nat/NatStaticForm.qml",
            "qml/features/nat/NatDynamicForm.qml",
            "qml/features/nat/NatPatForm.qml",
            "qml/features/nat/NatAclForm.qml",
            "qml/features/nat/NatRouteMapForm.qml",
            "qml/features/acl/AclSavedPanel.qml",
            "qml/features/acl/AclRulesPanel.qml",
        )

        self.assertIn("property color selectedColor: Theme.tableRowSelected", row)
        self.assertIn("visible: root.selected", row)
        self.assertIn("Theme.tableRowSelectionIndicator", row)
        self.assertNotIn("selectedColor: Theme.sideBarItemSelected", row)
        for token in (
            "tableRowAlternate",
            "tableRowHover",
            "tableRowSelected",
            "tableRowSelectionIndicator",
        ):
            self.assertIn(token, colors)

        for relative_path in saved_consumers:
            source = self.source(relative_path)
            with self.subTest(qml=relative_path):
                self.assertIn("RowLayout {", source)
                self.assertIn("DataTableCell {", source)
                self.assertNotRegex(source, r"ListView\s*\{.{0,220}?spacing:\s*2")

    def test_routing_network_tables_use_the_same_table_primitives(self) -> None:
        for relative_path in (
            "qml/features/routing/ospf/OspfNetworksSection.qml",
            "qml/features/routing/eigrp/EigrpNetworksSection.qml",
        ):
            source = self.source(relative_path)
            with self.subTest(qml=relative_path):
                self.assertIn("DataTableFrame {", source)
                self.assertIn("DataTableHeader {", source)
                self.assertIn("delegate: DataTableRow {", source)
                self.assertIn("DataTableCell {", source)

    def test_switch_workspace_uses_one_responsive_table_and_inspector_family(self) -> None:
        workspace = self.source("qml/features/switching/SwitchWorkspace.qml")
        switch_pages = {
            "qml/features/switching/interfaces/SwitchPortsPage.qml": "SwitchPortTable {",
            "qml/features/switching/interfaces/SviPage.qml": "DataTable {",
            "qml/features/switching/switching/VlanPage.qml": "DataTable {",
            "qml/features/switching/switching/EtherChannelPage.qml": "DataTable {",
            "qml/features/switching/switching/StpPage.qml": "DataTable {",
            "qml/features/switching/security/L2SecurityPage.qml": "DataTable {",
            "qml/features/switching/monitoring/SwitchMonitoringPage.qml": "DataTable {",
        }

        self.assertIn("visible: root.currentSubFeatureTabs.length >= 2", workspace)
        self.assertIn("Layout.preferredHeight: visible ? Theme.subBarHeight : 0", workspace)
        for relative_path, table_token in switch_pages.items():
            source = self.source(relative_path)
            with self.subTest(qml=relative_path):
                self.assertIn("WorkspaceHeader {", source)
                self.assertIn(table_token, source)
        for relative_path in tuple(switch_pages)[:4]:
            with self.subTest(responsive=relative_path):
                source = self.source(relative_path)
                self.assertIn("SplitView {", source)
                self.assertIn("StandardSplitHandle", source)

        port_table = self.source("qml/features/switching/interfaces/SwitchPortTable.qml")
        self.assertIn("DataTable {", port_table)
        self.assertIn("delegate: DataTableRow {", port_table)

    def test_switch_features_use_contextual_progressive_disclosure(self) -> None:
        qmldir = self.source("qmldir")
        workspace = self.source("qml/features/switching/SwitchWorkspace.qml")
        ports_page = self.source("qml/features/switching/interfaces/SwitchPortsPage.qml")
        port_table = self.source("qml/features/switching/interfaces/SwitchPortTable.qml")
        inspector = self.source("qml/features/switching/interfaces/InterfaceInspector.qml")
        svi = self.source("qml/features/switching/interfaces/SviPage.qml")
        vlan = self.source("qml/features/switching/switching/VlanPage.qml")
        etherchannel = self.source("qml/features/switching/switching/EtherChannelPage.qml")
        stp = self.source("qml/features/switching/switching/StpPage.qml")
        vtp = self.source("qml/features/switching/switching/VtpPage.qml")
        l2_security = self.source("qml/features/switching/security/L2SecurityPage.qml")
        monitoring = self.source("qml/features/switching/monitoring/SwitchMonitoringPage.qml")

        self.assertIn("deleteSwitchEtherChannel", etherchannel)
        self.assertIn('objectName: "etherChannelRowDeleteButton"', etherchannel)
        self.assertIn('objectName: "switchPortEditorActions"', inspector)
        self.assertIn('objectName: "sviEditorActions"', svi)
        self.assertIn('objectName: "sviAddButton"', svi)
        self.assertIn('objectName: "sviDeleteButton"', svi)
        self.assertIn('objectName: "sviCancelDeleteButton"', svi)
        self.assertIn('objectName: "sviSaveDeleteButton"', svi)
        self.assertIn('moduleName: "svi"', svi)
        self.assertIn("deleteSwitchSvi", svi)
        self.assertIn("function stageDelete()", svi)
        self.assertIn("function savePendingDelete()", svi)
        svi_stage_delete = svi[
            svi.index("function stageDelete()") : svi.index("function savePendingDelete()")
        ]
        self.assertNotIn("deleteSwitchSvi", svi_stage_delete)
        self.assertIn('objectName: "vlanEditorActions"', vlan)
        self.assertIn('objectName: "vlanDeleteButton"', vlan)
        self.assertIn('objectName: "vlanCancelDeleteButton"', vlan)
        self.assertIn('objectName: "vlanSaveDeleteButton"', vlan)
        self.assertIn("deleteSwitchVlan", vlan)
        self.assertIn("selectedVlanCanDelete", vlan)
        self.assertIn("function stageDelete()", vlan)
        self.assertIn("function savePendingDelete()", vlan)
        stage_delete = vlan[
            vlan.index("function stageDelete()") : vlan.index("function savePendingDelete()")
        ]
        self.assertNotIn("deleteSwitchVlan", stage_delete)
        self.assertIn('objectName: "etherChannelEditorActions"', etherchannel)
        self.assertIn('objectName: "stpEditorActions"', stp)
        self.assertIn('objectName: "vtpFormCancelButton"', vtp)
        self.assertIn('objectName: "l2PolicyCancelButton"', l2_security)

        for component in (
            "SwitchInspectorPane",
            "SwitchInspectorSection",
            "SwitchPropertyRow",
            "SwitchSummaryBar",
            "SwitchTableToolbar",
        ):
            self.assertIn(f"{component} 1.0 qml/features/switching/components/{component}.qml", qmldir)

        for token in (
            "switchPortsLoaded",
            "vlanLoaded",
            "etherChannelLoaded",
            "stpLoaded",
            "vtpLoaded",
            "l2SecurityLoaded",
            "portSecurityLoaded",
            "portCountersLoaded",
            "macTableLoaded",
            "asynchronous: true",
            "readonly property bool isViewLoading",
        ):
            self.assertIn(token, workspace)

        self.assertIn("allowCreate: !root.policyView", ports_page)
        for heading in ("Max MAC", "Violation", "Sticky"):
            self.assertIn(heading, port_table)
        for field in (
            "pruning_vlans",
            "bpdufilter",
            "loop_guard",
            "aging_type",
            "aging_time",
        ):
            self.assertIn(field, inspector)
        self.assertIn("SwitchPropertyRow {", inspector)
        self.assertIn("SwitchInspectorPane {", etherchannel)
        self.assertIn('moduleName: "etherchannel"', etherchannel)
        self.assertIn("SwitchInspectorPane {", stp)
        self.assertIn('moduleName: "stp"', stp)
        self.assertIn("SwitchInspectorPane {", l2_security)
        self.assertIn('moduleName: "l2_security"', l2_security)
        self.assertIn("SwitchSummaryBar {", vtp)
        self.assertIn("filteredHostOptions", vtp)
        self.assertIn("function loadGroup(index)", vtp)
        self.assertIn('text: "Add Group"', vtp)
        self.assertIn('text: "Reload UI"', vtp)
        self.assertNotIn('text: "Refresh"', vtp)
        self.assertNotIn("FormSection {", inspector)

        crud_actions = self.source(
            "qml/features/switching/components/CrudFormActions.qml"
        )
        workspace_header = self.source("components/layout/WorkspaceHeader.qml")
        for object_name, label in (
            ("crudAddButton", "Add"),
            ("crudEditButton", "Edit"),
            ("crudReloadButton", "Reload UI"),
            ("crudCancelButton", "Cancel"),
        ):
            self.assertIn(f'objectName: "{object_name}"', crud_actions)
            self.assertIn(f'text: "{label}"', crud_actions)
        self.assertGreaterEqual(crud_actions.count("autoCompact: false"), 5)
        self.assertIn("Flow {", workspace_header)
        self.assertIn("readonly property real naturalWidth", workspace_header)

        for source in (ports_page, svi, vlan, monitoring):
            self.assertIn("SwitchSummaryBar {", source)
        for source in (port_table, svi, vlan, monitoring):
            self.assertIn("SwitchTableToolbar {", source)
        self.assertIn("function formatBytes(value)", monitoring)
        self.assertIn('text: "Discards"', monitoring)
        self.assertIn('text: "Errors"', monitoring)

        summary = self.source("qml/features/switching/components/SwitchSummaryBar.qml")
        toolbar = self.source("qml/features/switching/components/SwitchTableToolbar.qml")
        status_badge = self.source("qml/features/switching/components/StatusBadge.qml")
        self.assertIn("readonly property bool compact", summary)
        self.assertIn("GridLayout {", summary)
        self.assertIn("GridLayout {", toolbar)
        self.assertIn('tooltip: "Clear filter"', toolbar)
        self.assertIn("readonly property string normalizedValue", status_badge)

    def test_direct_table_consumers_use_shared_primitives(self) -> None:
        consumers = {
            "qml/sidebar/new_device/BatchNewDevice.qml": (
                "DataTableFrame {", "DataTableHeader {", "delegate: DataTableRow {"
            ),
            "qml/sftp/SftpFilePanel.qml": (
                "DataTableHeader {", "delegate: DataTableRow {", "EmptyState {"
            ),
            "qml/content/DatabaseBrowserView.qml": (
                "DataTableFrame {", "DataTableHeader {", "delegate: DataTableRow {"
            ),
        }
        for relative_path, tokens in consumers.items():
            source = self.source(relative_path)
            for token in tokens:
                with self.subTest(qml=relative_path, token=token):
                    self.assertIn(token, source)


class NotificationUxContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_root = Path(__file__).resolve().parents[1] / "UI"

    def test_toasts_do_not_offer_copy_and_use_fixed_severity_tokens(self) -> None:
        toast = (self.ui_root / "qml" / "shared" / "ToastManager.qml").read_text(
            encoding="utf-8"
        )
        status_icon = (
            self.ui_root / "components" / "standard" / "StatusIcon.qml"
        ).read_text(encoding="utf-8")
        colors = (self.ui_root / "theme" / "tokens" / "ColorTokens.qml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("CopyButton {", toast)
        self.assertNotIn('objectName: "toastCopyButton"', toast)
        for token in (
            "notificationInfoAccent",
            "notificationSuccessAccent",
            "notificationWarningAccent",
            "notificationErrorAccent",
            "notificationInfoBackground",
            "notificationSuccessBackground",
            "notificationWarningBackground",
            "notificationErrorBackground",
        ):
            with self.subTest(token=token):
                self.assertIn(f"Theme.{token}", status_icon)
                self.assertIn(token, colors)
        self.assertIn('notificationInfoAccent: pick("#0969DA", "#58A6FF"', colors)

    def test_actionable_toasts_follow_the_vscode_style_lifecycle(self) -> None:
        toast = (self.ui_root / "qml" / "shared" / "ToastManager.qml").read_text(
            encoding="utf-8"
        )
        panel = (self.ui_root / "qml" / "shared" / "NotificationPanel.qml").read_text(
            encoding="utf-8"
        )
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(
            encoding="utf-8"
        )
        settings_panel = (
            self.ui_root / "qml" / "panels" / "SettingsPanel.qml"
        ).read_text(encoding="utf-8")

        for contract in (
            "property int maximumVisibleToasts: 3",
            "function timeoutForType(type)",
            "return 15000",
            "return 12000",
            "return 10000",
            "function showActionToast(",
            "signal actionTriggered(string actionId, string actionData)",
            'objectName: "toastPrimaryActionButton"',
            "readonly property bool pauseAutoClose",
            "toastHover.hovered",
            "primaryActionButton.activeFocus",
        ):
            with self.subTest(toast_contract=contract):
                self.assertIn(contract, toast)

        for contract in (
            "signal actionTriggered(string actionId, string actionData, int notificationIndex)",
            "signal dismissRequested(int notificationIndex)",
            'objectName: "historyPrimaryActionButton"',
            'objectName: "historyDismissButton"',
            '"Source: " + notificationItem.sourceText',
        ):
            with self.subTest(center_contract=contract):
                self.assertIn(contract, panel)

        for contract in (
            "function recordActionNotification(",
            "function executeNotificationAction(",
            "function openSettingsSection(settingKey)",
            "function showExternalToolsConfigurationNotification(",
            '"Open External Tools"',
            '"open-settings"',
            '"external_tools"',
        ):
            with self.subTest(main_contract=contract):
                self.assertIn(contract, main)
        self.assertIn("function selectSetting(key)", settings_panel)

    def test_notification_center_has_dynamic_height_and_icon_only_toolbar(self) -> None:
        panel = (self.ui_root / "qml" / "shared" / "NotificationPanel.qml").read_text(
            encoding="utf-8"
        )
        standard_button = (
            self.ui_root / "components" / "standard" / "StandardButton.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("property int panelMaximumHeight: 400", panel)
        self.assertIn("height: Math.min(panelMaximumHeight", panel)
        self.assertIn("readonly property bool hasScrollableOverflow", panel)
        self.assertIn('objectName: "notificationHeaderText"', panel)
        self.assertIn('"No New Notifications"', panel)
        self.assertNotIn('"No New Notification"', panel)
        self.assertNotIn('objectName: "emptyNotificationText"', panel)
        self.assertIn("visible: root.notificationCount > 0", panel)
        self.assertIn("closePolicy: Popup.CloseOnEscape", panel)
        self.assertIn("AppAssets.navigationChevronDown", panel)
        self.assertIn("AppAssets.actionClear", panel)
        self.assertIn("AppAssets.statusDoNotDisturb", panel)
        self.assertIn("AppAssets.statusNotification", panel)
        self.assertIn("signal toggleDndRequested()", panel)
        self.assertIn('objectName: "historyCopyButton"', panel)
        self.assertIn("CopyButton {", panel)
        self.assertNotIn("checkable: true", panel)
        self.assertNotIn("checked: root.doNotDisturb", panel)
        self.assertNotIn('text: "Clear All"', panel)
        self.assertIn('objectName: "historyDismissButton"', panel)
        self.assertIn("id: iconOnlyContent", standard_button)
        self.assertIn("anchors.centerIn: parent", standard_button)

    def test_main_and_status_bar_enforce_dnd_for_every_notification_path(self) -> None:
        main = (self.ui_root / "qml" / "app" / "Main.qml").read_text(encoding="utf-8")
        status_bar = (self.ui_root / "qml" / "layout" / "StatusBar.qml").read_text(
            encoding="utf-8"
        )
        devices = (self.ui_root / "qml" / "panels" / "DevicesPanel.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn("property bool isDoNotDisturb: false", main)
        self.assertIn("function setDoNotDisturb(enabled)", main)
        self.assertIn("notificationHistoryModel.insert", main)
        self.assertIn("toastManager.clearToasts()", main)
        self.assertIn("function dismissVisibleToasts()", main)
        self.assertIn("function canShowToast()", main)
        self.assertIn("!notificationPanel.visible", main)
        self.assertIn("doNotDisturb: root.isDoNotDisturb", main)
        self.assertIn("onToggleDndRequested: root.setDoNotDisturb", main)
        self.assertIn("showToast !== false && root.canShowToast()", main)
        self.assertIn("if (notificationPanel.visible)", main)
        self.assertIn("notificationPanel.close()", main)
        self.assertNotIn("toastManager.showToast", devices)

        self.assertIn("AppAssets.statusDoNotDisturb", status_bar)
        self.assertNotIn("bell-slash.svg", status_bar)
        self.assertIn("readonly property bool notificationShouldBlink", status_bar)
        self.assertIn("root.isDND", status_bar)
        self.assertIn("root.unreadCount > 0", status_bar)

    def test_toast_manager_suppresses_recent_visible_duplicates(self) -> None:
        toast = (self.ui_root / "qml" / "shared" / "ToastManager.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn("property int duplicateSuppressionWindowMs: 3000", toast)
        self.assertIn("function hasVisibleToast(message)", toast)
        self.assertIn("function isDuplicateToast(message, now)", toast)
        self.assertIn("if (!allowDuplicate && root.isDuplicateToast", toast)
        self.assertIn('return showToast(message, "loading", true)', toast)


class ExternalToolsQmlContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_source = (
            Path(__file__).resolve().parents[1]
            / "UI"
            / "qml"
            / "content"
            / "ExternalToolsSettings.qml"
        ).read_text(encoding="utf-8")
        cls.runtime_source = (
            Path(__file__).resolve().parents[1] / "core" / "external_tools.py"
        ).read_text(encoding="utf-8")
        cls.main_source = (
            Path(__file__).resolve().parents[1]
            / "UI"
            / "qml"
            / "app"
            / "Main.qml"
        ).read_text(encoding="utf-8")
        cls.feature_bar_source = (
            Path(__file__).resolve().parents[1]
            / "UI"
            / "qml"
            / "feature"
            / "FeatureBar.qml"
        ).read_text(encoding="utf-8")
        cls.device_context_menu_source = (
            Path(__file__).resolve().parents[1]
            / "UI"
            / "qml"
            / "sidebar"
            / "devices"
            / "DeviceContextMenu.qml"
        ).read_text(encoding="utf-8")

    def test_external_tools_uses_responsive_category_application_workflow(self) -> None:
        self.assertIn("SplitView {", self.ui_source)
        self.assertIn('objectName: "externalToolsMainSplit"', self.ui_source)
        self.assertIn("orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal", self.ui_source)
        self.assertIn('objectName: "externalToolCategoryList"', self.ui_source)
        self.assertIn('objectName: "externalToolsApplicationList"', self.ui_source)
        self.assertIn('objectName: "externalToolsFeatureBar"', self.ui_source)
        self.assertIn('tabs: ["Applications", "Suggestion"]', self.ui_source)
        self.assertIn('? "Current selection"', self.ui_source)
        self.assertIn('"Other configured apps" : "Suggested apps"', self.ui_source)
        self.assertIn("activeFocusOnTab: visible", self.ui_source)
        self.assertIn("Keys.onReturnPressed", self.ui_source)
        self.assertIn("Accessible.role: Accessible.ListItem", self.ui_source)
        self.assertIn("function safeText(value)", self.ui_source)
        self.assertNotIn('objectName: "externalToolType"', self.ui_source)
        self.assertIn("safeText(appName.text).trim(),\n            selectedCategory,", self.ui_source)
        self.assertIn("function activeApplicationForType(appType)", self.ui_source)
        self.assertIn('categoryRow.activeApplication + " in use"', self.ui_source)
        self.assertIn('"type": "SFTP Client"', self.ui_source)
        self.assertIn('"Built into NetworkTools"', self.ui_source)

    def test_external_tool_text_icon_actions_use_shared_button_variant(self) -> None:
        root = Path(__file__).resolve().parents[1]
        catalog = (root / "UI" / "qml" / "content" / "ExternalToolCatalogSettings.qml").read_text(encoding="utf-8")
        button = (root / "UI" / "components" / "standard" / "StandardButton.qml").read_text(encoding="utf-8")
        self.assertIn('type: "TextIcon"', self.ui_source)
        self.assertIn("AppAssets.navigationChevronRight", self.ui_source)
        self.assertIn("AppAssets.navigationChevronDown", self.ui_source)
        self.assertIn('type: "TextIcon"', catalog)
        self.assertIn("AppAssets.statusInfo", catalog)
        self.assertIn('root.type === "TextIcon"', button)

    def test_catalog_matches_category_application_and_install_state_layout(self) -> None:
        catalog = (
            Path(__file__).resolve().parents[1]
            / "UI" / "qml" / "content" / "ExternalToolCatalogSettings.qml"
        ).read_text(encoding="utf-8")
        self.assertIn('objectName: "externalToolCatalogSplit"', catalog)
        self.assertIn('objectName: "externalToolCatalogCategoryList"', catalog)
        self.assertIn('objectName: "externalToolCatalogApplicationList"', catalog)
        self.assertIn('? "In use"', catalog)
        self.assertIn('"Installed apps" : "Not installed"', catalog)
        self.assertIn("function activeApplicationForCategory(category)", catalog)
        self.assertIn('categoryRow.activeApplication + " in use"', catalog)
        self.assertIn('text: "Suggestion"', catalog)
        self.assertIn('"Built into NetworkTools"', catalog)
        self.assertIn("id: toolStatus", catalog)

    def test_detected_apps_require_review_and_are_never_auto_saved(self) -> None:
        self.assertIn("discoverExternalTools()", self.ui_source)
        self.assertIn('editorMode = row.configured ? "configured" : "detected"', self.ui_source)
        self.assertIn('editorMode === "detected"', self.ui_source)
        self.assertIn('dirty || editorMode === "detected" || editorMode === "custom"', self.ui_source)
        self.assertIn("root.saveCurrentTool()", self.ui_source)
        self.assertIn("toolsBackend.saveTool(", self.ui_source)
        self.assertNotIn("onTapped: root.saveCurrentTool()", self.ui_source)
        self.assertIn('text: enabledToggle.checked ? "Use application" : "Save"', self.ui_source)

    def test_native_browse_validation_preview_and_delete_confirmation_are_present(self) -> None:
        self.assertIn("FileDialog {", self.ui_source)
        self.assertIn("validateExecutable", self.ui_source)
        self.assertIn('nameFilters: ["Applications (*.exe *.com *.bat *.cmd)"', self.ui_source)
        self.assertIn("StandardDialog {", self.ui_source)
        self.assertIn('title: "Remove external tool?"', self.ui_source)
        self.assertIn("previewCommand()", self.ui_source)
        self.assertIn('previewArgs.replace(/\\{password\\}/gi, "[BLOCKED]")', self.ui_source)
        self.assertIn("argumentsUnsafe", self.ui_source)

    def test_windows_discovery_is_bounded_and_reports_source_confidence(self) -> None:
        self.assertIn("WINDOWS_TOOL_SPECS", self.runtime_source)
        self.assertIn("Windows App Paths", self.runtime_source)
        self.assertIn("PATH / App Execution Alias", self.runtime_source)
        self.assertIn("Windows default association", self.runtime_source)
        self.assertIn("Known install location", self.runtime_source)
        self.assertIn("Windows installed applications", self.runtime_source)
        self.assertIn("Linux default application", self.runtime_source)
        self.assertIn('("telnet", "SSH Client", True)', self.runtime_source)
        self.assertIn('("sftp", "SFTP Client", True)', self.runtime_source)
        self.assertIn('"app": "Xshell"', self.runtime_source)
        self.assertIn('"app": "MobaXterm"', self.runtime_source)
        self.assertIn('"app": "Tera Term"', self.runtime_source)
        self.assertIn('"app": "WinSCP"', self.runtime_source)
        self.assertIn('"app": "Letos"', self.runtime_source)
        self.assertIn('"confidence": confidence', self.runtime_source)
        self.assertNotIn("os.walk", self.runtime_source)
        self.assertNotIn("rglob(\"*.exe\")", self.runtime_source)

    def test_windows_default_apps_settings_remains_user_controlled(self) -> None:
        self.assertIn('Qt.openUrlExternally("ms-settings:defaultapps")', self.ui_source)
        self.assertIn("NetworkTools never changes the system default.", self.ui_source)

    def test_external_tools_and_catalog_share_one_settings_sidebar_entry(self) -> None:
        root = Path(__file__).resolve().parents[1]
        panel = (root / "UI" / "qml" / "panels" / "SettingsPanel.qml").read_text(encoding="utf-8")
        settings = (root / "UI" / "qml" / "content" / "SettingsView.qml").read_text(encoding="utf-8")
        self.assertIn('"key": "external_tools"', panel)
        self.assertNotIn('"key": "tool_catalog"', panel)
        self.assertIn("ExternalToolCatalogSettings {", self.ui_source)
        self.assertNotIn("ExternalToolCatalogSettings {", settings)

    def test_tool_catalog_is_subdued_when_missing_and_never_auto_installs(self) -> None:
        catalog_source = (
            Path(__file__).resolve().parents[1]
            / "UI"
            / "qml"
            / "content"
            / "ExternalToolCatalogSettings.qml"
        ).read_text(encoding="utf-8")
        catalog_backend = (
            Path(__file__).resolve().parents[1] / "core" / "tool_catalog.py"
        ).read_text(encoding="utf-8")

        self.assertIn("getExternalToolCatalog()", catalog_source)
        self.assertIn("Qt.openUrlExternally(", catalog_source)
        self.assertIn("Theme.textDisabled", catalog_source)
        self.assertIn("? 1.0 : 0.68", catalog_source)
        self.assertIn("does not install packages", catalog_source)
        self.assertNotIn("winget", catalog_source.casefold())
        self.assertNotIn("subprocess", catalog_backend)

    def test_feature_bar_cli_opens_the_external_managed_terminal(self) -> None:
        self.assertIn("function openDeviceCli(host)", self.main_source)
        self.assertIn("cli.openDeviceTerminal(targetHost)", self.main_source)
        self.assertIn(
            "onCliOpenRequested: root.openDeviceCli(deviceTabs.activeUid)",
            self.main_source,
        )
        self.assertIn(
            "onActivated: root.openDeviceCli(deviceTabs.activeUid)",
            self.main_source,
        )
        self.assertNotIn("onActivated: cli.openTerminal()", self.main_source)
        self.assertNotIn('statusBar.showMessage("Opened new Terminal"', self.main_source)
        self.assertIn('tooltip: "Open NetworkTools Terminal"', self.feature_bar_source)
        self.assertIn('text: "NetworkTools Terminal"', self.device_context_menu_source)
        self.assertIn("function onTerminalStateChanged(host, state)", self.main_source)
        self.assertIn("cli.deviceTerminalState(targetHost)", self.main_source)

    def test_external_tool_failures_route_to_actionable_settings_notifications(self) -> None:
        root = Path(__file__).resolve().parents[1]
        activity_bar = (
            root / "UI" / "qml" / "layout" / "ActivityBar.qml"
        ).read_text(encoding="utf-8")

        self.assertIn('"settingsKey": "external_tools"', self.runtime_source)
        self.assertIn(
            "function showExternalToolsConfigurationNotification(message, type)",
            self.main_source,
        )
        self.assertIn("string settingsKey", activity_bar)
        self.assertIn('String(result.settingsKey || "")', activity_bar)

    def test_activity_bar_uses_selected_external_sftp_client_with_builtin_fallback(self) -> None:
        root = Path(__file__).resolve().parents[1]
        activity_bar = (
            root / "UI" / "qml" / "layout" / "ActivityBar.qml"
        ).read_text(encoding="utf-8")
        sftp_view = (
            root / "UI" / "qml" / "sftp" / "SftpView.qml"
        ).read_text(encoding="utf-8")

        for contract in (
            "def openSftpClient(",
            "def hasEnabledSftpClient(",
            'WHERE enabled = 1 AND type = \'SFTP Client\'',
            '"mode": "builtin"',
            '"mode": "external"',
            '"{password}" in args_text.casefold()',
        ):
            with self.subTest(runtime_contract=contract):
                self.assertIn(contract, self.runtime_source)

        for contract in (
            "function activateSftp(toggleSidebarWhenActive)",
            "activityBar.toolsBackend.openSftpClient(",
            'result.mode === "external"',
            'activityBar.selectItem(3, "sftp")',
            "onClicked: activityBar.activateSftp(true)",
        ):
            with self.subTest(activity_contract=contract):
                self.assertIn(contract, activity_bar)

        self.assertIn(
            "onSftpOpenMessage: function(message, type, settingsKey)",
            self.main_source,
        )
        self.assertIn("property bool pointerNavigationEnabled", sftp_view)
        self.assertIn("enabled: root.pointerNavigationEnabled", sftp_view)
        self.assertIn(
            "sftp://{username}@{ip}:{port}{path}",
            self.ui_source,
        )


if __name__ == "__main__":
    unittest.main()
