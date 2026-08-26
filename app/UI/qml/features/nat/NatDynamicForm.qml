pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: natDynamicForm
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    color: Theme.contentBackground

    property string currentHostIp: ""
    property int editingDynamicId: -1
    property int nextLocalId: -1
    property var pendingDeletes: []
    property var aclNames: []
    property bool hasPendingLocalChanges: false
    signal dataChanged()

    function isEditing() { return editingDynamicId !== -1 }

    function indexOfValue(values, value) {
        for (let i = 0; i < values.length; i++)
            if (String(values[i]) === String(value)) return i
        return -1
    }

    function clearForm() {
        editingDynamicId = -1
        poolNameField.text = ""
        startIpField.text = ""
        endIpField.text = ""
        netmaskField.text = ""
        dynamicAclCombo.currentIndex = aclNames.length > 0 ? 0 : -1
    }

    function editPool(row) {
        editingDynamicId = row.nat_dynamic_id
        poolNameField.text = row.pool_name || ""
        startIpField.text = row.start_ip || ""
        endIpField.text = row.end_ip || ""
        netmaskField.text = row.netmask || ""
        dynamicAclCombo.currentIndex = indexOfValue(aclNames, row.acl_name)
    }

    function reloadAclNames() {
        aclNames = currentHostIp === "" ? [] : dbManager.getNatAclNames(currentHostIp)
        if (!isEditing()) dynamicAclCombo.currentIndex = aclNames.length > 0 ? 0 : -1
    }

    function refreshDirtyFlag() {
        let dirty = pendingDeletes.length > 0
        for (let i = 0; i < poolModel.count && !dirty; i++) dirty = poolModel.get(i)._isNew || poolModel.get(i)._isEdited
        hasPendingLocalChanges = dirty
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function reloadPools() {
        poolModel.clear()
        pendingDeletes = []
        nextLocalId = -1
        hasPendingLocalChanges = false
        if (currentHostIp === "") return
        const rows = dbManager.getNatDynamicPools(currentHostIp)
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            row._isNew = false
            row._isEdited = false
            poolModel.append(row)
        }
    }

    function stagePool() {
        const values = { pool_name: poolNameField.text.trim(), start_ip: startIpField.text.trim(),
            end_ip: endIpField.text.trim(), netmask: netmaskField.text.trim(), acl_name: dynamicAclCombo.currentValue }
        if (isEditing()) {
            for (let i = 0; i < poolModel.count; i++) {
                if (poolModel.get(i).nat_dynamic_id !== editingDynamicId) continue
                for (const key in values) poolModel.setProperty(i, key, values[key])
                if (!poolModel.get(i)._isNew) poolModel.setProperty(i, "_isEdited", true)
                break
            }
        } else poolModel.append({ nat_dynamic_id: nextLocalId--, nat_id: 0,
            nat_name: "dynamic_" + currentHostIp, pool_name: values.pool_name,
            start_ip: values.start_ip, end_ip: values.end_ip, netmask: values.netmask,
            prefix_length: 0, acl_name: values.acl_name, sync_status: "pending_apply",
            _isNew: true, _isEdited: false })
        clearForm()
        refreshDirtyFlag()
    }

    function removePool(index, row) {
        if (!row._isNew) pendingDeletes = pendingDeletes.concat([row.nat_dynamic_id])
        poolModel.remove(index)
        if (editingDynamicId === row.nat_dynamic_id) clearForm()
        refreshDirtyFlag()
    }

    function saveChanges() {
        let ok = true
        for (let i = 0; i < pendingDeletes.length && ok; i++) ok = dbManager.deleteNatDynamicPool(pendingDeletes[i])
        for (let i = 0; i < poolModel.count && ok; i++) {
            const row = poolModel.get(i)
            if (row._isEdited) ok = dbManager.deleteNatDynamicPool(row.nat_dynamic_id)
            if (ok && (row._isNew || row._isEdited)) ok = dbManager.addNatDynamicPool(currentHostIp, row.pool_name, row.start_ip, row.end_ip, row.netmask, row.acl_name)
        }
        reloadPools()
        reloadAclNames()
        if (ok) dataChanged()
        notify(ok ? "Saved dynamic NAT changes." : "Save dynamic NAT changes failed.", ok ? "success" : "error")
    }

    onCurrentHostIpChanged: {
        clearForm()
        reloadAclNames()
        reloadPools()
    }
    Component.onCompleted: { reloadAclNames(); reloadPools() }

    ListModel { id: poolModel }

    SplitView {
        id: dynamicSplit
        anchors.fill: parent
        anchors.bottomMargin: 60
        orientation: natDynamicForm.compactLayout ? Qt.Vertical : Qt.Horizontal

        handle: StandardSplitHandle { enabled: false }

        // ── CỘT TRÁI — Form nhập ──
        SplitFormPane {
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: natDynamicForm.compactLayout ? dynamicSplit.width : dynamicSplit.width * 0.4
            SplitView.minimumWidth: natDynamicForm.compactLayout ? 0 : dynamicSplit.width * 0.4
            SplitView.maximumWidth: natDynamicForm.compactLayout ? Number.POSITIVE_INFINITY : dynamicSplit.width * 0.4
            SplitView.preferredHeight: natDynamicForm.compactLayout ? dynamicSplit.height * 0.4 : dynamicSplit.height
            SplitView.minimumHeight: natDynamicForm.compactLayout ? dynamicSplit.height * 0.4 : 0
            SplitView.maximumHeight: natDynamicForm.compactLayout ? dynamicSplit.height * 0.4 : Number.POSITIVE_INFINITY

                Text {
                    text:           natDynamicForm.isEditing() ? "Edit Dynamic NAT Pool" : "Add Dynamic NAT Pool"
                    color:          Theme.textPrimary
                    font.pixelSize: Theme.fontSizeLarge
                    font.family:    Theme.fontFamily
                    font.bold:      true
                }

                Text {
                    Layout.fillWidth: true
                    text:             "Create a public IP pool and bind it to an ACL for dynamic NAT."
                    color:            Theme.textSecondary
                    font.pixelSize:   Theme.fontSizeSmall
                    font.family:      Theme.fontFamily
                    wrapMode:         Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    height:           Theme.borderWidth
                    color:            Theme.splitHandleColor
                }

                // Pool Name
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text:           "Pool Name"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardTextField {
                        id:               poolNameField
                        Layout.fillWidth: true
                        placeholderText:  "e.g., NAT_POOL"
                    }
                }

                // Pool Start IP
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text:           "Start IP"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardNetworkField {
                        id:               startIpField
                        inputKind:        "ipv4"
                        Layout.fillWidth: true
                        placeholderText:  "e.g., 203.0.113.1"
                    }
                }

                // Pool End IP
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text:           "End IP"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardNetworkField {
                        id:               endIpField
                        inputKind:        "ipv4"
                        Layout.fillWidth: true
                        placeholderText:  "e.g., 203.0.113.10"
                    }
                }

                // Netmask
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text:           "Netmask"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardNetworkField {
                        id:               netmaskField
                        inputKind:        "subnet"
                        Layout.fillWidth: true
                        placeholderText:  "e.g., 255.255.255.0 or /24"
                    }
                }

                StandardComboBox {
                    id: dynamicAclCombo
                    Layout.fillWidth: true
                    labelText: "NAT ACL Name"
                    model: natDynamicForm.aclNames
                    valueModel: natDynamicForm.aclNames
                    emptyText: "No NAT ACL available"
                    emptyWarningText: "No ACL exists in t05_NAT_ACL_DB for this device. Add and save a NAT ACL first."
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    StandardButton { Layout.preferredWidth: 84; text: "Cancel"; type: "Text"; visible: natDynamicForm.isEditing(); onClicked: natDynamicForm.clearForm() }
                    StandardButton {
                        Layout.fillWidth: true; Layout.preferredHeight: 36; type: "Primary"
                        text: natDynamicForm.isEditing() ? "Apply Edit" : "Add Locally"
                        enabled: dynamicAclCombo.currentIndex >= 0 && poolNameField.text.trim() !== "" && startIpField.text.trim() !== "" && endIpField.text.trim() !== "" && netmaskField.text.trim() !== "" && currentHostIp !== ""
                        onClicked: natDynamicForm.stagePool()
                    }
                }
            }

        // ── CỘT PHẢI — Danh sách ──
        SavedListPanel {
            SplitView.fillWidth: true
            SplitView.minimumWidth: 0
            SplitView.fillHeight: true
            SplitView.minimumHeight: natDynamicForm.compactLayout ? 220 : 0
            title: "Dynamic NAT Pools"
            count: poolModel.count
            emptyText: "No dynamic NAT pools configured yet.\nAdd a pool using the form on the left."
            headerComponent: Component {
                SavedListHeader {
                    width: parent ? parent.width : 0




                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.preferredWidth: 125
                            header: true
                            text: "NAT Name"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 130
                            header: true
                            text: "Pool Name"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 150
                            header: true
                            text: "Start IP"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 150
                            header: true
                            text: "End IP"
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            header: true
                            text: "NAT ACL"
                        }
                        DataTableCell { Layout.preferredWidth: 64; header: true; text: "Actions" }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                model: poolModel
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
                            Layout.preferredWidth: 125
                            primary: true
                            text: model.nat_name
                        }
                        DataTableCell {
                            Layout.preferredWidth: 130
                            text: model.pool_name
                        }
                        DataTableCell {
                            Layout.preferredWidth: 150
                            monospaced: true
                            text: model.start_ip
                        }
                        DataTableCell {
                            Layout.preferredWidth: 150
                            monospaced: true
                            text: model.end_ip
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            text: model.acl_name !== "" ? model.acl_name : "—"
                        }

                        Item {
                            Layout.preferredWidth: 64
                            Layout.fillHeight: true
                            Row {
                                anchors.centerIn: parent; spacing: 4
                                IconButton { buttonSize: 24; iconSize: 12; glyph: "E"; tooltip: "Edit"; onClicked: natDynamicForm.editPool(model) }
                                IconButton { buttonSize: 24; iconSize: 11; glyph: "✕"; danger: true; tooltip: "Delete"; onClicked: natDynamicForm.removePool(index, model) }
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
            text: "Dynamic NAT pools are saved locally before push."
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
        StandardButton {
            text: "Cancel Changes"
            type: "Text"
            enabled: hasPendingLocalChanges
            onClicked: {
                natDynamicForm.clearForm()
                natDynamicForm.reloadPools()
                natDynamicForm.notify("Discarded local dynamic NAT changes.", "info")
            }
        }
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            enabled: currentHostIp !== ""
            onClicked: { natDynamicForm.clearForm(); natDynamicForm.reloadAclNames(); natDynamicForm.reloadPools(); natDynamicForm.notify("Reloaded dynamic NAT pools from database.", "info") }
        }
        StandardButton {
            text: "Save"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && currentHostIp !== ""
            onClicked: natDynamicForm.saveChanges()
        }
    }
}
