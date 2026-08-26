pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: natPatForm
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    color: Theme.contentBackground

    property string currentHostIp: ""
    property int editingPatId: -1
    property int nextLocalId: -1
    property var pendingDeletes: []
    property var aclNames: []
    property var interfaceNames: []
    property var poolNames: []
    property var poolNatNames: ({})
    property var sourceTypeLabels: []
    property var sourceTypeValues: []
    property bool hasPendingLocalChanges: false
    signal dataChanged()

    function isEditing() { return editingPatId !== -1 }

    function indexOfValue(values, value) {
        for (let i = 0; i < values.length; i++)
            if (String(values[i]) === String(value)) return i
        return -1
    }

    function clearForm() {
        editingPatId = -1
        patAclCombo.currentIndex = aclNames.length > 0 ? 0 : -1
        interfaceCombo.currentIndex = interfaceNames.length > 0 ? 0 : -1
        patPoolCombo.currentIndex = poolNames.length > 0 ? 0 : -1
        sourceTypeCombo.currentIndex = sourceTypeValues.length > 0 ? 0 : -1
    }

    function editRule(row) {
        editingPatId = row.nat_pat_id
        patAclCombo.currentIndex = indexOfValue(aclNames, row.acl_name)
        if (row.source_type === "Interface" && indexOfValue(interfaceNames, row.source_value) < 0)
            interfaceNames = interfaceNames.concat([row.source_value])
        if (row.source_type === "Pool" && indexOfValue(poolNames, row.source_value) < 0)
            poolNames = poolNames.concat([row.source_value])
        rebuildSourceTypes(row.source_type)
        interfaceCombo.currentIndex = row.source_type === "Interface"
                ? indexOfValue(interfaceNames, row.source_value) : (interfaceNames.length > 0 ? 0 : -1)
        patPoolCombo.currentIndex = row.source_type === "Pool"
                ? indexOfValue(poolNames, row.source_value) : (poolNames.length > 0 ? 0 : -1)
    }

    function reloadAclNames() {
        aclNames = currentHostIp === "" ? [] : dbManager.getNatAclNames(currentHostIp)
        if (!isEditing()) patAclCombo.currentIndex = aclNames.length > 0 ? 0 : -1
    }

    function reloadSourceOptions() {
        interfaceNames = []
        poolNames = []
        poolNatNames = ({})
        if (currentHostIp === "") return

        const interfaces = dbManager.getNatInterfaces(currentHostIp)
        for (let i = 0; i < interfaces.length; i++) {
            const name = String(interfaces[i].interface_name || "")
            if (interfaces[i].direction === "outside" && name !== ""
                    && indexOfValue(interfaceNames, name) < 0)
                interfaceNames = interfaceNames.concat([name])
        }

        const pools = dbManager.getNatDynamicPools(currentHostIp)
        const natNames = ({})
        for (let i = 0; i < pools.length; i++) {
            const name = String(pools[i].pool_name || "")
            if (name === "" || indexOfValue(poolNames, name) >= 0) continue
            poolNames = poolNames.concat([name])
            natNames[name] = String(pools[i].nat_name || "")
        }
        poolNatNames = natNames
        rebuildSourceTypes("")
        if (!isEditing()) {
            interfaceCombo.currentIndex = interfaceNames.length > 0 ? 0 : -1
            patPoolCombo.currentIndex = poolNames.length > 0 ? 0 : -1
        }
    }

    function rebuildSourceTypes(preferredValue) {
        let labels = []
        let values = []
        if (interfaceNames.length > 0) {
            labels.push("Outside Interface")
            values.push("Interface")
        }
        if (poolNames.length > 0) {
            labels.push("Dynamic Pool")
            values.push("Pool")
        }
        sourceTypeLabels = labels
        sourceTypeValues = values
        const preferredIndex = indexOfValue(values, preferredValue)
        sourceTypeCombo.currentIndex = preferredIndex >= 0
                ? preferredIndex : (values.length > 0 ? 0 : -1)
    }

    function selectedSourceValue() {
        return sourceTypeCombo.currentValue === "Interface"
                ? interfaceCombo.currentValue : patPoolCombo.currentValue
    }

    function selectedNatName() {
        return sourceTypeCombo.currentValue === "Pool"
                ? String(poolNatNames[selectedSourceValue()] || "")
                : "pat_" + currentHostIp
    }

    function refreshDirtyFlag() {
        let dirty = pendingDeletes.length > 0
        for (let i = 0; i < patModel.count && !dirty; i++)
            dirty = patModel.get(i)._isNew || patModel.get(i)._isEdited
        hasPendingLocalChanges = dirty
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function reloadRules() {
        patModel.clear()
        pendingDeletes = []
        nextLocalId = -1
        hasPendingLocalChanges = false
        if (currentHostIp === "") return
        const rows = dbManager.getNatPatRules(currentHostIp)
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            row._isNew = false
            row._isEdited = false
            patModel.append(row)
        }
    }

    function stageRule() {
        const values = {
            acl_name: patAclCombo.currentValue, source_type: sourceTypeCombo.currentValue,
            source_value: selectedSourceValue(), nat_name: selectedNatName(),
            overload: true
        }
        if (isEditing()) {
            for (let i = 0; i < patModel.count; i++) {
                if (patModel.get(i).nat_pat_id !== editingPatId) continue
                for (const key in values) patModel.setProperty(i, key, values[key])
                if (!patModel.get(i)._isNew) patModel.setProperty(i, "_isEdited", true)
                break
            }
        } else {
            patModel.append({ nat_pat_id: nextLocalId--, nat_id: 0,
                nat_name: values.nat_name, nat_acl_id: 0, acl_name: values.acl_name,
                source_type: values.source_type, source_value: values.source_value,
                overload: values.overload, description: "", sync_status: "pending_apply",
                _isNew: true, _isEdited: false })
        }
        clearForm()
        refreshDirtyFlag()
    }

    function removeRule(index, row) {
        if (!row._isNew) pendingDeletes = pendingDeletes.concat([row.nat_pat_id])
        patModel.remove(index)
        if (editingPatId === row.nat_pat_id) clearForm()
        refreshDirtyFlag()
    }

    function saveChanges() {
        let ok = true
        for (let i = 0; i < pendingDeletes.length && ok; i++) ok = dbManager.deleteNatPatRule(pendingDeletes[i])
        for (let i = 0; i < patModel.count && ok; i++) {
            const row = patModel.get(i)
            if (row._isEdited) ok = dbManager.deleteNatPatRule(row.nat_pat_id)
            if (ok && (row._isNew || row._isEdited)) ok = dbManager.addNatPatRule(currentHostIp, row.acl_name, row.source_type, row.source_value, row.overload)
        }
        reloadRules()
        reloadAclNames()
        reloadSourceOptions()
        if (ok) dataChanged()
        notify(ok ? "Saved PAT changes." : "Save PAT changes failed.", ok ? "success" : "error")
    }

    onCurrentHostIpChanged: {
        clearForm()
        reloadAclNames()
        reloadSourceOptions()
        reloadRules()
    }
    Component.onCompleted: { reloadAclNames(); reloadSourceOptions(); reloadRules() }

    ListModel { id: patModel }

    SplitView {
        id: patSplit
        anchors.fill: parent
        anchors.bottomMargin: 60
        orientation: natPatForm.compactLayout ? Qt.Vertical : Qt.Horizontal

        handle: StandardSplitHandle { enabled: false }

        // ── CỘT TRÁI — Form nhập ──
        SplitFormPane {
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: natPatForm.compactLayout ? patSplit.width : patSplit.width * 0.4
            SplitView.minimumWidth: natPatForm.compactLayout ? 0 : patSplit.width * 0.4
            SplitView.maximumWidth: natPatForm.compactLayout ? Number.POSITIVE_INFINITY : patSplit.width * 0.4
            SplitView.preferredHeight: natPatForm.compactLayout ? patSplit.height * 0.4 : patSplit.height
            SplitView.minimumHeight: natPatForm.compactLayout ? patSplit.height * 0.4 : 0
            SplitView.maximumHeight: natPatForm.compactLayout ? patSplit.height * 0.4 : Number.POSITIVE_INFINITY

                Text {
                    text:           natPatForm.isEditing() ? "Edit PAT Rule" : "Add PAT Rule"
                    color:          Theme.textPrimary
                    font.pixelSize: Theme.fontSizeLarge
                    font.family:    Theme.fontFamily
                    font.bold:      true
                }

                Text {
                    Layout.fillWidth: true
                    text:             "PAT (Overload): many inside IPs share one public IP, separated by ports."
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

                StandardComboBox {
                    id: patAclCombo
                    Layout.fillWidth: true
                    labelText: "NAT ACL Name"
                    model: natPatForm.aclNames
                    valueModel: natPatForm.aclNames
                    emptyText: "No NAT ACL available"
                    emptyWarningText: "No ACL exists in t05_NAT_ACL_DB for this device. Add and save a NAT ACL first."
                }

                // Loại source: Interface hay Pool
                StandardComboBox {
                    id:               sourceTypeCombo
                    Layout.fillWidth: true
                    labelText:        "Source Type"
                    model:            natPatForm.sourceTypeLabels
                    valueModel:       natPatForm.sourceTypeValues
                    emptyText:        "No PAT source available"
                    emptyWarningText: "Save an outside NAT interface or a Dynamic NAT pool first."
                }

                StandardComboBox {
                    id: interfaceCombo
                    Layout.fillWidth: true
                    visible: sourceTypeCombo.currentValue === "Interface"
                    labelText: "Outside Interface"
                    model: natPatForm.interfaceNames
                    valueModel: natPatForm.interfaceNames
                    emptyText: "No outside interface available"
                    emptyWarningText: "Add and save an outside interface in the NAT Interfaces tab first."
                }

                StandardComboBox {
                    id: patPoolCombo
                    Layout.fillWidth: true
                    visible: sourceTypeCombo.currentValue === "Pool"
                    labelText: "Pool Name"
                    model: natPatForm.poolNames
                    valueModel: natPatForm.poolNames
                    emptyText: "No dynamic NAT pool available"
                    emptyWarningText: "Add and save a pool in the Dynamic tab first."
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    StandardButton {
                        Layout.preferredWidth: 84
                        text: "Cancel"
                        type: "Text"
                        visible: natPatForm.isEditing()
                        onClicked: natPatForm.clearForm()
                    }
                    StandardButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        type: "Primary"
                        text: natPatForm.isEditing() ? "Apply Edit" : "Add Locally"
                        enabled: patAclCombo.currentIndex >= 0 && currentHostIp !== "" &&
                                 sourceTypeCombo.currentIndex >= 0 &&
                                 (sourceTypeCombo.currentValue === "Interface"
                                  ? interfaceCombo.currentIndex >= 0 : patPoolCombo.currentIndex >= 0)
                        onClicked: natPatForm.stageRule()
                    }
                }
            }

        // ── CỘT PHẢI — Danh sách ──
        SavedListPanel {
            SplitView.fillWidth: true
            SplitView.minimumWidth: 0
            SplitView.fillHeight: true
            SplitView.minimumHeight: natPatForm.compactLayout ? 220 : 0
            title: "PAT Rules"
            count: patModel.count
            emptyText: "No PAT rules configured yet.\nAdd a rule using the form on the left."
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
                            Layout.preferredWidth: 110
                            header: true
                            text: "NAT ACL"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 100
                            header: true
                            text: "Type"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 180
                            header: true
                            text: "Interface / Pool"
                        }
                        Item { Layout.fillWidth: true }
                        DataTableCell { Layout.preferredWidth: 64; header: true; text: "Actions" }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                model: patModel
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
                            Layout.preferredWidth: 110
                            text: model.acl_name
                        }
                        DataTableCell {
                            Layout.preferredWidth: 100
                            text: model.source_type
                        }
                        DataTableCell {
                            Layout.preferredWidth: 180
                            text: model.source_value
                        }
                        Item { Layout.fillWidth: true }

                        Item {
                            Layout.preferredWidth: 64
                            Layout.fillHeight: true
                            Row {
                                anchors.centerIn: parent
                                spacing: 4
                                IconButton { buttonSize: 24; iconSize: 12; glyph: "E"; tooltip: "Edit"; onClicked: natPatForm.editRule(model) }
                                IconButton { buttonSize: 24; iconSize: 11; glyph: "✕"; danger: true; tooltip: "Delete"; onClicked: natPatForm.removeRule(index, model) }
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
            text: "PAT rules are saved locally before push."
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
        StandardButton {
            text: "Cancel Changes"
            type: "Text"
            enabled: hasPendingLocalChanges
            onClicked: { natPatForm.clearForm(); natPatForm.reloadAclNames(); natPatForm.reloadSourceOptions(); natPatForm.reloadRules(); natPatForm.notify("Discarded local PAT changes.", "info") }
        }
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            enabled: currentHostIp !== ""
            onClicked: {
                natPatForm.clearForm()
                natPatForm.reloadAclNames()
                natPatForm.reloadSourceOptions()
                natPatForm.reloadRules()
                natPatForm.notify("Reloaded PAT rules from database.", "info")
            }
        }
        StandardButton {
            text: "Save"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && currentHostIp !== ""
            onClicked: natPatForm.saveChanges()
        }
    }
}
