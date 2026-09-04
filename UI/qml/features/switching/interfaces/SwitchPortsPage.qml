pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import UI as App

Item {
    id: root

    required property string host
    property bool allowRouted: false
    property bool routedOnly: false
    property string viewMode: "interfaces"
    property int formMode: 0
    property int selectedIndex: -1
    property bool dirty: false
    property bool saving: false
    property var draftData: ({})
    property var allRows: []
    property var vlanOptions: []
    property int dataRevision: 0
    property string filterText: ""
    property string activePortTab: "Port Status"
    property string message: ""
    property bool messageError: false

    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property bool policyView: viewMode === "portSecurity"
    readonly property bool portTabsVisible: viewMode === "interfaces" && !routedOnly
    readonly property bool statusTab: portTabsVisible && activePortTab === "Port Status"
    readonly property bool advancedModeTab: portTabsVisible
                                                    && activePortTab !== "Port Status"
    readonly property string modeFilter: activePortTab === "Access" ? "access"
                                               : activePortTab === "Trunk" ? "trunk" : ""
    readonly property int currentTabTotal: {
        const revision = root.dataRevision
        if (root.modeFilter === "") return root.allRows.length
        return root.countWhere("mode", root.modeFilter)
    }
    readonly property var summaryMetrics: {
        const revision = root.dataRevision
        return root.buildSummaryMetrics()
    }
    readonly property string pageTitle: {
        if (root.routedOnly) return "Routed Ports"
        if (root.viewMode === "portSecurity") return "Port Security"
        return "Switch Ports"
    }
    readonly property string pageSubtitle: {
        if (root.routedOnly) return "Layer 3 port inventory and administrative settings."
        if (root.viewMode === "portSecurity")
            return "Apply MAC-learning limits to existing access ports."
        if (root.activePortTab === "Access")
            return "Manage untagged access ports and their data or voice VLAN membership."
        if (root.activePortTab === "Trunk")
            return "Manage tagged trunk ports, native VLANs and allowed VLAN lists."
        return "View every switch port and move ports between Access and Trunk modes."
    }

    ListModel { id: interfaceModel }

    function clone(value) { return JSON.parse(JSON.stringify(value || {})) }

    function selectedRow() {
        return selectedIndex >= 0 && selectedIndex < interfaceModel.count
             ? interfaceModel.get(selectedIndex) : null
    }

    function defaultDraft() {
        return {
            id: 0,
            if_name: "",
            description: "",
            mode: routedOnly ? "routed" : "access",
            admin_status: "up",
            oper_status: "unknown",
            speed: "auto",
            duplex: "auto",
            access_vlan: 1,
            voice_vlan: "",
            allowed_vlans: "all",
            native_vlan: 1,
            encapsulation: "dot1q",
            pruning_vlans: "none",
            portfast: "disabled",
            bpduguard: "disabled",
            bpdufilter: "disabled",
            root_guard: "disabled",
            loop_guard: "disabled",
            port_security_enabled: false,
            max_mac: 1,
            violation: "shutdown",
            sticky: false,
            aging_type: "absolute",
            aging_time: 0,
            success: "pending_apply",
            port_security_success: "skipped"
        }
    }

    function normalizedRow(row) {
        const source = row || ({})
        const defaults = defaultDraft()
        const normalized = ({})
        const keys = Object.keys(defaults)
        for (let i = 0; i < keys.length; i++) {
            const key = keys[i]
            const value = source[key]
            normalized[key] = value === undefined || value === null ? defaults[key] : value
        }
        normalized.id = Number(normalized.id || 0)
        normalized.access_vlan = Number(normalized.access_vlan || 1)
        normalized.voice_vlan = normalized.voice_vlan === "" ? "" : String(normalized.voice_vlan)
        normalized.native_vlan = Number(normalized.native_vlan || 1)
        normalized.port_security_enabled = Boolean(normalized.port_security_enabled)
        normalized.max_mac = Number(normalized.max_mac || 1)
        normalized.sticky = Boolean(normalized.sticky)
        normalized.aging_time = Number(normalized.aging_time || 0)
        normalized.updated_at = source.updated_at === undefined || source.updated_at === null
                                ? "" : String(source.updated_at)
        return normalized
    }

    function rowMatches(row, query) {
        if (query === "") return true
        const haystack = [
            row.if_name, row.description, row.mode, row.oper_status,
            row.access_vlan, row.voice_vlan, row.allowed_vlans, row.native_vlan,
            row.violation
        ].join(" ").toLocaleLowerCase()
        return haystack.indexOf(query) !== -1
    }

    function rebuildVisibleRows() {
        const selected = selectedRow()
        const selectedId = selected ? Number(selected.id || 0) : Number(draftData.id || 0)
        const query = String(filterText || "").trim().toLocaleLowerCase()
        interfaceModel.clear()
        let restoredIndex = -1
        for (let i = 0; i < allRows.length; i++) {
            const row = normalizedRow(allRows[i])
            if (modeFilter !== "" && String(row.mode) !== modeFilter) continue
            if (!rowMatches(row, query)) continue
            interfaceModel.append(row)
            if (Number(row.id || 0) === selectedId)
                restoredIndex = interfaceModel.count - 1
        }
        selectedIndex = restoredIndex >= 0 ? restoredIndex
                      : interfaceModel.count > 0 ? 0 : -1
        if (formMode === 0)
            draftData = selectedRow() ? clone(selectedRow()) : ({})
        dataRevision += 1
    }

    function load(reason) {
        const rows = dbManager.getSwitchInterfaces(host)
        const vlans = dbManager.getSwitchVlans(host)
        const accepted = []
        const availableVlans = []
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            if (routedOnly ? row.mode === "routed"
                           : (policyView ? row.mode !== "routed" : row.mode !== "routed"))
                accepted.push(row)
        }
        for (let i = 0; i < vlans.length; i++) {
            availableVlans.push({
                vlan_id: Number(vlans[i].vlan_id || 0),
                vlan_name: String(vlans[i].vlan_name || ""),
                state: String(vlans[i].state || "active")
            })
        }
        allRows = accepted
        vlanOptions = availableVlans
        formMode = 0
        dirty = false
        rebuildVisibleRows()
        if (reason === "manual")
            message = pageTitle + " reloaded."
    }

    function beginCreate() {
        if (policyView || statusTab) return
        draftData = defaultDraft()
        if (activePortTab === "Trunk")
            draftData.mode = "trunk"
        else if (activePortTab === "Access")
            draftData.mode = "access"
        formMode = 1
        dirty = false
    }

    function activatePortTab(tabName) {
        if (!portTabsVisible || activePortTab === tabName) return
        if (formMode !== 0 && dirty) {
            message = "Save or cancel the current port changes before switching tabs."
            messageError = true
            return
        }
        formMode = 0
        dirty = false
        activePortTab = tabName
        rebuildVisibleRows()
    }

    function beginEdit() {
        if (selectedRow()) {
            draftData = clone(selectedRow())
            formMode = 2
            dirty = false
        }
    }

    function updateField(name, value) {
        // Replace the draft object so bindings in InterfaceInspector are
        // reevaluated immediately when Mode changes between access and trunk.
        const next = clone(draftData)
        next[name] = value
        draftData = next
        dirty = true
    }

    function cancel() {
        formMode = 0
        dirty = false
        draftData = selectedRow() ? clone(selectedRow()) : ({})
    }

    function save() {
        saving = true
        const result = dbManager.saveSwitchInterface(host, draftData)
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok)
            load()
    }

    function countWhere(field, expected) {
        let count = 0
        for (let i = 0; i < allRows.length; i++) {
            if (String(allRows[i][field]) === String(expected)) count += 1
        }
        return count
    }

    function countTruthy(field) {
        let count = 0
        for (let i = 0; i < allRows.length; i++) {
            if (Boolean(allRows[i][field])) count += 1
        }
        return count
    }

    function buildSummaryMetrics() {
        const total = allRows.length
        if (viewMode === "portSecurity") {
            return [
                { label: "Eligible ports", value: total, tone: "neutral" },
                { label: "Protected", value: countTruthy("port_security_enabled"), tone: "success" },
                { label: "Sticky learning", value: countTruthy("sticky"), tone: "accent" },
                { label: "Shutdown policy", value: countWhere("violation", "shutdown"), tone: "warning" }
            ]
        }
        return [
            { label: routedOnly ? "Routed ports" : "Switch ports", value: total, tone: "neutral" },
            { label: "Links up", value: countWhere("oper_status", "up"), tone: "success" },
            { label: "Access", value: countWhere("mode", "access"), tone: "accent" },
            { label: routedOnly ? "Admin up" : "Trunks",
              value: countWhere(routedOnly ? "admin_status" : "mode", routedOnly ? "up" : "trunk"),
              tone: "neutral" }
        ]
    }

    Component.onCompleted: load()
    onHostChanged: load()
    onRoutedOnlyChanged: load()
    onViewModeChanged: load()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: root.pageTitle
            subtitle: root.pageSubtitle

            ViewPushButton {
                visible: !root.routedOnly
                controllerName: "switching"
                hostIp: root.host
                moduleName: root.policyView ? "port_security" : "interfaces"
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
                valid: String(root.draftData.if_name || "").trim() !== ""
                saving: root.saving
                allowCreate: !root.policyView && !root.statusTab
                allowEditorActions: false
                onAddRequested: root.beginCreate()
                onEditRequested: root.beginEdit()
                onRefreshRequested: root.load("manual")
                onSaveRequested: root.save()
                onCancelRequested: root.cancel()
            }
        }

        SubBar {
            objectName: "switchPortModeTabs"
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? Theme.subBarHeight : 0
            visible: root.portTabsVisible
            tabs: ["Port Status", "Access", "Trunk"]
            activeTab: root.activePortTab
            onTabClicked: tabName => root.activatePortTab(tabName)
        }

        InlineMessage {
            Layout.fillWidth: true
            message: root.message
            severity: root.messageError ? "error" : "success"
        }

        SwitchSummaryBar {
            Layout.fillWidth: true
            metrics: root.summaryMetrics
        }

        SplitView {
            id: portSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { orientation: portSplit.orientation }

            SwitchPortTable {
                SplitView.fillWidth: !root.compactLayout
                SplitView.fillHeight: root.compactLayout
                SplitView.preferredHeight: root.compactLayout
                                           ? Math.max(240, portSplit.height * 0.48)
                                           : portSplit.height
                SplitView.minimumHeight: root.compactLayout ? 220 : 0
                SplitView.minimumWidth: root.compactLayout ? 0 : 480
                sourceModel: interfaceModel
                totalCount: root.currentTabTotal
                selectedIndex: root.selectedIndex
                selectionEnabled: root.formMode === 0
                viewMode: root.viewMode
                routedOnly: root.routedOnly
                filterText: root.filterText
                emptyTitle: root.policyView ? "No eligible switch ports"
                                           : root.routedOnly ? "No routed ports"
                                           : root.activePortTab === "Access" ? "No access ports"
                                           : root.activePortTab === "Trunk" ? "No trunk ports"
                                           : "No switch ports"
                emptyDescription: root.policyView
                                  ? "Create an access port in Interfaces before applying a policy."
                                  : root.activePortTab === "Access"
                                    ? "Use Add to create an access port or convert an existing trunk."
                                  : root.activePortTab === "Trunk"
                                    ? "Use Add to create a trunk or convert an existing access port."
                                  : "Use Add to create the first desired-state entry."
                onSearchEdited: value => {
                    root.filterText = value
                    root.rebuildVisibleRows()
                }
                onRowSelected: index => {
                    root.selectedIndex = index
                    root.draftData = root.clone(root.selectedRow())
                }
            }

            InterfaceInspector {
                objectName: "switchPortInspector"
                SplitView.fillWidth: root.compactLayout
                SplitView.fillHeight: !root.compactLayout
                SplitView.preferredWidth: root.compactLayout
                                          ? portSplit.width
                                          : Math.min(440, root.width * 0.4)
                SplitView.minimumWidth: root.compactLayout ? 0 : 350
                SplitView.preferredHeight: root.compactLayout
                                           ? Math.max(280, portSplit.height * 0.52)
                                           : portSplit.height
                SplitView.minimumHeight: root.compactLayout ? 250 : 0
                draft: root.formMode === 0 ? (root.selectedRow() || ({})) : root.draftData
                editing: root.formMode !== 0
                allowRouted: root.allowRouted
                routedOnly: root.routedOnly
                viewMode: root.viewMode
                modeOnly: root.statusTab
                allowModeChange: root.statusTab || !root.advancedModeTab
                availableVlans: root.vlanOptions
                dirty: root.dirty
                valid: String(root.draftData.if_name || "").trim() !== ""
                saving: root.saving
                onFieldChanged: (name, value) => root.updateField(name, value)
                onSaveRequested: root.save()
                onCancelRequested: root.cancel()
            }
        }
    }
}
