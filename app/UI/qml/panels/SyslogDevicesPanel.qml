pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Item {
    id: root
    objectName: "syslogDevicesPanel"

    property var devices: []
    property var filteredDevices: []
    // SyslogGroupDialog also serves per-device forms. An empty host marks this
    // owner as the connected-host panel, which should refresh after any group save.
    property string host: ""
    property string selectedHost: ""
    property var selectedHosts: ({})
    property string anchorHost: ""
    property bool selectionMode: false
    readonly property var selectedHostList: Object.keys(selectedHosts)
    property bool busy: false
    readonly property var backend: typeof syslogManager !== "undefined" && syslogManager !== null
                                   ? syslogManager : null

    signal hostSelected(string host)
    signal operationFinished(bool ok, string message)

    function notify(message, type) {
        operationFinished(type !== "error", String(message || ""))
    }

    function reloadData(reason) {
        reloadDevices()
        return true
    }

    function setHostSelected(host, selected) {
        const target = String(host || "")
        if (target === "") return
        const next = Object.assign({}, selectedHosts)
        if (selected) next[target] = true
        else delete next[target]
        selectedHosts = next
        anchorHost = target
        selectionMode = Object.keys(next).length > 0
    }

    function toggleHost(host) {
        setHostSelected(host, selectedHosts[String(host || "")] !== true)
    }

    function clearSelection() {
        selectedHosts = ({})
        anchorHost = ""
        selectionMode = false
    }

    function reconcileSelection() {
        const valid = ({})
        for (let i = 0; i < devices.length; ++i)
            valid[String(devices[i].host || "")] = true
        const next = ({})
        const hosts = selectedHostList
        for (let i = 0; i < hosts.length; ++i) {
            if (valid[hosts[i]]) next[hosts[i]] = true
        }
        selectedHosts = next
        selectionMode = Object.keys(next).length > 0
        if (anchorHost !== "" && !valid[anchorHost]) anchorHost = ""
    }

    function visibleHosts() {
        return filteredDevices.map(row => String(row.host || ""))
    }

    function selectAllVisible() {
        const next = ({})
        const hosts = visibleHosts()
        for (let i = 0; i < hosts.length; ++i)
            next[hosts[i]] = true
        selectedHosts = next
        selectionMode = hosts.length > 0
        if (hosts.length > 0) anchorHost = hosts[0]
    }

    function selectRangeTo(host) {
        const hosts = visibleHosts()
        const targetIndex = hosts.indexOf(String(host || ""))
        if (targetIndex < 0) return
        let anchorIndex = hosts.indexOf(anchorHost)
        if (anchorIndex < 0) anchorIndex = targetIndex
        const next = ({})
        for (let i = Math.min(anchorIndex, targetIndex);
                i <= Math.max(anchorIndex, targetIndex); ++i)
            next[hosts[i]] = true
        selectedHosts = next
        selectionMode = true
    }

    function openHostContext(host, configured, sceneX, sceneY) {
        const target = String(host || "")
        if (selectionMode && selectedHosts[target] !== true)
            setHostSelected(target, true)
        hostContextMenu.selectionMode = selectionMode
        hostContextMenu.openAt(
            sceneX, sceneY, target, configured,
            selectionMode ? selectedHostList : [target])
    }

    function applyFilter() {
        const value = search.text.toLowerCase().trim()
        filteredDevices = devices.filter(function(row) {
            return value === ""
                || String(row.host || "").toLowerCase().indexOf(value) >= 0
                || String(row.device_name || "").toLowerCase().indexOf(value) >= 0
        })
    }

    function reloadDevices() {
        if (backend !== null)
            backend.loadConnectedDevices()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 36

            Text {
                objectName: "syslogPanelHeaderTitle"
                anchors.left: parent.left
                anchors.leftMargin: Theme.spacing16
                anchors.right: hostCountBadge.left
                anchors.rightMargin: Theme.spacing8
                anchors.verticalCenter: parent.verticalCenter
                text: "HOSTS"
                elide: Text.ElideRight
                color: Theme.panelSideBarTextSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.capitalization: Font.AllUppercase
                font.weight: Font.Medium
            }

            StandardBadge {
                id: hostCountBadge
                objectName: "syslogPanelHostCountBadge"
                anchors.right: reloadButton.left
                anchors.rightMargin: Theme.spacing8
                anchors.verticalCenter: parent.verticalCenter
                text: String(root.devices.length)
                badgeColor: Theme.accentEmphasis
            }

            IconButton {
                id: reloadButton
                objectName: "syslogPanelReloadButton"
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing8
                anchors.verticalCenter: parent.verticalCenter
                buttonSize: Theme.sideBarFeatureIcon
                iconSource: AppAssets.actionRefresh
                idleColor: Theme.panelSideBarTextSecondary
                activeColor: Theme.panelSideBarTextPrimary
                selectedBackground: Theme.panelSideBarItemSelected
                hoverBackground: Theme.panelSideBarItemHover
                tooltip: root.busy ? "Refreshing Connected Hosts..." : "Refresh Connected Hosts"
                enabled: root.backend !== null && !root.busy
                onClicked: root.reloadDevices()
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.borderWidth
                color: Theme.panelSideBarBorderColor
            }
        }

        SideBarSearch {
            id: search
            Layout.fillWidth: true
            Layout.margins: Theme.spacing8
            placeholderText: "Search connected hosts..."
            onTextChanged: debounce.restart()
        }

        DeviceBatchActionBar {
            Layout.fillWidth: true
            visible: root.selectionMode
            selectedCount: root.selectedHostList.length
            visibleCount: root.filteredDevices.length
            onSelectAllRequested: root.selectAllVisible()
            onClearRequested: root.clearSelection()
        }

        ListView {
            id: deviceList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.filteredDevices
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: SyslogDeviceItem {
                required property var modelData
                width: ListView.view.width
                deviceData: modelData
                selected: root.selectedHost === String(modelData.host || "")
                batchSelected: root.selectedHosts[String(modelData.host || "")] === true
                selectionMode: root.selectionMode
                onClicked: function(host) {
                    if (root.selectionMode) {
                        root.toggleHost(host)
                        return
                    }
                    root.selectedHost = host
                    root.hostSelected(host)
                }
                onToggleSelectionRequested: host => root.toggleHost(host)
                onRangeSelectionRequested: host => root.selectRangeTo(host)
                onRightClicked: (host, configured, x, y) =>
                    root.openHostContext(host, configured, x, y)
            }

            Text {
                anchors.centerIn: parent
                width: Math.max(0, parent.width - Theme.spacing32)
                visible: root.filteredDevices.length === 0
                text: root.backend === null
                      ? "System Logs backend is unavailable."
                      : root.devices.length === 0
                        ? "No connected devices.\nConnect a device from Dashboard first."
                        : "No hosts match the current search."
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: Theme.panelSideBarTextSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
        }

    }

    SyslogDeviceContextMenu {
        id: hostContextMenu
        parent: Overlay.overlay
        busy: root.busy
        onConfigureRequested: function(host) {
            if (root.backend !== null)
                root.backend.configureDevice(host)
        }
        onCancelRequested: function(host) {
            if (root.backend !== null)
                root.backend.cancelDevice(host)
        }
        onGroupRequested: hosts => groupDialog.openFor(root, hosts)
        onClearSelectionRequested: root.clearSelection()
    }

    SyslogSourceInterfaceDialog {
        id: sourceInterfaceDialog
        parent: Overlay.overlay
        onPushRequested: function(host, sourceInterface) {
            if (root.backend !== null)
                root.backend.configureDeviceWithInterface(host, sourceInterface)
        }
    }

    SyslogGroupDialog {
        id: groupDialog
        parent: Overlay.overlay
    }

    Timer {
        id: debounce
        interval: 250
        repeat: false
        onTriggered: root.applyFilter()
    }

    Timer {
        interval: 5000
        repeat: true
        running: root.visible && root.backend !== null
        onTriggered: root.reloadDevices()
    }

    Connections {
        target: root.backend

        function onConnectedDevicesChanged(rows) {
            root.devices = rows || []
            root.reconcileSelection()
            root.applyFilter()
        }

        function onDeviceConfigStarted(host, action) {
            root.busy = true
        }

        function onDeviceConfigFinished(host, action, ok, message) {
            root.busy = false
            root.operationFinished(Boolean(ok), String(message || ""))
            root.reloadDevices()
        }

        function onSourceInterfaceRequired(host, message) {
            root.busy = false
            sourceInterfaceDialog.openFor(String(host || ""), String(message || ""))
        }

    }

    onVisibleChanged: {
        if (visible)
            reloadDevices()
    }

    Shortcut {
        sequence: StandardKey.SelectAll
        enabled: root.visible && root.selectionMode
        onActivated: root.selectAllVisible()
    }
    Shortcut {
        sequence: "Escape"
        enabled: root.visible && root.selectionMode
        onActivated: root.clearSelection()
    }
}
