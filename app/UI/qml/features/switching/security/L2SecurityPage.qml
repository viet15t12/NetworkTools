pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import UI as App

Item {
    id: root
    objectName: "loadedL2SecurityPage"

    required property string host
    property string section: "vlans"
    property int selectedPolicyIndex: -1
    property int selectedStaticIndex: -1
    property int staticFormMode: 0
    property bool policyDirty: false
    property bool staticDirty: false
    property bool saving: false
    property bool refreshingReferences: false
    property var policyDraft: ({})
    property var staticDraft: ({})
    property var interfaceOptions: []
    property var vlanOptions: []
    property string message: ""
    property bool messageError: false
    property int dataRevision: 0

    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property bool hasVlanProtection: {
        const revision = root.dataRevision
        for (let i = 0; i < vlanPolicyModel.count; i++) {
            // Reflect the selected unsaved draft as the user moves between the
            // VLAN Protection and Trusted Uplinks sections.
            const row = root.policyDirty && i === root.selectedPolicyIndex
                      ? root.policyDraft : vlanPolicyModel.get(i)
            if (row.dhcp_snooping || row.dai_enabled) return true
        }
        return false
    }
    readonly property var summaryMetrics: {
        const revision = root.dataRevision
        let snooping = 0
        let dai = 0
        for (let i = 0; i < vlanPolicyModel.count; i++) {
            if (vlanPolicyModel.get(i).dhcp_snooping) snooping += 1
            if (vlanPolicyModel.get(i).dai_enabled) dai += 1
        }
        return [
            { label: "Snooping VLANs", value: snooping, tone: "accent" },
            { label: "DAI VLANs", value: dai, tone: "success" },
            { label: "Trusted uplinks", value: trustPortModel.count, tone: "warning" },
            { label: "Static MACs", value: staticMacModel.count, tone: "neutral" }
        ]
    }

    ListModel { id: vlanPolicyModel }
    ListModel { id: trustPortModel }
    ListModel { id: staticMacModel }

    function clone(value) { return JSON.parse(JSON.stringify(value || {})) }
    function comboIndex(model, value) {
        const index = model.indexOf(value)
        return index < 0 ? 0 : index
    }
    function policyAt(index) {
        return index >= 0 && index < vlanPolicyModel.count ? vlanPolicyModel.get(index) : null
    }
    function staticAt(index) {
        return index >= 0 && index < staticMacModel.count ? staticMacModel.get(index) : null
    }
    // Normalize the two cross-tab reference entities in one place so a schema
    // field addition cannot make full-load and background-refresh drift apart.
    function normalizedVlanReference(row) {
        const source = row || ({})
        return {
            id: Number(source.id || 0),
            vlan_id: Number(source.vlan_id || 0),
            vlan_name: source.vlan_name === undefined || source.vlan_name === null
                       ? "" : String(source.vlan_name),
            dhcp_snooping: Boolean(source.dhcp_snooping),
            dai_enabled: Boolean(source.dai_enabled),
            success: String(source.success || "skipped")
        }
    }
    function normalizedInterfaceReference(row) {
        const source = row || ({})
        return {
            id: Number(source.id || 0),
            if_name: String(source.if_name || ""),
            description: String(source.description || ""),
            mode: String(source.mode || "access"),
            admin_status: String(source.admin_status || "up"),
            oper_status: String(source.oper_status || "unknown")
        }
    }
    function replaceTrustPorts(rows) {
        trustPortModel.clear()
        for (let i = 0; i < rows.length; i++) {
            trustPortModel.append({
                id: Number(rows[i].id || 0),
                if_name: String(rows[i].if_name || ""),
                success: String(rows[i].success || "pending_apply")
            })
        }
    }
    function interfaceNames() {
        const values = []
        for (let i = 0; i < interfaceOptions.length; i++) values.push(interfaceOptions[i].if_name)
        return values
    }
    function availableTrustInterfaces() {
        const revision = root.dataRevision
        const values = []
        for (let i = 0; i < interfaceOptions.length; i++) {
            const candidate = interfaceOptions[i].if_name
            let alreadyTrusted = false
            for (let j = 0; j < trustPortModel.count; j++) {
                if (trustPortModel.get(j).if_name === candidate) {
                    alreadyTrusted = true
                    break
                }
            }
            if (!alreadyTrusted) values.push(candidate)
        }
        return values
    }
    function availableTrustInterfaceLabels() {
        const available = root.availableTrustInterfaces()
        const labels = []
        for (let i = 0; i < available.length; i++) {
            const ifName = available[i]
            let detail = "Layer 2"
            for (let j = 0; j < interfaceOptions.length; j++) {
                if (interfaceOptions[j].if_name === ifName) {
                    const mode = String(interfaceOptions[j].mode || "access")
                    const status = String(interfaceOptions[j].oper_status || "unknown")
                    detail = mode + (status === "unknown" ? "" : " · " + status)
                    break
                }
            }
            labels.push(ifName + "  —  " + detail)
        }
        return labels
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
    function load(reason) {
        const result = dbManager.getSwitchL2Security(host)
        const vlans = result && result.vlans ? result.vlans : []
        const ports = result && result.trust_ports ? result.trust_ports : []
        const macs = result && result.static_macs ? result.static_macs : []
        const interfaces = result && result.interfaces ? result.interfaces : []
        vlanPolicyModel.clear()
        staticMacModel.clear()
        // Build plain JavaScript arrays locally, then assign once. Mutating a
        // ``property var`` array with push() does not reliably notify QML
        // bindings such as the Trusted Uplink ComboBox.
        const nextVlanOptions = []
        const nextInterfaceOptions = []
        for (let i = 0; i < vlans.length; i++) {
            const normalized = normalizedVlanReference(vlans[i])
            vlanPolicyModel.append(normalized)
            nextVlanOptions.push(normalized)
        }
        replaceTrustPorts(ports)
        for (let i = 0; i < macs.length; i++) {
            staticMacModel.append({
                id: Number(macs[i].id || 0),
                mac_addr: String(macs[i].mac_addr || ""),
                vlan_id: Number(macs[i].vlan_id || 0),
                if_name: String(macs[i].if_name || ""),
                success: String(macs[i].success || "pending_apply")
            })
        }
        for (let i = 0; i < interfaces.length; i++) {
            nextInterfaceOptions.push(normalizedInterfaceReference(interfaces[i]))
        }
        vlanOptions = nextVlanOptions
        interfaceOptions = nextInterfaceOptions
        selectedPolicyIndex = vlanPolicyModel.count > 0 ? 0 : -1
        selectedStaticIndex = staticMacModel.count > 0 ? 0 : -1
        policyDraft = policyAt(selectedPolicyIndex) ? clone(policyAt(selectedPolicyIndex)) : ({})
        staticDraft = staticAt(selectedStaticIndex) ? clone(staticAt(selectedStaticIndex)) : ({})
        policyDirty = false
        staticDirty = false
        staticFormMode = 0
        dataRevision += 1
        if (reason === "manual") message = "Layer 2 security data reloaded."
    }
    function refreshReferenceData(reason) {
        // Refresh only cross-tab reference data. This intentionally preserves
        // an unsaved VLAN policy or Static MAC draft while interface inventory
        // is synchronized in the background.
        if (refreshingReferences) return
        refreshingReferences = true
        const result = dbManager.getSwitchL2Security(host)
        const interfaces = result && result.interfaces ? result.interfaces : []
        const vlans = result && result.vlans ? result.vlans : []
        const ports = result && result.trust_ports ? result.trust_ports : []
        const nextInterfaces = []
        const nextVlans = []

        for (let i = 0; i < interfaces.length; i++)
            nextInterfaces.push(normalizedInterfaceReference(interfaces[i]))
        for (let i = 0; i < vlans.length; i++)
            nextVlans.push(normalizedVlanReference(vlans[i]))
        replaceTrustPorts(ports)
        interfaceOptions = nextInterfaces
        vlanOptions = nextVlans
        dataRevision += 1
        refreshingReferences = false
        if (reason === "device-sync") {
            message = "Interface inventory synchronized; trusted uplinks refreshed."
            messageError = false
        }
    }
    function selectPolicy(index) {
        selectedPolicyIndex = index
        policyDraft = policyAt(index) ? clone(policyAt(index)) : ({})
        policyDirty = false
    }
    function updatePolicy(name, value) {
        policyDraft[name] = value
        policyDirty = true
        policyDraftChanged()
    }
    function savePolicy() {
        saving = true
        const result = dbManager.saveSwitchL2VlanSecurity(host, policyDraft)
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }
    function deletePolicy() {
        const rowId = Number(policyDraft.id || 0)
        if (rowId <= 0 || saving) return
        saving = true
        const result = dbManager.deleteSwitchL2VlanSecurity(host, rowId)
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }
    function cancelPolicy() {
        policyDraft = policyAt(selectedPolicyIndex)
                      ? clone(policyAt(selectedPolicyIndex)) : ({})
        policyDirty = false
    }
    function addTrustPort(ifName) {
        const result = dbManager.addSwitchL2TrustPort(host, ifName)
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }
    function deleteTrustPort(rowId) {
        if (Number(rowId || 0) <= 0 || saving) return
        saving = true
        const result = dbManager.deleteSwitchL2TrustPort(host, Number(rowId))
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }
    function beginStaticCreate() {
        staticDraft = {
            id: 0,
            mac_addr: "",
            vlan_id: vlanOptions.length > 0 ? vlanOptions[0].vlan_id : 0,
            if_name: interfaceOptions.length > 0 ? interfaceOptions[0].if_name : ""
        }
        staticFormMode = 1
        staticDirty = false
    }
    function beginStaticEdit() {
        if (!staticAt(selectedStaticIndex)) return
        staticDraft = clone(staticAt(selectedStaticIndex))
        staticFormMode = 2
        staticDirty = false
    }
    function selectStatic(index) {
        if (staticFormMode !== 0) return
        selectedStaticIndex = index
        staticDraft = staticAt(index) ? clone(staticAt(index)) : ({})
    }
    function updateStatic(name, value) {
        staticDraft[name] = value
        staticDirty = true
        staticDraftChanged()
    }
    function cancelStatic() {
        staticFormMode = 0
        staticDirty = false
        staticDraft = staticAt(selectedStaticIndex) ? clone(staticAt(selectedStaticIndex)) : ({})
    }
    function saveStatic() {
        saving = true
        const result = dbManager.saveSwitchStaticMac(host, staticDraft)
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }
    function deleteStatic() {
        const row = staticAt(selectedStaticIndex)
        if (!row || Number(row.id || 0) <= 0 || saving) return
        saving = true
        const result = dbManager.deleteSwitchStaticMac(host, Number(row.id))
        saving = false
        message = String(result.message || "")
        messageError = !result.ok
        if (result.ok) load()
    }

    Component.onCompleted: load()
    onHostChanged: load()
    onSectionChanged: {
        if (section === "trust" || section === "staticMac")
            refreshReferenceData("section")
    }

    Connections {
        target: typeof dbManager !== "undefined" ? dbManager : null
        function onRunningConfigUpdated(updatedHost) {
            if (String(updatedHost || "").trim() === String(root.host || "").trim())
                root.refreshReferenceData("device-sync")
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: "Layer 2 Security"
            subtitle: "Configure DHCP Snooping, Dynamic ARP Inspection, trusted uplinks and static MAC bindings."

            ViewPushButton {
                controllerName: "switching"
                hostIp: root.host
                moduleName: "l2_security"
                refreshKey: root.dataRevision
                ownerForm: root
                onPushCompleted: function(ok, detail) {
                    root.message = detail
                    root.messageError = !ok
                    if (ok) root.load()
                }
            }
            StandardButton {
                text: "Reload UI"
                icon.source: AppAssets.actionDatabaseReload
                autoCompact: false
                Layout.minimumWidth: expandedImplicitWidth
                onClicked: root.load("manual")
            }
        }

        InlineMessage {
            Layout.fillWidth: true
            visible: root.message !== ""
            message: root.message
            severity: root.messageError ? "error" : "success"
        }
        SwitchSummaryBar { Layout.fillWidth: true; metrics: root.summaryMetrics }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8
            SegmentTab { label: "VLAN Protection"; selected: root.section === "vlans"; onClicked: root.section = "vlans" }
            SegmentTab { label: "Trusted Uplinks"; selected: root.section === "trust"; onClicked: root.section = "trust" }
            SegmentTab { label: "Static MAC"; selected: root.section === "staticMac"; onClicked: root.section = "staticMac" }
            Item { Layout.fillWidth: true }
            Text {
                visible: !root.compactLayout
                text: root.section === "vlans" ? "Per-VLAN controls"
                      : root.section === "trust" ? "Add-only safe workflow"
                                                   : "Pinned forwarding entries"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            SplitView {
                id: vlanSecuritySplit
                anchors.fill: parent
                visible: root.section === "vlans"
                orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
                handle: StandardSplitHandle { orientation: vlanSecuritySplit.orientation }

                DataTable {
                    SplitView.fillWidth: !root.compactLayout
                    SplitView.fillHeight: root.compactLayout
                    SplitView.minimumWidth: root.compactLayout ? 0 : 520
                    SplitView.minimumHeight: root.compactLayout ? 220 : 0
                    count: vlanPolicyModel.count
                    bodyMargins: 0
                    emptyTitle: "No VLANs available"
                    emptyDescription: "Create VLANs before enabling Layer 2 protections."
                    headerComponent: Component {
                        DataTableHeader {
                            RowLayout {
                                anchors.fill: parent
                                spacing: Theme.spacing8
                                DataTableCell { Layout.preferredWidth: 90; header: true; text: "VLAN" }
                                DataTableCell { Layout.fillWidth: true; header: true; text: "Name" }
                                DataTableCell { Layout.preferredWidth: 110; header: true; text: "Snooping" }
                                DataTableCell { Layout.preferredWidth: 80; header: true; text: "DAI" }
                            }
                        }
                    }
                    ListView {
                        anchors.fill: parent
                        clip: true
                        model: vlanPolicyModel
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        delegate: DataTableRow {
                            id: policyRow
                            required property int index
                            required property var model
                            width: ListView.view.width
                            height: Theme.tableRowHeight
                            rowIndex: index
                            selected: root.selectedPolicyIndex === index
                            RowLayout {
                                anchors.fill: parent
                                spacing: Theme.spacing8
                                DataTableCell { Layout.preferredWidth: 90; primary: true; text: String(policyRow.model.vlan_id) }
                                DataTableCell { Layout.fillWidth: true; text: policyRow.model.vlan_name || "—" }
                                DataTableCell { Layout.preferredWidth: 110; text: policyRow.model.dhcp_snooping ? "Enabled" : "Disabled"; color: policyRow.model.dhcp_snooping ? Theme.alertSuccess : Theme.textSecondary }
                                DataTableCell { Layout.preferredWidth: 80; text: policyRow.model.dai_enabled ? "Enabled" : "Disabled"; color: policyRow.model.dai_enabled ? Theme.alertSuccess : Theme.textSecondary }
                            }
                            TapHandler { onTapped: root.selectPolicy(policyRow.index) }
                        }
                    }
                }

                SwitchInspectorPane {
                    SplitView.fillWidth: root.compactLayout
                    SplitView.fillHeight: !root.compactLayout
                    SplitView.preferredWidth: root.compactLayout ? vlanSecuritySplit.width : 410
                    SplitView.minimumWidth: root.compactLayout ? 0 : 350
                    SplitView.minimumHeight: root.compactLayout ? 260 : 0
                    title: root.policyDraft.vlan_id ? "VLAN " + root.policyDraft.vlan_id : "VLAN protection"
                    subtitle: root.policyDraft.vlan_name || "DHCP and ARP validation"
                    hasContent: root.selectedPolicyIndex >= 0
                    editing: root.policyDirty
                    emptyTitle: "No VLAN selected"
                    emptyDescription: "Select a VLAN to configure its protection policy."

                    SwitchInspectorSection {
                        Layout.fillWidth: true
                        title: "DHCP Snooping"
                        helpText: "DHCP Snooping validates DHCP messages for this VLAN and learns IP-MAC-port bindings. Enable it only after identifying trusted uplinks; client-facing access ports should remain untrusted."
                        description: "Inspect DHCP exchanges and build the trusted binding database for this VLAN."
                        SwitchPropertyRow { label: "Push status"; value: String(root.policyDraft.success || "skipped").replace(/_/g, " ") }
                        StandardToggleButton {
                            objectName: "l2DhcpSnoopingToggle"
                            Layout.fillWidth: true
                            text: "Enable DHCP Snooping"
                            description: "Required before DAI can use dynamically learned bindings."
                            checked: Boolean(root.policyDraft.dhcp_snooping)
                            onToggled: {
                                root.updatePolicy("dhcp_snooping", checked)
                                // DAI in this workflow uses Snooping bindings.
                                // Turning Snooping off also turns DAI off so the
                                // saved policy always remains deployable.
                                if (!checked && Boolean(root.policyDraft.dai_enabled))
                                    root.updatePolicy("dai_enabled", false)
                            }
                        }
                    }
                    SwitchInspectorSection {
                        Layout.fillWidth: true
                        title: "Dynamic ARP Inspection"
                        helpText: "DAI validates ARP packets against DHCP Snooping or static bindings to prevent spoofing. DHCP Snooping must be enabled for dynamically learned clients, and uplinks toward legitimate infrastructure must be trusted."
                        description: "Validate ARP packets against trusted bindings on untrusted access ports."
                        showDivider: false
                        StandardToggleButton {
                            objectName: "l2DaiToggle"
                            Layout.fillWidth: true
                            text: "Enable DAI"
                            description: "Protect this VLAN from ARP spoofing."
                            checked: Boolean(root.policyDraft.dai_enabled)
                            onToggled: {
                                root.updatePolicy("dai_enabled", checked)
                                // One-click convenience: enabling DAI also
                                // enables its required DHCP Snooping bindings.
                                if (checked && !Boolean(root.policyDraft.dhcp_snooping))
                                    root.updatePolicy("dhcp_snooping", true)
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true

                            Item { Layout.fillWidth: true }
                            StandardButton {
                                text: "Delete Policy"
                                icon.source: AppAssets.actionDelete
                                type: "Danger"
                                visible: Number(root.policyDraft.id || 0) > 0
                                enabled: !root.saving
                                onClicked: root.deletePolicy()
                            }
                            StandardButton {
                                objectName: "l2PolicyCancelButton"
                                text: "Cancel"
                                icon.source: AppAssets.actionClear
                                type: "Text"
                                visible: root.policyDirty
                                enabled: !root.saving
                                onClicked: root.cancelPolicy()
                            }
                            StandardButton {
                                text: root.saving ? "Saving..." : "Save Policy"
                                icon.source: AppAssets.actionSave
                                type: "Primary"
                                enabled: root.policyDirty && !root.saving
                                onClicked: root.savePolicy()
                            }
                        }
                    }
                }
            }

            SplitView {
                id: trustPortSplit
                anchors.fill: parent
                visible: root.section === "trust"
                orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
                handle: StandardSplitHandle { orientation: trustPortSplit.orientation }

                DataTable {
                    SplitView.fillWidth: !root.compactLayout
                    SplitView.fillHeight: root.compactLayout
                    SplitView.minimumWidth: root.compactLayout ? 0 : 500
                    SplitView.minimumHeight: root.compactLayout ? 220 : 0
                    count: trustPortModel.count
                    bodyMargins: 0
                    emptyTitle: "No trusted uplinks"
                    emptyDescription: "Add a trunk or uplink that legitimately carries DHCP server traffic."
                    headerComponent: Component {
                        DataTableHeader {
                            RowLayout {
                                anchors.fill: parent
                                DataTableCell { Layout.fillWidth: true; header: true; text: "Trusted Interface" }
                                DataTableCell { Layout.preferredWidth: 180; header: true; text: "Applied Controls" }
                                DataTableCell { Layout.preferredWidth: 48; header: true; text: "" }
                            }
                        }
                    }
                    ListView {
                        anchors.fill: parent
                        model: trustPortModel
                        clip: true
                        delegate: DataTableRow {
                            required property var model
                            width: ListView.view.width
                            height: Theme.tableRowHeight
                            interactive: false
                            RowLayout {
                                anchors.fill: parent
                                DataTableCell { Layout.fillWidth: true; primary: true; text: model.if_name }
                                DataTableCell { Layout.preferredWidth: 180; text: "DHCP + ARP trust"; color: Theme.alertSuccess }
                                IconButton {
                                    Layout.preferredWidth: 48
                                    buttonSize: 28
                                    iconSize: Theme.iconSizeNormal
                                    iconSource: AppAssets.actionDelete
                                    danger: true
                                    tooltip: "Delete trusted uplink"
                                    enabled: !root.saving
                                    onClicked: root.deleteTrustPort(Number(model.id || 0))
                                }
                            }
                        }
                    }
                }

                FormSection {
                    SplitView.fillWidth: root.compactLayout
                    SplitView.fillHeight: !root.compactLayout
                    SplitView.preferredWidth: root.compactLayout ? trustPortSplit.width
                                                                 : Math.min(390, root.width * 0.38)
                    SplitView.minimumWidth: root.compactLayout ? 0 : 340
                    SplitView.minimumHeight: root.compactLayout ? 260 : 0
                    title: "Add trusted uplink"
                    helpText: "Layer 2 interface identifies the port toward a legitimate DHCP server or trusted upstream switch. Trust bypasses DHCP Snooping and DAI checks, so never trust ordinary client-facing access ports."

                    Text {
                        Layout.fillWidth: true
                        text: "Only interfaces that lead toward legitimate DHCP servers should be trusted."
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        wrapMode: Text.WordWrap
                    }
                    InlineMessage {
                        Layout.fillWidth: true
                        message: root.hasVlanProtection
                                 ? "Trust only the interface facing a legitimate DHCP server or upstream switch. Client-facing access ports must remain untrusted."
                                 : "No VLAN protection is enabled yet. You may select the uplink now, then enable DHCP Snooping in VLAN Protection before Push."
                        severity: root.hasVlanProtection ? "info" : "warning"
                    }
                    StandardComboBox {
                        id: trustInterfaceCombo
                        objectName: "trustInterfaceCombo"
                        Layout.fillWidth: true
                        labelText: "Layer 2 interface"
                        model: root.availableTrustInterfaceLabels()
                        valueModel: root.availableTrustInterfaces()
                        emptyText: root.refreshingReferences
                                   ? "Refreshing interfaces..."
                                   : "No Layer 2 interfaces available"
                        emptyWarningText: "No usable Layer 2 interface is available. Complete or synchronize the Interfaces tab, then return here or select Reload UI."
                    }
                    StandardButton {
                        Layout.alignment: Qt.AlignRight
                        text: "Add Trust Port"
                        type: "Primary"
                        enabled: trustInterfaceCombo.count > 0 && !root.saving
                        onClicked: root.addTrustPort(trustInterfaceCombo.currentValue)
                    }
                }
            }

            SplitView {
                id: staticMacSplit
                anchors.fill: parent
                visible: root.section === "staticMac"
                orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
                handle: StandardSplitHandle { orientation: staticMacSplit.orientation }

                DataTable {
                    SplitView.fillWidth: !root.compactLayout
                    SplitView.fillHeight: root.compactLayout
                    SplitView.minimumWidth: root.compactLayout ? 0 : 500
                    SplitView.minimumHeight: root.compactLayout ? 220 : 0
                    count: staticMacModel.count
                    bodyMargins: 0
                    emptyTitle: "No static MAC bindings"
                    emptyDescription: "Add a deterministic MAC-to-VLAN/interface forwarding entry."
                    headerComponent: Component {
                        DataTableHeader {
                            RowLayout {
                                anchors.fill: parent
                                DataTableCell { Layout.preferredWidth: 180; header: true; text: "MAC Address" }
                                DataTableCell { Layout.preferredWidth: 80; header: true; text: "VLAN" }
                                DataTableCell { Layout.fillWidth: true; header: true; text: "Interface" }
                            }
                        }
                    }
                    ListView {
                        anchors.fill: parent
                        model: staticMacModel
                        clip: true
                        delegate: DataTableRow {
                            id: staticRow
                            required property int index
                            required property var model
                            width: ListView.view.width
                            height: Theme.tableRowHeight
                            rowIndex: index
                            selected: root.selectedStaticIndex === index
                            interactive: root.staticFormMode === 0
                            RowLayout {
                                anchors.fill: parent
                                DataTableCell { Layout.preferredWidth: 180; primary: true; monospaced: true; text: staticRow.model.mac_addr }
                                DataTableCell { Layout.preferredWidth: 80; text: String(staticRow.model.vlan_id) }
                                DataTableCell { Layout.fillWidth: true; text: staticRow.model.if_name }
                            }
                            TapHandler { onTapped: root.selectStatic(staticRow.index) }
                        }
                    }
                }

                SwitchInspectorPane {
                    SplitView.fillWidth: root.compactLayout
                    SplitView.fillHeight: !root.compactLayout
                    SplitView.preferredWidth: root.compactLayout ? staticMacSplit.width : 420
                    SplitView.minimumWidth: root.compactLayout ? 0 : 350
                    SplitView.minimumHeight: root.compactLayout ? 280 : 0
                    title: root.staticFormMode === 1 ? "New Static MAC"
                           : root.staticDraft.mac_addr || "Static MAC details"
                    subtitle: "Pinned forwarding entry"
                    hasContent: root.staticFormMode !== 0 || root.selectedStaticIndex >= 0
                    editing: root.staticFormMode !== 0
                    emptyTitle: "No binding selected"
                    emptyDescription: "Select a binding, or choose Add to create one."

                    App.CrudFormActions {
                        Layout.fillWidth: true
                        formMode: root.staticFormMode
                        hasSelection: root.selectedStaticIndex >= 0
                        dirty: root.staticDirty
                        valid: String(root.staticDraft.mac_addr || "").trim() !== ""
                               && String(root.staticDraft.if_name || "").trim() !== ""
                               && Number(root.staticDraft.vlan_id || 0) > 0
                        saving: root.saving
                        allowEdit: false
                        allowDelete: root.selectedStaticIndex >= 0
                        onAddRequested: root.beginStaticCreate()
                        onEditRequested: root.beginStaticEdit()
                        onDeleteRequested: root.deleteStatic()
                        onRefreshRequested: root.load("manual")
                        onSaveRequested: root.saveStatic()
                        onCancelRequested: root.cancelStatic()
                    }
                    SwitchInspectorSection {
                        Layout.fillWidth: true
                        title: "Forwarding binding"
                        helpText: "MAC address identifies the client and is normalized to Cisco xxxx.xxxx.xxxx format. VLAN and Layer-2 interface define where the address is valid. Use static bindings for fixed hosts not learned through DHCP Snooping."
                        description: "The MAC address is normalized to Cisco xxxx.xxxx.xxxx notation."
                        showDivider: false
                        SwitchPropertyRow { visible: root.staticFormMode === 0; label: "MAC"; value: root.staticDraft.mac_addr || "—"; monospaced: true }
                        SwitchPropertyRow { visible: root.staticFormMode === 0; label: "VLAN"; value: String(root.staticDraft.vlan_id || "—") }
                        SwitchPropertyRow { visible: root.staticFormMode === 0; label: "Interface"; value: root.staticDraft.if_name || "—" }
                        SwitchPropertyRow { visible: root.staticFormMode === 0; label: "Push status"; value: String(root.staticDraft.success || "pending_apply").replace(/_/g, " ") }
                        StandardTextField {
                            Layout.fillWidth: true
                            visible: root.staticFormMode !== 0
                            labelText: "MAC address"
                            placeholderText: "0011.2233.4455"
                            text: String(root.staticDraft.mac_addr || "")
                            onTextEdited: value => root.updateStatic("mac_addr", value)
                        }
                        StandardComboBox {
                            Layout.fillWidth: true
                            visible: root.staticFormMode !== 0
                            labelText: "VLAN"
                            model: root.vlanLabels()
                            valueModel: root.vlanValues()
                            currentIndex: root.comboIndex(valueModel, Number(root.staticDraft.vlan_id || 0))
                            onActivated: index => root.updateStatic("vlan_id", Number(valueModel[index]))
                        }
                        StandardComboBox {
                            Layout.fillWidth: true
                            visible: root.staticFormMode !== 0
                            labelText: "Layer 2 interface"
                            model: root.interfaceNames()
                            currentIndex: root.comboIndex(model, String(root.staticDraft.if_name || ""))
                            onActivated: index => root.updateStatic("if_name", model[index])
                        }
                    }
                }
            }
        }
    }
}
