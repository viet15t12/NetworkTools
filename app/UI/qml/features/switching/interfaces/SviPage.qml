pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import UI as App

Item {
    id: root
    objectName: "loadedSwitchSviPage"

    required property string host
    property int formMode: 0
    property int selectedIndex: -1
    property bool dirty: false
    property bool saving: false
    property bool deletePending: false
    property int pendingDeleteId: 0
    property int pendingDeleteVlanId: 0
    property bool ipRoutingEnabled: false
    property var draftData: ({})
    property var allRows: []
    property int dataRevision: 0
    property string filterText: ""
    property string message: ""
    property bool messageError: false

    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property bool hasPendingDeletes: deletePending
    readonly property bool hasDetail: formMode !== 0 || selectedRow() !== null
    readonly property bool selectedSviCanDelete: selectedRow() !== null
    readonly property var summaryMetrics: {
        const revision = root.dataRevision
        let up = 0
        let addressed = 0
        for (let i = 0; i < root.allRows.length; i++) {
            if (!root.allRows[i].shutdown) up += 1
            if (String(root.allRows[i].ip_address || "") !== "") addressed += 1
        }
        return [
            { label: "SVIs", value: root.allRows.length, tone: "neutral" },
            { label: "Admin up", value: up, tone: "success" },
            { label: "Addressed", value: addressed, tone: "accent" },
            { label: "IP routing", value: root.ipRoutingEnabled ? "On" : "Off", tone: root.ipRoutingEnabled ? "success" : "warning" }
        ]
    }

    ListModel { id: sviModel }

    function clone(value) { return JSON.parse(JSON.stringify(value || {})) }
    function normalizedRow(row) {
        const source = row || ({})
        return {
            id: Number(source.id || 0),
            vlan_id: Number(source.vlan_id || 0),
            vlan_name: source.vlan_name === undefined || source.vlan_name === null
                       ? "" : String(source.vlan_name),
            ip_address: source.ip_address === undefined || source.ip_address === null
                        ? "" : String(source.ip_address),
            subnet_mask: source.subnet_mask === undefined || source.subnet_mask === null
                         ? "" : String(source.subnet_mask),
            shutdown: Boolean(source.shutdown),
            sync_status: source.sync_status === undefined || source.sync_status === null
                         ? "pending_apply" : String(source.sync_status)
        }
    }
    function selectedRow() {
        return selectedIndex >= 0 && selectedIndex < sviModel.count
             ? sviModel.get(selectedIndex) : null
    }
    function activeData() { return formMode === 0 ? (selectedRow() || ({})) : draftData }

    function rebuildVisibleRows() {
        const current = selectedRow()
        const selectedId = current ? Number(current.id || 0) : Number(draftData.id || 0)
        const query = String(filterText || "").trim().toLocaleLowerCase()
        sviModel.clear()
        let restoredIndex = -1
        for (let i = 0; i < allRows.length; i++) {
            const row = normalizedRow(allRows[i])
            const searchable = [row.vlan_id, row.vlan_name, row.ip_address, row.subnet_mask].join(" ").toLocaleLowerCase()
            if (query !== "" && searchable.indexOf(query) === -1) continue
            sviModel.append(row)
            if (Number(row.id || 0) === selectedId)
                restoredIndex = sviModel.count - 1
        }
        selectedIndex = restoredIndex >= 0 ? restoredIndex : sviModel.count > 0 ? 0 : -1
        if (formMode === 0)
            draftData = selectedRow() ? clone(selectedRow()) : ({})
        dataRevision += 1
    }

    function load(reason) {
        const rows = dbManager.getSwitchSvis(host)
        const values = []
        for (let i = 0; i < rows.length; i++) values.push(rows[i])
        allRows = values
        const routing = dbManager.getSwitchIpRouting(host)
        ipRoutingEnabled = Boolean(routing.ip_routing || false)
        formMode = 0
        dirty = false
        deletePending = false
        pendingDeleteId = 0
        pendingDeleteVlanId = 0
        rebuildVisibleRows()
        if (reason === "manual") message = "SVI inventory reloaded."
    }

    function beginCreate() {
        deletePending = false
        draftData = { id: 0, vlan_id: "", vlan_name: "", ip_address: "", subnet_mask: "", shutdown: false }
        formMode = 1
        dirty = false
    }

    function beginEdit() {
        if (!selectedRow()) return
        deletePending = false
        draftData = clone(selectedRow())
        formMode = 2
        dirty = false
    }

    function updateField(name, value) {
        draftData[name] = value
        dirty = true
        draftDataChanged()
    }

    function save() {
        saving = true
        const result = dbManager.saveSwitchSvi(host, draftData)
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }

    function cancel() {
        formMode = 0
        dirty = false
        draftData = selectedRow() ? clone(selectedRow()) : ({})
    }

    function stageDelete() {
        const row = selectedRow()
        if (formMode !== 0 || !row || saving) return
        pendingDeleteId = Number(row.id || 0)
        pendingDeleteVlanId = Number(row.vlan_id || 0)
        if (pendingDeleteId <= 0) return
        deletePending = true
        message = "SVI Vlan" + String(pendingDeleteVlanId)
                + " is marked for deletion. Select Save to commit or Cancel to discard."
        messageError = false
    }

    function savePendingDelete() {
        if (!deletePending || pendingDeleteId <= 0 || saving) return
        saving = true
        const result = dbManager.deleteSwitchSvi(host, pendingDeleteId)
        saving = false
        message = String(result && result.message
                         ? result.message : "Could not delete the selected SVI.")
        messageError = !result || result.ok !== true
        if (result && result.ok === true) load()
    }

    function cancelDelete() {
        if (!deletePending) return
        deletePending = false
        pendingDeleteId = 0
        pendingDeleteVlanId = 0
        message = "SVI deletion cancelled. No changes were saved."
        messageError = false
    }

    function setIpRouting(enabled) {
        const result = dbManager.saveSwitchIpRouting(host, enabled)
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) {
            ipRoutingEnabled = enabled
            dataRevision += 1
        }
    }

    Component.onCompleted: load()
    onHostChanged: load()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: "Switch Virtual Interfaces"
            subtitle: "Manage routed VLAN gateways and the switch-wide IP-routing state."

            StandardToggleButton {
                text: "IP Routing"
                checked: root.ipRoutingEnabled
                onClicked: root.setIpRouting(checked)
            }

            ViewPushButton {
                controllerName: "switching"
                hostIp: root.host
                moduleName: "svi"
                refreshKey: root.dataRevision
                ownerForm: root
                onPushCompleted: function(ok, detail) {
                    root.message = detail
                    root.messageError = !ok
                    if (ok) root.load()
                }
            }

            StandardButton {
                objectName: "sviAddButton"
                text: "Add"
                visible: root.formMode === 0
                enabled: !root.saving && !root.deletePending
                onClicked: root.beginCreate()
            }

            StandardButton {
                objectName: "sviCancelDeleteButton"
                text: "Cancel"
                icon.source: AppAssets.actionClear
                type: "Text"
                visible: root.formMode === 0 && root.deletePending
                enabled: !root.saving
                onClicked: root.cancelDelete()
            }

            StandardButton {
                objectName: "sviDeleteButton"
                text: "Delete SVI"
                icon.source: AppAssets.actionDelete
                type: "Secondary"
                visible: root.formMode === 0
                enabled: root.selectedSviCanDelete && !root.deletePending && !root.saving
                tooltip: "Delete the selected SVI"
                onClicked: root.stageDelete()
            }

            StandardButton {
                objectName: "sviSaveDeleteButton"
                text: root.saving ? "Saving..." : "Save"
                icon.source: AppAssets.actionSave
                type: "Danger"
                visible: root.formMode === 0 && root.deletePending
                enabled: !root.saving
                onClicked: root.savePendingDelete()
            }

            App.CrudFormActions {
                formMode: root.formMode
                hasSelection: root.selectedIndex >= 0
                dirty: root.dirty
                valid: String(root.draftData.vlan_id || "").trim() !== ""
                saving: root.saving
                allowCreate: false
                allowEdit: !root.deletePending
                allowRefresh: !root.deletePending
                allowEditorActions: false
                onEditRequested: root.beginEdit()
                onRefreshRequested: root.load("manual")
                onSaveRequested: root.save()
                onCancelRequested: root.cancel()
            }
        }

        InlineMessage {
            Layout.fillWidth: true
            message: root.message
            severity: root.deletePending ? "warning"
                      : root.messageError ? "error" : "success"
        }

        SwitchSummaryBar {
            Layout.fillWidth: true
            metrics: root.summaryMetrics
        }

        SplitView {
            id: sviSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { orientation: sviSplit.orientation }

            Item {
                SplitView.fillWidth: !root.compactLayout
                SplitView.fillHeight: root.compactLayout
                SplitView.minimumWidth: root.compactLayout ? 0 : 450
                SplitView.minimumHeight: root.compactLayout ? 220 : 0
                SplitView.preferredHeight: root.compactLayout
                                           ? Math.max(240, sviSplit.height * 0.52)
                                           : sviSplit.height

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.spacing8

                    SwitchTableToolbar {
                        Layout.fillWidth: true
                        title: "SVI inventory"
                        totalCount: root.allRows.length
                        visibleCount: sviModel.count
                        searchText: root.filterText
                        searchPlaceholder: "Filter SVIs..."
                        onSearchEdited: value => {
                            root.filterText = value
                            root.rebuildVisibleRows()
                        }
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        count: sviModel.count
                        bodyMargins: 0
                        emptyTitle: root.filterText === "" ? "No SVIs" : "No matching SVIs"
                        emptyDescription: root.filterText === ""
                                          ? "Use Add to create the first Layer 3 VLAN interface."
                                          : "Try a different VLAN, name, or address."
                        headerComponent: Component {
                            DataTableHeader {
                                RowLayout {
                                    anchors.fill: parent
                                    spacing: Theme.spacing8
                                    DataTableCell { Layout.preferredWidth: 100; header: true; text: "Interface" }
                                    DataTableCell { Layout.preferredWidth: 150; header: true; text: "VLAN Name" }
                                    DataTableCell { Layout.fillWidth: true; header: true; text: "IPv4 Address" }
                                    DataTableCell { Layout.preferredWidth: 88; header: true; text: "Admin" }
                                }
                            }
                        }

                        ListView {
                            anchors.fill: parent
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            model: sviModel
                            spacing: 0
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                            delegate: DataTableRow {
                                id: row
                                required property int index
                                required property var model

                                width: ListView.view.width
                                height: Theme.tableRowHeight
                                rowIndex: index
                                selected: root.selectedIndex === index
                                interactive: root.formMode === 0 && !root.deletePending

                                RowLayout {
                                    anchors.fill: parent
                                    spacing: Theme.spacing8
                                    DataTableCell { Layout.preferredWidth: 100; primary: true; text: "Vlan" + String(row.model.vlan_id) }
                                    DataTableCell { Layout.preferredWidth: 150; text: row.model.vlan_name || "—" }
                                    DataTableCell {
                                        Layout.fillWidth: true
                                        primary: true
                                        monospaced: true
                                        text: row.model.ip_address
                                              ? row.model.ip_address + " / " + (row.model.subnet_mask || "")
                                              : "No address"
                                    }
                                    App.StatusBadge { Layout.preferredWidth: 88; value: row.model.shutdown ? "down" : "up" }
                                }
                                TapHandler {
                                    enabled: root.formMode === 0 && !root.deletePending
                                    onTapped: {
                                        root.selectedIndex = row.index
                                        root.draftData = root.clone(root.selectedRow())
                                    }
                                }
                            }
                        }
                    }
                }
            }

            SwitchInspectorPane {
                SplitView.fillWidth: root.compactLayout
                SplitView.fillHeight: !root.compactLayout
                SplitView.preferredWidth: root.compactLayout ? sviSplit.width
                                                             : Math.min(420, root.width * 0.38)
                SplitView.minimumWidth: root.compactLayout ? 0 : 340
                SplitView.minimumHeight: root.compactLayout ? 220 : 0
                title: root.formMode === 1 ? "New SVI"
                       : root.hasDetail ? "Vlan" + String(root.activeData().vlan_id || "")
                       : "SVI details"
                subtitle: root.formMode === 1 ? "Create a routed VLAN interface"
                          : root.hasDetail ? String(root.activeData().vlan_name || "Layer 3 gateway")
                          : ""
                hasContent: root.hasDetail
                editing: root.formMode !== 0
                emptyTitle: "No SVI selected"
                emptyDescription: "Select a row to inspect it, or choose Add to create an SVI."

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "VLAN interface"
                    helpText: "VLAN ID selects the existing VLAN whose switched virtual interface is created. Valid normal-range IDs are 1-4094; the corresponding VLAN must exist before the SVI can forward traffic."
                    description: "The VLAN must already exist in the local VLAN database."

                    SwitchPropertyRow { visible: root.formMode === 0; label: "Interface"; value: "Vlan" + String(root.activeData().vlan_id || "—"); emphasize: true }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "VLAN name"; value: String(root.activeData().vlan_name || "—") }
                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "VLAN ID"
                        readOnly: root.formMode === 2
                        placeholderText: "1–4094"
                        text: String(root.activeData().vlan_id || "")
                        onTextEdited: value => root.updateField("vlan_id", value)
                    }
                }

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "IPv4 gateway"
                    helpText: "IP address is the Layer-3 address clients may use as their gateway. Subnet mask accepts dotted decimal or CIDR such as /24. Supply both fields together and avoid address overlap with another routed interface."
                    description: "Address and subnet mask must be supplied together."

                    SwitchPropertyRow { visible: root.formMode === 0; label: "IP address"; value: String(root.activeData().ip_address || "Not assigned"); monospaced: true }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Subnet mask"; value: String(root.activeData().subnet_mask || "—"); monospaced: true }
                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "IP address"
                        placeholderText: "192.168.10.1"
                        text: String(root.activeData().ip_address || "")
                        onTextEdited: value => root.updateField("ip_address", value)
                    }
                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Subnet mask"
                        placeholderText: "255.255.255.0 or /24"
                        text: String(root.activeData().subnet_mask || "")
                        onTextEdited: value => root.updateField("subnet_mask", value)
                    }
                }

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Administrative state"
                    helpText: "Administratively enabled emits no shutdown. The SVI becomes operational only when its VLAN exists and at least one associated Layer-2 port is active, depending on platform behavior."
                    showDivider: false

                    SwitchPropertyRow {
                        visible: root.formMode === 0
                        label: "State"
                        value: root.activeData().shutdown ? "Shutdown" : "Up"
                        valueColor: root.activeData().shutdown ? Theme.alertWarning : Theme.alertSuccess
                    }
                    StandardToggleButton {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        text: "Administratively enabled"
                        description: "Turn off to retain the SVI in a shutdown state."
                        checked: !Boolean(root.activeData().shutdown || false)
                        onToggled: root.updateField("shutdown", !checked)
                    }
                }

                App.CrudFormActions {
                    objectName: "sviEditorActions"
                    Layout.fillWidth: true
                    visible: root.formMode !== 0
                    formMode: root.formMode
                    dirty: root.dirty
                    valid: String(root.draftData.vlan_id || "").trim() !== ""
                    saving: root.saving
                    allowCreate: false
                    allowEdit: false
                    allowRefresh: false
                    onSaveRequested: root.save()
                    onCancelRequested: root.cancel()
                }
            }
        }
    }
}
