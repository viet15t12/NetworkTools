pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: natStaticForm
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    color: Theme.contentBackground

    property string currentHostIp: ""
    property int editingStaticId: -1
    property int nextLocalId: -1
    property var pendingDeletes: []
    property bool hasPendingLocalChanges: false
    signal dataChanged()

    function isEditing() { return editingStaticId !== -1 }

    function clearForm() {
        editingStaticId = -1
        insideLocalField.text = ""
        insideGlobalField.text = ""
        localPortSpin.value = 80
        globalPortSpin.value = 8080
        protocolCombo.currentIndex = 0
    }

    function editEntry(row) {
        editingStaticId = row.nat_static_id
        insideLocalField.text = row.inside_local || ""
        insideGlobalField.text = row.inside_global || ""
        localPortSpin.value = Number(row.local_port || 80)
        globalPortSpin.value = Number(row.global_port || 8080)
        protocolCombo.currentIndex = String(row.protocol || "").toUpperCase() === "TCP" ? 1 : (String(row.protocol || "").toUpperCase() === "UDP" ? 2 : 0)
    }

    function refreshDirtyFlag() {
        let dirty = pendingDeletes.length > 0
        for (let i = 0; i < entryModel.count && !dirty; i++) dirty = entryModel.get(i)._isNew || entryModel.get(i)._isEdited
        hasPendingLocalChanges = dirty
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function reloadEntries() {
        entryModel.clear()
        pendingDeletes = []
        nextLocalId = -1
        hasPendingLocalChanges = false
        if (currentHostIp === "") return
        const rows = dbManager.getNatStaticEntries(currentHostIp)
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            row._isNew = false
            row._isEdited = false
            entryModel.append(row)
        }
    }

    function stageEntry() {
        const values = { inside_local: insideLocalField.text.trim(), inside_global: insideGlobalField.text.trim(),
            protocol: protocolCombo.currentValue === "Any" ? "" : protocolCombo.currentValue,
            local_port: protocolCombo.currentValue === "Any" ? "" : String(localPortSpin.value),
            global_port: protocolCombo.currentValue === "Any" ? "" : String(globalPortSpin.value) }
        if (isEditing()) {
            for (let i = 0; i < entryModel.count; i++) {
                if (entryModel.get(i).nat_static_id !== editingStaticId) continue
                for (const key in values) entryModel.setProperty(i, key, values[key])
                if (!entryModel.get(i)._isNew) entryModel.setProperty(i, "_isEdited", true)
                break
            }
        } else entryModel.append({ nat_static_id: nextLocalId--, nat_id: 0,
            inside_local: values.inside_local,
            inside_global: values.inside_global, protocol: values.protocol, local_port: values.local_port,
            global_port: values.global_port, is_extendable: 0, description: "",
            sync_status: "pending_apply", _isNew: true, _isEdited: false })
        clearForm()
        refreshDirtyFlag()
    }

    function removeEntry(index, row) {
        if (!row._isNew) pendingDeletes = pendingDeletes.concat([row.nat_static_id])
        entryModel.remove(index)
        if (editingStaticId === row.nat_static_id) clearForm()
        refreshDirtyFlag()
    }

    function saveChanges() {
        let ok = true
        for (let i = 0; i < pendingDeletes.length && ok; i++) ok = dbManager.deleteNatStaticEntry(pendingDeletes[i])
        for (let i = 0; i < entryModel.count && ok; i++) {
            const row = entryModel.get(i)
            if (row._isEdited) ok = dbManager.deleteNatStaticEntry(row.nat_static_id)
            if (ok && (row._isNew || row._isEdited)) ok = dbManager.addNatStaticEntry(currentHostIp, row.inside_local, row.inside_global, row.protocol, row.local_port, row.global_port)
        }
        reloadEntries()
        if (ok) dataChanged()
        notify(ok ? "Saved static NAT changes." : "Save static NAT changes failed.", ok ? "success" : "error")
    }

    onCurrentHostIpChanged: {
        clearForm()
        reloadEntries()
    }
    Component.onCompleted:  reloadEntries()

    ListModel { id: entryModel }

    SplitView {
        id: staticSplit
        objectName: "natStaticResponsiveSplit"
        anchors.fill: parent
        anchors.bottomMargin: 60
        orientation: natStaticForm.compactLayout ? Qt.Vertical : Qt.Horizontal

        handle: StandardSplitHandle { enabled: false }

        // ── CỘT TRÁI — Form nhập ──
        SplitFormPane {
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: natStaticForm.compactLayout ? staticSplit.width : staticSplit.width * 0.4
            SplitView.minimumWidth: natStaticForm.compactLayout ? 0 : staticSplit.width * 0.4
            SplitView.maximumWidth: natStaticForm.compactLayout ? Number.POSITIVE_INFINITY : staticSplit.width * 0.4
            SplitView.preferredHeight: natStaticForm.compactLayout ? staticSplit.height * 0.4 : staticSplit.height
            SplitView.minimumHeight: natStaticForm.compactLayout ? staticSplit.height * 0.4 : 0
            SplitView.maximumHeight: natStaticForm.compactLayout ? staticSplit.height * 0.4 : Number.POSITIVE_INFINITY

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    Text {
                        Layout.fillWidth: true
                        text:           natStaticForm.isEditing() ? "Edit Static NAT" : "Add Static NAT"
                        color:          Theme.textPrimary
                        font.pixelSize: Theme.fontSizeLarge
                        font.family:    Theme.fontFamily
                        font.bold:      true
                    }
                    ParameterHelpButton {
                        Layout.preferredWidth: 22
                        Layout.preferredHeight: 22
                        helpTitle: "Static NAT parameters"
                        helpText: "Inside Local IP is the private address seen inside the network. Inside Global IP is its public translated address.\n\nProtocol and local/global ports optionally create a static TCP or UDP port mapping; when used, provide both ports. Ensure NAT inside/outside roles are assigned to the relevant interfaces."
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text:             "Map one inside local IP to one public IP."
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

                // Inside Local IP
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text:           "Inside Local IP"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardNetworkField {
                        id:               insideLocalField
                        inputKind:        "ipv4"
                        Layout.fillWidth: true
                        placeholderText:  "e.g., 192.168.1.10"
                    }
                }

                // Inside Global IP
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text:           "Inside Global IP"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardNetworkField {
                        id:               insideGlobalField
                        inputKind:        "ipv4"
                        Layout.fillWidth: true
                        placeholderText:  "e.g., 203.0.113.10"
                    }
                }

                // Protocol (optional)
                StandardComboBox {
                    id:               protocolCombo
                    Layout.fillWidth: true
                    labelText:        "Protocol (optional)"
                    model:            ["Any", "TCP", "UDP"]
                    valueModel:       ["Any", "TCP", "UDP"]
                }

                // Port fields — chỉ hiện khi Protocol != Any
                RowLayout {
                    Layout.fillWidth: true
                    spacing:          8
                    visible:          protocolCombo.currentValue !== "Any"

                    StandardSpinBox {
                        id: localPortSpin
                        Layout.fillWidth: true
                        labelText: "Inside Local Port"
                        from: 1
                        to: 65535
                        value: 80
                        stepSize: 1
                    }

                    StandardSpinBox {
                        id: globalPortSpin
                        Layout.fillWidth: true
                        labelText: "Inside Global Port"
                        from: 1
                        to: 65535
                        value: 8080
                        stepSize: 1
                    }
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    StandardButton { Layout.preferredWidth: 84; text: "Cancel"; type: "Text"; visible: natStaticForm.isEditing(); onClicked: natStaticForm.clearForm() }
                    StandardButton {
                        Layout.fillWidth: true; Layout.preferredHeight: 36; type: "Primary"
                        text: natStaticForm.isEditing() ? "Apply Edit" : "Add Locally"
                        enabled: insideLocalField.text.trim() !== "" && insideGlobalField.text.trim() !== "" && currentHostIp !== ""
                        onClicked: natStaticForm.stageEntry()
                    }
                }
            }

        // ── CỘT PHẢI — Danh sách ──
        SavedListPanel {
            SplitView.fillWidth: true
            SplitView.minimumWidth: 0
            SplitView.fillHeight: true
            SplitView.minimumHeight: natStaticForm.compactLayout ? 220 : 0
            title: "Static NAT Entries"
            count: entryModel.count
            emptyText: "No static NAT entries configured yet.\nAdd an entry using the form on the left."
            headerComponent: Component {
                SavedListHeader {
                    width: parent ? parent.width : 0




                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.preferredWidth: 160
                            header: true
                            text: "Inside Local"
                        }
                        DataTableCell {
                            Layout.preferredWidth: 160
                            header: true
                            text: "Inside Global"
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            header: true
                            text: "Protocol / Port"
                        }
                        DataTableCell { Layout.preferredWidth: 64; header: true; text: "Actions" }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                model: entryModel
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
                            Layout.preferredWidth: 160
                            monospaced: true
                            primary: true
                            text: model.inside_local
                        }
                        DataTableCell {
                            Layout.preferredWidth: 160
                            monospaced: true
                            text: model.inside_global
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            text: {
                                const proto = model.protocol || ""
                                const lp    = model.local_port || ""
                                const gp    = model.global_port || ""
                                if (proto === "") return "Any"
                                if (lp !== "" && gp !== "") return proto + "  " + lp + " → " + gp
                                return proto
                            }
                        }

                        Item {
                            Layout.preferredWidth: 64
                            Layout.fillHeight: true
                            Row {
                                anchors.centerIn: parent; spacing: 4
                                IconButton { buttonSize: 24; iconSize: 12; glyph: "E"; tooltip: "Edit"; onClicked: natStaticForm.editEntry(model) }
                                IconButton { buttonSize: 24; iconSize: 11; glyph: "✕"; danger: true; tooltip: "Delete"; onClicked: natStaticForm.removeEntry(index, model) }
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
            text: "Static NAT entries are saved locally before push."
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
                natStaticForm.clearForm()
                natStaticForm.reloadEntries()
                natStaticForm.notify("Discarded local static NAT changes.", "info")
            }
        }
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            enabled: currentHostIp !== ""
            onClicked: {
                natStaticForm.clearForm()
                natStaticForm.reloadEntries()
                natStaticForm.notify("Reloaded static NAT entries from database.", "info")
            }
        }
        StandardButton {
            text: "Save"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && currentHostIp !== ""
            onClicked: natStaticForm.saveChanges()
        }
    }
}
