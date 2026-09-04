pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import UI as App

Item {
    id: root

    required property string host
    property int formMode: 0
    property int selectedIndex: -1
    property bool dirty: false
    property bool saving: false
    property bool deletePending: false
    property int pendingDeleteId: 0
    property int pendingDeleteVlanId: 0
    property var draftData: ({})
    property var allRows: []
    property int dataRevision: 0
    property string filterText: ""
    property string message: ""
    property bool messageError: false

    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property bool hasPendingDeletes: deletePending
    readonly property bool hasDetail: formMode !== 0 || rowAt(selectedIndex) !== null
    readonly property bool selectedVlanCanDelete: {
        const row = rowAt(selectedIndex)
        return row !== null && Number(row.vlan_id || 0) !== 1
    }
    readonly property var summaryMetrics: {
        const revision = root.dataRevision
        let active = 0
        let assigned = 0
        for (let i = 0; i < root.allRows.length; i++) {
            if (root.allRows[i].state === "active") active += 1
            assigned += Number(root.allRows[i].access_port_count || 0)
        }
        return [
            { label: "VLANs", value: root.allRows.length, tone: "neutral" },
            { label: "Active", value: active, tone: "success" },
            { label: "Suspended", value: root.allRows.length - active, tone: "warning" },
            { label: "Access assignments", value: assigned, tone: "accent" }
        ]
    }

    ListModel { id: vlanModel }

    function clone(value) { return JSON.parse(JSON.stringify(value || {})) }
    function normalizedRow(row) {
        const source = row || ({})
        return {
            id: Number(source.id || 0),
            vlan_id: Number(source.vlan_id || 0),
            vlan_name: source.vlan_name === undefined || source.vlan_name === null
                       ? "" : String(source.vlan_name),
            state: source.state === undefined || source.state === null
                   ? "active" : String(source.state),
            success: source.success === undefined || source.success === null
                     ? "pending_apply" : String(source.success),
            access_port_count: Number(source.access_port_count || 0)
        }
    }
    function rowAt(index) {
        return index >= 0 && index < vlanModel.count ? vlanModel.get(index) : null
    }
    function activeData() { return formMode === 0 ? (rowAt(selectedIndex) || ({})) : draftData }

    function rebuildVisibleRows() {
        const current = rowAt(selectedIndex)
        const selectedId = current ? Number(current.id || 0) : Number(draftData.id || 0)
        const query = String(filterText || "").trim().toLocaleLowerCase()
        vlanModel.clear()
        let restoredIndex = -1
        for (let i = 0; i < allRows.length; i++) {
            const row = normalizedRow(allRows[i])
            const searchable = [row.vlan_id, row.vlan_name, row.state].join(" ").toLocaleLowerCase()
            if (query !== "" && searchable.indexOf(query) === -1) continue
            vlanModel.append(row)
            if (Number(row.id || 0) === selectedId)
                restoredIndex = vlanModel.count - 1
        }
        selectedIndex = restoredIndex >= 0 ? restoredIndex : vlanModel.count > 0 ? 0 : -1
        if (formMode === 0)
            draftData = rowAt(selectedIndex) ? clone(rowAt(selectedIndex)) : ({})
        dataRevision += 1
    }

    function load(reason) {
        const rows = dbManager.getSwitchVlans(host)
        const values = []
        for (let i = 0; i < rows.length; i++) values.push(rows[i])
        allRows = values
        formMode = 0
        dirty = false
        deletePending = false
        pendingDeleteId = 0
        pendingDeleteVlanId = 0
        rebuildVisibleRows()
        if (reason === "manual") message = "VLAN inventory reloaded."
    }

    function beginCreate() {
        deletePending = false
        draftData = { id: 0, vlan_id: "", vlan_name: "", state: "active", access_port_count: 0 }
        formMode = 1
        dirty = false
    }

    function beginEdit() {
        const row = rowAt(selectedIndex)
        if (!row) return
        deletePending = false
        draftData = clone(row)
        formMode = 2
        dirty = false
    }

    function updateDraft(name, value) {
        draftData[name] = value
        dirty = true
        draftDataChanged()
    }

    function save() {
        saving = true
        const result = dbManager.saveSwitchVlan(host, draftData)
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }

    function cancel() {
        formMode = 0
        dirty = false
        draftData = rowAt(selectedIndex) ? clone(rowAt(selectedIndex)) : ({})
    }

    function stageDelete() {
        const row = rowAt(selectedIndex)
        if (formMode !== 0 || !row || !selectedVlanCanDelete || saving) return
        pendingDeleteId = Number(row.id || 0)
        pendingDeleteVlanId = Number(row.vlan_id || 0)
        if (pendingDeleteId <= 0) return
        deletePending = true
        message = "VLAN " + String(pendingDeleteVlanId)
                + " is marked for deletion. Select Save to commit or Cancel to discard."
        messageError = false
    }

    function savePendingDelete() {
        if (!deletePending || pendingDeleteId <= 0 || saving) return
        saving = true
        const result = dbManager.deleteSwitchVlan(host, pendingDeleteId)
        saving = false
        message = String(result && result.message
                         ? result.message : "Could not delete the selected VLAN.")
        messageError = !result || result.ok !== true
        if (result && result.ok === true) load()
    }

    function cancelDelete() {
        if (!deletePending) return
        deletePending = false
        pendingDeleteId = 0
        pendingDeleteVlanId = 0
        message = "VLAN deletion cancelled. No changes were saved."
        messageError = false
    }

    Component.onCompleted: load()
    onHostChanged: load()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: "VLAN Database"
            subtitle: "Create a clear Layer 2 segmentation plan and review access-port usage."

            ViewPushButton {
                controllerName: "switching"
                hostIp: root.host
                moduleName: "vlan"
                refreshKey: root.dataRevision
                ownerForm: root
                onPushCompleted: function(ok, detail) {
                    root.message = detail
                    root.messageError = !ok
                    if (ok) root.load()
                }
            }

            StandardButton {
                objectName: "vlanAddButton"
                text: "Add"
                visible: root.formMode === 0
                enabled: !root.saving && !root.deletePending
                onClicked: root.beginCreate()
            }

            StandardButton {
                objectName: "vlanCancelDeleteButton"
                text: "Cancel"
                icon.source: AppAssets.actionClear
                type: "Text"
                visible: root.formMode === 0 && root.deletePending
                enabled: !root.saving
                onClicked: root.cancelDelete()
            }

            StandardButton {
                objectName: "vlanDeleteButton"
                text: "Delete VLAN"
                icon.source: AppAssets.actionDelete
                type: "Secondary"
                visible: root.formMode === 0
                enabled: root.selectedVlanCanDelete && !root.deletePending && !root.saving
                tooltip: root.selectedIndex >= 0 && !root.selectedVlanCanDelete
                         ? "VLAN 1 is the default VLAN and cannot be deleted."
                         : "Delete the selected VLAN"
                onClicked: root.stageDelete()
            }

            StandardButton {
                objectName: "vlanSaveDeleteButton"
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
            id: vlanSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { orientation: vlanSplit.orientation }

            Item {
                SplitView.fillWidth: !root.compactLayout
                SplitView.fillHeight: root.compactLayout
                SplitView.minimumWidth: root.compactLayout ? 0 : 430
                SplitView.minimumHeight: root.compactLayout ? 220 : 0
                SplitView.preferredHeight: root.compactLayout
                                           ? Math.max(240, vlanSplit.height * 0.52)
                                           : vlanSplit.height

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.spacing8

                    SwitchTableToolbar {
                        Layout.fillWidth: true
                        title: "VLAN inventory"
                        totalCount: root.allRows.length
                        visibleCount: vlanModel.count
                        searchText: root.filterText
                        searchPlaceholder: "Filter VLANs..."
                        onSearchEdited: value => {
                            root.filterText = value
                            root.rebuildVisibleRows()
                        }
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        count: vlanModel.count
                        bodyMargins: 0
                        emptyTitle: root.filterText === "" ? "No VLANs" : "No matching VLANs"
                        emptyDescription: root.filterText === ""
                                          ? "Use Add to create the first VLAN desired-state entry."
                                          : "Try a different VLAN ID, name, or state."
                        headerComponent: Component {
                            DataTableHeader {
                                RowLayout {
                                    anchors.fill: parent
                                    spacing: Theme.spacing8
                                    DataTableCell { Layout.preferredWidth: 80; header: true; text: "VLAN" }
                                    DataTableCell { Layout.fillWidth: true; header: true; text: "Name" }
                                    DataTableCell { Layout.preferredWidth: 110; header: true; text: "Access Ports"; horizontalAlignment: Text.AlignHCenter }
                                    DataTableCell { Layout.preferredWidth: 88; header: true; text: "State" }
                                }
                            }
                        }

                        ListView {
                            anchors.fill: parent
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            model: vlanModel
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
                                    DataTableCell { Layout.preferredWidth: 80; primary: true; text: String(row.model.vlan_id) }
                                    DataTableCell { Layout.fillWidth: true; primary: true; text: row.model.vlan_name || "—" }
                                    DataTableCell { Layout.preferredWidth: 110; text: String(row.model.access_port_count || 0); horizontalAlignment: Text.AlignHCenter }
                                    App.StatusBadge { Layout.preferredWidth: 88; value: row.model.state || "active" }
                                }
                                TapHandler {
                                    enabled: root.formMode === 0 && !root.deletePending
                                    onTapped: {
                                        root.selectedIndex = row.index
                                        root.draftData = root.clone(root.rowAt(row.index))
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
                SplitView.preferredWidth: root.compactLayout ? vlanSplit.width
                                                             : Math.min(420, root.width * 0.38)
                SplitView.minimumWidth: root.compactLayout ? 0 : 340
                SplitView.minimumHeight: root.compactLayout ? 220 : 0
                title: root.formMode === 1 ? "New VLAN"
                       : root.hasDetail ? "VLAN " + String(root.activeData().vlan_id || "")
                       : "VLAN details"
                subtitle: root.formMode === 1 ? "Create local desired state"
                          : root.hasDetail ? String(root.activeData().vlan_name || "Unnamed VLAN")
                          : ""
                hasContent: root.hasDetail
                editing: root.formMode !== 0
                emptyTitle: "No VLAN selected"
                emptyDescription: "Select a row to inspect it, or choose Add to create a VLAN."

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Identity"
                    helpText: "VLAN ID is the unique numeric VLAN identifier, normally 1-4094. Name is an optional human-readable label such as Users, Voice, or Management."
                    description: "VLAN identifiers must be unique on the selected switch."

                    SwitchPropertyRow { visible: root.formMode === 0; label: "VLAN ID"; value: String(root.activeData().vlan_id || "—"); emphasize: true }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Name"; value: String(root.activeData().vlan_name || "—") }
                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "VLAN ID"
                        readOnly: root.formMode === 2
                        placeholderText: "1–4094"
                        text: String(root.activeData().vlan_id || "")
                        onTextEdited: value => root.updateDraft("vlan_id", value)
                    }
                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Name"
                        placeholderText: "Users, Voice, Management..."
                        text: String(root.activeData().vlan_name || "")
                        onTextEdited: value => root.updateDraft("vlan_name", value)
                    }
                }

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Lifecycle"
                    helpText: "Active permits the VLAN to forward when ports are available. Suspend retains the VLAN definition but marks it inactive. Push status reports whether the local change still needs deployment."
                    description: "Suspending a VLAN preserves its definition while marking it inactive."
                    showDivider: false

                    SwitchPropertyRow { visible: root.formMode === 0; label: "State"; value: String(root.activeData().state || "active"); valueColor: root.activeData().state === "active" ? Theme.alertSuccess : Theme.alertWarning }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Push status"; value: String(root.activeData().success || "pending_apply").replace(/_/g, " ") }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Access ports"; value: String(root.activeData().access_port_count || 0) }
                    StandardComboBox {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "State"
                        model: ["active", "suspend"]
                        currentIndex: String(root.activeData().state || "active") === "suspend" ? 1 : 0
                        onActivated: index => root.updateDraft("state", model[index])
                    }
                }

                App.CrudFormActions {
                    objectName: "vlanEditorActions"
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
