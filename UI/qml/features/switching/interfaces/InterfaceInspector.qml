pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

SwitchInspectorPane {
    id: root

    required property var draft
    property bool allowRouted: false
    property bool routedOnly: false
    property string viewMode: "interfaces"
    property bool modeOnly: false
    property bool allowModeChange: true
    property var availableVlans: []
    property bool dirty: false
    property bool valid: true
    property bool saving: false

    readonly property bool hasPort: String(value("if_name", "")).trim() !== ""
    readonly property bool accessPort: value("mode", "access") === "access"
    readonly property bool trunkPort: value("mode", "access") === "trunk"
    readonly property bool layer2Port: value("mode", "access") !== "routed"
    readonly property string profileTitle: viewMode === "portSecurity" ? "Port Security"
                                                   : routedOnly ? "Routed Port" : "Switch Port"

    signal fieldChanged(string name, var value)
    signal saveRequested()
    signal cancelRequested()

    function value(name, fallback) {
        const current = root.draft && root.draft[name]
        return current === undefined || current === null ? fallback : current
    }

    function comboIndex(model, value) {
        const index = model.indexOf(String(value))
        return index < 0 ? 0 : index
    }

    function enabledLabel(value) {
        return value === true || value === 1 || String(value) === "enabled" ? "Enabled" : "Disabled"
    }

    function vlanSummary() {
        if (root.accessPort) {
            const voice = root.value("voice_vlan", "")
            return "Access " + root.value("access_vlan", 1)
                    + (voice ? " · Voice " + voice : "")
        }
        if (root.trunkPort)
            return "Native " + root.value("native_vlan", 1)
                    + " · Allowed " + root.value("allowed_vlans", "all")
        return "Layer 3"
    }

    function allowedExpression() {
        return String(root.value("allowed_vlans", "all")).trim().toLowerCase()
    }

    function vlanIsAllowed(vlanId) {
        const expression = allowedExpression()
        if (expression === "all") return true
        if (expression === "" || expression === "none") return false
        const parts = expression.split(",")
        for (let i = 0; i < parts.length; i++) {
            const bounds = parts[i].trim().split("-")
            const first = Number(bounds[0])
            const last = bounds.length > 1 ? Number(bounds[1]) : first
            if (Number(vlanId) >= first && Number(vlanId) <= last) return true
        }
        return false
    }

    function selectedVlanIds() {
        const ids = []
        for (let i = 0; i < availableVlans.length; i++) {
            const vlanId = Number(availableVlans[i].vlan_id || 0)
            if (vlanId > 0 && vlanIsAllowed(vlanId)) ids.push(vlanId)
        }
        ids.sort(function(first, second) { return first - second })
        return ids
    }

    function compactVlanIds(ids) {
        if (!ids || ids.length === 0) return "none"
        const ranges = []
        let first = Number(ids[0])
        let last = first
        for (let i = 1; i < ids.length; i++) {
            const current = Number(ids[i])
            if (current === last + 1) {
                last = current
                continue
            }
            ranges.push(first === last ? String(first) : first + "-" + last)
            first = current
            last = current
        }
        ranges.push(first === last ? String(first) : first + "-" + last)
        return ranges.join(",")
    }

    function updateAllowedVlans(ids) {
        if (availableVlans.length > 0 && ids.length === availableVlans.length)
            root.fieldChanged("allowed_vlans", "all")
        else
            root.fieldChanged("allowed_vlans", compactVlanIds(ids))
    }

    function toggleAllVlans(selected) {
        root.fieldChanged("allowed_vlans", selected ? "all" : "none")
    }

    function toggleAllowedVlan(vlanId, selected) {
        const current = selectedVlanIds()
        const target = Number(vlanId)
        const next = []
        let found = false
        for (let i = 0; i < current.length; i++) {
            if (current[i] === target) found = true
            else next.push(current[i])
        }
        if (selected && !found) next.push(target)
        next.sort(function(first, second) { return first - second })
        updateAllowedVlans(next)
    }

    title: root.hasPort ? String(root.value("if_name", root.profileTitle)) : root.profileTitle
    subtitle: root.viewMode === "interfaces" ? "Port configuration"
             : "MAC admission policy"
    hasContent: root.editing || root.hasPort
    emptyTitle: "No port selected"
    emptyDescription: "Select a row to inspect it, then choose Edit to make changes."

    SwitchInspectorSection {
        Layout.fillWidth: true
        title: root.viewMode === "interfaces" ? "Identity and link" : "Target interface"
        helpText: "Interface identifies the physical switch port. Description documents its purpose. Mode selects access, trunk, or routed operation. Administrative state controls shutdown/no shutdown; operational state reports the observed link."
        description: root.viewMode === "interfaces"
                     ? root.modeOnly
                       ? "Review current link state before converting the port mode."
                       : "The physical identity and administrative link settings."
                     : "Security profiles are attached to an existing Layer 2 port."

        SwitchPropertyRow {
            visible: !root.editing || root.viewMode !== "interfaces"
            label: "Interface"
            value: String(root.value("if_name", "—"))
            emphasize: true
        }
        SwitchPropertyRow {
            visible: !root.editing && root.viewMode === "interfaces"
            label: "Description"
            value: String(root.value("description", "—"))
        }
        SwitchPropertyRow {
            visible: !root.editing || root.viewMode !== "interfaces"
            label: "Mode"
            value: String(root.value("mode", "access"))
        }
        SwitchPropertyRow {
            visible: !root.editing
            label: "Admin / Link"
            value: String(root.value("admin_status", "up")) + " / "
                   + String(root.value("oper_status", "unknown"))
            valueColor: root.value("oper_status", "unknown") === "up"
                        ? Theme.alertSuccess : Theme.textSecondary
        }
        SwitchPropertyRow {
            visible: !root.editing && root.viewMode === "interfaces"
            label: "Speed / Duplex"
            value: String(root.value("speed", "auto")) + " / "
                   + String(root.value("duplex", "auto"))
        }
        SwitchPropertyRow {
            visible: !root.editing
            label: "Push status"
            value: String(root.value(root.viewMode === "portSecurity"
                                     ? "port_security_success" : "success",
                                     root.viewMode === "portSecurity" ? "skipped" : "pending_apply"))
                   .replace(/_/g, " ")
        }

        StandardTextField {
            Layout.fillWidth: true
            visible: root.editing && root.viewMode === "interfaces" && !root.modeOnly
            labelText: "Interface name"
            readOnly: true
            text: String(root.value("if_name", ""))
            onTextEdited: value => root.fieldChanged("if_name", value)
        }
        StandardTextField {
            Layout.fillWidth: true
            visible: root.editing && root.viewMode === "interfaces" && !root.modeOnly
            labelText: "Description"
            text: String(root.value("description", ""))
            onTextEdited: value => root.fieldChanged("description", value)
        }
        StandardComboBox {
            Layout.fillWidth: true
            visible: root.editing && root.viewMode === "interfaces" && !root.modeOnly
            labelText: "Admin status"
            model: ["up", "down"]
            currentIndex: root.comboIndex(model, root.value("admin_status", "up"))
            onActivated: index => root.fieldChanged("admin_status", model[index])
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.editing && root.viewMode === "interfaces" && !root.modeOnly

            StandardComboBox {
                Layout.fillWidth: true
                labelText: "Speed"
                model: ["auto", "10", "100", "1000", "10000"]
                currentIndex: root.comboIndex(model, root.value("speed", "auto"))
                onActivated: index => root.fieldChanged("speed", model[index])
            }
            StandardComboBox {
                Layout.fillWidth: true
                labelText: "Duplex"
                model: ["auto", "full", "half"]
                currentIndex: root.comboIndex(model, root.value("duplex", "auto"))
                onActivated: index => root.fieldChanged("duplex", model[index])
            }
        }
    }

    SwitchInspectorSection {
        Layout.fillWidth: true
        visible: root.viewMode === "interfaces"
        title: "Port mode"
        helpText: "Access carries one untagged data VLAN. Trunk carries multiple VLANs using 802.1Q tags. Routed removes Layer-2 switchport behavior and makes the port suitable for Layer-3 addressing."
        description: root.modeOnly
                     ? "Change only between Access and Trunk; advanced settings live in their dedicated tabs."
                     : !root.allowModeChange
                       ? "Mode is fixed in this tab. Use Port Status to convert the port."
                     : root.routedOnly
                     ? "Routed ports do not participate in Layer 2 VLAN forwarding."
                     : "Choose Access or Trunk; the matching configuration form appears below."

        SwitchPropertyRow {
            visible: !root.editing || !root.allowModeChange
            label: "Mode"
            value: String(root.value("mode", "access"))
            emphasize: true
        }
        StandardComboBox {
            Layout.fillWidth: true
            visible: root.editing && root.allowModeChange
            labelText: "Mode"
            model: root.routedOnly ? ["routed"]
                 : root.allowRouted ? ["access", "trunk", "routed"]
                 : ["access", "trunk"]
            currentIndex: root.comboIndex(model, root.value("mode", "access"))
            onActivated: index => root.fieldChanged("mode", model[index])
        }
    }

    SwitchInspectorSection {
        Layout.fillWidth: true
        visible: root.viewMode === "interfaces" && root.accessPort && !root.modeOnly
        title: "Access configuration"
        helpText: "Access VLAN is the untagged data VLAN assigned to this port, normally 1-4094. Voice VLAN is an optional separate VLAN advertised to an attached IP phone. Both VLANs should already exist."
        description: "One untagged data VLAN with an optional voice VLAN."

        SwitchPropertyRow {
            visible: !root.editing
            label: "Access VLAN"
            value: String(root.value("access_vlan", 1))
            emphasize: true
        }
        SwitchPropertyRow {
            visible: !root.editing
            label: "Voice VLAN"
            value: String(root.value("voice_vlan", "") || "None")
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.editing

            StandardTextField {
                Layout.fillWidth: true
                labelText: "Access VLAN"
                text: String(root.value("access_vlan", 1))
                onTextEdited: value => root.fieldChanged("access_vlan", value)
            }
            StandardTextField {
                Layout.fillWidth: true
                labelText: "Voice VLAN"
                placeholderText: "Optional"
                text: String(root.value("voice_vlan", ""))
                onTextEdited: value => root.fieldChanged("voice_vlan", value)
            }
        }
    }

    SwitchInspectorSection {
        Layout.fillWidth: true
        visible: root.viewMode === "interfaces" && root.trunkPort && !root.modeOnly
        title: "Trunk configuration"
        helpText: "Allowed VLANs limits which VLAN tags cross the trunk; use IOS list/range syntax or all. Native VLAN is sent untagged and must match the peer. Encapsulation is normally dot1q. Pruning limits unnecessary VLAN forwarding."
        description: "Tagged VLAN transport with explicit native VLAN and encapsulation."

        SwitchPropertyRow {
            visible: !root.editing
            label: "Allowed VLANs"
            value: String(root.value("allowed_vlans", "all"))
            emphasize: true
        }
        SwitchPropertyRow {
            visible: !root.editing
            label: "Native VLAN"
            value: String(root.value("native_vlan", 1))
        }
        SwitchPropertyRow {
            visible: !root.editing
            label: "Encapsulation"
            value: String(root.value("encapsulation", "dot1q"))
        }
        SwitchPropertyRow {
            visible: !root.editing
            label: "Pruning"
            value: String(root.value("pruning_vlans", "none"))
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: root.editing
            spacing: Theme.spacing8

            Text {
                Layout.fillWidth: true
                text: "Allowed VLANs"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
            StandardCheckBox {
                id: allVlansCheckbox
                objectName: "trunkAllVlansCheckbox"
                Layout.fillWidth: true
                text: "All VLANs"
                checked: root.allowedExpression() === "all"
                onToggled: root.toggleAllVlans(checked)
            }
            GridLayout {
                Layout.fillWidth: true
                columns: root.width >= 390 ? 2 : 1
                columnSpacing: Theme.spacing12
                rowSpacing: Theme.spacing4

                Repeater {
                    model: root.availableVlans
                    delegate: StandardCheckBox {
                        required property var modelData
                        Layout.fillWidth: true
                        text: "VLAN " + String(modelData.vlan_id)
                              + (String(modelData.vlan_name || "") !== ""
                                 ? " — " + String(modelData.vlan_name) : "")
                        checked: root.vlanIsAllowed(Number(modelData.vlan_id))
                        onToggled: root.toggleAllowedVlan(
                            Number(modelData.vlan_id), checked
                        )
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                visible: root.availableVlans.length === 0
                text: "No VLANs are available. Create VLANs in the VLAN tab first."
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                visible: root.availableVlans.length > 0
                text: "Selected: " + String(root.value("allowed_vlans", "all"))
                color: Theme.textSecondary
                font.family: Theme.monoFontFamily
                font.pixelSize: Theme.fontSizeSmall
                elide: Text.ElideRight
            }
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.editing

            StandardTextField {
                Layout.fillWidth: true
                labelText: "Native VLAN"
                text: String(root.value("native_vlan", 1))
                onTextEdited: value => root.fieldChanged("native_vlan", value)
            }
            StandardComboBox {
                Layout.fillWidth: true
                labelText: "Encapsulation"
                model: ["dot1q", "isl"]
                currentIndex: root.comboIndex(model, root.value("encapsulation", "dot1q"))
                onActivated: index => root.fieldChanged("encapsulation", model[index])
            }
        }
        StandardTextField {
            Layout.fillWidth: true
            visible: root.editing
            labelText: "Pruning VLANs"
            placeholderText: "none or 10,20-30"
            text: String(root.value("pruning_vlans", "none"))
            onTextEdited: value => root.fieldChanged("pruning_vlans", value)
        }
    }

    SwitchInspectorSection {
        Layout.fillWidth: true
        visible: root.viewMode === "interfaces" && root.layer2Port && !root.modeOnly
        title: "Loop protection"
        helpText: "PortFast skips normal STP convergence and should be used only on edge ports. BPDU Guard disables an edge port that receives BPDUs. BPDU Filter suppresses BPDUs and requires caution. Root Guard blocks an unexpected superior root; Loop Guard protects against missing BPDUs on redundant links."
        description: "Edge and guard controls for Layer 2 topology safety."
        showDivider: false

        SwitchPropertyRow { visible: !root.editing; label: "PortFast"; value: root.enabledLabel(root.value("portfast", "disabled")) }
        SwitchPropertyRow { visible: !root.editing; label: "BPDU Guard"; value: root.enabledLabel(root.value("bpduguard", "disabled")) }
        SwitchPropertyRow { visible: !root.editing; label: "BPDU Filter"; value: root.enabledLabel(root.value("bpdufilter", "disabled")) }
        SwitchPropertyRow { visible: !root.editing; label: "Root Guard"; value: root.enabledLabel(root.value("root_guard", "disabled")) }
        SwitchPropertyRow { visible: !root.editing; label: "Loop Guard"; value: root.enabledLabel(root.value("loop_guard", "disabled")) }

        GridLayout {
            Layout.fillWidth: true
            visible: root.editing
            columns: root.width >= 390 ? 2 : 1
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing4

            StandardCheckBox { text: "PortFast"; checked: root.value("portfast", "disabled") === "enabled"; onToggled: root.fieldChanged("portfast", checked ? "enabled" : "disabled") }
            StandardCheckBox { text: "BPDU Guard"; checked: root.value("bpduguard", "disabled") === "enabled"; onToggled: root.fieldChanged("bpduguard", checked ? "enabled" : "disabled") }
            StandardCheckBox { text: "BPDU Filter"; checked: root.value("bpdufilter", "disabled") === "enabled"; onToggled: root.fieldChanged("bpdufilter", checked ? "enabled" : "disabled") }
            StandardCheckBox { text: "Root Guard"; checked: root.value("root_guard", "disabled") === "enabled"; onToggled: root.fieldChanged("root_guard", checked ? "enabled" : "disabled") }
            StandardCheckBox { text: "Loop Guard"; checked: root.value("loop_guard", "disabled") === "enabled"; onToggled: root.fieldChanged("loop_guard", checked ? "enabled" : "disabled") }
        }
    }

    SwitchInspectorSection {
        objectName: "switchPortSecuritySection"
        Layout.fillWidth: true
        visible: root.viewMode === "portSecurity" && root.layer2Port
        title: "MAC admission policy"
        helpText: "Enable Port Security to restrict learned source MAC addresses. Maximum MAC sets the allowed count. Violation chooses protect, restrict, or shutdown behavior. Sticky saves dynamically learned addresses. Aging type/time controls when secure MAC entries expire."
        description: "Limit learned source addresses and define violation handling."
        showDivider: false

        SwitchPropertyRow { visible: !root.editing; label: "Policy"; value: root.enabledLabel(Boolean(root.value("port_security_enabled", 0))); valueColor: root.value("port_security_enabled", 0) ? Theme.alertSuccess : Theme.textSecondary }
        SwitchPropertyRow { visible: !root.editing; label: "Maximum MAC"; value: String(root.value("max_mac", 1)) }
        SwitchPropertyRow { visible: !root.editing; label: "Violation"; value: String(root.value("violation", "shutdown")) }
        SwitchPropertyRow { visible: !root.editing; label: "Sticky learning"; value: root.value("sticky", 0) ? "Enabled" : "Disabled" }
        SwitchPropertyRow { visible: !root.editing; label: "Aging"; value: String(root.value("aging_type", "absolute")) + " · " + String(root.value("aging_time", 0)) }

        StandardToggleButton {
            Layout.fillWidth: true
            visible: root.editing
            text: "Enable Port Security"
            description: "Enforce the MAC admission policy on this access port."
            checked: Boolean(root.value("port_security_enabled", 0))
            onToggled: root.fieldChanged("port_security_enabled", checked)
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.editing
            enabled: Boolean(root.value("port_security_enabled", 0))

            StandardTextField {
                Layout.fillWidth: true
                labelText: "Maximum MAC"
                text: String(root.value("max_mac", 1))
                onTextEdited: value => root.fieldChanged("max_mac", value)
            }
            StandardComboBox {
                Layout.fillWidth: true
                labelText: "Violation action"
                model: ["shutdown", "restrict", "protect"]
                currentIndex: root.comboIndex(model, root.value("violation", "shutdown"))
                onActivated: index => root.fieldChanged("violation", model[index])
            }
        }
        StandardCheckBox {
            visible: root.editing
            enabled: Boolean(root.value("port_security_enabled", 0))
            text: "Sticky MAC learning"
            checked: Boolean(root.value("sticky", 0))
            onToggled: root.fieldChanged("sticky", checked)
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.editing
            enabled: Boolean(root.value("port_security_enabled", 0))

            StandardComboBox {
                Layout.fillWidth: true
                labelText: "Aging type"
                model: ["absolute", "inactivity"]
                currentIndex: root.comboIndex(model, root.value("aging_type", "absolute"))
                onActivated: index => root.fieldChanged("aging_type", model[index])
            }
            StandardTextField {
                Layout.fillWidth: true
                labelText: "Aging time"
                text: String(root.value("aging_time", 0))
                onTextEdited: value => root.fieldChanged("aging_time", value)
            }
        }
    }

    CrudFormActions {
        objectName: "switchPortEditorActions"
        Layout.fillWidth: true
        visible: root.editing
        formMode: root.editing ? 2 : 0
        dirty: root.dirty
        valid: root.valid
        saving: root.saving
        allowCreate: false
        allowEdit: false
        allowRefresh: false
        onSaveRequested: root.saveRequested()
        onCancelRequested: root.cancelRequested()
    }

}
