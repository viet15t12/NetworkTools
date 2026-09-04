pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: natAclForm
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    color: Theme.contentBackground

    property string currentHostIp: ""
    property int editingRuleId: -1
    property int nextLocalId: -1
    property var pendingDeletes: []
    property var aclNames: []
    property bool hasPendingLocalChanges: false
    signal dataChanged()

    function isEditing() { return editingRuleId !== -1 }

    function clearForm() {
        editingRuleId = -1
        aclNameField.text = ""
        aclNameCombo.currentIndex = 0
        sourceNetField.text = ""
        wildcardField.text = ""
        sourceKindCombo.currentIndex = 0
        actionCombo.currentIndex = 0
    }

    function editAcl(row) {
        editingRuleId = row.rule_id
        const aclIndex = indexOfValue(aclNames, row.acl_name)
        aclNameCombo.currentIndex = aclIndex >= 0 ? aclIndex + 1 : 0
        aclNameField.text = aclIndex >= 0 ? "" : (row.acl_name || "")
        actionCombo.currentIndex = row.action === "deny" ? 1 : 0
        if (String(row.source_network || "").toLowerCase() === "any") {
            sourceKindCombo.currentIndex = 2
            sourceNetField.text = ""
            wildcardField.text = ""
        } else if (String(row.wildcard || "") === "") {
            sourceKindCombo.currentIndex = 1
            sourceNetField.text = row.source_network || ""
            wildcardField.text = ""
        } else {
            sourceKindCombo.currentIndex = 0
            sourceNetField.text = row.source_network || ""
            wildcardField.text = row.wildcard || ""
        }
    }

    function indexOfValue(values, value) {
        for (let i = 0; i < values.length; i++)
            if (String(values[i]) === String(value)) return i
        return -1
    }

    function selectedAclName() {
        return aclNameCombo.currentIndex > 0
                ? aclNameCombo.currentValue
                : aclNameField.text.trim()
    }

    function reloadAclNames() {
        aclNames = currentHostIp === "" ? [] : dbManager.getNatAclNames(currentHostIp)
        if (!isEditing()) aclNameCombo.currentIndex = 0
    }

    function refreshDirtyFlag() {
        let dirty = pendingDeletes.length > 0
        for (let i = 0; i < aclModel.count && !dirty; i++) dirty = aclModel.get(i)._isNew || aclModel.get(i)._isEdited
        hasPendingLocalChanges = dirty
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function reloadAcls() {
        aclModel.clear()
        pendingDeletes = []
        nextLocalId = -1
        hasPendingLocalChanges = false
        if (currentHostIp === "") return
        const rows = dbManager.getNatAcls(currentHostIp)
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            row._isNew = false
            row._isEdited = false
            aclModel.append(row)
        }
    }

    function stageAcl() {
        const sourceKind = sourceKindCombo.currentValue
        const values = { acl_name: selectedAclName(), action: actionCombo.currentValue,
            source_network: sourceKind === "any" ? "any" : sourceNetField.text.trim(),
            wildcard: sourceKind === "network" ? wildcardField.text.trim() : "" }
        if (isEditing()) {
            for (let i = 0; i < aclModel.count; i++) {
                if (aclModel.get(i).rule_id !== editingRuleId) continue
                for (const key in values) aclModel.setProperty(i, key, values[key])
                if (!aclModel.get(i)._isNew) aclModel.setProperty(i, "_isEdited", true)
                break
            }
        } else aclModel.append({ nat_acl_id: 0, rule_id: nextLocalId--,
            acl_name: values.acl_name, acl_type: "standard", host: currentHostIp,
            description: "", sequence: 0, action: values.action,
            source_network: values.source_network, wildcard: values.wildcard,
            sync_status: "pending_apply", _isNew: true, _isEdited: false })
        if (indexOfValue(aclNames, values.acl_name) < 0)
            aclNames = aclNames.concat([values.acl_name])
        clearForm()
        aclNameCombo.currentIndex = indexOfValue(aclNames, values.acl_name) + 1
        refreshDirtyFlag()
    }

    function removeAcl(index, row) {
        if (!row._isNew) pendingDeletes = pendingDeletes.concat([row.rule_id])
        aclModel.remove(index)
        if (editingRuleId === row.rule_id) clearForm()
        refreshDirtyFlag()
    }

    function saveChanges() {
        let ok = true
        for (let i = 0; i < pendingDeletes.length && ok; i++) ok = dbManager.deleteNatAcl(pendingDeletes[i])
        for (let i = 0; i < aclModel.count && ok; i++) {
            const row = aclModel.get(i)
            if (row._isEdited) ok = dbManager.deleteNatAcl(row.rule_id)
            if (ok && (row._isNew || row._isEdited)) ok = dbManager.addNatAcl(currentHostIp, row.acl_name, row.action, row.source_network, row.wildcard)
        }
        reloadAcls()
        reloadAclNames()
        if (ok) dataChanged()
        notify(ok ? "Saved NAT ACL changes." : "Save NAT ACL changes failed.", ok ? "success" : "error")
    }

    onCurrentHostIpChanged: {
        clearForm()
        reloadAclNames()
        reloadAcls()
    }
    Component.onCompleted: { reloadAclNames(); reloadAcls() }

    ListModel { id: aclModel }

    SplitView {
        id: aclSplit
        anchors.fill: parent
        anchors.bottomMargin: 60
        orientation: natAclForm.compactLayout ? Qt.Vertical : Qt.Horizontal

        handle: StandardSplitHandle { enabled: false }

        // ── CỘT TRÁI — Form nhập ──
        SplitFormPane {
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: natAclForm.compactLayout ? aclSplit.width : aclSplit.width * 0.4
            SplitView.minimumWidth: natAclForm.compactLayout ? 0 : aclSplit.width * 0.4
            SplitView.maximumWidth: natAclForm.compactLayout ? Number.POSITIVE_INFINITY : aclSplit.width * 0.4
            SplitView.preferredHeight: natAclForm.compactLayout ? aclSplit.height * 0.4 : aclSplit.height
            SplitView.minimumHeight: natAclForm.compactLayout ? aclSplit.height * 0.4 : 0
            SplitView.maximumHeight: natAclForm.compactLayout ? aclSplit.height * 0.4 : Number.POSITIVE_INFINITY

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    Text {
                        Layout.fillWidth: true
                        text:           natAclForm.isEditing() ? "Edit NAT ACL" : "Add NAT ACL"
                        color:          Theme.textPrimary
                        font.pixelSize: Theme.fontSizeLarge
                        font.family:    Theme.fontFamily
                        font.bold:      true
                    }
                    ParameterHelpButton {
                        Layout.preferredWidth: 22
                        Layout.preferredHeight: 22
                        helpTitle: "NAT ACL parameters"
                        helpText: "NAT ACL Name selects an existing list or creates a new named list. Action Permit makes matching inside addresses eligible for translation; Deny exempts matching traffic from that NAT rule.\n\nSource Type Network uses address plus wildcard, Host matches one IPv4 address, and Any matches every source. Rule order matters because the first ACL match wins."
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height:           Theme.borderWidth
                    color:            Theme.splitHandleColor
                }

                StandardComboBox {
                    id: aclNameCombo
                    Layout.fillWidth: true
                    labelText: "NAT ACL Name"
                    model: ["Create new NAT ACL"].concat(natAclForm.aclNames)
                    valueModel: [""].concat(natAclForm.aclNames)
                }

                // New ACL Name
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    visible: aclNameCombo.currentIndex === 0
                    Text {
                        text:           "New NAT ACL Name"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardTextField {
                        id:               aclNameField
                        Layout.fillWidth: true
                        placeholderText:  "e.g., NAT_ACL"
                    }
                }

                // Action
                StandardComboBox {
                    id:               actionCombo
                    Layout.fillWidth: true
                    labelText:        "Action"
                    model:            ["Permit", "Deny"]
                    valueModel:       ["permit", "deny"]
                }

                StandardComboBox {
                    id: sourceKindCombo
                    Layout.fillWidth: true
                    labelText: "Source Type"
                    model: ["Network", "Host", "Any"]
                    valueModel: ["network", "host", "any"]
                }

                // Source Network
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    visible: sourceKindCombo.currentValue !== "any"
                    Text {
                        text: sourceKindCombo.currentValue === "host" ? "Source Host" : "Source Network"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardNetworkField {
                        id:               sourceNetField
                        inputKind:        "ipv4"
                        Layout.fillWidth: true
                        placeholderText:  "e.g., 192.168.1.0"
                    }
                }

                // Wildcard
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    visible: sourceKindCombo.currentValue === "network"
                    Text {
                        text:           "Wildcard Mask"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardNetworkField {
                        id:               wildcardField
                        inputKind:        "wildcard"
                        Layout.fillWidth: true
                        placeholderText:  "e.g., 0.0.0.255 or -/24"
                    }
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    StandardButton { Layout.preferredWidth: 84; text: "Cancel"; type: "Text"; visible: natAclForm.isEditing(); onClicked: natAclForm.clearForm() }
                    StandardButton {
                        Layout.fillWidth: true; Layout.preferredHeight: 36; type: "Primary"
                        text: natAclForm.isEditing() ? "Apply Edit" : "Add Locally"
                        enabled: natAclForm.selectedAclName() !== "" && currentHostIp !== ""
                                 && (sourceKindCombo.currentValue === "any"
                                     || sourceNetField.text.trim() !== "")
                                 && (sourceKindCombo.currentValue !== "network"
                                     || wildcardField.text.trim() !== "")
                        onClicked: natAclForm.stageAcl()
                    }
                }
            }

        // ── CỘT PHẢI — Danh sách ──
        SavedListPanel {
            SplitView.fillWidth: true
            SplitView.minimumWidth: 0
            SplitView.fillHeight: true
            SplitView.minimumHeight: natAclForm.compactLayout ? 220 : 0
            title: "NAT ACL Entries"
            count: aclModel.count
            emptyText: "No NAT ACL entries configured yet.\nAdd an entry using the form on the left."
            headerComponent: Component {
                SavedListHeader {
                    width: parent ? parent.width : 0




                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.preferredWidth: 150
                            header: true
                            text: "ACL Name"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 90
                            header: true
                            text: "Action"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 150
                            header: true
                            text: "Network"
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            header: true
                            text: "Wildcard"
                        }
                        DataTableCell { Layout.preferredWidth: 64; header: true; text: "Actions" }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                model: aclModel
                clip: true
                spacing: 0
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: SavedListRow {
                    required property int index
                    required property var model
                    rowIndex: index

                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.preferredWidth: 150
                            primary: true
                            text: model.acl_name
                        }

                        Rectangle {
                            Layout.preferredWidth: 90
                            Layout.fillHeight: true
                            color: "transparent"

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                width: actionBadgeText.implicitWidth + 16
                                height: 22
                                radius: Theme.radiusSmall
                                color: model.action === "permit"
                                       ? Theme.alertSuccessSubtle
                                       : Qt.rgba(Theme.alertError.r, Theme.alertError.g, Theme.alertError.b, 0.15)

                                Text {
                                    id: actionBadgeText
                                    anchors.centerIn: parent
                                    text: model.action
                                    color: model.action === "permit"
                                           ? Theme.statusConnected
                                           : Theme.alertError
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    font.bold: true
                                }
                            }
                        }

                        DataTableCell {
                            Layout.preferredWidth: 150
                            monospaced: true
                            text: model.source_network
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            monospaced: true
                            text: model.wildcard
                        }

                        Item {
                            Layout.preferredWidth: 64
                            Layout.fillHeight: true
                            Row {
                                anchors.centerIn: parent; spacing: 4
                                IconButton { buttonSize: 24; iconSize: 12; glyph: "E"; tooltip: "Edit"; onClicked: natAclForm.editAcl(model) }
                                IconButton { buttonSize: 24; iconSize: 11; glyph: "✕"; danger: true; tooltip: "Delete"; onClicked: natAclForm.removeAcl(index, model) }
                            }
                        }
                    }
                }
        }
        }
    }

    RowLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 12
        spacing: Theme.spacing8

        Text {
            Layout.fillWidth: true
            text: "NAT ACL entries are saved locally before push."
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
        StandardButton {
            text: "Cancel Changes"
            type: "Text"
            enabled: hasPendingLocalChanges
            onClicked: { natAclForm.clearForm(); natAclForm.reloadAclNames(); natAclForm.reloadAcls(); natAclForm.notify("Discarded local NAT ACL changes.", "info") }
        }
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            enabled: currentHostIp !== ""
            onClicked: { natAclForm.clearForm(); natAclForm.reloadAclNames(); natAclForm.reloadAcls(); natAclForm.notify("Reloaded NAT ACL entries from database.", "info") }
        }
        StandardButton {
            text: "Save"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && currentHostIp !== ""
            onClicked: natAclForm.saveChanges()
        }
    }
}
