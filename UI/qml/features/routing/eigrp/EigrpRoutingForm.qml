pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

FormLayout {
    id: eigrpRoutingForm

    signal routingGroupRequested(string protocol)

    title: "EIGRP Routing"
    hostIp: currentHostIp
    isDirty: hasPendingLocalChanges
    errorMessage: ""
    showHeader: false
    pinnedContent: EigrpPinnedHeader { form: eigrpRoutingForm }

    property string currentHostIp: ""
    property bool isLoading: false
    property bool isSaving: false
    property bool hasPendingLocalChanges: false
    property string lastError: ""
    property string loadedProcessesSignature: "[]"
    property int nextUid: 1
    property int statsRevision: 0
    property string activeRoutingSection: "Process"
    property int selectedNetworkProcessIndex: 0
    property int processCount: processModel.count
    property var processOptions: []
    property var processPayloadByUid: ({})
    property int viewPushRevision: 0

    ListModel { id: processModel }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function showValidation(message) {
        notify(message, "error")
    }

    function resetProcessModel() {
        processModel.clear()
        processPayloadByUid = ({})
    }

    function processPayloadForUid(processUid) {
        const key = String(processUid)
        return processPayloadByUid[key] !== undefined ? processPayloadByUid[key] : ({})
    }

    function processItems() {
        const items = []
        for (let i = 0; i < processRepeater.count; i++) {
            const item = processRepeater.itemAt(i)
            if (item)
                items.push(item)
        }
        return items
    }

    function currentProcessesSignature() {
        const processes = []
        const items = processItems()
        for (let i = 0; i < items.length; i++)
            processes.push(items[i].signatureData())
        return JSON.stringify(processes)
    }

    function refreshDirtyFlag() {
        if (!isLoading && !isSaving)
            hasPendingLocalChanges = currentProcessesSignature() !== loadedProcessesSignature
    }

    function refreshStats() {
        statsRevision += 1
    }

    function processOptionLabel(index) {
        const item = processRepeater.itemAt(index)
        const host = String(currentHostIp || "").trim()
        if (!item)
            return "Process %1".arg(index + 1)

        const asText = String(item.processId || "").trim()
        const processText = asText !== "" ? ("AS " + asText) : "Process %1".arg(index + 1)
        return (host !== "" ? host : "Host") + " / " + processText
    }

    function rebuildProcessOptions() {
        const options = []
        for (let i = 0; i < processRepeater.count; i++)
            options.push(processOptionLabel(i))
        processOptions = options

        if (processOptions.length === 0)
            selectedNetworkProcessIndex = 0
        else if (selectedNetworkProcessIndex >= processOptions.length)
            selectedNetworkProcessIndex = processOptions.length - 1
    }

    function selectedNetworkProcessItem() {
        if (selectedNetworkProcessIndex < 0 || selectedNetworkProcessIndex >= processRepeater.count)
            return null
        return processRepeater.itemAt(selectedNetworkProcessIndex)
    }

    function selectedProcessItem() {
        return selectedNetworkProcessItem()
    }

    function totalNetworkCount() {
        const revision = statsRevision
        let total = 0
        const items = processItems()
        for (let i = 0; i < items.length; i++)
            total += items[i].networks.count
        return total
    }

    function totalChildCount(modelName) {
        const revision = statsRevision
        let total = 0
        const items = processItems()
        for (let i = 0; i < items.length; i++) {
            if (items[i][modelName])
                total += items[i][modelName].count
        }
        return total
    }

    function handleCardChanged() {
        refreshDirtyFlag()
        refreshStats()
        rebuildProcessOptions()
    }

    function selectRoutingSection(sectionName) {
        activeRoutingSection = sectionName
    }

    function addNetworkToSelectedProcess(network, wildcard, interfaceName) {
        const item = selectedProcessItem()
        const networkText = String(network || "").trim()
        if (!item || networkText === "") {
            notify("Process and network are required.", "warning")
            return false
        }
        item.networks.append({
            network: networkText,
            wildcard: String(wildcard || "").trim(),
            interface_name: String(interfaceName || "").trim()
        })
        handleCardChanged()
        notify("Added EIGRP network.", "info")
        return true
    }

    function removeNetworkFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (!item || rowIndex < 0 || rowIndex >= item.networks.count)
            return
        item.networks.remove(rowIndex)
        handleCardChanged()
    }

    function addInterfaceSettingToSelectedProcess(interfaceName, bandwidth, delay, hello, hold, authKeyChain, summaryIp, summaryMask, splitHorizon, bandwidthPercent, nextHopSelf, bfd, bfdTx, bfdRx, bfdMultiplier) {
        const item = selectedProcessItem()
        const iface = String(interfaceName || "").trim()
        if (!item || iface === "") {
            notify("Process and interface name are required.", "warning")
            return false
        }
        item.interfaceSettings.append({
            interface_name: iface,
            bandwidth: String(bandwidth || "").trim(),
            delay: String(delay || "").trim(),
            hello_interval: String(hello || "").trim(),
            hold_time: String(hold || "").trim(),
            auth_key_chain: String(authKeyChain || "").trim(),
            summary_ip: String(summaryIp || "").trim(),
            summary_mask: String(summaryMask || "").trim(),
            split_horizon: splitHorizon,
            bandwidth_percent: String(bandwidthPercent || "").trim(),
            next_hop_self: nextHopSelf,
            bfd: bfd,
            bfd_tx: String(bfdTx || "").trim(),
            bfd_rx: String(bfdRx || "").trim(),
            bfd_multiplier: String(bfdMultiplier || "").trim()
        })
        handleCardChanged()
        notify("Added EIGRP interface setting.", "info")
        return true
    }

    function removeInterfaceSettingFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (item && rowIndex >= 0 && rowIndex < item.interfaceSettings.count) {
            item.interfaceSettings.remove(rowIndex)
            handleCardChanged()
        }
    }

    function addPassiveInterfaceToSelectedProcess(interfaceName, mode) {
        const item = selectedProcessItem()
        const iface = String(interfaceName || "").trim()
        if (!item || iface === "") {
            notify("Process and interface name are required.", "warning")
            return false
        }
        item.passiveInterfaces.append({ interface_name: iface, mode: mode || "passive" })
        handleCardChanged()
        return true
    }

    function removePassiveInterfaceFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (item && rowIndex >= 0 && rowIndex < item.passiveInterfaces.count) {
            item.passiveInterfaces.remove(rowIndex)
            handleCardChanged()
        }
    }

    function addDistributeListToSelectedProcess(listName, direction, interfaceName) {
        const item = selectedProcessItem()
        const name = String(listName || "").trim()
        if (!item || name === "") {
            notify("Process and list name are required.", "warning")
            return false
        }
        item.distributeLists.append({ list_name: name, direction: direction || "in", interface_name: String(interfaceName || "").trim() })
        handleCardChanged()
        return true
    }

    function removeDistributeListFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (item && rowIndex >= 0 && rowIndex < item.distributeLists.count) {
            item.distributeLists.remove(rowIndex)
            handleCardChanged()
        }
    }

    function addOffsetListToSelectedProcess(listName, direction, value, interfaceName) {
        const item = selectedProcessItem()
        const name = String(listName || "").trim()
        const valueText = String(value || "").trim()
        if (!item || name === "" || valueText === "") {
            notify("Process, list name, and offset value are required.", "warning")
            return false
        }
        item.offsetLists.append({ list_name: name, direction: direction || "in", value: valueText, interface_name: String(interfaceName || "").trim() })
        handleCardChanged()
        return true
    }

    function removeOffsetListFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (item && rowIndex >= 0 && rowIndex < item.offsetLists.count) {
            item.offsetLists.remove(rowIndex)
            handleCardChanged()
        }
    }

    function addRedistributeToSelectedProcess(protocol, routeMap, bw, delay, reliability, load, mtu) {
        const item = selectedProcessItem()
        const protocolText = String(protocol || "").trim()
        if (!item || protocolText === "") {
            notify("Process and protocol are required.", "warning")
            return false
        }
        item.redistribute.append({
            protocol: protocolText,
            route_map: String(routeMap || "").trim(),
            metric_bw: String(bw || "").trim(),
            metric_delay: String(delay || "").trim(),
            metric_reliability: String(reliability || "").trim(),
            metric_load: String(load || "").trim(),
            metric_mtu: String(mtu || "").trim()
        })
        handleCardChanged()
        return true
    }

    function removeRedistributeFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (item && rowIndex >= 0 && rowIndex < item.redistribute.count) {
            item.redistribute.remove(rowIndex)
            handleCardChanged()
        }
    }

    function addKeyChainToSelectedProcess(chainName, keyId, keyString, acceptLifetime, sendLifetime) {
        const item = selectedProcessItem()
        const chain = String(chainName || "").trim()
        const idText = String(keyId || "").trim()
        const secret = String(keyString || "").trim()
        if (!item || chain === "" || idText === "" || secret === "") {
            notify("Process, chain name, key id, and key string are required.", "warning")
            return false
        }
        item.keyChains.append({
            chain_name: chain,
            key_id: idText,
            key_string: secret,
            accept_lifetime: String(acceptLifetime || "").trim(),
            send_lifetime: String(sendLifetime || "").trim()
        })
        handleCardChanged()
        return true
    }

    function removeKeyChainFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (item && rowIndex >= 0 && rowIndex < item.keyChains.count) {
            item.keyChains.remove(rowIndex)
            handleCardChanged()
        }
    }

    function appendProcess(payload) {
        const key = String(nextUid)
        const nextPayloads = Object.assign({}, processPayloadByUid)
        nextPayloads[key] = payload || ({})
        processPayloadByUid = nextPayloads
        processModel.append({ processUid: nextUid, processOrder: processModel.count + 1 })
        nextUid += 1
        Qt.callLater(rebuildProcessOptions)
    }

    function resequenceProcessOrders() {
        for (let i = 0; i < processModel.count; i++)
            processModel.setProperty(i, "processOrder", i + 1)
    }

    function removeProcessByUid(processUid) {
        const key = String(processUid)
        for (let i = 0; i < processModel.count; i++) {
            const row = processModel.get(i)
            if (Number(row.processUid) === Number(processUid)) {
                processModel.remove(i)
                const nextPayloads = Object.assign({}, processPayloadByUid)
                delete nextPayloads[key]
                processPayloadByUid = nextPayloads
                resequenceProcessOrders()
                refreshStats()
                Qt.callLater(rebuildProcessOptions)
                Qt.callLater(refreshDirtyFlag)
                return
            }
        }
    }

    function addEmptyProcess() {
        appendProcess({
            as_number: "",
            router_id: "",
            timers_active_time: 0,
            bfd_all_interfaces: false,
            auto_summary: false,
            passive_default: false,
            use_metric_weights: false,
            metric_weights: "0 1 0 1 0 0",
            distance_internal: 0,
            distance_external: 0,
            variance: 0,
            maximum_paths: 0,
            stub_enabled: false,
            stub_options: "",
            stub_leak_map: "",
            action_Cfg: "1111111",
            networks: [],
            interface_settings: [],
            passive_interfaces: [],
            distribute_lists: [],
            offset_lists: [],
            redistribute: [],
            key_chains: []
        })
        notify("Added a new EIGRP process card.", "info")
        refreshStats()
        Qt.callLater(rebuildProcessOptions)
        Qt.callLater(refreshDirtyFlag)
    }

    function buildProcessesPayload(strictValidation) {
        const items = processItems()
        const payload = []
        for (let i = 0; i < items.length; i++) {
            const validation = items[i].validate(strictValidation)
            if (!validation.ok) {
                lastError = validation.message
                if (strictValidation)
                    showValidation(validation.message)
                return null
            }
            payload.push(items[i].snapshotForSave())
        }
        return payload
    }

    function loadFromDatabase() {
        resetProcessModel()
        lastError = ""
        loadedProcessesSignature = "[]"
        hasPendingLocalChanges = false

        const host = String(currentHostIp || "").trim()
        if (host === "")
            return

        isLoading = true
        const payload = dbManager.getEigrpRouting(host)
        const ok = payload && (payload.ok === undefined || payload.ok === true)
        if (!ok) {
            lastError = payload && payload.message ? String(payload.message) : "Load EIGRP routing failed."
            notify(lastError, "error")
            isLoading = false
            return
        }

        const processes = payload.processes ? payload.processes : []
        for (let i = 0; i < processes.length; i++)
            appendProcess(processes[i])

        Qt.callLater(function() {
            eigrpRoutingForm.loadedProcessesSignature = eigrpRoutingForm.currentProcessesSignature()
            eigrpRoutingForm.hasPendingLocalChanges = false
            eigrpRoutingForm.isLoading = false
            eigrpRoutingForm.refreshStats()
            eigrpRoutingForm.rebuildProcessOptions()
            eigrpRoutingForm.viewPushRevision++
        })
    }

    function saveToDatabase() {
        if (isLoading || isSaving)
            return false
        const host = String(currentHostIp || "").trim()
        if (host === "") {
            notify("Select a device tab before saving EIGRP.", "warning")
            return false
        }
        const payload = buildProcessesPayload(true)
        if (payload === null)
            return false

        isSaving = true
        const ok = dbManager.saveEigrpRouting(host, payload)
        isSaving = false
        if (ok) {
            lastError = ""
            loadFromDatabase()
            notify("Saved EIGRP routing for host " + host, "success")
            return true
        }
        lastError = "Save EIGRP routing failed."
        notify(lastError, "error")
        return false
    }

    function cancelAllChanges() {
        if (isLoading || isSaving)
            return false
        loadFromDatabase()
        notify("Discarded local EIGRP changes.", "info")
        refreshStats()
        return true
    }

    onCurrentHostIpChanged: loadFromDatabase()
    Component.onCompleted: loadFromDatabase()

    Text {
        visible: String(eigrpRoutingForm.currentHostIp || "").trim() === ""
        Layout.leftMargin: 24
        Layout.rightMargin: 24
        Layout.topMargin: 18
        Layout.fillWidth: true
        text: "Select a device tab to load EIGRP configuration."
        color: Theme.textDisabled
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily
        horizontalAlignment: Text.AlignHCenter
    }

    Text {
        visible: !eigrpRoutingForm.isLoading
            && String(eigrpRoutingForm.currentHostIp || "").trim() !== ""
            && processModel.count === 0
            && (eigrpRoutingForm.activeRoutingSection === "Process"
                || eigrpRoutingForm.activeRoutingSection === "Networks")
        Layout.leftMargin: 24
        Layout.rightMargin: 24
        Layout.topMargin: 18
        Layout.fillWidth: true
        text: "No EIGRP process saved. Use Add Process to create one."
        color: Theme.textDisabled
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily
        horizontalAlignment: Text.AlignHCenter
    }

    EigrpNetworksSection { form: eigrpRoutingForm }
    EigrpInterfacesSection { form: eigrpRoutingForm }
    EigrpPassiveInterfacesSection { form: eigrpRoutingForm }
    EigrpRedistributeSection { form: eigrpRoutingForm }
    EigrpDistributeListsSection { form: eigrpRoutingForm }
    EigrpOffsetListsSection { form: eigrpRoutingForm }
    EigrpKeyChainsSection { form: eigrpRoutingForm }

    Repeater {
        id: processRepeater
        model: processModel

        delegate: EigrpProcessCard {
            required property int processUid
            required property int processOrder
            visible: eigrpRoutingForm.activeRoutingSection === "Process"
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            property int modelUid: processUid
            processIndex: processOrder
            activeSection: eigrpRoutingForm.activeRoutingSection
            showSectionTabs: false
            payload: eigrpRoutingForm.processPayloadForUid(modelUid)

            onRemoveRequested: eigrpRoutingForm.removeProcessByUid(modelUid)
            onCardChanged: eigrpRoutingForm.handleCardChanged()
        }
    }

    Item { height: 8 }

    footer: [
        StandardButton {
            text: "+ Add Process"
            type: "Primary"
            visible: String(eigrpRoutingForm.currentHostIp || "").trim() !== ""
                && (eigrpRoutingForm.activeRoutingSection === "Process"
                    || eigrpRoutingForm.activeRoutingSection === "Networks")
            onClicked: eigrpRoutingForm.addEmptyProcess()
        },
        Item { Layout.fillWidth: true },
        StandardButton {
            text: "Cancel Changes"
            type: "Text"
            enabled: hasPendingLocalChanges
            onClicked: eigrpRoutingForm.cancelAllChanges()
        },
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            onClicked: {
                eigrpRoutingForm.loadFromDatabase()
                eigrpRoutingForm.notify("Reloaded EIGRP routing from database.", "info")
            }
        },
        ViewPushButton {
            id: viewPushButton
            text: "View & Push"
            type: "Primary"
            controllerName: "routing"
            moduleName: "eigrp"
            hostIp: eigrpRoutingForm.currentHostIp
            ownerForm: eigrpRoutingForm
            refreshKey: eigrpRoutingForm.viewPushRevision
            onPushCompleted: function(ok, message) {
                if (ok)
                    eigrpRoutingForm.loadFromDatabase()
            }
        },
        StandardButton {
            text: isSaving ? "Saving..." : "Save EIGRP"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && !isLoading && !isSaving
            onClicked: eigrpRoutingForm.saveToDatabase()
        }
    ]

}
