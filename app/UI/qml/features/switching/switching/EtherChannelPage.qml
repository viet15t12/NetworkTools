pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import UI as App

Item {
    id: root
    objectName: "loadedEtherChannelPage"

    required property string host
    property int formMode: 0
    property int selectedIndex: -1
    property bool dirty: false
    property bool saving: false
    property var draftData: ({})
    property var allRows: []
    property var interfaceOptions: []
    property int dataRevision: 0
    property string filterText: ""
    property string message: ""
    property bool messageError: false

    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property bool hasDetail: formMode !== 0 || selectedRow() !== null
    readonly property var summaryMetrics: {
        const revision = root.dataRevision
        let up = 0
        let lacp = 0
        let members = 0
        for (let i = 0; i < root.allRows.length; i++) {
            const row = root.allRows[i]
            if (String(row.status || "").toLowerCase() === "up") up += 1
            if (String(row.protocol || "").toLowerCase() === "lacp") lacp += 1
            members += root.memberCount(row.member_ports)
        }
        return [
            { label: "Port-channels", value: root.allRows.length, tone: "neutral" },
            { label: "Operational", value: up, tone: "success" },
            { label: "LACP", value: lacp, tone: "accent" },
            { label: "Member ports", value: members, tone: "neutral" }
        ]
    }

    ListModel { id: channelModel }

    function clone(value) { return JSON.parse(JSON.stringify(value || {})) }

    function normalizedRow(row) {
        const source = row || ({})
        return {
            id: Number(source.id || 0),
            po_number: Number(source.po_number || 0),
            protocol: source.protocol === undefined || source.protocol === null
                      ? "lacp" : String(source.protocol),
            mode: source.mode === undefined || source.mode === null
                  ? "active" : String(source.mode),
            member_ports: source.member_ports === undefined || source.member_ports === null
                          ? "" : String(source.member_ports),
            description: source.description === undefined || source.description === null
                         ? "" : String(source.description),
            status: source.status === undefined || source.status === null
                    ? "unknown" : String(source.status),
            success: source.success === undefined || source.success === null
                     ? "pending_apply" : String(source.success)
        }
    }

    function selectedRow() {
        return selectedIndex >= 0 && selectedIndex < channelModel.count
             ? channelModel.get(selectedIndex) : null
    }

    function activeData() {
        return formMode === 0 ? (selectedRow() || ({})) : draftData
    }

    function memberCount(value) {
        const parts = String(value || "").split(",")
        let count = 0
        for (let i = 0; i < parts.length; i++) {
            if (parts[i].trim() !== "") count += 1
        }
        return count
    }

    function memberNames(value) {
        const members = []
        const parts = String(value || "").split(",")
        for (let i = 0; i < parts.length; i++) {
            const member = parts[i].trim()
            if (member !== "") members.push(member)
        }
        return members
    }

    function isMemberSelected(ifName) {
        const target = String(ifName || "").toLocaleLowerCase()
        const members = memberNames(draftData.member_ports)
        for (let i = 0; i < members.length; i++) {
            if (members[i].toLocaleLowerCase() === target) return true
        }
        return false
    }

    function assignedToAnotherChannel(ifName) {
        const target = String(ifName || "").toLocaleLowerCase()
        const editingId = Number(draftData.id || 0)
        for (let i = 0; i < allRows.length; i++) {
            const row = allRows[i]
            if (Number(row.id || 0) === editingId) continue
            const members = memberNames(row.member_ports)
            for (let j = 0; j < members.length; j++) {
                if (members[j].toLocaleLowerCase() === target) return true
            }
        }
        return false
    }

    function availableMemberInterfaces() {
        const values = []
        for (let i = 0; i < interfaceOptions.length; i++) {
            const row = interfaceOptions[i] || ({})
            const name = String(row.if_name || "")
            if (name === "" || String(row.mode || "") === "routed") continue
            if (/^(?:port[- ]?channel|po)\d/i.test(name)) continue
            if (!assignedToAnotherChannel(name)) values.push(name)
        }
        return values
    }

    function toggleMember(ifName, selected) {
        const members = memberNames(draftData.member_ports)
        const target = String(ifName || "")
        const targetKey = target.toLocaleLowerCase()
        const next = []
        let found = false
        for (let i = 0; i < members.length; i++) {
            if (members[i].toLocaleLowerCase() === targetKey) found = true
            else next.push(members[i])
        }
        if (selected && !found) next.push(target)
        updateField("member_ports", next.join(", "))
    }

    function modesForProtocol(protocol) {
        switch (String(protocol || "lacp")) {
        case "pagp": return ["desirable", "auto"]
        case "static": return ["on"]
        default: return ["active", "passive"]
        }
    }

    function comboIndex(model, value) {
        const index = model.indexOf(String(value))
        return index < 0 ? 0 : index
    }

    function rebuildVisibleRows() {
        const current = selectedRow()
        const selectedId = current ? Number(current.id || 0) : Number(draftData.id || 0)
        const query = String(filterText || "").trim().toLocaleLowerCase()
        channelModel.clear()
        let restoredIndex = -1
        for (let i = 0; i < allRows.length; i++) {
            const row = normalizedRow(allRows[i])
            const searchable = [
                "port-channel" + row.po_number, row.protocol, row.mode,
                row.member_ports, row.description, row.status
            ].join(" ").toLocaleLowerCase()
            if (query !== "" && searchable.indexOf(query) === -1) continue
            channelModel.append(row)
            if (Number(row.id || 0) === selectedId)
                restoredIndex = channelModel.count - 1
        }
        selectedIndex = restoredIndex >= 0 ? restoredIndex
                      : channelModel.count > 0 ? 0 : -1
        if (formMode === 0)
            draftData = selectedRow() ? clone(selectedRow()) : ({})
        dataRevision += 1
    }

    function load(reason) {
        const rows = dbManager.getSwitchEtherChannels(host)
        const interfaces = dbManager.getSwitchInterfaces(host)
        const values = []
        const availableInterfaces = []
        for (let i = 0; i < rows.length; i++) values.push(rows[i])
        for (let i = 0; i < interfaces.length; i++) availableInterfaces.push(interfaces[i])
        allRows = values
        interfaceOptions = availableInterfaces
        formMode = 0
        dirty = false
        rebuildVisibleRows()
        if (reason === "manual") message = "EtherChannel inventory reloaded."
    }

    function beginCreate() {
        draftData = {
            id: 0,
            po_number: "",
            protocol: "lacp",
            mode: "active",
            member_ports: "",
            description: "",
            status: "unknown"
        }
        formMode = 1
        dirty = false
    }

    function beginEdit() {
        if (!selectedRow()) return
        draftData = clone(selectedRow())
        formMode = 2
        dirty = false
    }

    function updateField(name, value) {
        draftData[name] = value
        dirty = true
        draftDataChanged()
    }

    function changeProtocol(protocol) {
        draftData.protocol = protocol
        const modes = modesForProtocol(protocol)
        if (modes.indexOf(String(draftData.mode || "")) === -1)
            draftData.mode = modes[0]
        dirty = true
        draftDataChanged()
    }

    function cancel() {
        formMode = 0
        dirty = false
        draftData = selectedRow() ? clone(selectedRow()) : ({})
    }

    function save() {
        saving = true
        const result = dbManager.saveSwitchEtherChannel(host, draftData)
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }

    function deleteChannel(index, row) {
        if (formMode !== 0 || !row) return
        selectedIndex = index
        const rowId = Number(row.id || 0)
        if (rowId <= 0) return
        saving = true
        const result = dbManager.deleteSwitchEtherChannel(host, rowId)
        saving = false
        message = String(result && result.message
                         ? result.message : "Could not delete the selected EtherChannel.")
        messageError = !result || result.ok !== true
        if (result && result.ok === true) load()
    }

    function deleteSelected() {
        const row = selectedRow()
        if (row) deleteChannel(selectedIndex, row)
    }

    Component.onCompleted: load()
    onHostChanged: load()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: "EtherChannel"
            subtitle: "Bundle physical links into a single logical Port-channel."

            ViewPushButton {
                controllerName: "switching"
                hostIp: root.host
                moduleName: "etherchannel"
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
                valid: String(root.draftData.po_number || "").trim() !== ""
                       && String(root.draftData.member_ports || "").trim() !== ""
                saving: root.saving
                allowEditorActions: false
                onAddRequested: root.beginCreate()
                onEditRequested: root.beginEdit()
                onRefreshRequested: root.load("manual")
                onSaveRequested: root.save()
                onCancelRequested: root.cancel()
            }
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
            id: channelSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { orientation: channelSplit.orientation }

            Item {
                SplitView.fillWidth: !root.compactLayout
                SplitView.fillHeight: root.compactLayout
                SplitView.minimumWidth: root.compactLayout ? 0 : 500
                SplitView.minimumHeight: root.compactLayout ? 220 : 0
                SplitView.preferredHeight: root.compactLayout
                                           ? Math.max(240, channelSplit.height * 0.52)
                                           : channelSplit.height

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.spacing8

                    SwitchTableToolbar {
                        Layout.fillWidth: true
                        title: "Channel inventory"
                        totalCount: root.allRows.length
                        visibleCount: channelModel.count
                        searchText: root.filterText
                        searchPlaceholder: "Filter channels or members..."
                        onSearchEdited: value => {
                            root.filterText = value
                            root.rebuildVisibleRows()
                        }
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        count: channelModel.count
                        bodyMargins: 0
                        emptyTitle: root.filterText === "" ? "No EtherChannels" : "No matching channels"
                        emptyDescription: root.filterText === ""
                                          ? "Use Add to define the first link aggregation group."
                                          : "Try a Port-channel number, protocol, or member interface."
                        headerComponent: Component {
                            DataTableHeader {
                                RowLayout {
                                    anchors.fill: parent
                                    spacing: Theme.spacing8
                                    DataTableCell { Layout.preferredWidth: 130; header: true; text: "Port-channel" }
                                    DataTableCell { Layout.preferredWidth: 90; header: true; text: "Protocol" }
                                    DataTableCell { Layout.preferredWidth: 90; header: true; text: "Mode" }
                                    DataTableCell { Layout.fillWidth: true; header: true; text: "Members" }
                                    DataTableCell { Layout.preferredWidth: 88; header: true; text: "Status" }
                                    DataTableCell { Layout.preferredWidth: 48; header: true; text: "" }
                                }
                            }
                        }

                        ListView {
                            anchors.fill: parent
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            model: channelModel
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
                                interactive: root.formMode === 0

                                RowLayout {
                                    anchors.fill: parent
                                    spacing: Theme.spacing8
                                    DataTableCell { Layout.preferredWidth: 130; primary: true; text: "Port-channel" + String(row.model.po_number) }
                                    DataTableCell { Layout.preferredWidth: 90; text: String(row.model.protocol).toUpperCase() }
                                    DataTableCell { Layout.preferredWidth: 90; text: String(row.model.mode) }
                                    DataTableCell { Layout.fillWidth: true; monospaced: true; text: row.model.member_ports || "—" }
                                    App.StatusBadge { Layout.preferredWidth: 88; value: row.model.status || "unknown" }
                                    IconButton {
                                        objectName: "etherChannelRowDeleteButton"
                                        Layout.preferredWidth: 48
                                        buttonSize: 28
                                        iconSize: Theme.iconSizeNormal
                                        iconSource: AppAssets.actionDelete
                                        danger: true
                                        tooltip: "Delete Port-channel"
                                        enabled: root.formMode === 0 && !root.saving
                                        onClicked: root.deleteChannel(row.index, row.model)
                                    }
                                }

                                TapHandler {
                                    enabled: root.formMode === 0
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
                SplitView.preferredWidth: root.compactLayout ? channelSplit.width
                                                             : Math.min(430, root.width * 0.4)
                SplitView.minimumWidth: root.compactLayout ? 0 : 350
                SplitView.minimumHeight: root.compactLayout ? 240 : 0
                title: root.formMode === 1 ? "New EtherChannel"
                       : root.hasDetail ? "Port-channel" + String(root.activeData().po_number || "")
                       : "EtherChannel details"
                subtitle: root.formMode === 1 ? "Create local desired state"
                          : root.hasDetail ? String(root.activeData().description || "Link aggregation group")
                          : ""
                hasContent: root.hasDetail
                editing: root.formMode !== 0
                emptyTitle: "No channel selected"
                emptyDescription: "Select a row to inspect it, or choose Add to create an EtherChannel."

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Channel identity"
                    helpText: "Port-channel number uniquely identifies the logical bundle on this switch. Description is an optional operational note. Use a number supported by the target IOS platform."
                    description: "The Port-channel number must be unique on this switch."

                    SwitchPropertyRow { visible: root.formMode === 0; label: "Interface"; value: "Port-channel" + String(root.activeData().po_number || "—"); emphasize: true }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Description"; value: String(root.activeData().description || "—") }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Operational"; value: String(root.activeData().status || "unknown"); valueColor: root.activeData().status === "up" ? Theme.alertSuccess : Theme.textSecondary }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Push status"; value: String(root.activeData().success || "pending_apply").replace(/_/g, " ") }

                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Port-channel number"
                        readOnly: root.formMode === 2
                        placeholderText: "1–4096"
                        text: String(root.activeData().po_number || "")
                        onTextEdited: value => root.updateField("po_number", value)
                    }
                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Description"
                        placeholderText: "Uplink to distribution switch"
                        text: String(root.activeData().description || "")
                        onTextEdited: value => root.updateField("description", value)
                    }
                }

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Negotiation"
                    helpText: "LACP uses active/passive, PAgP uses desirable/auto, and Static uses on. At least one side must actively negotiate for LACP or PAgP. Protocol and compatible mode must match the peer design."
                    description: "Protocol and mode are constrained to valid Cisco IOS pairs."

                    SwitchPropertyRow { visible: root.formMode === 0; label: "Protocol"; value: String(root.activeData().protocol || "lacp").toUpperCase() }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Mode"; value: String(root.activeData().mode || "active") }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0

                        StandardComboBox {
                            Layout.fillWidth: true
                            labelText: "Protocol"
                            model: ["lacp", "pagp", "static"]
                            currentIndex: root.comboIndex(model, root.activeData().protocol || "lacp")
                            onActivated: index => root.changeProtocol(model[index])
                        }
                        StandardComboBox {
                            Layout.fillWidth: true
                            labelText: "Mode"
                            model: root.modesForProtocol(root.activeData().protocol)
                            currentIndex: root.comboIndex(model, root.activeData().mode || "active")
                            onActivated: index => root.updateField("mode", model[index])
                        }
                    }
                }

                SwitchInspectorSection {
                    Layout.fillWidth: true
                    title: "Member interfaces"
                    helpText: "Enter comma-separated physical interface names. Members must have compatible speed, duplex, VLAN mode, and trunk/access settings, and an interface must not belong to another channel."
                    description: "Enter physical interfaces separated by commas."
                    showDivider: false

                    SwitchPropertyRow { visible: root.formMode === 0; label: "Members"; value: String(root.activeData().member_ports || "—"); monospaced: true }
                    SwitchPropertyRow { visible: root.formMode === 0; label: "Member count"; value: String(root.memberCount(root.activeData().member_ports)) }
                    StandardTextField {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0
                        labelText: "Member interfaces"
                        placeholderText: "GigabitEthernet0/1, GigabitEthernet0/2"
                        text: String(root.activeData().member_ports || "")
                        onTextEdited: value => root.updateField("member_ports", value)
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0 && root.availableMemberInterfaces().length > 0
                        text: "Quick select available interfaces"
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.formMode !== 0 && root.availableMemberInterfaces().length > 0
                        spacing: Theme.spacing4
                        Repeater {
                            model: root.availableMemberInterfaces()
                            delegate: StandardCheckBox {
                                required property string modelData
                                Layout.fillWidth: true
                                text: modelData
                                checked: root.isMemberSelected(modelData)
                                onToggled: root.toggleMember(modelData, checked)
                            }
                        }
                    }
                }

                App.CrudFormActions {
                    objectName: "etherChannelEditorActions"
                    Layout.fillWidth: true
                    visible: root.formMode !== 0
                    formMode: root.formMode
                    dirty: root.dirty
                    valid: String(root.draftData.po_number || "").trim() !== ""
                           && String(root.draftData.member_ports || "").trim() !== ""
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

    Shortcut {
        sequence: "Delete"
        enabled: root.visible && root.formMode === 0 && root.selectedIndex >= 0
                 && !root.saving
        onActivated: root.deleteSelected()
    }
}
