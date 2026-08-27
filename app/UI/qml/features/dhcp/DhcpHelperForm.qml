pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: dhcpHelperForm
    color: Theme.contentBackground
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint

    property string currentHostIp: ""
    property var ifaceIds: []
    property var ifaceNames: []
    property int nextLocalId: -1
    property var pendingDeletes: []
    property bool hasPendingLocalChanges: false

    signal dataChanged()

    function selectedIfaceId() {
        if (interfaceCombo.currentIndex < 0 || interfaceCombo.currentIndex >= ifaceIds.length)
            return -1
        return ifaceIds[interfaceCombo.currentIndex]
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function normalizedHelper(row) {
        return {
            id: Number(row.id || 0),
            iface_id: Number(row.iface_id || 0),
            interface_name: String(row.interface_name || ""),
            helper_ip: String(row.helper_ip || ""),
            syncStatus: String(row.sync_status || StatusValues.pendingApply),
            _isNew: false
        }
    }

    function clearForm() {
        helperIpField.text = ""
        interfaceCombo.currentIndex = ifaceNames.length > 0 ? 0 : -1
    }

    function stageHelper() {
        const index = interfaceCombo.currentIndex
        helperListModel.append({
            id: nextLocalId--, iface_id: selectedIfaceId(),
            interface_name: ifaceNames[index], helper_ip: helperIpField.text.trim(),
            syncStatus: StatusValues.pendingApply, _isNew: true
        })
        clearForm()
        hasPendingLocalChanges = true
    }

    function removeHelper(index, row) {
        if (!row._isNew) pendingDeletes = pendingDeletes.concat([row.id])
        helperListModel.remove(index)
        hasPendingLocalChanges = pendingDeletes.length > 0
        for (let i = 0; i < helperListModel.count && !hasPendingLocalChanges; i++)
            hasPendingLocalChanges = helperListModel.get(i)._isNew
    }

    function saveChanges() {
        let ok = true
        for (let i = 0; i < pendingDeletes.length && ok; i++)
            ok = dbManager.deleteDhcpHelperAddress(pendingDeletes[i])
        for (let i = 0; i < helperListModel.count && ok; i++) {
            const row = helperListModel.get(i)
            if (row._isNew) ok = dbManager.addDhcpHelperAddress(row.iface_id, row.helper_ip)
        }
        reloadHelpers()
        if (ok) { dataChanged(); notify("Saved DHCP helper changes.", "success") }
        else notify("Save DHCP helper changes failed.", "error")
    }

    function cancelChanges() {
        clearForm()
        reloadHelpers()
        notify("Discarded local DHCP helper changes.", "info")
    }

    function reloadInterfaces() {
        const ids = []
        const names = []
        if (currentHostIp === "") {
            ifaceIds = ids
            ifaceNames = names
            interfaceCombo.currentIndex = -1
            return
        }

        const rows = dbManager.getRouterInterfaces(currentHostIp)
        for (let i = 0; i < rows.length; i++) {
            const name = rows[i].interface_name || ""
            if (name === "") continue
            ids.push(rows[i].iface_id)
            names.push(name)
        }
        ifaceIds = ids
        ifaceNames = names
        interfaceCombo.currentIndex = ifaceNames.length > 0 ? 0 : -1
    }

    function reloadHelpers() {
        helperListModel.clear()
        pendingDeletes = []
        nextLocalId = -1
        hasPendingLocalChanges = false
        if (currentHostIp === "") return

        const rows = dbManager.getDhcpHelperAddresses(currentHostIp)
        for (let i = 0; i < rows.length; i++)
            helperListModel.append(normalizedHelper(rows[i]))
    }

    function reloadAll() {
        reloadInterfaces()
        reloadHelpers()
    }

    onCurrentHostIpChanged: { reloadAll(); clearForm() }
    Component.onCompleted: reloadAll()

    ListModel { id: helperListModel }

    SplitView {
        id: helperSplit
        anchors.fill: parent
        anchors.bottomMargin: 60
        orientation: dhcpHelperForm.compactLayout ? Qt.Vertical : Qt.Horizontal
        handle: StandardSplitHandle { enabled: false }

        SplitFormPane {
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: dhcpHelperForm.compactLayout ? helperSplit.width : helperSplit.width * 0.4
            SplitView.minimumWidth: dhcpHelperForm.compactLayout ? 0 : helperSplit.width * 0.4
            SplitView.maximumWidth: dhcpHelperForm.compactLayout ? Number.POSITIVE_INFINITY : helperSplit.width * 0.4
            SplitView.preferredHeight: dhcpHelperForm.compactLayout ? helperSplit.height * 0.4 : helperSplit.height
            SplitView.minimumHeight: dhcpHelperForm.compactLayout ? helperSplit.height * 0.4 : 0
            SplitView.maximumHeight: dhcpHelperForm.compactLayout ? helperSplit.height * 0.4 : Number.POSITIVE_INFINITY

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing8

                Text {
                    Layout.fillWidth: true
                    text: "Add Helper Address"
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeLarge
                    font.family: Theme.fontFamily
                    font.bold: true
                }

                ParameterHelpButton {
                    Layout.preferredWidth: 22
                    Layout.preferredHeight: 22
                    helpTitle: "DHCP helper parameters"
                    helpText: "Interface: Layer-3 interface that receives client DHCP broadcasts. It must have an IP address and be reachable by the clients.\n\n" +
                              "Helper IP: unicast IPv4 address of the remote DHCP server. The router relays supported UDP broadcasts from this interface to that server. Add one entry per server when redundancy is required."
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: Theme.borderWidth
                color: Theme.splitHandleColor
            }

            StandardComboBox {
                id: interfaceCombo
                Layout.fillWidth: true
                labelText: "Interface"
                model: dhcpHelperForm.ifaceNames
                emptyWarningText: "No Interface options are available for this device. Add or load interfaces before configuring DHCP Helper."
            }

            StandardNetworkField {
                id: helperIpField
                inputKind: "ipv4"
                Layout.fillWidth: true
                labelText: "Helper IP"
                placeholderText: "e.g., 10.10.10.5"
            }

            Item { Layout.fillHeight: true }

            StandardButton {
                Layout.fillWidth: true
                Layout.preferredHeight: 36
                type: "Primary"
                text: "Add Locally"
                enabled: dhcpHelperForm.selectedIfaceId() >= 0 &&
                         helperIpField.text.trim() !== "" &&
                         currentHostIp !== ""

                onClicked: dhcpHelperForm.stageHelper()
            }
        }

        SavedListPanel {
            SplitView.fillWidth: true
            SplitView.fillHeight: true
            SplitView.minimumWidth: 0
            SplitView.minimumHeight: dhcpHelperForm.compactLayout ? 220 : 0
            title: "Helper Addresses"
            count: helperListModel.count
            countColor: Theme.accentColor
            emptyText: "No helper addresses configured yet.\nAdd one from the form on the left."
            headerComponent: Component {
                SavedListHeader {
                    width: parent ? parent.width : 0

                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.fillWidth: true
                            header: true
                            text: "Interface"
                        }
                        DataTableCell {
                            Layout.fillWidth: true
                            header: true
                            text: "Helper IP"
                        }
                        DataTableCell { Layout.preferredWidth: 32; header: true; text: "" }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                model: helperListModel
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
                        DataTableCell {
                            Layout.fillWidth: true
                            monospaced: true
                            text: model.helper_ip
                        }

                        Item {
                            Layout.preferredWidth: 32
                            Layout.fillHeight: true

                            IconButton {
                                anchors.centerIn: parent
                                buttonSize: 24
                                iconSize: 11
                                glyph: "X"
                                danger: true
                                tooltip: "Delete"
                                onClicked: dhcpHelperForm.removeHelper(index, model)
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
            text: "Helper addresses are saved locally before push."
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        StandardButton {
            text: "Cancel Changes"
            type: "Text"
            enabled: hasPendingLocalChanges
            onClicked: dhcpHelperForm.cancelChanges()
        }
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            enabled: currentHostIp !== ""
            onClicked: {
                dhcpHelperForm.reloadAll()
                dhcpHelperForm.notify("Reloaded DHCP helper addresses for host " + currentHostIp, "info")
            }
        }
        StandardButton {
            text: "Save"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && currentHostIp !== ""
            onClicked: dhcpHelperForm.saveChanges()
        }

    }
}
