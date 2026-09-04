pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    color: Theme.contentBackground

    property string currentHostIp: ""
    property var aclCatalog: []
    property var aclLabels: []
    property var interfaceLabels: ["None"]
    property var interfaceIds: []
    property string loadedSignature: "[]"
    property bool hasPendingLocalChanges: false

    function notify(message, type) {
        if (typeof statusBar !== "undefined") statusBar.showMessage(message, type)
    }

    function selectedAclId() {
        const index = aclCombo.currentIndex
        return index >= 0 && index < aclCatalog.length ? Number(aclCatalog[index].Acl_id || 0) : 0
    }

    function loadInterfaces() {
        const labels = ["None"]
        const ids = []
        if (currentHostIp !== "" && typeof dbManager !== "undefined") {
            const rows = dbManager.getRouterInterfaces(currentHostIp)
            for (let i = 0; i < rows.length; ++i) {
                ids.push(Number(rows[i].iface_id || 0))
                labels.push(rows[i].interface_name || "Interface #" + rows[i].iface_id)
            }
        }
        interfaceLabels = labels
        interfaceIds = ids
    }

    function loadCatalog(preferredAclId) {
        aclCatalog = []
        aclLabels = []
        aclCombo.currentIndex = -1
        if (currentHostIp === "" || typeof dbManager === "undefined") {
            bindingEditor.reset()
            return
        }
        aclCatalog = dbManager.getAclBindingCatalog(currentHostIp)
        const labels = []
        let selectedIndex = aclCatalog.length > 0 ? 0 : -1
        for (let i = 0; i < aclCatalog.length; ++i) {
            const acl = aclCatalog[i]
            labels.push((acl.acl_name || "") + " (" + String(acl.acl_type || "").toUpperCase() + ")")
            if (Number(acl.Acl_id || 0) === Number(preferredAclId || 0)) selectedIndex = i
        }
        aclLabels = labels
        aclCombo.currentIndex = selectedIndex
        loadSelectedAcl()
    }

    function loadSelectedAcl() {
        const index = aclCombo.currentIndex
        if (index < 0 || index >= aclCatalog.length) {
            bindingEditor.reset()
            loadedSignature = "[]"
            hasPendingLocalChanges = false
            return
        }
        bindingEditor.loadBindings(aclCatalog[index].bindings || [])
        loadedSignature = bindingEditor.signature()
        hasPendingLocalChanges = false
    }

    function refreshDirty() {
        hasPendingLocalChanges = bindingEditor.signature() !== loadedSignature
    }

    function saveChanges() {
        const aclId = selectedAclId()
        if (aclId <= 0 || typeof dbManager === "undefined") return
        if (!dbManager.saveAclBindings(aclId, bindingEditor.payload())) {
            notify("Save ACL interface bindings failed.", "error")
            return
        }
        loadCatalog(aclId)
        notify("ACL interface bindings saved.", "success")
    }

    function reloadAll() {
        loadInterfaces()
        loadCatalog(0)
    }

    onCurrentHostIpChanged: reloadAll()
    Component.onCompleted: reloadAll()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: Theme.spacing12

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: "ACL Interface Bindings"
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLarge
                font.family: Theme.fontFamily
                font.bold: true
            }
            StandardButton {
                text: "Reload UI"
                icon.source: AppAssets.actionDatabaseReload
                type: "Secondary"
                autoCompact: false
                Layout.minimumWidth: expandedImplicitWidth
                enabled: root.currentHostIp !== ""
                onClicked: root.reloadAll()
            }
        }

        Text {
            Layout.fillWidth: true
            text: "Apply one ACL to multiple Cisco interfaces. Each interface supports independent IN and OUT bindings."
            color: Theme.textSecondary
            wrapMode: Text.WordWrap
        }

        StandardComboBox {
            id: aclCombo
            Layout.fillWidth: true
            labelText: "ACL"
            model: root.aclLabels
            emptyWarningText: "No ACL is available. Create an ACL in one of the rule tabs first."
            onCurrentIndexChanged: root.loadSelectedAcl()
        }

        AclBindingsEditor {
            id: bindingEditor
            Layout.fillWidth: true
            interfaceLabels: root.interfaceLabels
            interfaceIds: root.interfaceIds
            onBindingDataChanged: root.refreshDirty()
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: hasPendingLocalChanges ? "Unsaved binding changes" : "Bindings are synchronized with the local database"
                color: hasPendingLocalChanges ? Theme.alertWarning : Theme.textSecondary
            }
            StandardButton {
                text: "Cancel Changes"
                type: "Text"
                enabled: root.hasPendingLocalChanges
                onClicked: root.loadSelectedAcl()
            }
            StandardButton {
                text: "Save"
                icon.source: AppAssets.actionSave
                type: "Primary"
                enabled: root.hasPendingLocalChanges && root.selectedAclId() > 0
                onClicked: root.saveChanges()
            }
        }
    }
}
