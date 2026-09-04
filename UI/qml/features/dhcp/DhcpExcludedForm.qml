pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: dhcpExcludedForm
    color: Theme.contentBackground
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint

    property string currentHostIp: ""
    property int nextLocalId: -1
    property var pendingDeletes: []
    property bool hasPendingLocalChanges: false

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function normalizedExcluded(row) {
        return {
            ex_id: Number(row.ex_id || 0),
            host: String(row.host || ""),
            start_ip: String(row.start_ip || ""),
            end_ip: String(row.end_ip || ""),
            syncStatus: String(row.sync_status || StatusValues.pendingApply),
            _isNew: false
        }
    }

    function clearForm() {
        startIpField.text = ""
        endIpField.text = ""
    }

    function stageExcluded() {
        excludedListModel.append({
            ex_id: nextLocalId--, host: currentHostIp,
            start_ip: startIpField.text.trim(),
            end_ip: endIpField.text.trim() || startIpField.text.trim(),
            syncStatus: StatusValues.pendingApply, _isNew: true
        })
        clearForm()
        hasPendingLocalChanges = true
    }

    function removeExcluded(index, row) {
        if (!row._isNew) pendingDeletes = pendingDeletes.concat([row.ex_id])
        excludedListModel.remove(index)
        hasPendingLocalChanges = pendingDeletes.length > 0
        for (let i = 0; i < excludedListModel.count && !hasPendingLocalChanges; i++)
            hasPendingLocalChanges = excludedListModel.get(i)._isNew
    }

    function saveChanges() {
        let ok = true
        for (let i = 0; i < pendingDeletes.length && ok; i++)
            ok = dbManager.deleteExcludedAddress(pendingDeletes[i])
        for (let i = 0; i < excludedListModel.count && ok; i++) {
            const row = excludedListModel.get(i)
            if (row._isNew) ok = dbManager.addExcludedAddress(currentHostIp, row.start_ip, row.end_ip)
        }
        reloadExcluded()
        if (ok) { dataChanged(); notify("Saved excluded address changes.", "success") }
        else notify("Save excluded address changes failed.", "error")
    }

    function cancelChanges() {
        clearForm()
        reloadExcluded()
        notify("Discarded local excluded address changes.", "info")
    }

    signal dataChanged()

    function reloadExcluded() {
        excludedListModel.clear()
        pendingDeletes = []
        nextLocalId = -1
        hasPendingLocalChanges = false
        if (currentHostIp === "") return
        // @suppress("missing-property") dbManager is context property from C++
        const rows = dbManager.getExcludedAddresses(currentHostIp)
        for (let i = 0; i < rows.length; i++) {
            excludedListModel.append(normalizedExcluded(rows[i]))
        }
    }

    onCurrentHostIpChanged: { clearForm(); reloadExcluded() }
    Component.onCompleted:  reloadExcluded()

    ListModel { id: excludedListModel }

    SplitView {
        id: excludedSplit
        anchors.fill: parent
        anchors.bottomMargin: 60
        orientation: dhcpExcludedForm.compactLayout ? Qt.Vertical : Qt.Horizontal

        handle: StandardSplitHandle { enabled: false }

        // ══════════════════════════════════════════════════════════
        // CỘT TRÁI — Form
        // ══════════════════════════════════════════════════════════
        SplitFormPane {
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: dhcpExcludedForm.compactLayout ? excludedSplit.width : excludedSplit.width * 0.4
            SplitView.minimumWidth: dhcpExcludedForm.compactLayout ? 0 : excludedSplit.width * 0.4
            SplitView.maximumWidth: dhcpExcludedForm.compactLayout ? Number.POSITIVE_INFINITY : excludedSplit.width * 0.4
            SplitView.preferredHeight: dhcpExcludedForm.compactLayout ? excludedSplit.height * 0.4 : excludedSplit.height
            SplitView.minimumHeight: dhcpExcludedForm.compactLayout ? excludedSplit.height * 0.4 : 0
            SplitView.maximumHeight: dhcpExcludedForm.compactLayout ? excludedSplit.height * 0.4 : Number.POSITIVE_INFINITY

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    Text {
                        Layout.fillWidth: true
                        text:           "Add Excluded Address"
                        color:          Theme.textPrimary
                        font.pixelSize: Theme.fontSizeLarge
                        font.family:    Theme.fontFamily
                        font.bold:      true
                    }

                    ParameterHelpButton {
                        Layout.preferredWidth: 22
                        Layout.preferredHeight: 22
                        helpTitle: "DHCP excluded-address parameters"
                        helpText: "Start IP: first IPv4 address the local DHCP server must never allocate, commonly a gateway or statically assigned device.\n\n" +
                                  "End IP: optional last address of a contiguous excluded range. It must be in the same relevant subnet and not lower than Start IP. Leave it empty to exclude only the Start IP."
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height:           Theme.borderWidth
                    color:            Theme.splitHandleColor
                }

                // Start IP
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
                        placeholderText:  "e.g., 192.168.10.1"
                    }
                }

                // End IP
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text:           "End IP (optional)"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }
                    StandardNetworkField {
                        id:               endIpField
                        inputKind:        "ipv4"
                        Layout.fillWidth: true
                        placeholderText:  "e.g., 192.168.10.10"
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text:             "Leave End IP empty to exclude one address."
                    color:            Theme.textDisabled
                    font.pixelSize:   Theme.fontSizeSmall
                    font.family:      Theme.fontFamily
                    lineHeight:       1.5
                    wrapMode:         Text.WordWrap
                }

                Item { Layout.fillHeight: true }

                StandardButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    type: "Primary"
                    text: "Add Locally"
                    enabled: startIpField.text.trim() !== "" && currentHostIp !== ""

                    onClicked: dhcpExcludedForm.stageExcluded()
                }
        }

        // ══════════════════════════════════════════════════════════
        // CỘT PHẢI — Danh sách
        // ══════════════════════════════════════════════════════════
        SavedListPanel {
            SplitView.fillWidth: true
            SplitView.fillHeight: true
            SplitView.minimumWidth: dhcpExcludedForm.compactLayout ? 0 : 200
            SplitView.minimumHeight: dhcpExcludedForm.compactLayout ? 220 : 0
            title: "Excluded Addresses"
            count: excludedListModel.count
            countColor: Theme.alertError
            emptyText: "No excluded addresses configured yet.\nAdd an entry using the form on the left."
            headerComponent: Component {
                SavedListHeader {
                    width: parent ? parent.width : 0




                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.preferredWidth: 36
                            header: true
                            text: "#"
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            header: true
                            text: "Start IP"
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            header: true
                            text: "End IP"
                        }
                        DataTableCell { Layout.preferredWidth: 32; header: true; text: "" }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                model: excludedListModel
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
                            Layout.preferredWidth: 36
                            text: index + 1
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            monospaced: true
                            primary: true
                            text: model.start_ip
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            monospaced: true
                            primary: true
                            text: model.end_ip
                        }

                        Item {
                            Layout.preferredWidth: 32
                            Layout.fillHeight: true

                            IconButton {
                                anchors.centerIn: parent
                                buttonSize: 24
                                iconSize: 11
                                glyph: "✕"
                                danger: true
                                tooltip: "Delete"
                                onClicked: dhcpExcludedForm.removeExcluded(index, model)
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
            text: "Excluded addresses are saved locally before push."
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        StandardButton {
            text: "Cancel Changes"
            type: "Text"
            enabled: hasPendingLocalChanges
            onClicked: dhcpExcludedForm.cancelChanges()
        }

        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            enabled: currentHostIp !== ""
            onClicked: {
                dhcpExcludedForm.reloadExcluded()
                dhcpExcludedForm.notify("Reloaded DHCP excluded addresses for host " + currentHostIp, "info")
            }
        }
        StandardButton {
            text: "Save"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && currentHostIp !== ""
            onClicked: dhcpExcludedForm.saveChanges()
        }

    }
}
