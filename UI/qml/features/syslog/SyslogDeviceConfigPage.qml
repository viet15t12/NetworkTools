pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Item {
    id: root
    objectName: "syslogDeviceConfigPage"

    required property string host
    property int formMode: 0
    property int selectedIndex: -1
    property bool dirty: false
    property bool saving: false
    property bool syncingPortEditor: false
    property var draftData: ({})
    property var allRows: []
    property var sourceInterfaceOptions: []
    property string filterText: ""
    property string message: ""
    property bool messageError: false
    property int dataRevision: 0
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property var backend: typeof syslogManager !== "undefined"
                                   && syslogManager !== null ? syslogManager : null
    readonly property var databaseBackend: typeof dbManager !== "undefined"
                                           && dbManager !== null ? dbManager : null
    readonly property var severityLabels: [
        "0 · Emergencies", "1 · Alerts", "2 · Critical", "3 · Errors",
        "4 · Warnings", "5 · Notifications", "6 · Informational", "7 · Debugging"
    ]
    readonly property bool draftValid: String(draftData.server_ip || "").trim() !== ""
                                       && String(draftData.source_interface || "").trim() !== ""
                                       && Number(draftData.port || 0) >= 1
                                       && Number(draftData.port || 0) <= 65535
    readonly property var summaryMetrics: {
        const revision = root.dataRevision
        let applied = 0
        let pending = 0
        let removals = 0
        for (let i = 0; i < root.allRows.length; ++i) {
            const state = String(root.allRows[i].sync_status || "pending_apply")
            if (state === "synchronized") applied += 1
            else if (state === "pending_delete") removals += 1
            else pending += 1
        }
        return [
            { label: "Destinations", value: root.allRows.length, tone: "neutral" },
            { label: "Applied", value: applied, tone: "success" },
            { label: "Pending apply", value: pending, tone: "warning" },
            { label: "Pending removal", value: removals, tone: "danger" }
        ]
    }

    ListModel { id: serverModel }

    function clone(value) { return JSON.parse(JSON.stringify(value || {})) }
    function appendSourceInterface(options, seen, value) {
        const name = String(value || "").trim()
        const key = name.toLocaleLowerCase()
        if (name === "" || seen[key]) return
        seen[key] = true
        options.push(name)
    }
    function sourceInterfaceIndex(value) {
        const target = String(value || "").trim().toLocaleLowerCase()
        for (let i = 0; i < root.sourceInterfaceOptions.length; ++i) {
            if (String(root.sourceInterfaceOptions[i]).toLocaleLowerCase() === target)
                return i
        }
        return -1
    }
    function loadSourceInterfaces() {
        const options = []
        const seen = ({})
        const manager = root.databaseBackend

        if (manager !== null) {
            if (typeof manager.getRouterInterfaces === "function") {
                const rows = manager.getRouterInterfaces(root.host) || []
                for (let i = 0; i < rows.length; ++i)
                    appendSourceInterface(options, seen, rows[i].interface_name)
            }
            if (typeof manager.getSwitchInterfaces === "function") {
                const rows = manager.getSwitchInterfaces(root.host) || []
                for (let i = 0; i < rows.length; ++i)
                    appendSourceInterface(options, seen, rows[i].if_name)
            }
            if (typeof manager.getSwitchSvis === "function") {
                const rows = manager.getSwitchSvis(root.host) || []
                for (let i = 0; i < rows.length; ++i) {
                    const vlanId = Number(rows[i].vlan_id || 0)
                    if (vlanId > 0)
                        appendSourceInterface(options, seen, "Vlan" + vlanId)
                }
            }
            if (typeof manager.getSwitchEtherChannels === "function") {
                const rows = manager.getSwitchEtherChannels(root.host) || []
                for (let i = 0; i < rows.length; ++i) {
                    const channel = Number(rows[i].po_number || 0)
                    if (channel > 0)
                        appendSourceInterface(options, seen, "Port-channel" + channel)
                }
            }
        }

        // Keep interfaces used by existing rows selectable even when the local
        // interface inventory has not been synchronized yet.
        for (let i = 0; i < root.allRows.length; ++i)
            appendSourceInterface(options, seen, root.allRows[i].source_interface)

        options.sort(function(left, right) {
            return left.toLocaleLowerCase().localeCompare(right.toLocaleLowerCase())
        })
        root.sourceInterfaceOptions = options
    }
    function normalizedRow(source) {
        const row = source || ({})
        return {
            device_host: String(row.device_host || root.host),
            server_ip: String(row.server_ip || ""),
            protocol: String(row.protocol || "udp").toLowerCase(),
            port: Number(row.port || 5514),
            source_interface: String(row.source_interface || ""),
            trap_severity: Number(row.trap_severity === undefined ? 5 : row.trap_severity),
            timestamps: Boolean(row.timestamps),
            sequence_numbers: Boolean(row.sequence_numbers),
            configured: Boolean(row.configured),
            sync_status: String(row.sync_status || "pending_apply"),
            last_result: String(row.last_result || ""),
            updated_at: String(row.updated_at || "")
        }
    }
    function rowAt(index) {
        return index >= 0 && index < serverModel.count ? serverModel.get(index) : null
    }
    function activeData() {
        return formMode === 0 ? (rowAt(selectedIndex) || ({})) : draftData
    }
    function endpoint(row) {
        if (!row || !row.server_ip) return "—"
        return String(row.server_ip) + ":" + String(row.port || 5514)
    }
    function rebuildVisibleRows() {
        const selected = rowAt(selectedIndex)
        const selectedKey = selected
                          ? [selected.server_ip, selected.protocol, selected.port].join("|") : ""
        const query = filterText.trim().toLocaleLowerCase()
        serverModel.clear()
        let restored = -1
        for (let i = 0; i < allRows.length; ++i) {
            const row = normalizedRow(allRows[i])
            const searchable = [row.server_ip, row.protocol, row.port,
                                row.source_interface, row.sync_status].join(" ").toLocaleLowerCase()
            if (query !== "" && searchable.indexOf(query) === -1) continue
            serverModel.append(row)
            if ([row.server_ip, row.protocol, row.port].join("|") === selectedKey)
                restored = serverModel.count - 1
        }
        selectedIndex = restored >= 0 ? restored : serverModel.count > 0 ? 0 : -1
        if (formMode === 0)
            draftData = rowAt(selectedIndex) ? clone(rowAt(selectedIndex)) : ({})
        dataRevision += 1
    }
    function load(reason) {
        allRows = backend !== null ? backend.getDeviceConfigurations(host) : []
        loadSourceInterfaces()
        formMode = 0
        dirty = false
        rebuildVisibleRows()
        if (reason === "manual") {
            message = "Syslog server configurations reloaded."
            messageError = false
        }
    }
    function reloadData(reason) {
        if (formMode !== 0 || saving) return false
        load(reason)
        return true
    }
    function beginCreate() {
        draftData = {
            server_ip: "", protocol: "udp", port: 5514,
            source_interface: "", trap_severity: 5,
            timestamps: true, sequence_numbers: true
        }
        formMode = 1
        dirty = false
        syncPortEditor()
    }
    function beginEdit() {
        const row = rowAt(selectedIndex)
        if (!row || row.sync_status === "pending_delete") return
        draftData = clone(row)
        draftData.original_server_ip = row.server_ip
        draftData.original_protocol = row.protocol
        draftData.original_port = row.port
        formMode = 2
        dirty = false
        syncPortEditor()
    }
    function syncPortEditor() {
        syncingPortEditor = true
        portEditor.value = Number(draftData.port || 5514)
        syncingPortEditor = false
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
        if (backend === null || !draftValid || saving) return
        saving = true
        const result = backend.saveDeviceConfiguration(host, draftData)
        saving = false
        message = String(result.message || "")
        messageError = !Boolean(result.ok)
        if (result.ok) load()
    }
    function deleteSelected() {
        const row = rowAt(selectedIndex)
        if (backend === null || !row || saving) return
        saving = true
        // ListModel.get() returns a QML row proxy. Convert it to a plain JS
        // object before crossing the QVariant boundary into Python.
        const result = backend.deleteDeviceConfiguration(host, clone(row))
        saving = false
        message = String(result.message || "")
        messageError = !Boolean(result.ok)
        if (result.ok) load()
    }

    Component.onCompleted: load()
    onHostChanged: load()

    Connections {
        target: typeof dbManager !== "undefined" ? dbManager : null

        function onRunningConfigUpdated(updatedHost) {
            if (String(updatedHost || "").trim() === String(root.host || "").trim()
                    && root.formMode === 0 && !root.saving)
                root.reloadData("backgroundSync")
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: "Syslog Servers"
            subtitle: "Manage multiple Cisco Syslog destinations for " + root.host + "."

            StandardButton {
                objectName: "syslogGroupButton"
                text: "Syslog Group"
                icon.source: AppAssets.actionPush
                type: "Primary"
                onClicked: syslogGroupDialog.openFor(root)
            }

            ViewPushButton {
                objectName: "syslogViewPushButton"
                controllerName: "syslog"
                hostIp: root.host
                moduleName: "servers"
                refreshKey: root.dataRevision
                ownerForm: root
                onPushCompleted: function(ok, detail) {
                    root.message = detail
                    root.messageError = !ok
                    root.load()
                }
            }

            CrudFormActions {
                objectName: "syslogCrudActions"
                formMode: root.formMode
                hasSelection: root.selectedIndex >= 0
                dirty: root.dirty
                valid: root.draftValid
                saving: root.saving
                allowDelete: root.selectedIndex >= 0
                allowEdit: root.selectedIndex >= 0
                           && String(root.activeData().sync_status || "") !== "pending_delete"
                allowEditorActions: false
                onAddRequested: root.beginCreate()
                onEditRequested: root.beginEdit()
                onDeleteRequested: root.deleteSelected()
                onRefreshRequested: root.load("manual")
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
            id: configSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { orientation: configSplit.orientation }

            Item {
                SplitView.fillWidth: !root.compactLayout
                SplitView.fillHeight: root.compactLayout
                SplitView.minimumWidth: root.compactLayout ? 0 : 520
                SplitView.minimumHeight: root.compactLayout ? 220 : 0

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.spacing8

                    SwitchTableToolbar {
                        Layout.fillWidth: true
                        title: "Configured destinations"
                        totalCount: root.allRows.length
                        visibleCount: serverModel.count
                        searchText: root.filterText
                        searchPlaceholder: "Filter server, protocol, interface..."
                        onSearchEdited: value => {
                            root.filterText = value
                            root.rebuildVisibleRows()
                        }
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        count: serverModel.count
                        bodyMargins: 0
                        emptyTitle: root.filterText === "" ? "No Syslog servers" : "No matching servers"
                        emptyDescription: root.filterText === ""
                                          ? "Use Add to create the first destination."
                                          : "Clear the filter or try another value."
                        headerComponent: Component {
                            DataTableHeader {
                                RowLayout {
                                    anchors.fill: parent
                                    spacing: Theme.spacing8
                                    DataTableCell { Layout.fillWidth: true; header: true; text: "Destination" }
                                    DataTableCell { Layout.preferredWidth: 90; header: true; text: "Protocol" }
                                    DataTableCell { Layout.preferredWidth: 130; header: true; text: "Status" }
                                }
                            }
                        }
                        ListView {
                            anchors.fill: parent
                            clip: true
                            model: serverModel
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: DataTableRow {
                                id: configRow
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
                                    DataTableCell {
                                        Layout.fillWidth: true
                                        primary: true
                                        text: root.endpoint(configRow.model)
                                    }
                                    DataTableCell {
                                        Layout.preferredWidth: 90
                                        text: String(configRow.model.protocol || "udp").toUpperCase()
                                    }
                                    Item {
                                        Layout.preferredWidth: 130
                                        Layout.fillHeight: true
                                        StatusBadge {
                                            anchors.left: parent.left
                                            anchors.verticalCenter: parent.verticalCenter
                                            value: String(configRow.model.sync_status || "pending_apply")
                                        }
                                    }
                                }
                                TapHandler {
                                    enabled: root.formMode === 0
                                    onTapped: {
                                        root.selectedIndex = configRow.index
                                        root.draftData = root.clone(root.rowAt(configRow.index))
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
                SplitView.preferredWidth: root.compactLayout ? configSplit.width
                                                             : Math.min(440, root.width * 0.42)
                SplitView.minimumWidth: root.compactLayout ? 0 : 360
                SplitView.minimumHeight: root.compactLayout ? 330 : 0
                title: root.formMode === 1 ? "New Syslog Server"
                       : root.activeData().server_ip ? root.endpoint(root.activeData())
                                                     : "Syslog server details"
                subtitle: root.activeData().source_interface || "Cisco logging destination"
                hasContent: root.formMode !== 0 || root.selectedIndex >= 0
                editing: root.formMode !== 0
                emptyTitle: "No destination selected"
                emptyDescription: "Select a server row, or choose Add to create one."

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Destination"
                    helpText: "Server IP: Reachable IPv4 or IPv6 address of the collector.\n\nProtocol: UDP or TCP transport used by this destination.\n\nPort: Destination port from 1 to 65535; normally the CAMS listener port.\n\nSource interface: Cisco interface used as the source address of outgoing Syslog traffic. Prefer a reachable Loopback, management interface, or SVI."
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Server"; value: root.endpoint(root.activeData()); emphasize: true }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Protocol"; value: String(root.activeData().protocol || "—").toUpperCase() }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Source interface"; value: root.activeData().source_interface || "—" }

                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Server IP"
                        placeholderText: "192.0.2.100"
                        text: String(root.draftData.server_ip || "")
                        onTextEdited: function(value) {
                            root.updateField("server_ip", value.trim())
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        StandardComboBox {
                            Layout.fillWidth: true
                            labelText: "Protocol"
                            model: ["UDP", "TCP"]
                            currentIndex: String(root.draftData.protocol || "udp") === "tcp" ? 1 : 0
                            onActivated: index => root.updateField("protocol", index === 1 ? "tcp" : "udp")
                        }
                        StandardSpinBox {
                            id: portEditor
                            Layout.fillWidth: true
                            labelText: "Port"
                            from: 1
                            to: 65535
                            value: 5514
                            onValueChanged: {
                                if (root.formMode !== 0 && !root.syncingPortEditor
                                        && Number(root.draftData.port || 0) !== value)
                                    root.updateField("port", value)
                            }
                        }
                    }
                    StandardComboBox {
                        id: sourceInterfaceCombo
                        objectName: "syslogSourceInterfaceCombo"
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Source interface"
                        model: root.sourceInterfaceOptions
                        emptyText: "No interfaces available"
                        emptyWarningText: "No interface is available for this device. Synchronize Router Interfaces or Switching before configuring Syslog."
                        currentIndex: root.sourceInterfaceIndex(
                                          root.draftData.source_interface)
                        onActivated: index => root.updateField(
                                         "source_interface",
                                         root.sourceInterfaceOptions[index])
                    }
                }

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Message policy"
                    helpText: "Trap severity: Controls which message levels Cisco sends. Lower numbers are more severe; 7 Debug is the most verbose.\n\nTimestamps: Adds millisecond timestamps to generated log messages.\n\nSequence numbers: Adds device-side ordering numbers.\n\nPush status: pending_apply waits to be pushed, pending_delete waits for removal, synchronized matches verified device state, and skipped is intentionally not applied."
                    showDivider: false
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Trap severity"; value: root.severityLabels[Number(root.activeData().trap_severity || 0)] || "—" }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Timestamps"; value: root.activeData().timestamps ? "Enabled" : "Disabled" }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Sequence numbers"; value: root.activeData().sequence_numbers ? "Enabled" : "Disabled" }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Push status"; value: String(root.activeData().sync_status || "—").replace(/_/g, " ") }

                    StandardComboBox {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Trap severity"
                        model: root.severityLabels
                        currentIndex: Number(root.draftData.trap_severity === undefined ? 5 : root.draftData.trap_severity)
                        onActivated: index => root.updateField("trap_severity", index)
                    }
                    StandardCheckBox {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        text: "Include millisecond log timestamps"
                        checked: Boolean(root.draftData.timestamps)
                        onToggled: root.updateField("timestamps", checked)
                    }
                    StandardCheckBox {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        text: "Include sequence numbers"
                        checked: Boolean(root.draftData.sequence_numbers)
                        onToggled: root.updateField("sequence_numbers", checked)
                    }
                }

                CrudFormActions {
                    objectName: "syslogEditorActions"
                    Layout.fillWidth: true
                    visible: root.formMode !== 0
                    formMode: root.formMode
                    dirty: root.dirty
                    valid: root.draftValid
                    saving: root.saving
                    allowCreate: false
                    allowEdit: false
                    allowDelete: false
                    allowRefresh: false
                    onSaveRequested: root.save()
                    onCancelRequested: root.cancel()
                }
            }
        }
    }

    SyslogGroupDialog {
        id: syslogGroupDialog
        parent: Overlay.overlay
    }
}
