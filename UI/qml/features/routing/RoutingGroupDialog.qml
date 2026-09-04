pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// Four-step workflow for creating one OSPF/EIGRP configuration on many hosts.
StandardDialog {
    id: dialog

    property string protocol: "ospf"
    property int stepIndex: 0
    property var ownerForm: null
    property var hostRows: []
    property int selectedCount: 0
    readonly property int maxHosts: 5
    property string errorText: ""

    preferredWidth: 920
    height: Math.min(parent ? parent.height - 48 : 720, 760)
    title: "Routing Group · " + protocol.toUpperCase()
    subtitle: "Configure the same routing policy on multiple devices"

    ListModel { id: targetModel }

    function notify(message, type) {
        if (ownerForm && ownerForm.notify)
            ownerForm.notify(message, type)
    }

    function openFor(kind, form) {
        protocol = String(kind || "ospf").toLowerCase()
        ownerForm = form || null
        stepIndex = 0
        errorText = ""
        const result = dbManager.getRoutingGroupOptions()
        populateTargets(result && result.hosts ? result.hosts : [])
        open()
    }

    function populateTargets(rows) {
        hostRows = rows || []
        selectedCount = 0
        targetModel.clear()
        for (let i = 0; i < hostRows.length; i++) {
            targetModel.append({
                host: String(hostRows[i].host),
                deviceName: String(hostRows[i].device_name || ""),
                selected: false,
                processId: "",
                routerId: "",
                networks: hostRows[i].networks || []
            })
        }
    }

    function collectionCount(collection) {
        if (!collection)
            return 0
        if (typeof collection.count === "number")
            return collection.count
        return collection.length || 0
    }

    function collectionItem(collection, index) {
        if (collection && typeof collection.get === "function")
            return collection.get(index)
        return collection[index]
    }

    function updateSelected(index, selected) {
        if (index < 0 || index >= targetModel.count)
            return
        const row = targetModel.get(index)
        if (Boolean(row.selected) === Boolean(selected))
            return
        if (selected && selectedCount >= maxHosts) {
            errorText = "A Routing Group supports at most " + maxHosts + " hosts."
            targetModel.setProperty(index, "selected", false)
            return
        }
        targetModel.setProperty(index, "selected", selected)
        selectedCount += selected ? 1 : -1
        selectedCount = Math.max(0, selectedCount)
        errorText = ""
    }

    function selectedTargets() {
        const result = []
        for (let i = 0; i < targetModel.count; i++) {
            const row = targetModel.get(i)
            if (!row.selected)
                continue
            const networks = []
            const choices = row.networks || []
            for (let n = 0; n < collectionCount(choices); n++) {
                const choice = collectionItem(choices, n)
                if (choice.selected === true) {
                    networks.push({
                        network: choice.network,
                        wildcard: choice.wildcard,
                        area: choice.area || "0"
                    })
                }
            }
            const target = {
                host: row.host,
                router_id: String(row.routerId || "").trim(),
                networks: networks
            }
            if (protocol === "ospf")
                target.process_id = Number(row.processId)
            else
                target.as_number = Number(row.processId)
            result.push(target)
        }
        return result
    }

    function updateNetwork(hostIndex, networkIndex, field, value) {
        const row = targetModel.get(hostIndex)
        const networks = row.networks
        if (!networks || networkIndex < 0
                || networkIndex >= collectionCount(networks))
            return
        if (typeof networks.setProperty === "function") {
            networks.setProperty(networkIndex, field, value)
            return
        }
        const changedNetworks = networks.slice()
        const changed = Object.assign({}, changedNetworks[networkIndex])
        changed[field] = value
        changedNetworks[networkIndex] = changed
        targetModel.setProperty(hostIndex, "networks", changedNetworks)
    }

    function stepValid() {
        errorText = ""
        if (stepIndex === 0 && selectedCount < 2) {
            errorText = "Select at least two hosts."
            return false
        }
        if (stepIndex === 0 && selectedCount > maxHosts) {
            errorText = "Select no more than " + maxHosts + " hosts."
            return false
        }
        if (stepIndex === 1) {
            const routerIds = ({})
            for (let i = 0; i < targetModel.count; i++) {
                const row = targetModel.get(i)
                if (!row.selected)
                    continue
                if (String(row.processId || "").trim() === "" || Number(row.processId) < 1) {
                    errorText = "Enter a valid Process ID / AS Number for " + row.host + "."
                    return false
                }
                const routerId = String(row.routerId || "").trim()
                if (routerId !== "" && routerIds[routerId]) {
                    errorText = "Router ID " + routerId + " is duplicated."
                    return false
                }
                if (routerId !== "")
                    routerIds[routerId] = true
            }
        }
        if (stepIndex === 3) {
            const targets = selectedTargets()
            for (let t = 0; t < targets.length; t++) {
                if (targets[t].networks.length === 0) {
                    errorText = "Select at least one connected network for " + targets[t].host + "."
                    return false
                }
            }
        }
        return true
    }

    function commonParameters() {
        return commonStep.parameters()
    }

    function saveGroup(pushAfterSave) {
        if (!stepValid())
            return
        const result = dbManager.saveRoutingGroup(
            protocol, selectedTargets(), commonParameters())
        notify(String(result.message || ""), result.ok ? "success"
                                                       : (result.partial ? "warning" : "error"))
        if (result.ok || result.partial) {
            const hosts = result.successful || []
            close()
            if (ownerForm && ownerForm.loadFromDatabase
                    && hosts.indexOf(String(ownerForm.currentHostIp || "")) >= 0)
                ownerForm.loadFromDatabase()
            if (pushAfterSave)
                batchDialog.openPreview(hosts, protocol)
        }
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacing12

        RowLayout {
            Layout.fillWidth: true
            Repeater {
                model: ["1. Hosts", "2. Identity", "3. Common", "4. Networks"]
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
                        color: index === dialog.stepIndex
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

                RoutingGroupHostStep {
                    Layout.fillWidth: true
                    visible: dialog.stepIndex === 0
                    targetModel: targetModel
                    controller: dialog
                }
                RoutingGroupIdentityStep {
                    Layout.fillWidth: true
                    visible: dialog.stepIndex === 1
                    targetModel: targetModel
                    protocol: dialog.protocol
                }
                RoutingGroupCommonStep {
                    id: commonStep
                    Layout.fillWidth: true
                    visible: dialog.stepIndex === 2
                    protocol: dialog.protocol
                }
                RoutingGroupNetworkStep {
                    Layout.fillWidth: true
                    visible: dialog.stepIndex === 3
                    targetModel: targetModel
                    controller: dialog
                    protocol: dialog.protocol
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
                visible: dialog.stepIndex < 3
                text: "Next"
                type: "Primary"
                onClicked: {
                    if (dialog.stepValid())
                        dialog.stepIndex++
                }
            }
            StandardButton {
                visible: dialog.stepIndex === 3
                text: "Save"
                icon.source: AppAssets.actionSave
                type: "Secondary"
                onClicked: dialog.saveGroup(false)
            }
            StandardButton {
                visible: dialog.stepIndex === 3
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
        controllerName: "routing"
        featureLabel: dialog.protocol.toUpperCase()
        ownerForm: dialog.ownerForm
    }
}
