pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: natInterfaceForm
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    color: Theme.contentBackground

    property string currentHostIp: ""
    property int editingInterfaceId: -1
    property int nextLocalId: -1
    property var pendingDeletes: []
    property var interfaceNames: []
    property bool hasPendingLocalChanges: false
    signal dataChanged()

    function isEditing() { return editingInterfaceId !== -1 }

    function clearForm() {
        editingInterfaceId = -1
        intfNameCombo.currentIndex = interfaceNames.length > 0 ? 0 : -1
        directionCombo.currentIndex = 0
    }

    function editInterface(row) {
        editingInterfaceId = row.nat_intf_id
        if (indexOfValue(interfaceNames, row.interface_name) < 0)
            interfaceNames = interfaceNames.concat([row.interface_name])
        intfNameCombo.currentIndex = indexOfValue(interfaceNames, row.interface_name)
        directionCombo.currentIndex = row.direction === "outside" ? 1 : 0
    }

    function indexOfValue(values, value) {
        for (let i = 0; i < values.length; i++)
            if (String(values[i]) === String(value)) return i
        return -1
    }

    function reloadInterfaceNames() {
        interfaceNames = []
        if (currentHostIp === "") return
        const rows = dbManager.getRouterInterfaces(currentHostIp)
        let names = []
        for (let i = 0; i < rows.length; i++) {
            const name = String(rows[i].interface_name || "")
            if (name !== "" && indexOfValue(names, name) < 0)
                names.push(name)
        }
        interfaceNames = names
        if (!isEditing()) intfNameCombo.currentIndex = names.length > 0 ? 0 : -1
    }

    function refreshDirtyFlag() {
        let dirty = pendingDeletes.length > 0
        for (let i = 0; i < interfaceModel.count && !dirty; i++) dirty = interfaceModel.get(i)._isNew || interfaceModel.get(i)._isEdited
        hasPendingLocalChanges = dirty
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function reloadInterfaces() {
        interfaceModel.clear()
        pendingDeletes = []
        nextLocalId = -1
        hasPendingLocalChanges = false
        if (currentHostIp === "") return
        const rows = dbManager.getNatInterfaces(currentHostIp)
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            row._isNew = false
            row._isEdited = false
            interfaceModel.append(row)
        }
    }

    function stageInterface() {
        const values = { interface_name: intfNameCombo.currentValue, direction: directionCombo.currentValue }
        if (isEditing()) {
            for (let i = 0; i < interfaceModel.count; i++) {
                if (interfaceModel.get(i).nat_intf_id !== editingInterfaceId) continue
                interfaceModel.setProperty(i, "interface_name", values.interface_name)
                interfaceModel.setProperty(i, "direction", values.direction)
                if (!interfaceModel.get(i)._isNew) interfaceModel.setProperty(i, "_isEdited", true)
                break
            }
        } else interfaceModel.append({ nat_intf_id: nextLocalId--, nat_id: 0,
            interface_name: values.interface_name, direction: values.direction,
            sync_status: "pending_apply", _isNew: true, _isEdited: false })
        clearForm()
        refreshDirtyFlag()
    }

    function removeInterface(index, row) {
        if (!row._isNew) pendingDeletes = pendingDeletes.concat([row.nat_intf_id])
        interfaceModel.remove(index)
        if (editingInterfaceId === row.nat_intf_id) clearForm()
        refreshDirtyFlag()
    }

    function saveChanges() {
        let ok = true
        for (let i = 0; i < pendingDeletes.length && ok; i++) ok = dbManager.deleteNatInterface(pendingDeletes[i])
        for (let i = 0; i < interfaceModel.count && ok; i++) {
            const row = interfaceModel.get(i)
            if (row._isEdited) ok = dbManager.deleteNatInterface(row.nat_intf_id)
            if (ok && (row._isNew || row._isEdited)) ok = dbManager.addNatInterface(currentHostIp, row.interface_name, row.direction)
        }
        reloadInterfaces()
        if (ok) dataChanged()
        notify(ok ? "Saved NAT interface changes." : "Save NAT interface changes failed.", ok ? "success" : "error")
    }

    onCurrentHostIpChanged: {
        clearForm()
        reloadInterfaceNames()
        reloadInterfaces()
    }
    Component.onCompleted: { reloadInterfaceNames(); reloadInterfaces() }

    ListModel { id: interfaceModel }

    SplitView {
        id: interfaceSplit
        anchors.fill: parent
        anchors.bottomMargin: 60
        orientation: natInterfaceForm.compactLayout ? Qt.Vertical : Qt.Horizontal

        handle: StandardSplitHandle { enabled: false }

        // ── CỘT TRÁI — Form nhập ──
        SplitFormPane {
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: natInterfaceForm.compactLayout ? interfaceSplit.width : interfaceSplit.width * 0.4
            SplitView.minimumWidth: natInterfaceForm.compactLayout ? 0 : interfaceSplit.width * 0.4
            SplitView.maximumWidth: natInterfaceForm.compactLayout ? Number.POSITIVE_INFINITY : interfaceSplit.width * 0.4
            SplitView.preferredHeight: natInterfaceForm.compactLayout ? interfaceSplit.height * 0.4 : interfaceSplit.height
            SplitView.minimumHeight: natInterfaceForm.compactLayout ? interfaceSplit.height * 0.4 : 0
            SplitView.maximumHeight: natInterfaceForm.compactLayout ? interfaceSplit.height * 0.4 : Number.POSITIVE_INFINITY

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    Text {
                        Layout.fillWidth: true
                        text:           natInterfaceForm.isEditing() ? "Edit NAT Interface" : "Assign NAT Interface"
                        color:          Theme.textPrimary
                        font.pixelSize: Theme.fontSizeLarge
                        font.family:    Theme.fontFamily
                        font.bold:      true
                    }
                    ParameterHelpButton {
                        Layout.preferredWidth: 22
                        Layout.preferredHeight: 22
                        helpTitle: "NAT interface parameters"
                        helpText: "Interface Name selects a routed interface. NAT Role Inside marks the private side where inside-local addresses originate; Outside marks the public/upstream side. A working translation path normally requires at least one interface in each role."
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text:             "Mark an interface as Inside or Outside for NAT."
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
                    id: intfNameCombo
                    Layout.fillWidth: true
                    labelText: "Interface Name"
                    model: natInterfaceForm.interfaceNames
                    valueModel: natInterfaceForm.interfaceNames
                    emptyText: "No router interface available"
                    emptyWarningText: "No interface exists for this device. Add or synchronize router interfaces first."
                }

                // Direction
                StandardComboBox {
                    id:               directionCombo
                    Layout.fillWidth: true
                    labelText:        "NAT Role"
                    model:            ["Inside", "Outside"]
                    valueModel:       ["inside", "outside"]
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    StandardButton { Layout.preferredWidth: 84; text: "Cancel"; type: "Text"; visible: natInterfaceForm.isEditing(); onClicked: natInterfaceForm.clearForm() }
                    StandardButton {
                        Layout.fillWidth: true; Layout.preferredHeight: 36; type: "Primary"
                        text: natInterfaceForm.isEditing() ? "Apply Edit" : "Add Locally"
                        enabled: intfNameCombo.currentIndex >= 0 && currentHostIp !== ""
                        onClicked: natInterfaceForm.stageInterface()
                    }
                }
            }

        // ── CỘT PHẢI — Danh sách ──
        SavedListPanel {
            SplitView.fillWidth: true
            SplitView.minimumWidth: 0
            SplitView.fillHeight: true
            SplitView.minimumHeight: natInterfaceForm.compactLayout ? 220 : 0
            title: "NAT Interfaces"
            count: interfaceModel.count
            emptyText: "No NAT interfaces assigned yet.\nAdd an interface using the form on the left."
            headerComponent: Component {
                SavedListHeader {
                    width: parent ? parent.width : 0




                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.fillWidth: true
                            header: true
                            text: "Interface Name"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 120
                            header: true
                            text: "NAT Role"
                        }
                        DataTableCell { Layout.preferredWidth: 64; header: true; text: "Actions" }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                model: interfaceModel
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
                            Layout.fillWidth: true
                            primary: true
                            text: model.interface_name
                        }

                        Rectangle {
                            Layout.preferredWidth: 120
                            Layout.fillHeight: true
                            color: "transparent"

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                width: dirText.implicitWidth + 16
                                height: 22
                                radius: Theme.radiusSmall
                                color: model.direction === "inside"
                                       ? Theme.alertSuccessSubtle
                                       : Theme.alertWarningSubtle

                                Text {
                                    id: dirText
                                    anchors.centerIn: parent
                                    text: model.direction
                                    color: model.direction === "inside"
                                           ? Theme.statusConnected
                                           : Theme.alertWarning
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    font.bold: true
                                }
                            }
                        }

                        Item {
                            Layout.preferredWidth: 64
                            Layout.fillHeight: true
                            Row {
                                anchors.centerIn: parent; spacing: 4
                                IconButton { buttonSize: 24; iconSize: 12; glyph: "E"; tooltip: "Edit"; onClicked: natInterfaceForm.editInterface(model) }
                                IconButton { buttonSize: 24; iconSize: 11; glyph: "✕"; danger: true; tooltip: "Delete"; onClicked: natInterfaceForm.removeInterface(index, model) }
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
            text: "NAT interface roles are saved locally before push."
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
        StandardButton {
            text: "Cancel Changes"
            type: "Text"
            enabled: hasPendingLocalChanges
            onClicked: { natInterfaceForm.clearForm(); natInterfaceForm.reloadInterfaceNames(); natInterfaceForm.reloadInterfaces(); natInterfaceForm.notify("Discarded local NAT interface changes.", "info") }
        }
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            enabled: currentHostIp !== ""
            onClicked: { natInterfaceForm.clearForm(); natInterfaceForm.reloadInterfaceNames(); natInterfaceForm.reloadInterfaces(); natInterfaceForm.notify("Reloaded NAT interfaces from database.", "info") }
        }
        StandardButton {
            text: "Save"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && currentHostIp !== ""
            onClicked: natInterfaceForm.saveChanges()
        }
    }
}
