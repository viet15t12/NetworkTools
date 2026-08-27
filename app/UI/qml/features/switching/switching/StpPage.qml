pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import UI as App

Item {
    id: root
    objectName: "loadedStpPage"

    required property string host
    property int formMode: 0
    property int selectedIndex: -1
    property bool dirty: false
    property bool saving: false
    property var draftData: ({})
    property var allRows: []
    property var vlanOptions: []
    property string filterText: ""
    property string message: ""
    property bool messageError: false
    property int dataRevision: 0

    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property var priorityValues: [
        0, 4096, 8192, 12288, 16384, 20480, 24576, 28672,
        32768, 36864, 40960, 45056, 49152, 53248, 57344, 61440
    ]
    readonly property var summaryMetrics: {
        const revision = root.dataRevision
        let primary = 0
        let secondary = 0
        for (let i = 0; i < root.allRows.length; i++) {
            if (root.allRows[i].root_role === "primary") primary += 1
            if (root.allRows[i].root_role === "secondary") secondary += 1
        }
        return [
            { label: "Protected VLANs", value: root.allRows.length, tone: "neutral" },
            { label: "Global mode", value: root.globalModeLabel(), tone: "accent" },
            { label: "Root primary", value: primary, tone: "success" },
            { label: "Root secondary", value: secondary, tone: "warning" }
        ]
    }

    ListModel { id: stpModel }

    function clone(value) { return JSON.parse(JSON.stringify(value || {})) }
    function normalizedRow(row) {
        const source = row || ({})
        return {
            id: Number(source.id || 0),
            vlan_id: Number(source.vlan_id || 0),
            vlan_name: source.vlan_name === undefined || source.vlan_name === null
                       ? "" : String(source.vlan_name),
            stp_mode: source.stp_mode === undefined || source.stp_mode === null
                      ? "rapid-pvst" : String(source.stp_mode),
            priority: Number(source.priority === undefined ? 32768 : source.priority),
            root_role: source.root_role === undefined || source.root_role === null
                       ? "none" : String(source.root_role),
            success: source.success === undefined || source.success === null
                     ? "pending_apply" : String(source.success)
        }
    }
    function rowAt(index) {
        return index >= 0 && index < stpModel.count ? stpModel.get(index) : null
    }
    function activeData() { return formMode === 0 ? (rowAt(selectedIndex) || ({})) : draftData }
    function comboIndex(model, value) {
        const index = model.indexOf(value)
        return index < 0 ? 0 : index
    }
    function globalModeLabel() {
        if (allRows.length === 0) return "Not set"
        return String(allRows[0].stp_mode || "rapid-pvst")
    }
    function policyLabel(row) {
        return row.root_role && row.root_role !== "none"
             ? "Root " + row.root_role : "Priority " + row.priority
    }
    function vlanLabels() {
        const labels = []
        for (let i = 0; i < vlanOptions.length; i++)
            labels.push("VLAN " + vlanOptions[i].vlan_id
                        + (vlanOptions[i].vlan_name ? " · " + vlanOptions[i].vlan_name : ""))
        return labels
    }
    function vlanValues() {
        const values = []
        for (let i = 0; i < vlanOptions.length; i++) values.push(vlanOptions[i].vlan_id)
        return values
    }
    function rebuildVisibleRows() {
        const selected = rowAt(selectedIndex)
        const selectedId = selected ? Number(selected.id || 0) : Number(draftData.id || 0)
        const query = filterText.trim().toLocaleLowerCase()
        stpModel.clear()
        let restored = -1
        for (let i = 0; i < allRows.length; i++) {
            const row = normalizedRow(allRows[i])
            const text = [row.vlan_id, row.vlan_name, row.stp_mode,
                          row.root_role, row.priority].join(" ").toLocaleLowerCase()
            if (query !== "" && text.indexOf(query) === -1) continue
            stpModel.append(row)
            if (row.id === selectedId) restored = stpModel.count - 1
        }
        selectedIndex = restored >= 0 ? restored : stpModel.count > 0 ? 0 : -1
        if (formMode === 0) draftData = rowAt(selectedIndex) ? clone(rowAt(selectedIndex)) : ({})
        dataRevision += 1
    }
    function load(reason) {
        const rows = dbManager.getSwitchStpConfigs(host)
        const vlans = dbManager.getSwitchVlans(host)
        allRows = []
        vlanOptions = []
        for (let i = 0; i < rows.length; i++) allRows.push(rows[i])
        for (let i = 0; i < vlans.length; i++) vlanOptions.push(vlans[i])
        formMode = 0
        dirty = false
        rebuildVisibleRows()
        if (reason === "manual") message = "STP policies reloaded."
    }
    function beginCreate() {
        draftData = {
            id: 0,
            vlan_id: vlanOptions.length > 0 ? vlanOptions[0].vlan_id : 0,
            vlan_name: "",
            stp_mode: allRows.length > 0 ? allRows[0].stp_mode : "rapid-pvst",
            priority: 32768,
            root_role: "none"
        }
        formMode = 1
        dirty = false
    }
    function beginEdit() {
        if (!rowAt(selectedIndex)) return
        draftData = clone(rowAt(selectedIndex))
        formMode = 2
        dirty = false
    }
    function updateField(name, value) {
        draftData[name] = value
        dirty = true
        draftDataChanged()
    }
    function cancel() {
        formMode = 0
        dirty = false
        draftData = rowAt(selectedIndex) ? clone(rowAt(selectedIndex)) : ({})
    }
    function save() {
        saving = true
        const result = dbManager.saveSwitchStpConfig(host, draftData)
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }
    function deleteSelected() {
        const row = rowAt(selectedIndex)
        if (!row || Number(row.id || 0) <= 0 || saving) return
        saving = true
        const result = dbManager.deleteSwitchStpConfig(host, Number(row.id))
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }

    Component.onCompleted: load()
    onHostChanged: load()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: "Spanning Tree"
            subtitle: "Control the global STP mode and per-VLAN root election policy."

            ViewPushButton {
                controllerName: "switching"
                hostIp: root.host
                moduleName: "stp"
                refreshKey: root.dataRevision
                ownerForm: root
                onPushCompleted: function(ok, detail) {
                    root.message = detail
                    root.messageError = !ok
                    if (ok) root.load()
                }
            }
            App.CrudFormActions {
                formMode: root.formMode
                hasSelection: root.selectedIndex >= 0
                dirty: root.dirty
                valid: Number(root.draftData.vlan_id || 0) > 0
                saving: root.saving
                allowCreate: root.vlanOptions.length > 0
                allowDelete: root.selectedIndex >= 0
                allowEditorActions: false
                onAddRequested: root.beginCreate()
                onEditRequested: root.beginEdit()
                onDeleteRequested: root.deleteSelected()
                onRefreshRequested: root.load("manual")
                onSaveRequested: root.save()
                onCancelRequested: root.cancel()
            }
        }

        InlineMessage {
            Layout.fillWidth: true
            visible: root.message !== ""
            message: root.message
            severity: root.messageError ? "error" : "success"
        }

        SwitchSummaryBar { Layout.fillWidth: true; metrics: root.summaryMetrics }

        SplitView {
            id: stpSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { orientation: stpSplit.orientation }

            Item {
                SplitView.fillWidth: !root.compactLayout
                SplitView.fillHeight: root.compactLayout
                SplitView.minimumWidth: root.compactLayout ? 0 : 500
                SplitView.minimumHeight: root.compactLayout ? 220 : 0
                SplitView.preferredHeight: root.compactLayout ? stpSplit.height * 0.5 : stpSplit.height

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.spacing8
                    SwitchTableToolbar {
                        Layout.fillWidth: true
                        title: "VLAN root policies"
                        totalCount: root.allRows.length
                        visibleCount: stpModel.count
                        searchText: root.filterText
                        searchPlaceholder: "Filter VLAN, role, mode..."
                        onSearchEdited: value => {
                            root.filterText = value
                            root.rebuildVisibleRows()
                        }
                    }
                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        count: stpModel.count
                        bodyMargins: 0
                        emptyTitle: root.filterText === "" ? "No STP policies" : "No matching policies"
                        emptyDescription: root.filterText === ""
                                          ? "Use Add to define root election for a VLAN."
                                          : "Clear the filter or try another VLAN."
                        headerComponent: Component {
                            DataTableHeader {
                                RowLayout {
                                    anchors.fill: parent
                                    spacing: Theme.spacing8
                                    DataTableCell { Layout.preferredWidth: 90; header: true; text: "VLAN" }
                                    DataTableCell { Layout.preferredWidth: 140; header: true; text: "Mode" }
                                    DataTableCell { Layout.fillWidth: true; header: true; text: "Election Policy" }
                                }
                            }
                        }
                        ListView {
                            anchors.fill: parent
                            clip: true
                            model: stpModel
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: DataTableRow {
                                id: row
                                required property int index
                                required property var model
                                width: ListView.view.width
                                height: Theme.tableRowHeight
                                rowIndex: index
                                selected: root.selectedIndex === index
                                interactive: root.formMode === 0
                                RowLayout {
                                    anchors.fill: parent
                                    spacing: Theme.spacing8
                                    DataTableCell { Layout.preferredWidth: 90; primary: true; text: String(row.model.vlan_id) }
                                    DataTableCell { Layout.preferredWidth: 140; text: String(row.model.stp_mode) }
                                    DataTableCell { Layout.fillWidth: true; text: root.policyLabel(row.model) }
                                }
                                TapHandler {
                                    enabled: root.formMode === 0
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
                SplitView.preferredWidth: root.compactLayout ? stpSplit.width
                                                             : Math.min(430, root.width * 0.4)
                SplitView.minimumWidth: root.compactLayout ? 0 : 350
                SplitView.minimumHeight: root.compactLayout ? 260 : 0
                title: root.formMode === 1 ? "New STP Policy"
                       : root.activeData().vlan_id ? "VLAN " + root.activeData().vlan_id
                                                   : "STP details"
                subtitle: root.activeData().vlan_name || "Root election policy"
                hasContent: root.formMode !== 0 || root.selectedIndex >= 0
                editing: root.formMode !== 0
                emptyTitle: "No STP policy selected"
                emptyDescription: "Select a VLAN policy, or choose Add to create one."

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Global protocol"
                    helpText: "PVST runs a spanning-tree instance per VLAN. Rapid-PVST uses rapid convergence and is generally preferred when all participating switches support it. The mode is global and must be compatible across the Layer-2 domain."
                    description: "Cisco IOS uses one global STP mode; changing it updates every saved VLAN policy."
                    SwitchPropertyRow { visible: root.formMode === 0; label: "STP mode"; value: root.activeData().stp_mode || "—"; emphasize: true }
                    StandardComboBox {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "STP mode"
                        model: ["pvst", "rapid-pvst"]
                        currentIndex: root.comboIndex(model, String(root.activeData().stp_mode || "rapid-pvst"))
                        onActivated: index => root.updateField("stp_mode", model[index])
                    }
                }

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Root election"
                    helpText: "VLAN selects the STP instance. Root role Primary/Secondary lets IOS choose an appropriate priority. Explicit Priority uses values in increments of 4096; lower values win the root election. Avoid conflicting root policies on multiple switches."
                    description: "Use a root role for automatic priority selection, or choose an explicit priority."
                    showDivider: false

                    SwitchPropertyRow { visible: root.formMode === 0; label: "VLAN"; value: String(root.activeData().vlan_id || "—") }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Root role"; value: String(root.activeData().root_role || "none") }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Priority"; value: String(root.activeData().priority === undefined ? "—" : root.activeData().priority) }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Push status"; value: String(root.activeData().success || "pending_apply").replace(/_/g, " ") }

                    StandardComboBox {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "VLAN"
                        model: root.vlanLabels()
                        valueModel: root.vlanValues()
                        enabled: root.formMode === 1
                        currentIndex: root.comboIndex(valueModel, Number(root.activeData().vlan_id || 0))
                        onActivated: index => root.updateField("vlan_id", Number(valueModel[index]))
                    }
                    StandardComboBox {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Root role"
                        model: ["none", "primary", "secondary"]
                        currentIndex: root.comboIndex(model, String(root.activeData().root_role || "none"))
                        onActivated: index => root.updateField("root_role", model[index])
                    }
                    StandardComboBox {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0 && root.activeData().root_role === "none"
                        labelText: "Bridge priority"
                        model: root.priorityValues
                        currentIndex: root.comboIndex(model, Number(root.activeData().priority || 32768))
                        onActivated: index => root.updateField("priority", Number(model[index]))
                    }
                }

                App.CrudFormActions {
                    objectName: "stpEditorActions"
                    Layout.fillWidth: true
                    visible: root.formMode !== 0
                    formMode: root.formMode
                    dirty: root.dirty
                    valid: Number(root.draftData.vlan_id || 0) > 0
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
