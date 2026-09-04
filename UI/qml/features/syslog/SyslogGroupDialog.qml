pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// Three-step batch workflow modeled after Routing Group. Shared policy fields
// are entered once; only the source interface varies by device.
StandardDialog {
    id: dialog

    property var ownerForm: null
    property int stepIndex: 0
    property int selectedCount: 0
    readonly property int maxHosts: 5
    property string errorText: ""
    property string serverIp: ""
    property string transport: "udp"
    property int serverPort: 5514
    property int trapSeverity: 5
    property bool timestamps: true
    property bool sequenceNumbers: true

    preferredWidth: 860
    height: Math.min(parent ? parent.height - 48 : 700, 720)
    title: "Syslog Group"
    subtitle: "Stage one practical Syslog policy on multiple Cisco devices"

    ListModel { id: targetModel }

    function collectionCount(collection) {
        if (!collection) return 0
        if (typeof collection.count === "number") return collection.count
        return collection.length || 0
    }

    function collectionItem(collection, index) {
        if (collection && typeof collection.get === "function")
            return collection.get(index)
        return collection[index]
    }

    function interfaceNames(collection) {
        const names = []
        for (let i = 0; i < collectionCount(collection); ++i) {
            const item = collectionItem(collection, i)
            names.push(String(item && item.name !== undefined ? item.name : item || ""))
        }
        return names
    }

    function interfaceIndex(collection, value) {
        const target = String(value || "").toLocaleLowerCase()
        const names = interfaceNames(collection)
        for (let i = 0; i < names.length; ++i) {
            if (names[i].toLocaleLowerCase() === target) return i
        }
        return -1
    }

    function notify(message, isError) {
        if (!ownerForm) return
        if (ownerForm.notify) {
            ownerForm.notify(message, isError ? "error" : "success")
            return
        }
        ownerForm.message = String(message || "")
        ownerForm.messageError = Boolean(isError)
    }

    function openFor(form, preselectedHosts) {
        ownerForm = form || null
        stepIndex = 0
        selectedCount = 0
        errorText = ""
        targetModel.clear()
        const backend = typeof syslogManager !== "undefined" ? syslogManager : null
        if (backend === null || typeof backend.getSyslogGroupOptions !== "function") {
            notify("Syslog Group backend is unavailable.", true)
            return
        }
        const result = backend.getSyslogGroupOptions()
        if (!result || !result.ok) {
            notify(String(result && result.message || "Could not load Syslog Group options."), true)
            return
        }
        populateOptions(result)
        const requested = preselectedHosts || []
        for (let requestedIndex = 0; requestedIndex < requested.length; ++requestedIndex) {
            for (let rowIndex = 0; rowIndex < targetModel.count; ++rowIndex) {
                if (String(targetModel.get(rowIndex).host || "")
                        === String(requested[requestedIndex] || "")) {
                    updateSelected(rowIndex, true)
                    break
                }
            }
        }
        open()
    }

    function populateOptions(result) {
        selectedCount = 0
        targetModel.clear()
        const defaults = result.defaults || ({})
        serverIp = String(defaults.server_ip || "")
        transport = String(defaults.protocol || "udp").toLowerCase()
        serverPort = Number(defaults.port || 5514)
        trapSeverity = Number(defaults.trap_severity === undefined
                              ? 5 : defaults.trap_severity)
        timestamps = defaults.timestamps === undefined ? true : Boolean(defaults.timestamps)
        sequenceNumbers = defaults.sequence_numbers === undefined
                          ? true : Boolean(defaults.sequence_numbers)
        const hosts = result.hosts || []
        for (let i = 0; i < hosts.length; ++i) {
            targetModel.append({
                host: String(hosts[i].host || ""),
                deviceName: String(hosts[i].device_name || ""),
                roleName: String(hosts[i].role || ""),
                selected: false,
                interfaces: hosts[i].interfaces || [],
                sourceInterface: String(hosts[i].recommended_interface || "")
            })
        }
    }

    function updateSelected(index, selected) {
        if (index < 0 || index >= targetModel.count) return
        const row = targetModel.get(index)
        if (Boolean(row.selected) === Boolean(selected)) return
        if (selected && selectedCount >= maxHosts) {
            errorText = "A Syslog Group supports at most " + maxHosts + " hosts."
            targetModel.setProperty(index, "selected", false)
            return
        }
        targetModel.setProperty(index, "selected", selected)
        selectedCount = Math.max(0, selectedCount + (selected ? 1 : -1))
        errorText = ""
    }

    function selectedTargets() {
        const targets = []
        for (let i = 0; i < targetModel.count; ++i) {
            const row = targetModel.get(i)
            if (row.selected) {
                targets.push({
                    host: String(row.host || "").trim(),
                    source_interface: String(row.sourceInterface || "").trim()
                })
            }
        }
        return targets
    }

    function commonPolicy() {
        return {
            server_ip: String(serverIp || "").trim(),
            protocol: transport,
            port: serverPort,
            trap_severity: trapSeverity,
            timestamps: timestamps,
            sequence_numbers: sequenceNumbers
        }
    }

    function stepValid() {
        errorText = ""
        if (stepIndex === 0 && selectedCount < 2) {
            errorText = "Select at least two hosts."
            return false
        }
        if (stepIndex === 1) {
            const targets = selectedTargets()
            for (let i = 0; i < targets.length; ++i) {
                if (targets[i].source_interface === "") {
                    errorText = "Select a source interface for " + targets[i].host + "."
                    return false
                }
            }
        }
        if (stepIndex === 2) {
            if (String(serverIp || "").trim() === "") {
                errorText = "Enter the Syslog server IP."
                return false
            }
            if (serverPort < 1 || serverPort > 65535) {
                errorText = "Port must be between 1 and 65535."
                return false
            }
        }
        return true
    }

    function saveGroup(pushAfterSave) {
        if (!stepValid()) return
        const backend = typeof syslogManager !== "undefined" ? syslogManager : null
        if (backend === null || typeof backend.saveSyslogGroup !== "function") {
            notify("Syslog Group backend is unavailable.", true)
            return
        }
        const result = backend.saveSyslogGroup(selectedTargets(), commonPolicy())
        notify(String(result.message || ""), !result.ok)
        if (result.ok || result.partial) {
            const hosts = result.successful || []
            close()
            if (ownerForm && ownerForm.reloadData) {
                const ownerHost = String(ownerForm.host || "")
                if (ownerHost === "" || hosts.indexOf(ownerHost) >= 0)
                    ownerForm.reloadData("groupSaved")
            }
            if (pushAfterSave)
                batchDialog.openPreview(hosts, "servers")
        }
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacing12

        RowLayout {
            Layout.fillWidth: true
            Repeater {
                model: ["1. Hosts", "2. Interfaces", "3. Policy"]
                delegate: Rectangle {
                    required property int index
                    required property string modelData
                    Layout.fillWidth: true
                    implicitHeight: 34
                    radius: Theme.radiusSmall
                    color: index === dialog.stepIndex
                           ? Theme.accentColor : Theme.contentPanelSurface
                    border.color: index <= dialog.stepIndex
                                  ? Theme.accentColor : Theme.borderColor
                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        color: parent.index === dialog.stepIndex
                               ? Theme.buttonTextSolid : Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        font.bold: true
                    }
                }
            }
        }

        InlineMessage {
            Layout.fillWidth: true
            visible: dialog.errorText !== ""
            severity: "warning"
            message: dialog.errorText
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: Theme.spacing12

                FormSection {
                    Layout.fillWidth: true
                    visible: dialog.stepIndex === 0
                    title: "Select participating hosts (2–5 devices)"
                    helpTitle: "Syslog Group host selection"
                    helpText: "Participating hosts: Select between two and five connected Cisco IOS/IOS-XE devices. Each host is saved independently, so one failure does not roll back successful hosts.\n\nInterface count: Number of synchronized source-interface candidates owned by that device. A host without interface inventory is disabled until Interfaces or Switching data is synchronized."

                    Repeater {
                        model: targetModel
                        delegate: RowLayout {
                            required property int index
                            required property string host
                            required property string deviceName
                            required property string roleName
                            required property bool selected
                            required property var interfaces
                            Layout.fillWidth: true
                            StandardCheckBox {
                                text: host
                                checked: selected
                                enabled: selected
                                         || (dialog.collectionCount(interfaces) > 0
                                             && dialog.selectedCount < dialog.maxHosts)
                                onToggled: dialog.updateSelected(index, checked)
                            }
                            Text {
                                Layout.fillWidth: true
                                text: deviceName + (roleName ? " · " + roleName.toUpperCase() : "")
                                color: Theme.textSecondary
                                font.family: Theme.fontFamily
                            }
                            StandardBadge {
                                text: dialog.collectionCount(interfaces) > 0
                                      ? dialog.collectionCount(interfaces) + " interfaces"
                                      : "Inventory required"
                                badgeColor: dialog.collectionCount(interfaces) > 0
                                            ? Theme.accentEmphasis : Theme.badgeWarningBg
                                textColor: dialog.collectionCount(interfaces) > 0
                                           ? Theme.buttonTextSolid : Theme.badgeWarningText
                            }
                        }
                    }
                    InlineMessage {
                        Layout.fillWidth: true
                        visible: targetModel.count === 0
                        severity: "warning"
                        message: "No connected Cisco IOS/IOS-XE devices are available."
                    }
                }

                FormSection {
                    Layout.fillWidth: true
                    visible: dialog.stepIndex === 1
                    title: "Choose one source interface per host"
                    helpTitle: "Per-host source interface"
                    helpText: "Source interface: Cisco interface whose IP address is used as the source of outgoing Syslog packets. Loopback is preferred for stable identity; otherwise choose the management interface or reachable SVI. The interface must belong to the selected host."

                    Repeater {
                        model: targetModel
                        delegate: RowLayout {
                            required property int index
                            required property string host
                            required property bool selected
                            required property var interfaces
                            required property string sourceInterface
                            visible: selected
                            Layout.fillWidth: true
                            Text {
                                Layout.preferredWidth: 190
                                text: host
                                color: Theme.textPrimary
                                font.family: Theme.fontFamily
                            }
                            StandardComboBox {
                                Layout.fillWidth: true
                                labelText: "Source interface"
                                model: dialog.interfaceNames(interfaces)
                                currentIndex: dialog.interfaceIndex(interfaces, sourceInterface)
                                emptyText: "No synchronized interfaces"
                                emptyWarningText: "Synchronize interface inventory before using Syslog Group."
                                onActivated: comboIndex => targetModel.setProperty(
                                                 index, "sourceInterface",
                                                 dialog.interfaceNames(interfaces)[comboIndex])
                            }
                        }
                    }
                }

                FormSection {
                    Layout.fillWidth: true
                    visible: dialog.stepIndex === 2
                    title: "Shared Syslog destination and message policy"
                    helpTitle: "Shared Syslog policy"
                    helpText: "Server IP: Reachable IPv4 or IPv6 address of the Syslog collector.\n\nTransport: UDP is lightweight; TCP provides a connection-oriented stream. It must match the collector.\n\nPort: Destination port from 1 to 65535; it should match Listener port when sending to CAMS.\n\nTrap severity: Highest verbosity sent by Cisco, from 0 Emergency through 7 Debug.\n\nMillisecond timestamps: Adds precise event time.\n\nSequence numbers: Adds an increasing device-side message number for ordering and troubleshooting."

                    StandardTextField {
                        Layout.fillWidth: true
                        labelText: "Server IP"
                        placeholderText: "192.0.2.100"
                        text: dialog.serverIp
                        onTextEdited: value => dialog.serverIp = value.trim()
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        StandardComboBox {
                            Layout.fillWidth: true
                            labelText: "Transport"
                            model: ["UDP", "TCP"]
                            currentIndex: dialog.transport === "tcp" ? 1 : 0
                            onActivated: index => dialog.transport = index === 1 ? "tcp" : "udp"
                        }
                        StandardSpinBox {
                            Layout.fillWidth: true
                            labelText: "Port"
                            from: 1
                            to: 65535
                            value: dialog.serverPort
                            onValueChanged: dialog.serverPort = value
                        }
                    }
                    StandardComboBox {
                        Layout.fillWidth: true
                        labelText: "Trap severity"
                        model: [
                            "0 · Emergencies", "1 · Alerts", "2 · Critical",
                            "3 · Errors", "4 · Warnings", "5 · Notifications",
                            "6 · Informational", "7 · Debugging"
                        ]
                        currentIndex: dialog.trapSeverity
                        onActivated: index => dialog.trapSeverity = index
                    }
                    StandardCheckBox {
                        text: "Include millisecond log timestamps"
                        checked: dialog.timestamps
                        onToggled: dialog.timestamps = checked
                    }
                    StandardCheckBox {
                        text: "Include sequence numbers"
                        checked: dialog.sequenceNumbers
                        onToggled: dialog.sequenceNumbers = checked
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardButton {
                text: "Back"
                type: "Text"
                enabled: dialog.stepIndex > 0
                onClicked: dialog.stepIndex--
            }
            Item { Layout.fillWidth: true }
            StandardButton {
                text: "Cancel"
                type: "Text"
                onClicked: dialog.close()
            }
            StandardButton {
                visible: dialog.stepIndex < 2
                text: "Next"
                type: "Primary"
                onClicked: {
                    if (dialog.stepValid()) dialog.stepIndex++
                }
            }
            StandardButton {
                visible: dialog.stepIndex === 2
                text: "Save"
                icon.source: AppAssets.actionSave
                type: "Secondary"
                onClicked: dialog.saveGroup(false)
            }
            StandardButton {
                visible: dialog.stepIndex === 2
                text: "Save & Push"
                icon.source: AppAssets.actionSave
                type: "Primary"
                onClicked: dialog.saveGroup(true)
            }
        }
    }

    MultiHostViewPushDialog {
        id: batchDialog
        parent: Overlay.overlay
        controllerName: "syslog"
        featureLabel: "Syslog Group"
        ownerForm: dialog.ownerForm
    }
}
