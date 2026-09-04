pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: dhcpPoolForm
    color: Theme.contentBackground
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint

    property string currentHostIp: ""
    property int editingDhcpId: -1
    property int editingModelIndex: -1
    property int nextLocalId: -1
    property var pendingDeletes: []
    property bool hasPendingLocalChanges: false

    signal dataChanged()

    function isEditing() {
        return editingModelIndex >= 0
    }

    function hasValidFormDraft() {
        return poolField.text.trim() !== "" &&
               networkField.text.trim() !== "" &&
               subnetField.text.trim() !== "" &&
               currentHostIp !== ""
    }

    function clearForm() {
        editingDhcpId = -1
        editingModelIndex = -1
        poolField.text = ""
        networkField.text = ""
        subnetField.text = ""
        gatewayField.text = ""
        dnsField.text = ""
        leaseField.text = "1"
    }

    function poolSignature(row) {
        return JSON.stringify([
            String(row.pool || "").trim(),
            String(row.network || "").trim(),
            String(row.subnetmask || "").trim(),
            String(row.defaut || "").trim(),
            String(row.dns || "").trim(),
            String(row.lease || "1").trim() || "1"
        ])
    }

    function draftValues() {
        return {
            pool: poolField.text.trim(), network: networkField.text.trim(),
            subnetmask: subnetField.text.trim(), defaut: gatewayField.text.trim(),
            dns: dnsField.text.trim(), lease: leaseField.text.trim() || "1"
        }
    }

    function draftHasChanges() {
        if (!isEditing() || editingModelIndex >= poolListModel.count)
            return hasValidFormDraft()
        return poolSignature(draftValues()) !== poolSignature(poolListModel.get(editingModelIndex))
    }

    function editPool(index, row) {
        editingModelIndex = index
        editingDhcpId = row.dhcp_id
        poolField.text = row.pool || ""
        networkField.text = row.network || ""
        subnetField.text = row.subnetmask || ""
        gatewayField.text = row.defaut || ""
        dnsField.text = row.dns || ""
        leaseField.text = row.lease || "1"
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function normalizedPool(row) {
        return {
            dhcp_id: Number(row.dhcp_id || 0),
            host: String(row.host || ""),
            pool: String(row.pool || ""),
            network: String(row.network || ""),
            subnetmask: String(row.subnetmask || ""),
            defaut: row.defaut === undefined || row.defaut === null ? "" : String(row.defaut),
            dns: row.dns === undefined || row.dns === null ? "" : String(row.dns),
            lease: row.lease === undefined || row.lease === null || String(row.lease).trim() === "" ? "1" : String(row.lease),
            syncStatus: String(row.sync_status || StatusValues.pendingApply),
            action_Cfg: String(row.action_Cfg || "111"),
            _baselineSignature: poolSignature(row),
            _isNew: false,
            _isEdited: false
        }
    }

    function refreshDirtyFlag() {
        let dirty = pendingDeletes.length > 0
        for (let i = 0; i < poolListModel.count && !dirty; i++)
            dirty = poolListModel.get(i)._isNew || poolListModel.get(i)._isEdited
        hasPendingLocalChanges = dirty
    }

    function stagePool() {
        const values = draftValues()
        if (isEditing()) {
            if (editingModelIndex >= poolListModel.count) return
            const index = editingModelIndex
            for (const key in values) poolListModel.setProperty(index, key, values[key])
            if (!poolListModel.get(index)._isNew) {
                poolListModel.setProperty(
                    index,
                    "_isEdited",
                    poolSignature(values) !== poolListModel.get(index)._baselineSignature
                )
            }
        } else {
            poolListModel.append({
                dhcp_id: nextLocalId--, host: currentHostIp,
                pool: values.pool, network: values.network, subnetmask: values.subnetmask,
                defaut: values.defaut, dns: values.dns, lease: values.lease,
                syncStatus: StatusValues.pendingApply, action_Cfg: "000",
                _baselineSignature: poolSignature(values), _isNew: true, _isEdited: false
            })
        }
        clearForm()
        refreshDirtyFlag()
    }

    function removePool(index, row) {
        if (!row._isNew) pendingDeletes = pendingDeletes.concat([row.dhcp_id])
        poolListModel.remove(index)
        if (editingModelIndex === index) clearForm()
        else if (editingModelIndex > index) editingModelIndex--
        refreshDirtyFlag()
    }

    function saveChanges() {
        // Save should also commit the pool currently present in the editor.
        // "Add Locally" remains useful for staging several pools at once, but
        // it is no longer a hidden prerequisite for persistence.
        if (hasValidFormDraft())
            stagePool()
        let ok = true
        for (let i = 0; i < pendingDeletes.length && ok; i++)
            ok = dbManager.deleteDhcpPool(pendingDeletes[i])
        for (let i = 0; i < poolListModel.count && ok; i++) {
            const row = poolListModel.get(i)
            if (row._isNew)
                ok = dbManager.addDhcpPool(currentHostIp, row.pool, row.network, row.subnetmask, row.defaut, row.dns, row.lease)
            else if (row._isEdited)
                ok = dbManager.updateDhcpPool(row.dhcp_id, row.pool, row.network, row.subnetmask, row.defaut, row.dns, row.lease)
        }
        reloadPools()
        if (ok) {
            dataChanged()
            notify("Saved DHCP pool changes.", "success")
        } else notify("Save DHCP pool changes failed.", "error")
        return ok
    }

    function cancelChanges() {
        clearForm()
        reloadPools()
        notify("Discarded local DHCP pool changes.", "info")
    }

    function reloadPools() {
        poolListModel.clear()
        pendingDeletes = []
        nextLocalId = -1
        hasPendingLocalChanges = false
        if (currentHostIp === "") return
        // @suppress("missing-property") dbManager is context property from C++
        const rows = dbManager.getDhcpPools(currentHostIp)
        for (let i = 0; i < rows.length; i++)
            poolListModel.append(normalizedPool(rows[i]))
    }

    onCurrentHostIpChanged: {
        clearForm()
        reloadPools()
    }
    Component.onCompleted: reloadPools()

    ListModel { id: poolListModel }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        SplitView {
            id: poolSplit
            objectName: "dhcpPoolResponsiveSplit"
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: dhcpPoolForm.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { enabled: false }

            SplitFormPane {
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: dhcpPoolForm.compactLayout ? poolSplit.width : poolSplit.width * 0.4
            SplitView.minimumWidth: dhcpPoolForm.compactLayout ? 0 : poolSplit.width * 0.4
            SplitView.maximumWidth: dhcpPoolForm.compactLayout ? Number.POSITIVE_INFINITY : poolSplit.width * 0.4
            SplitView.preferredHeight: dhcpPoolForm.compactLayout ? poolSplit.height * 0.4 : poolSplit.height
            SplitView.minimumHeight: dhcpPoolForm.compactLayout ? poolSplit.height * 0.4 : 0
            SplitView.maximumHeight: dhcpPoolForm.compactLayout ? poolSplit.height * 0.4 : Number.POSITIVE_INFINITY

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing8

                Text {
                    Layout.fillWidth: true
                    text: dhcpPoolForm.isEditing() ? "Edit DHCP Pool" : "Add DHCP Pool"
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeLarge
                    font.family: Theme.fontFamily
                    font.bold: true
                }

                ParameterHelpButton {
                    Layout.preferredWidth: 22
                    Layout.preferredHeight: 22
                    helpTitle: "DHCP pool parameters"
                    helpText: "Pool Name: IOS DHCP pool identifier, for example POOL_VLAN10. Use a clear unique name without spaces.\n\n" +
                              "Network: subnet served by this pool, such as 192.168.10.0.\n\n" +
                              "Subnet Mask: dotted mask or CIDR prefix, for example 255.255.255.0 or /24.\n\n" +
                              "Default Router: gateway offered to clients; normally an address on the served subnet.\n\n" +
                              "DNS Server: DNS resolver address offered to clients.\n\n" +
                              "Lease: IOS lease duration. Enter days (1) or days hours minutes (7 12 0)."
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: Theme.borderWidth
                color: Theme.splitHandleColor
            }

            StandardTextField {
                id: poolField
                Layout.fillWidth: true
                labelText: "Pool Name"
                placeholderText: "e.g., POOL_VLAN10"
            }

            StandardNetworkField {
                id: networkField
                inputKind: "ipv4"
                Layout.fillWidth: true
                labelText: "Network"
                placeholderText: "e.g., 192.168.10.0"
            }

            StandardNetworkField {
                id: subnetField
                inputKind: "subnet"
                Layout.fillWidth: true
                labelText: "Subnet Mask (/24)"
                placeholderText: "e.g., 255.255.255.0 or /24"
            }

            StandardNetworkField {
                id: gatewayField
                inputKind: "ipv4"
                Layout.fillWidth: true
                labelText: "Default Router"
                placeholderText: "e.g., 192.168.10.1"
            }

            StandardTextField {
                id: dnsField
                Layout.fillWidth: true
                labelText: "DNS Server"
                placeholderText: "e.g., 8.8.8.8"
            }

            StandardTextField {
                id: leaseField
                Layout.fillWidth: true
                labelText: "Lease"
                placeholderText: "e.g., 1 or 7 12 0"
                text: "1"
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing8

                StandardButton {
                    Layout.preferredWidth: 84
                    Layout.preferredHeight: 36
                    text: "Cancel"
                    type: "Text"
                    visible: dhcpPoolForm.isEditing()
                    onClicked: dhcpPoolForm.clearForm()
                }

                StandardButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    type: "Primary"
                text: dhcpPoolForm.isEditing() ? "Apply Edit" : "Add Locally"
                    enabled: dhcpPoolForm.hasValidFormDraft() &&
                             (!dhcpPoolForm.isEditing() || dhcpPoolForm.draftHasChanges())

                    onClicked: dhcpPoolForm.stagePool()
                }
            }
        }

            DhcpPoolList {
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.minimumWidth: 0
                SplitView.minimumHeight: dhcpPoolForm.compactLayout ? 220 : 0
                poolModel: poolListModel
                onEditRequested: (index, row) => dhcpPoolForm.editPool(index, row)
                onDeleteRequested: (index, row) => dhcpPoolForm.removePool(index, row)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 12
            spacing: Theme.spacing8

            Text {
                Layout.fillWidth: true
                text: "DHCP pools are saved locally before push."
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeSmall
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }

            StandardButton {
                text: "Cancel Changes"
                type: "Text"
                enabled: hasPendingLocalChanges
                onClicked: dhcpPoolForm.cancelChanges()
            }

            StandardButton {
                text: "Reload UI"
                icon.source: AppAssets.actionDatabaseReload
                type: "Secondary"
                autoCompact: false
                Layout.minimumWidth: expandedImplicitWidth
                enabled: currentHostIp !== ""
                onClicked: {
                    dhcpPoolForm.clearForm()
                    dhcpPoolForm.reloadPools()
                    dhcpPoolForm.notify("Reloaded DHCP pools for host " + currentHostIp, "info")
                }
            }

            StandardButton {
                text: "Save"
                icon.source: AppAssets.actionSave
                type: "Primary"
                enabled: currentHostIp !== "" &&
                         (hasPendingLocalChanges ||
                          (dhcpPoolForm.hasValidFormDraft() &&
                           (!dhcpPoolForm.isEditing() || dhcpPoolForm.draftHasChanges())))
                onClicked: dhcpPoolForm.saveChanges()
            }

        }
    }
}
