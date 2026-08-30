pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import UI

Item {
    id: devicesPanel

    // ── PUBLIC API ────────────────────────────────────────────────────────────
    property string activeHost: ""
    property var selectedHosts: ({})
    property string anchorHost: ""
    property string contextTargetHost: ""
    property bool multiSelectMode: false
    readonly property var selectedHostList: Object.keys(selectedHosts)
    property var hostOperations: ({})
    property string activeBatchId: ""
    property bool activeBatchExitsMultipleSelection: false
    property string displayFormat: "both"
    property var allDevices: []
    property var connectingHosts: ({})
    readonly property bool isConnectRunning: Object.keys(connectingHosts).length > 0
    readonly property string connectTargetIp: {
        const hosts = Object.keys(connectingHosts)
        return hosts.length > 0 ? hosts[0] : ""
    }
    readonly property bool isRunningConfigRunning: activeBatchId !== ""
                                                      && activeBatchOperation === "running-config"
    property string activeBatchOperation: ""
    property string pendingManualSyncHost: ""
    property string pendingScpHost: ""
    property bool pythonDepsChecking: false
    property string pythonDepsStatus: "idle"
    property string pythonDepsStatusText: "STARTING..."
    property string pythonDepsStatusDetail: "Checking Python runtime and database schemas."
    readonly property bool deviceShortcutEnabled: devicesPanel.visible && !UiState.windowLock && !searchBar.inputActiveFocus
    readonly property bool hostDeletionEnabled: true
    readonly property bool allDeviceGroupsCollapsed: !connectedSection.expanded
                                                    && !waitingSection.expanded
                                                    && !disconnectedSection.expanded
    readonly property bool allDeviceGroupsExpanded: connectedSection.expanded
                                                   && waitingSection.expanded
                                                   && disconnectedSection.expanded

    signal deviceSelected(string ip, string name, string deviceType, string status)
    signal deviceActivated(string host, string name, string deviceType, string status)
    signal deviceSelectionChanged(var hosts)
    signal deviceDeleted(string ip)
    signal devicesLoaded(var devices)

    // ── HÀM XỬ LÝ LÕI ─────────────────────────────────────────────────────────
    function applyFilters() {
        let connected = [], waiting = [], disconnected = []
        const searchStr = searchBar.text.toLowerCase()
        const activeStatus = standardDropdown.activeStatusFilters
        const activeType = standardDropdown.activeTypeFilters

        for (let i = 0; i < allDevices.length; i++) {
            const d = allDevices[i]
            const matchStatus = activeStatus.length === 0 || activeStatus.indexOf(d.status) !== -1
            const matchType = activeType.length === 0 || activeType.indexOf(d.type) !== -1
            const matchSearch = searchStr === "" || d.name.toLowerCase().indexOf(searchStr) !== -1 || d.ip.indexOf(searchStr) !== -1

            if (matchStatus && matchType && matchSearch) {
                if (d.status === "connected") connected.push(d)
                else if (d.status === "waiting") waiting.push(d)
                else if (d.status === "disconnected") disconnected.push(d)
            }
        }
        connectedSection.devices = connected
        waitingSection.devices = waiting
        disconnectedSection.devices = disconnected
    }

    function reloadDevices() {
        devicesPanel.allDevices = dbManager.getDevices()
        reconcileHostState()
        devicesPanel.applyFilters()
        devicesPanel.devicesLoaded(devicesPanel.allDevices)
    }

    function openNewDeviceWindow() {
        newDeviceLoader.active = true
        if (UiState.windowLock && !newDeviceLoader.item.visible) UiState.windowLock = false
        newDeviceLoader.item.resetAndOpen(false, null)
    }

    function openBatchDeviceWindow() {
        batchDeviceLoader.active = true
        if (UiState.windowLock && !batchDeviceLoader.item.visible) UiState.windowLock = false
        batchDeviceLoader.item.resetAndOpen()
    }

    function handleEditDevice(ip) {
        const deviceData = dbManager.getDeviceByHost(ip)
        if (!deviceData || !deviceData.ip) return
        newDeviceLoader.active = true
        if (UiState.windowLock && !newDeviceLoader.item.visible) UiState.windowLock = false
        if (!UiState.windowLock) {
            UiState.windowLock = true
            newDeviceLoader.item.resetAndOpen(true, deviceData)
        }
    }

    function handleDeleteDevice(ip) {
        if (!hostDeletionEnabled || String(ip || "") === "") return
        deleteConfirmationDialog.targetIp = String(ip)
        deleteAcknowledgement.checked = false
        deleteConfirmationField.text = ""
        deleteConfirmationDialog.open()
    }

    function devicesForSection(section) {
        if (section === 0) return connectedSection.devices
        if (section === 1) return waitingSection.devices
        if (section === 2) return disconnectedSection.devices
        return []
    }

    function deviceByHost(host) {
        const target = String(host || "")
        for (let i = 0; i < allDevices.length; i++) {
            if (String(allDevices[i].ip || "") === target)
                return allDevices[i]
        }
        return null
    }

    function selectedDevice() {
        return deviceByHost(activeHost)
    }

    function reconcileHostState() {
        const valid = ({})
        for (let i = 0; i < allDevices.length; i++)
            valid[String(allDevices[i].ip || "")] = true
        const next = ({})
        const hosts = Object.keys(selectedHosts)
        for (let i = 0; i < hosts.length; i++) {
            if (valid[hosts[i]])
                next[hosts[i]] = true
        }
        selectedHosts = next
        if (Object.keys(next).length === 0)
            multiSelectMode = false
        if (activeHost !== "" && !valid[activeHost])
            activeHost = ""
        if (anchorHost !== "" && !valid[anchorHost])
            anchorHost = ""
        deviceSelectionChanged(selectedHostList)
    }

    function setHostSelected(host, selected) {
        const target = String(host || "")
        if (target === "") return
        const next = Object.assign({}, selectedHosts)
        if (selected)
            next[target] = true
        else
            delete next[target]
        selectedHosts = next
        anchorHost = target
        deviceSelectionChanged(selectedHostList)
    }

    function clearSelection() {
        selectedHosts = ({})
        anchorHost = ""
        multiSelectMode = false
        deviceSelectionChanged([])
    }

    function toggleHostSelection(host) {
        setHostSelected(host, selectedHosts[host] !== true)
    }

    function handleToggleHostSelection(host) {
        const target = String(host || "")
        if (target === "") return
        multiSelectMode = true
        toggleHostSelection(target)
        if (selectedHostList.length === 0)
            clearSelection()
    }

    function visibleHosts() {
        return connectedSection.devices.concat(
            waitingSection.devices,
            disconnectedSection.devices
        ).map(device => String(device.ip || ""))
    }

    function selectAllVisibleHosts() {
        const next = ({})
        const hosts = visibleHosts()
        for (let i = 0; i < hosts.length; ++i)
            next[hosts[i]] = true
        selectedHosts = next
        multiSelectMode = hosts.length > 0
        if (hosts.length > 0)
            anchorHost = hosts[0]
        deviceSelectionChanged(selectedHostList)
    }

    function selectRangeTo(host) {
        const target = String(host || "")
        const hosts = visibleHosts()
        const targetIndex = hosts.indexOf(target)
        if (targetIndex < 0)
            return
        let anchorIndex = hosts.indexOf(anchorHost)
        if (anchorIndex < 0)
            anchorIndex = targetIndex
        const first = Math.min(anchorIndex, targetIndex)
        const last = Math.max(anchorIndex, targetIndex)
        const next = ({})
        for (let i = first; i <= last; ++i)
            next[hosts[i]] = true
        selectedHosts = next
        multiSelectMode = true
        deviceSelectionChanged(selectedHostList)
    }

    function hostStatusMap() {
        const statuses = ({})
        for (let i = 0; i < allDevices.length; ++i)
            statuses[String(allDevices[i].ip || "")] = String(allDevices[i].status || "")
        return statuses
    }

    function eligibleHosts(operation, hosts) {
        const requiredStatus = operation === "connect" ? "waiting"
                             : operation === "running-config" ? "connected"
                             : operation === "disconnect" ? "connected" : ""
        const targets = []
        for (let i = 0; i < (hosts || []).length; ++i) {
            const host = String(hosts[i] || "")
            const device = deviceByHost(host)
            if (host !== "" && device
                    && (requiredStatus === "" || device.status === requiredStatus))
                targets.push(host)
        }
        return targets
    }

    function startMultipleSelection(host) {
        const target = String(host || "")
        if (target === "") return
        multiSelectMode = true
        anchorHost = target
        const next = ({})
        next[target] = true
        selectedHosts = next
        deviceSelectionChanged(selectedHostList)
    }

    function showDeviceShortcutMessage(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type || "warning")
    }

    function operationSeverity(result) {
        if (result && result.severity)
            return String(result.severity)
        return result && result.ok ? "success" : "error"
    }

    function operationMessage(result, fallbackMessage) {
        if (result && result.message)
            return String(result.message)
        return fallbackMessage
    }

    function notifyOperationResult(result, fallbackMessage) {
        showDeviceShortcutMessage(operationMessage(result, fallbackMessage), operationSeverity(result))
    }

    function requireShortcutDevice(actionName) {
        const dev = selectedDevice()
        if (!dev)
            showDeviceShortcutMessage("Select a device before using " + actionName + ".", "warning")
        return dev
    }

    function requireShortcutStatus(dev, actionName, statusName) {
        if (!dev)
            return false
        if (dev.status !== statusName) {
            showDeviceShortcutMessage(actionName + " is available only for " + statusName + " devices.", "warning")
            return false
        }
        return true
    }

    function handleDeviceRightClicked(ip, status, mx, my) {
        contextTargetHost = String(ip || "")
        // Desktop selection convention: right-click preserves a selected
        // batch, but an unselected row becomes an independent context target.
        if (multiSelectMode && selectedHosts[contextTargetHost] !== true)
            clearSelection()
        const batchHosts = multiSelectMode && selectedHostList.length > 0
                         ? selectedHostList : [contextTargetHost]
        const contextDevice = deviceByHost(contextTargetHost)
        deviceContextMenu.targetIsDevelopment = Boolean(
            contextDevice && Number(contextDevice.dev || 0) === 1)
        deviceContextMenu.openForHost(
            contextTargetHost, status, batchHosts, hostStatusMap(), mx, my)
    }

    function handlePingDevice(ip) {
        const result = cli.pingHost(ip)
        notifyOperationResult(result, "Ping finished for " + ip + ".")
    }

    function handleUpDevDevice(ip) {
        const result = dbManager.setDeviceDevState(ip, 1, StatusValues.connected)
        notifyOperationResult(result, "Development mode enabled for " + ip + ".")
        if (result && result.ok)
            devicesPanel.reloadDevices()
    }

    function handleDownDevDevice(ip) {
        const result = dbManager.setDeviceDevState(ip, 0, StatusValues.waiting)
        notifyOperationResult(result, "Switched " + ip + " to live connection mode.")
        if (result && result.ok)
            devicesPanel.reloadDevices()
    }

    function handleReconnectDevice(ip) {
        const result = dbManager.resetDeviceToWaiting(ip)
        notifyOperationResult(result, "Reset to Waiting finished for " + ip + ".")
        if (result && result.ok)
            devicesPanel.reloadDevices()
    }

    function handleShortcutReconnect() {
        const dev = requireShortcutDevice("Reconnect")
        if (requireShortcutStatus(dev, "Reconnect", "disconnected"))
            devicesPanel.handleReconnectDevice(dev.ip)
    }

    function handleConnectDevice(ip) {
        const targetIp = String(ip || "")
        if (devicesPanel.connectingHosts[targetIp] === true) {
            showDeviceShortcutMessage("A connect task is already running for " + targetIp, "warning")
            return
        }
        const pending = Object.assign({}, devicesPanel.connectingHosts)
        pending[targetIp] = true
        devicesPanel.connectingHosts = pending
        if (typeof cli === "undefined" || !cli.connectHostAndSyncAsync) {
            delete pending[targetIp]
            devicesPanel.connectingHosts = Object.assign({}, pending)
            showDeviceShortcutMessage("Async connect backend is not available.", "error")
            return
        }

        const accepted = cli.connectHostAndSyncAsync(targetIp)
        if (!accepted) {
            delete pending[targetIp]
            devicesPanel.connectingHosts = Object.assign({}, pending)
            showDeviceShortcutMessage("Connect task could not start for " + targetIp + ".", "error")
        }
    }

    function handleConnectHosts(hosts) {
        const targets = (hosts || []).map(host => String(host || ""))
                .filter(host => host !== "" && devicesPanel.connectingHosts[host] !== true)
        if (targets.length === 0) {
            showDeviceShortcutMessage("No waiting host is available to connect.", "info")
            return
        }
        if (typeof cli === "undefined" || !cli.connectHostsAndSyncAsync) {
            for (let i = 0; i < targets.length; i++)
                devicesPanel.handleConnectDevice(targets[i])
            return
        }
        const pending = Object.assign({}, devicesPanel.connectingHosts)
        for (let i = 0; i < targets.length; i++)
            pending[targets[i]] = true
        devicesPanel.connectingHosts = pending
        const result = cli.connectHostsAndSyncAsync(targets)
        const rejected = result && result.rejected ? result.rejected : []
        for (let i = 0; i < rejected.length; i++)
            delete pending[String(rejected[i])]
        devicesPanel.connectingHosts = Object.assign({}, pending)
        notifyOperationResult(result, "Started concurrent device connections.")
    }

    function handleConnectAllWaiting() {
        handleConnectHosts(waitingSection.devices.map(device => device.ip))
    }

    function handleRunningConfigDevice(ip) {
        handleBatchOperation("running-config", [String(ip || "")])
    }

    function confirmRunningConfigScp(ip) {
        // NOTE: chuc nang chua phat trien xong, khong tam quan tam nieu viet bao cao
        const host = String(ip || "").trim()
        if (host === "")
            return
        scpConfirmDialog.targetHost = host
        scpConfirmDialog.messageText =
            "Get running-config from " + host + " via SCP?\n\nIf SCP is not enabled, "
            + "NetworkTools will configure 'ip scp server enable' and save that "
            + "change. A temporary file will be created in flash, downloaded to "
            + "the SFTP/SCP local directory, then removed."
        scpConfirmDialog.open()
    }

    function handleSaveConfigDevice(ip) {
        const host = String(ip || "").trim()
        if (host === "" || typeof cli === "undefined" || !cli.saveDeviceConfigAsync) {
            showDeviceShortcutMessage("Save configuration backend is not available.", "error")
            return
        }
        if (!cli.saveDeviceConfigAsync(host))
            showDeviceShortcutMessage("Save configuration task could not start for " + host + ".", "error")
    }

    function handleBatchOperation(operation, hosts) {
        const requested = (hosts || []).map(host => String(host || ""))
                .filter(host => host !== "")
        const targets = eligibleHosts(operation, requested)
        if (targets.length === 0 || typeof cli === "undefined") {
            showDeviceShortcutMessage(
                "No selected host is eligible for " + operation + ".", "warning")
            return
        }
        // Operation badges are transient and belong only to the active batch.
        // Never carry green/red results into the next operation.
        hostOperations = ({})
        if (targets.length < requested.length) {
            showDeviceShortcutMessage(
                "Starting " + operation + " for " + targets.length + " eligible host(s); "
                + (requested.length - targets.length) + " skipped by status.", "info")
        }
        let batchId = ""
        if (operation === "connect" && cli.connectHostsAsync)
            batchId = cli.connectHostsAsync(targets)
        else if (operation === "running-config" && cli.getRunningConfigsAsync)
            batchId = cli.getRunningConfigsAsync(targets)
        else if (operation === "disconnect" && cli.disconnectHostsAsync)
            batchId = cli.disconnectHostsAsync(targets)
        if (batchId === "") {
            showDeviceShortcutMessage("Batch backend is not available for " + operation + ".", "error")
            return
        }
        activeBatchId = batchId
        activeBatchOperation = operation
        activeBatchExitsMultipleSelection = multiSelectMode
    }

    function cancelActiveBatch() {
        if (activeBatchId !== "" && typeof cli !== "undefined" && cli.cancelBatch)
            cli.cancelBatch(activeBatchId)
    }

    function handleShortcutEdit() {
        const dev = requireShortcutDevice("Edit")
        if (dev)
            devicesPanel.handleEditDevice(dev.ip)
    }

    function handleCliDevice(ip) {
        if (!ip) return
        if (typeof cli !== "undefined" && cli.openDeviceTerminal) {
            // Context-menu CLI uses the same managed external session as the FeatureBar.
            const res = cli.openDeviceTerminal(ip)
            if (!res.ok) {
                const message = "CLI Error: "
                              + (res.message || "Failed to open NetworkTools Terminal.")
                showDeviceShortcutMessage(message, "error")
            } else {
                showDeviceShortcutMessage(
                    "CLI Opened: " + (res.message || `Opening ${ip}`),
                    "success"
                )
            }
        } else {
            showDeviceShortcutMessage("CLI Error: NetworkTools Terminal backend is not available.", "error")
        }
    }

    function handleShortcutPing() {
        const dev = requireShortcutDevice("Ping")
        if (requireShortcutStatus(dev, "Ping", "connected"))
            devicesPanel.handlePingDevice(dev.ip)
    }

    function handleShortcutDownDev() {
        const dev = requireShortcutDevice("Switch to Live Connection")
        if (!requireShortcutStatus(dev, "Switch to Live Connection", "connected"))
            return
        if (Number(dev.dev || 0) !== 1) {
            showDeviceShortcutMessage(dev.ip + " already uses a live connection.", "info")
            return
        }
        devicesPanel.handleDownDevDevice(dev.ip)
    }

    function handleShortcutUpDev() {
        const dev = requireShortcutDevice("Enable Development Mode")
        if (requireShortcutStatus(dev, "Enable Development Mode", "waiting"))
            devicesPanel.handleUpDevDevice(dev.ip)
    }

    function handleShortcutConnect() {
        const dev = requireShortcutDevice("Connect")
        if (requireShortcutStatus(dev, "Connect", "waiting"))
            devicesPanel.handleConnectDevice(dev.ip)
    }

    function activateDevice(host) {
        const dev = deviceByHost(host)
        if (!dev) return
        if (dev.status === "waiting") {
            if (typeof statusBar !== "undefined") statusBar.showMessage("Device is waiting. Configuration is disabled.", "warning")
            return
        }
        devicesPanel.activeHost = String(dev.ip || "")
        devicesPanel.deviceSelected(dev.ip, dev.name, dev.type || "unknown", dev.status || "disconnected")
        devicesPanel.deviceActivated(dev.ip, dev.name, dev.type || "unknown", dev.status || "disconnected")
    }

    function handleDeviceActivated(host) {
        if (multiSelectMode) {
            handleToggleHostSelection(host)
            return
        }
        activateDevice(host)
    }

    function selectDeviceByIp(ip) {
        if (allDevices.length === 0) reloadDevices()
        devicesPanel.activeHost = deviceByHost(ip) ? String(ip || "") : ""
    }

    function triggerPythonCheck() {
        if (!devicesPanel.pythonDepsChecking) pythonDepsCheckTimer.restart()
    }

    function collapseAllDeviceGroups() {
        connectedSection.expanded = false
        waitingSection.expanded = false
        disconnectedSection.expanded = false
    }

    function expandAllDeviceGroups() {
        connectedSection.expanded = true
        waitingSection.expanded = true
        disconnectedSection.expanded = true
    }

    function openDeviceGroupContext(sceneX, sceneY) {
        deviceGroupContextMenu.openAt(sceneX, sceneY)
    }

    // ── GIAO DIỆN CHÍNH ───────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        SideBarHeader {
            Layout.fillWidth: true
            isFilterActive: standardDropdown.visible
            onFilterClicked: standardDropdown.toggle()
            onRefreshClicked: devicesPanel.reloadDevices()
            onAddMultipleClicked: {
                if (!UiState.windowLock) {
                    UiState.windowLock = true
                    devicesPanel.openBatchDeviceWindow()
                }
            }
            onAddClicked: {
                if (!UiState.windowLock) {
                    UiState.windowLock = true
                    devicesPanel.openNewDeviceWindow()
                }
            }
        }

        SideBarSearch {
            id: searchBar
            Layout.fillWidth: true
            Layout.margins: 8
            onTextChanged: searchDebounceTimer.restart()
        }

        DeviceBatchActionBar {
            objectName: "deviceBatchActionBar"
            Layout.fillWidth: true
            visible: devicesPanel.multiSelectMode
            selectedCount: devicesPanel.selectedHostList.length
            visibleCount: devicesPanel.visibleHosts().length
            onSelectAllRequested: devicesPanel.selectAllVisibleHosts()
            onClearRequested: devicesPanel.clearSelection()
        }

        ScrollView {
            id: deviceScrollView
            objectName: "deviceGroupScrollView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            padding: 0
            leftPadding: 0
            rightPadding: 0
            topPadding: 0
            bottomPadding: 0
            contentWidth: width
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            Column {
                width: deviceScrollView.width
                DeviceSection {
                    id: connectedSection; objectName: "connectedDeviceGroup"; width: parent.width; sectionTitle: "Connected"; expanded: true
                    activeHost: devicesPanel.activeHost; selectedHosts: devicesPanel.selectedHosts
                    selectionMode: devicesPanel.multiSelectMode
                    hostOperations: devicesPanel.hostOperations; displayFormat: devicesPanel.displayFormat
                    onDeviceActivated: host => devicesPanel.handleDeviceActivated(host)
                    onDeviceToggleSelectionRequested: host => devicesPanel.handleToggleHostSelection(host)
                    onDeviceRangeSelectionRequested: host => devicesPanel.selectRangeTo(host)
                    onDeviceContextRequested: (host, status, mx, my) => devicesPanel.handleDeviceRightClicked(host, status, mx, my)
                    onGroupContextRequested: (sceneX, sceneY) => devicesPanel.openDeviceGroupContext(sceneX, sceneY)
                }
                DeviceSection {
                    id: waitingSection; objectName: "waitingDeviceGroup"; width: parent.width; sectionTitle: "Waiting"; expanded: true
                    activeHost: devicesPanel.activeHost; selectedHosts: devicesPanel.selectedHosts
                    selectionMode: devicesPanel.multiSelectMode
                    hostOperations: devicesPanel.hostOperations; displayFormat: devicesPanel.displayFormat
                    onDeviceActivated: host => devicesPanel.handleDeviceActivated(host)
                    onDeviceToggleSelectionRequested: host => devicesPanel.handleToggleHostSelection(host)
                    onDeviceRangeSelectionRequested: host => devicesPanel.selectRangeTo(host)
                    onDeviceContextRequested: (host, status, mx, my) => devicesPanel.handleDeviceRightClicked(host, status, mx, my)
                    onGroupContextRequested: (sceneX, sceneY) => devicesPanel.openDeviceGroupContext(sceneX, sceneY)
                }
                DeviceSection {
                    id: disconnectedSection; objectName: "disconnectedDeviceGroup"; width: parent.width; sectionTitle: "Disconnected"; expanded: false; autoExpand: false
                    activeHost: devicesPanel.activeHost; selectedHosts: devicesPanel.selectedHosts
                    selectionMode: devicesPanel.multiSelectMode
                    hostOperations: devicesPanel.hostOperations; displayFormat: devicesPanel.displayFormat
                    onDeviceActivated: host => devicesPanel.handleDeviceActivated(host)
                    onDeviceToggleSelectionRequested: host => devicesPanel.handleToggleHostSelection(host)
                    onDeviceRangeSelectionRequested: host => devicesPanel.selectRangeTo(host)
                    onDeviceContextRequested: (host, status, mx, my) => devicesPanel.handleDeviceRightClicked(host, status, mx, my)
                    onGroupContextRequested: (sceneX, sceneY) => devicesPanel.openDeviceGroupContext(sceneX, sceneY)
                }
                Item { width: 1; height: 8 }
            }
        }

    }

    // ── COMPONENT PHỤ TRỢ (Loaders, Menus, Timers) ───────────────────────────
    StandardDropdown { id: standardDropdown; anchors.top: parent.top; anchors.topMargin: 36; anchors.right: parent.right; anchors.rightMargin: 4; z: 10; onFiltersChanged: devicesPanel.applyFilters() }

    DeviceContextMenu {
        id: deviceContextMenu; parent: Overlay.overlay
        allowHostDeletion: devicesPanel.hostDeletionEnabled
        hostOperations: devicesPanel.hostOperations
        selectionMode: devicesPanel.multiSelectMode
        onPingRequested: (ip) => devicesPanel.handlePingDevice(ip)
        onRunningConfigRequested: (ip) => devicesPanel.handleRunningConfigDevice(ip)
        onRunningConfigScpRequested: (ip) => devicesPanel.confirmRunningConfigScp(ip)
        onSaveConfigRequested: (ip) => devicesPanel.handleSaveConfigDevice(ip)
        onSyncRequested: (ip) => {
            devicesPanel.showDeviceShortcutMessage("Manual Sync started for " + ip + ".", "info")
            if (devicesPanel.pendingManualSyncHost !== "" || typeof cli === "undefined" || !cli.manualSyncAsync) {
                devicesPanel.showDeviceShortcutMessage("Manual Sync cannot start for " + ip + ".", "warning")
                return
            }
            devicesPanel.pendingManualSyncHost = ip
            if (!cli.manualSyncAsync(ip)) {
                devicesPanel.pendingManualSyncHost = ""
            }
        }
        onEditRequested: (ip) => devicesPanel.handleEditDevice(ip)
        onDeleteRequested: (ip) => devicesPanel.handleDeleteDevice(ip)
        onUpDevRequested: (ip) => devicesPanel.handleUpDevDevice(ip)
        onDownDevRequested: (ip) => devicesPanel.handleDownDevDevice(ip)
        onConnecRequested: (_ip) => devicesPanel.handleConnectDevice(_ip)
        onConnectBatchRequested: hosts => devicesPanel.handleBatchOperation("connect", hosts)
        onRunningConfigBatchRequested: hosts => devicesPanel.handleBatchOperation("running-config", hosts)
        onDisconnectBatchRequested: hosts => devicesPanel.handleBatchOperation("disconnect", hosts)
        onSelectAllVisibleRequested: devicesPanel.selectAllVisibleHosts()
        onClearSelectionRequested: devicesPanel.clearSelection()
        onStartMultipleSelectionRequested: host => devicesPanel.startMultipleSelection(host)
        onReconnectRequested: (ip) => devicesPanel.handleReconnectDevice(ip)
        onCliRequested: (ip) => devicesPanel.handleCliDevice(ip)
    }

    PanelGroupContextMenu {
        id: deviceGroupContextMenu
        parent: Overlay.overlay
        canCollapseAll: !devicesPanel.allDeviceGroupsCollapsed
        canExpandAll: !devicesPanel.allDeviceGroupsExpanded
        connectAllVisible: waitingSection.devices.length > 0
        connectAllRunning: devicesPanel.isConnectRunning
        onCollapseAllRequested: devicesPanel.collapseAllDeviceGroups()
        onExpandAllRequested: devicesPanel.expandAllDeviceGroups()
        onConnectAllRequested: devicesPanel.handleConnectAllWaiting()
    }

    Connections {
        target: typeof cli !== "undefined" ? cli : null
        function onConnectHostFinished(host, ok, message) {
            const targetIp = String(host || "")
            if (devicesPanel.connectingHosts[targetIp] !== true)
                return
            devicesPanel.reloadDevices()
            const pending = Object.assign({}, devicesPanel.connectingHosts)
            delete pending[targetIp]
            devicesPanel.connectingHosts = pending
        }

        function onManualSyncPreviewFinished(host, ok, message, summary) {
            const targetIp = String(host || "")
            if (targetIp !== devicesPanel.pendingManualSyncHost)
                return
            if (!ok) {
                devicesPanel.pendingManualSyncHost = ""
                devicesPanel.showDeviceShortcutMessage(message, "error")
                return
            }
            const conflicts = summary && summary.conflicts ? summary.conflicts : []
            if (conflicts.length === 0) {
                if (!cli.applyManualSyncAsync(targetIp, "safe")) {
                    devicesPanel.pendingManualSyncHost = ""
                }
                return
            }
            manualSyncDecisionDialog.targetHost = targetIp
            manualSyncDecisionDialog.conflicts = conflicts
            manualSyncDecisionDialog.open()
        }

        function onSaveConfigFinished(host, ok, message) {
            devicesPanel.showDeviceShortcutMessage(
                message || ("Save configuration finished for " + host + "."),
                ok ? "success" : "error"
            )
        }

        function onDeviceSessionClosed(host) {
            devicesPanel.reloadDevices()
        }

        function onHostOperationChanged(batchId, host, state, message, progress) {
            if (String(batchId || "") !== devicesPanel.activeBatchId)
                return
            const next = Object.assign({}, devicesPanel.hostOperations)
            next[String(host || "")] = {
                "host": String(host || ""), "operation": devicesPanel.activeBatchOperation,
                "state": String(state || ""), "message": String(message || ""),
                "progress": progress
            }
            devicesPanel.hostOperations = next
        }

        function onBatchFinished(batchId, ok, payload) {
            if (String(batchId || "") !== devicesPanel.activeBatchId)
                return
            const exitMultipleSelection = devicesPanel.activeBatchExitsMultipleSelection
            devicesPanel.activeBatchId = ""
            devicesPanel.activeBatchOperation = ""
            devicesPanel.activeBatchExitsMultipleSelection = false
            devicesPanel.hostOperations = ({})
            if (exitMultipleSelection)
                devicesPanel.clearSelection()
            devicesPanel.reloadDevices()
            devicesPanel.showDeviceShortcutMessage(
                "Batch finished: " + Number(payload.success || 0) + " succeeded, "
                + Number(payload.failed || 0) + " failed.",
                ok ? "success" : "warning"
            )
        }
    }

    Connections {
        target: typeof sftpController !== "undefined" ? sftpController : null

        function onScpRunningConfigFinished(host, ok, message, localPath) {
            if (devicesPanel.pendingScpHost !== String(host || ""))
                return
            devicesPanel.pendingScpHost = ""
            devicesPanel.showDeviceShortcutMessage(
                message || ("SCP running-config finished for " + host + "."),
                ok ? "success" : "error"
            )
        }

        function onHostKeyConfirmationRequired(host, keyType, fingerprint) {
            if (devicesPanel.pendingScpHost !== String(host || ""))
                return
            scpHostKeyDialog.messageText = "Host: " + host
                + "\nKey type: " + keyType
                + "\nFingerprint: " + fingerprint
                + "\n\nContinue only if this fingerprint matches the device you manage."
            scpHostKeyDialog.open()
        }
    }

    Timer {
        id: pythonDepsCheckTimer
        interval: 1
        repeat: false

        onTriggered: {
            if (devicesPanel.pythonDepsChecking)
                return

            devicesPanel.pythonDepsChecking = true
            devicesPanel.pythonDepsStatus = "checking"
            devicesPanel.pythonDepsStatusText = "CHECKING..."
            devicesPanel.pythonDepsStatusDetail = "Checking Python runtime and database schemas..."

            const result = cli.ensurePythonLoginDeps()
            const detailMessage = result.message ? String(result.message) : "Python dependency check finished."

            devicesPanel.pythonDepsStatus = result.ok ? "success" : "error"
            devicesPanel.pythonDepsStatusText = result.statusText
                                               ? String(result.statusText)
                                               : (result.ok ? "SYSTEM READY" : "NOT READY")
            devicesPanel.pythonDepsStatusDetail = detailMessage
            devicesPanel.pythonDepsChecking = false
        }
    }
    Timer { id: searchDebounceTimer; interval: 300; repeat: false; onTriggered: devicesPanel.applyFilters() }

    SftpMessageDialog {
        id: scpConfirmDialog
        parent: Overlay.overlay
        property string targetHost: ""
        titleText: "Get running-config via SCP"
        confirmation: true
        acceptText: "Get config"
        onAccepted: {
            const host = targetHost
            targetHost = ""
            if (typeof sftpController === "undefined" || !sftpController) {
                devicesPanel.showDeviceShortcutMessage(
                    "SCP client backend is unavailable.", "error"
                )
                return
            }
            devicesPanel.pendingScpHost = host
            sftpController.getRunningConfigViaScpForDevice(host)
        }
        onRejected: targetHost = ""
    }

    SftpMessageDialog {
        id: scpHostKeyDialog
        parent: Overlay.overlay
        titleText: "Confirm SSH Host Key"
        confirmation: true
        acceptText: "Trust and Continue"
        onAccepted: {
            if (typeof sftpController !== "undefined" && sftpController)
                sftpController.confirmHostKey(true)
        }
        onRejected: {
            if (typeof sftpController !== "undefined" && sftpController)
                sftpController.confirmHostKey(false)
        }
    }

    Shortcut { sequence: "Ctrl+N"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: { UiState.windowLock = true; devicesPanel.openNewDeviceWindow() } }
    Shortcut { sequence: "Ctrl+Alt+N"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: { UiState.windowLock = true; devicesPanel.openBatchDeviceWindow() } }
    Shortcut { sequence: "F2"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleShortcutEdit() }
    Shortcut { sequence: "Ctrl+Alt+P"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleShortcutPing() }
    Shortcut { sequence: "Ctrl+Alt+Down"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleShortcutDownDev() }
    Shortcut { sequence: "Ctrl+Alt+Up"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleShortcutUpDev() }
    Shortcut { sequence: "Ctrl+Alt+C"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleShortcutConnect() }
    Shortcut { sequence: "Ctrl+Alt+R"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleShortcutReconnect() }
    Shortcut { sequence: "Ctrl+Shift+C"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleBatchOperation("connect", devicesPanel.selectedHostList) }
    Shortcut { sequence: "Ctrl+Shift+R"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleBatchOperation("running-config", devicesPanel.selectedHostList) }
    Shortcut { sequence: "Ctrl+Shift+D"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.handleBatchOperation("disconnect", devicesPanel.selectedHostList) }
    Shortcut { sequence: StandardKey.SelectAll; enabled: devicesPanel.deviceShortcutEnabled && devicesPanel.multiSelectMode; onActivated: devicesPanel.selectAllVisibleHosts() }
    Shortcut { sequence: "Escape"; enabled: devicesPanel.deviceShortcutEnabled; onActivated: devicesPanel.clearSelection() }

    StandardDialog {
        id: deleteConfirmationDialog
        objectName: "devicePermanentDeleteDialog"
        preferredWidth: 520
        title: "Permanently delete host?"
        closeTooltip: "Cancel host deletion"
        property string targetIp: ""
        readonly property string confirmationPhrase: "DELETE " + targetIp
        readonly property bool confirmed: deleteAcknowledgement.checked
                                                  && deleteConfirmationField.text
                                                     === confirmationPhrase

        contentItem: ColumnLayout {
            spacing: Theme.spacing12

            InlineMessage {
                Layout.fillWidth: true
                severity: "error"
                message: "This permanently deletes " + deleteConfirmationDialog.targetIp
                         + ", its configuration, collected data, Syslog data, and backup history. This cannot be undone."
            }

            StandardCheckBox {
                id: deleteAcknowledgement
                objectName: "deviceDeleteAcknowledgement"
                Layout.fillWidth: true
                text: "I understand that all data related to this host will be permanently deleted."
            }

            Text {
                Layout.fillWidth: true
                text: "Type “" + deleteConfirmationDialog.confirmationPhrase + "” to confirm:"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                wrapMode: Text.WordWrap
            }

            StandardTextField {
                id: deleteConfirmationField
                objectName: "deviceDeleteConfirmationField"
                Layout.fillWidth: true
                placeholderText: deleteConfirmationDialog.confirmationPhrase
            }
        }

        footer: Rectangle {
            implicitHeight: 58
            color: "transparent"
            RowLayout {
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing16
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacing8

                StandardButton {
                    text: "Cancel"
                    type: "Text"
                    onClicked: deleteConfirmationDialog.close()
                }
                StandardButton {
                    objectName: "devicePermanentDeleteButton"
                    text: "Permanently Delete"
                    type: "Danger"
                    enabled: deleteConfirmationDialog.confirmed
                    onClicked: {
                        const targetIp = deleteConfirmationDialog.targetIp
                        deleteConfirmationDialog.close()
                        if (typeof cli !== "undefined" && cli.closeDeviceSession)
                            cli.closeDeviceSession(targetIp)
                        const result = dbManager.deleteDevice(targetIp)
                        devicesPanel.notifyOperationResult(
                            result, "Delete finished for " + targetIp + ".")
                        if (result && result.ok) {
                            devicesPanel.reloadDevices()
                            devicesPanel.deviceDeleted(targetIp)
                        }
                        deleteConfirmationDialog.targetIp = ""
                    }
                }
            }
        }

        onClosed: {
            deleteAcknowledgement.checked = false
            deleteConfirmationField.text = ""
        }
    }
    StandardDialog {
        id: manualSyncDecisionDialog
        parent: Overlay.overlay
        property string targetHost: ""
        property var conflicts: []
        preferredWidth: 520
        title: "Manual Sync conflict"
        subtitle: targetHost
        closeEnabled: true
        onClosed: {
            if (devicesPanel.pendingManualSyncHost === targetHost) {
                devicesPanel.pendingManualSyncHost = ""
            }
        }
        contentItem: ColumnLayout {
            spacing: 14
            InlineMessage {
                Layout.fillWidth: true
                severity: "warning"
                message: "Pending local changes exist in: "
                         + manualSyncDecisionDialog.conflicts.join(", ")
                         + ". Choose which state should win."
            }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Theme.textSecondary
                text: "Keep pending changes skips those modules. Use device state discards pending database changes and replaces them with the latest running-config."
            }
            RowLayout {
                Layout.fillWidth: true
                StandardButton {
                    text: "Cancel"
                    type: "Text"
                    onClicked: manualSyncDecisionDialog.close()
                }
                Item { Layout.fillWidth: true }
                StandardButton {
                    text: "Keep pending changes"
                    type: "Secondary"
                    onClicked: {
                        const host = manualSyncDecisionDialog.targetHost
                        manualSyncDecisionDialog.targetHost = ""
                        manualSyncDecisionDialog.close()
                        cli.applyManualSyncAsync(host, "safe")
                    }
                }
                StandardButton {
                    text: "Use device state"
                    type: "Danger"
                    onClicked: {
                        const host = manualSyncDecisionDialog.targetHost
                        manualSyncDecisionDialog.targetHost = ""
                        manualSyncDecisionDialog.close()
                        cli.applyManualSyncAsync(host, "force_device_state")
                    }
                }
            }
        }
    }
    Loader { id: newDeviceLoader; active: false; sourceComponent: Component { NewDevice { onDeviceAdded: function(newDev) { devicesPanel.reloadDevices(); const added = devicesPanel.allDevices.find(function(d) { return d.ip === newDev.ip }); if (added && added.status === "waiting") { if (typeof statusBar !== "undefined") statusBar.showMessage("Device added in waiting state. Configuration is disabled until connected.", "warning"); return } devicesPanel.deviceSelected(newDev.ip, newDev.name, added ? added.type : (newDev.type || "unknown"), added ? added.status : (newDev.status || "connected")) }; onDeviceEdited: function(originalIp, dev) { if (typeof cli !== "undefined" && cli.closeDeviceSession) cli.closeDeviceSession(originalIp); devicesPanel.reloadDevices() } } } }
    Loader {
        id: batchDeviceLoader
        active: false
        sourceComponent: Component {
            BatchNewDevice {
                onDevicesAdded: function(addedList, totalRows, skipped, foldersOk) {
                    devicesPanel.reloadDevices()
                    if (typeof statusBar !== "undefined" && addedList.length > 0) {
                        const hasSkipped = skipped !== undefined && skipped > 0
                        const folderFailed = foldersOk !== undefined && !foldersOk
                        const totalText = totalRows !== undefined && totalRows > 0 ? "/" + totalRows : ""
                        let suffix = hasSkipped ? ". Skipped: %1.".arg(skipped) : "."
                        if (folderFailed)
                            suffix += " Backup folder creation failed."
                        statusBar.showMessage("Added %1%2 devices from batch input%3".arg(addedList.length).arg(totalText).arg(suffix), (hasSkipped || folderFailed) ? "warning" : "success")
                    }
                }
            }
        }
    }

    Component.onCompleted: { devicesPanel.reloadDevices(); pythonDepsCheckTimer.restart() }
}
