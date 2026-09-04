pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// Bọc toàn bộ form bằng FormLayout
FormLayout {
    id: ospfRoutingForm

    // Gắn dữ liệu vào Public API của FormLayout
    title: "OSPF Routing"
    hostIp: currentHostIp
    isDirty: hasPendingLocalChanges
    errorMessage: lastError
    showHeader: false
    pinnedContent: OspfPinnedHeader { form: ospfRoutingForm }

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
    property int selectedAreaIndex: 0
    property int processCount: processModel.count
    property var processOptions: []
    property var processPayloadByUid: ({})
    property int viewPushRevision: 0
    signal routingGroupRequested(string protocol)

    onSelectedNetworkProcessIndexChanged: Qt.callLater(clampSelectedAreaIndex)

    ListModel {
        id: processModel
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function showValidation(message) {
        lastError = String(message || "")
        notify(message, "error")
    }

    function valueText(value) {
        return String(value === undefined || value === null ? "" : value).trim()
    }

    function rowsToArray(value) {
        const rows = []
        if (!value)
            return rows
        if (value.count !== undefined && typeof value.get === "function") {
            for (let i = 0; i < value.count; i++)
                rows.push(JSON.parse(JSON.stringify(value.get(i))))
            return rows
        }
        if (Array.isArray(value))
            return JSON.parse(JSON.stringify(value))
        return rows
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
        for (let i = 0; i < items.length; i++) {
            processes.push(items[i].signatureData())
        }
        return JSON.stringify(processes)
    }

    function refreshDirtyFlag() {
        if (isLoading || isSaving)
            return

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

        const processIdText = String(item.processId || "").trim()
        const processText = processIdText !== "" ? ("PID " + processIdText) : "Process %1".arg(index + 1)
        return (host !== "" ? host : "Host") + " / " + processText
    }

    function rebuildProcessOptions() {
        const options = []
        for (let i = 0; i < processRepeater.count; i++) {
            options.push(processOptionLabel(i))
        }
        processOptions = options

        if (processOptions.length === 0) {
            selectedNetworkProcessIndex = 0
        } else if (selectedNetworkProcessIndex >= processOptions.length) {
            selectedNetworkProcessIndex = processOptions.length - 1
        }
    }

    function selectedNetworkProcessItem() {
        if (selectedNetworkProcessIndex < 0 || selectedNetworkProcessIndex >= processRepeater.count)
            return null
        return processRepeater.itemAt(selectedNetworkProcessIndex)
    }

    function selectedProcessItem() {
        return selectedNetworkProcessItem()
    }

    function clampSelectedAreaIndex() {
        const item = selectedProcessItem()
        const areaCount = item ? item.areas.count : 0
        selectedAreaIndex = areaCount > 0
                            ? Math.min(Math.max(selectedAreaIndex, 0), areaCount - 1)
                            : 0
    }

    function totalNetworkCount() {
        const revision = statsRevision
        let total = 0
        const items = processItems()
        for (let i = 0; i < items.length; i++) {
            total += items[i].networks.count
        }
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
        lastError = ""
        refreshDirtyFlag()
        refreshStats()
        rebuildProcessOptions()
    }

    function addNetworkToSelectedProcess(network, wildcard, area) {
        const item = selectedNetworkProcessItem()
        if (!item) {
            notify("Create an OSPF process before adding networks.", "warning")
            return false
        }

        const networkText = String(network || "").trim()
        const wildcardText = String(wildcard || "").trim()
        const enteredArea = String(area === undefined || area === null ? "" : area).trim()
        const areaText = enteredArea === "" ? "0" : enteredArea
        if (networkText === "" || wildcardText === "") {
            notify("Network and wildcard are required.", "warning")
            return false
        }

        item.networks.append({
            network: networkText,
            wildcard: wildcardText,
            area: areaText
        })
        handleCardChanged()
        notify("Added OSPF network to " + processOptionLabel(selectedNetworkProcessIndex) + ".", "info")
        return true
    }

    function removeNetworkFromSelectedProcess(rowIndex) {
        const item = selectedNetworkProcessItem()
        if (!item || rowIndex < 0 || rowIndex >= item.networks.count)
            return

        item.networks.remove(rowIndex)
        handleCardChanged()
        notify("Removed OSPF network from " + processOptionLabel(selectedNetworkProcessIndex) + ".", "warning")
    }

    function selectRoutingSection(sectionName) {
        activeRoutingSection = sectionName
    }

    function addAreaToSelectedProcess(areaId, areaType, noSummary, authentication) {
        const item = selectedProcessItem()
        const areaText = valueText(areaId)
        if (!item || areaText === "") {
            showValidation("Process and Area ID are required.")
            return false
        }
        if (!/^\d+$/.test(areaText) || Number(areaText) > 4294967295) {
            showValidation("OSPF Area ID must be an integer between 0 and 4294967295.")
            return false
        }
        const normalizedAreaId = Number(areaText)
        for (let index = 0; index < item.areas.count; index++) {
            if (Number(valueText(item.areas.get(index).area_id)) === normalizedAreaId) {
                showValidation("OSPF Area ID %1 already exists in this process.".arg(normalizedAreaId))
                return false
            }
        }
        item.areas.append({
            area_id: areaText,
            area_type: areaType || "normal",
            no_summary: noSummary,
            authentication: authentication || "",
            ranges: []
        })
        selectedAreaIndex = item.areas.count - 1
        handleCardChanged()
        notify("Added OSPF area.", "info")
        return true
    }

    function removeAreaFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (!item || rowIndex < 0 || rowIndex >= item.areas.count)
            return
        item.areas.remove(rowIndex)
        if (selectedAreaIndex >= item.areas.count)
            selectedAreaIndex = Math.max(0, item.areas.count - 1)
        handleCardChanged()
    }

    function areaOptionsForSelectedProcess() {
        const revision = statsRevision
        const item = selectedProcessItem()
        const options = []
        if (!item)
            return options
        for (let i = 0; i < item.areas.count; i++) {
            const area = item.areas.get(i)
            options.push("Area " + valueText(area.area_id))
        }
        return options
    }

    function selectedAreaRanges() {
        const revision = statsRevision
        const item = selectedProcessItem()
        if (!item || selectedAreaIndex < 0 || selectedAreaIndex >= item.areas.count)
            return []
        return item.areas.get(selectedAreaIndex).ranges || []
    }

    function addAreaRangeToSelectedArea(ip, mask, advertise, cost) {
        const item = selectedProcessItem()
        if (!item || selectedAreaIndex < 0 || selectedAreaIndex >= item.areas.count) {
            notify("Create/select an OSPF area before adding ranges.", "warning")
            return false
        }
        const ipText = String(ip || "").trim()
        const maskText = String(mask || "").trim()
        if (ipText === "" || maskText === "") {
            notify("Range IP and mask are required.", "warning")
            return false
        }
        const area = item.areas.get(selectedAreaIndex)
        const newRange = {
            ip: ipText,
            mask: maskText,
            advertise: advertise,
            cost: valueText(cost)
        }
        // A nested ListModel role must be mutated directly. Replacing it with
        // setProperty() can clear the role instead of installing the JS array.
        if (area.ranges && typeof area.ranges.append === "function") {
            area.ranges.append(newRange)
        } else {
            const ranges = rowsToArray(area.ranges)
            ranges.push(newRange)
            item.areas.setProperty(selectedAreaIndex, "ranges", ranges)
        }
        handleCardChanged()
        notify("Added OSPF area range.", "info")
        return true
    }

    function removeAreaRangeFromSelectedArea(rowIndex) {
        const item = selectedProcessItem()
        if (!item || selectedAreaIndex < 0 || selectedAreaIndex >= item.areas.count)
            return
        const area = item.areas.get(selectedAreaIndex)
        if (area.ranges && typeof area.ranges.remove === "function") {
            if (rowIndex < 0 || rowIndex >= area.ranges.count)
                return
            area.ranges.remove(rowIndex)
        } else {
            const ranges = rowsToArray(area.ranges)
            if (rowIndex < 0 || rowIndex >= ranges.length)
                return
            ranges.splice(rowIndex, 1)
            item.areas.setProperty(selectedAreaIndex, "ranges", ranges)
        }
        handleCardChanged()
    }

    function addRedistributeToSelectedProcess(protocol, processId, subnets, metric, metricType, routeMap) {
        const item = selectedProcessItem()
        if (!item) {
            notify("Create an OSPF process before adding redistribution.", "warning")
            return false
        }
        item.redistribute.append({
            protocol: protocol || "static",
            process_id: valueText(processId),
            subnets: subnets,
            metric: valueText(metric),
            metric_type: valueText(metricType),
            route_map: String(routeMap || "").trim()
        })
        handleCardChanged()
        notify("Added OSPF redistribution.", "info")
        return true
    }

    function removeRedistributeFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (!item || rowIndex < 0 || rowIndex >= item.redistribute.count)
            return
        item.redistribute.remove(rowIndex)
        handleCardChanged()
    }

    function addPassiveInterfaceToSelectedProcess(interfaceName, passive) {
        const item = selectedProcessItem()
        const iface = String(interfaceName || "").trim()
        if (!item || iface === "") {
            notify("Process and interface name are required.", "warning")
            return false
        }
        item.passiveInterfaces.append({ interface_name: iface, passive: passive })
        handleCardChanged()
        notify("Added OSPF passive-interface entry.", "info")
        return true
    }

    function removePassiveInterfaceFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (!item || rowIndex < 0 || rowIndex >= item.passiveInterfaces.count)
            return
        item.passiveInterfaces.remove(rowIndex)
        handleCardChanged()
    }

    function addInterfaceSettingToSelectedProcess(interfaceName, area, cost, priority, hello, dead, mtuIgnore, bfd, networkType, authType, authKey) {
        const item = selectedProcessItem()
        const iface = String(interfaceName || "").trim()
        const areaText = valueText(area)
        if (!item || iface === "" || areaText === "") {
            notify("Interface name and area are required.", "warning")
            return false
        }
        item.interfaceSettings.append({
            interface_name: iface,
            area: areaText,
            cost: valueText(cost),
            priority: valueText(priority) === "" ? "1" : valueText(priority),
            hello_interval: valueText(hello),
            dead_interval: valueText(dead),
            mtu_ignore: mtuIgnore,
            bfd: bfd,
            network_type: networkType || "",
            auth_type: authType || "",
            auth_key: String(authKey || "").trim()
        })
        handleCardChanged()
        notify("Added OSPF interface setting.", "info")
        return true
    }

    function removeInterfaceSettingFromSelectedProcess(rowIndex) {
        const item = selectedProcessItem()
        if (!item || rowIndex < 0 || rowIndex >= item.interfaceSettings.count)
            return
        item.interfaceSettings.remove(rowIndex)
        handleCardChanged()
    }

    function setDistanceForSelectedProcess(external, intraArea, interArea) {
        const item = selectedProcessItem()
        if (!item)
            return false
        item.distance = {
            external: valueText(external),
            intra_area: valueText(intraArea),
            inter_area: valueText(interArea)
        }
        handleCardChanged()
        notify("Updated OSPF distance.", "info")
        return true
    }

    function setTuningForSelectedProcess(maximumPaths, maxLsa, spfDelay, spfMin, spfMax, lsaDelay, lsaMin, lsaMax) {
        const item = selectedProcessItem()
        if (!item)
            return false
        item.tuning = {
            maximum_paths: valueText(maximumPaths),
            max_lsa: valueText(maxLsa),
            spf_delay: valueText(spfDelay),
            spf_min_delay: valueText(spfMin),
            spf_max_delay: valueText(spfMax),
            lsa_delay: valueText(lsaDelay),
            lsa_min_delay: valueText(lsaMin),
            lsa_max_delay: valueText(lsaMax)
        }
        handleCardChanged()
        notify("Updated OSPF tuning.", "info")
        return true
    }

    function appendProcess(payload) {
        const key = String(nextUid)
        const payloadMap = payload || ({})
        const nextPayloads = Object.assign({}, processPayloadByUid)
        nextPayloads[key] = payloadMap
        processPayloadByUid = nextPayloads

        processModel.append({
            processUid: nextUid,
            processOrder: processModel.count + 1
        })
        nextUid += 1
        Qt.callLater(rebuildProcessOptions)
    }

    function resequenceProcessOrders() {
        for (let i = 0; i < processModel.count; i++) {
            processModel.setProperty(i, "processOrder", i + 1)
        }
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
                notify("Removed OSPF process %1 from the local editor.".arg(row.processOrder), "warning")
                refreshStats()
                Qt.callLater(rebuildProcessOptions)
                Qt.callLater(refreshDirtyFlag)
                return
            }
        }
    }

    function addEmptyProcess() {
        appendProcess({
            process_id:               "",
            router_id:                "",
            reference_bandwidth:      0,
            passive_default:          false,
            default_originate:        false,
            default_originate_always: false,
            networks:                 [],
            distance:                 {},
            tuning:                   {},
            areas:                    [],
            redistribute:             [],
            passive_interfaces:       [],
            interface_settings:       []
        })
        notify("Added a new OSPF process card.", "info")
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
        if (typeof dbManager === "undefined" || dbManager === null
                || !dbManager.getOspfRouting) {
            lastError = "OSPF database service is unavailable."
            notify(lastError, "error")
            isLoading = false
            return
        }

        const payload = dbManager.getOspfRouting(host)
        const ok = payload && (payload.ok === undefined || payload.ok === true)

        if (!ok) {
            lastError = payload && payload.message ? String(payload.message) : "Load OSPF routing failed."
            notify(lastError, "error")
            isLoading = false
            return
        }

        const processes = payload.processes ? payload.processes : []
        for (let i = 0; i < processes.length; i++) {
            appendProcess(processes[i])
        }

        Qt.callLater(function() {
            ospfRoutingForm.loadedProcessesSignature = ospfRoutingForm.currentProcessesSignature()
            ospfRoutingForm.hasPendingLocalChanges = false
            ospfRoutingForm.isLoading = false
            ospfRoutingForm.refreshStats()
            ospfRoutingForm.rebuildProcessOptions()
            ospfRoutingForm.viewPushRevision++
        })
    }

    function saveToDatabase() {
        if (isLoading || isSaving)
            return false

        const host = String(currentHostIp || "").trim()
        if (host === "") {
            notify("Select a device tab before saving OSPF.", "warning")
            return false
        }

        const payload = buildProcessesPayload(true)
        if (payload === null)
            return false

        isSaving = true
        if (typeof dbManager === "undefined" || dbManager === null
                || !dbManager.saveOspfRouting) {
            lastError = "OSPF database service is unavailable."
            notify(lastError, "error")
            isSaving = false
            return false
        }

        const ok = dbManager.saveOspfRouting(host, payload)
        isSaving = false

        if (ok) {
            lastError = ""
            loadFromDatabase()
            notify("Saved OSPF routing for host " + host, "success")
            return true
        }

        const backendError = String(dbManager.getLastRoutingError ? dbManager.getLastRoutingError() : "").trim()
        lastError = backendError !== "" ? backendError : "Save OSPF routing failed."
        notify(lastError, "error")
        return false
    }

    function cancelAllChanges() {
        if (isLoading || isSaving)
            return false

        loadFromDatabase()
        notify("Discarded local OSPF changes.", "info")
        refreshStats()
        return true
    }

    onCurrentHostIpChanged: loadFromDatabase()
    Component.onCompleted: loadFromDatabase()

    // ── NỘI DUNG CHÍNH (Body) ──
    Text {
        visible: String(ospfRoutingForm.currentHostIp || "").trim() === ""
        Layout.leftMargin: 24
        Layout.rightMargin: 24
        Layout.topMargin: 18
        Layout.fillWidth: true
        text: "Select a device tab to load OSPF configuration."
        color: Theme.textDisabled
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily
        horizontalAlignment: Text.AlignHCenter
    }

    Text {
        visible: !ospfRoutingForm.isLoading
            && String(ospfRoutingForm.currentHostIp || "").trim() !== ""
            && processModel.count === 0
            && (ospfRoutingForm.activeRoutingSection === "Process"
                || ospfRoutingForm.activeRoutingSection === "Networks")
        Layout.leftMargin: 24
        Layout.rightMargin: 24
        Layout.topMargin: 18
        Layout.fillWidth: true
        text: "No OSPF process saved. Use Add Process to create one."
        color: Theme.textDisabled
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily
        horizontalAlignment: Text.AlignHCenter
    }

    OspfAreasSection { form: ospfRoutingForm }

    OspfRedistributeSection { form: ospfRoutingForm }
    OspfPassiveInterfacesSection { form: ospfRoutingForm }
    OspfDistanceSection { form: ospfRoutingForm }
    OspfTuningSection { form: ospfRoutingForm }

    OspfInterfacesSection { form: ospfRoutingForm }

    OspfNetworksSection { form: ospfRoutingForm }

    Repeater {
        id: processRepeater
        model: processModel

        delegate: OspfProcessCard {
            required property int processUid
            required property int processOrder
            visible: ospfRoutingForm.activeRoutingSection === "Process"
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            property int modelUid: processUid
            processIndex: processOrder
            activeSection: ospfRoutingForm.activeRoutingSection
            showSectionTabs: false
            payload: ospfRoutingForm.processPayloadForUid(modelUid)

            onRemoveRequested: {
                ospfRoutingForm.removeProcessByUid(modelUid)
            }

            onCardChanged: ospfRoutingForm.handleCardChanged()
        }
    }

    Item { height: 8 }

    // ── FOOTER (Nút Bấm) ──
    footer: [
        StandardButton {
            text: "+ Add Process"
            type: "Primary"
            visible: String(ospfRoutingForm.currentHostIp || "").trim() !== ""
                && (ospfRoutingForm.activeRoutingSection === "Process"
                    || ospfRoutingForm.activeRoutingSection === "Networks")
            onClicked: ospfRoutingForm.addEmptyProcess()
        },
        Item { Layout.fillWidth: true },
        StandardButton {
            text: "Cancel Changes"
            type: "Text"
            enabled: hasPendingLocalChanges
            onClicked: ospfRoutingForm.cancelAllChanges()
        },
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            onClicked: {
                ospfRoutingForm.loadFromDatabase()
                ospfRoutingForm.notify("Reloaded OSPF routing from database.", "info")
            }
        },
        ViewPushButton {
            id: viewPushButton
            text: "View & Push"
            type: "Primary"
            controllerName: "routing"
            moduleName: "ospf"
            hostIp: ospfRoutingForm.currentHostIp
            ownerForm: ospfRoutingForm
            refreshKey: ospfRoutingForm.viewPushRevision
            onPushCompleted: function(ok, message) {
                if (ok)
                    ospfRoutingForm.loadFromDatabase()
            }
        },
        StandardButton {
            text: isSaving ? "Saving..." : "Save OSPF"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: hasPendingLocalChanges && !isLoading && !isSaving
            onClicked: ospfRoutingForm.saveToDatabase()
        }
    ]

}
