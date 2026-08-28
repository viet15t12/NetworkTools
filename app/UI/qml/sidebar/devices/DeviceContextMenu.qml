pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: contextMenu

    // ── Thông tin thiết bị đang được right-click ──
    property string targetHost: ""
    property string targetStatus: ""
    property bool targetIsDevelopment: false
    property var batchHosts: []
    property var hostStatuses: ({})
    property var hostOperations: ({})
    property bool selectionMode: false
    property bool allowHostDeletion: false
    readonly property var connectedBatchHosts: filteredBatchHosts("connected")
    readonly property var waitingBatchHosts: filteredBatchHosts("waiting")
    readonly property bool canPing: targetStatus === "connected"
    readonly property bool isWaiting: targetStatus === "waiting"
    readonly property bool isConnected: targetStatus === "connected"
    readonly property bool isDisconnected: targetStatus === "disconnected"
    readonly property bool targetConnectRunning: {
        const operation = hostOperations[targetHost]
        return Boolean(operation)
               && (operation.state === "queued" || operation.state === "running")
    }
    readonly property int menuWidth: 300
    readonly property color menuBorderColor: Theme.isHighContrast
                                             ? Theme.panelSideBarBorderColor
                                             : (Theme.isDarkMode ? Qt.rgba(1, 1, 1, 0.12)
                                                                 : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.12))
    readonly property color menuDividerColor: Theme.isHighContrast
                                              ? Theme.panelSideBarBorderColor
                                              : (Theme.isDarkMode ? Qt.rgba(1, 1, 1, 0.14)
                                                                  : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.14))
    readonly property color menuShadowColor: Theme.isDarkMode ? Qt.rgba(0, 0, 0, 0.24)
                                                              : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.06)

    // ── Signals bắn ra ngoài khi người dùng chọn ──
    signal editRequested(string ip)
    signal deleteRequested(string ip)
    signal pingRequested(string ip)
    signal runningConfigRequested(string ip)
    signal runningConfigScpRequested(string ip)
    signal saveConfigRequested(string ip)
    signal syncRequested(string ip)
    // Compatibility signal for consumers created before the Sync spelling fix.
    signal sysSyncRequested(string ip)
    signal upDevRequested(string ip)
    signal downDevRequested(string ip)
    signal connecRequested(string ip)
    signal reconnectRequested(string ip)
    signal cliRequested(string ip)
    signal connectBatchRequested(var hosts)
    signal runningConfigBatchRequested(var hosts)
    signal disconnectBatchRequested(var hosts)
    signal selectAllVisibleRequested()
    signal clearSelectionRequested()
    signal startMultipleSelectionRequested(string host)

    // ── Hàm mở menu tại tọa độ cửa sổ ──
    function filteredBatchHosts(status) {
        const result = []
        for (let i = 0; i < batchHosts.length; ++i) {
            const host = String(batchHosts[i] || "")
            if (String(hostStatuses[host] || "") === status)
                result.push(host)
        }
        return result
    }

    function openForHost(host, status, selectedHosts, statuses, x, y) {
        targetHost = String(host || "")
        targetStatus = status || ""
        batchHosts = (selectedHosts || []).slice(0)
        hostStatuses = Object.assign({}, statuses || ({}))

        // Ngăn menu bị tràn ra ngoài cạnh phải / dưới màn hình
        const win = Window.window
        if (win) {
            contextMenu.x = Math.min(x, win.width  - contextMenu.width  - 4)
            contextMenu.y = Math.min(y, win.height - contextMenu.height - 4)
        } else {
            contextMenu.x = x
            contextMenu.y = y
        }

        visible = true
    }

    function close() {
        visible = false
        targetHost = ""
        targetStatus = ""
        targetIsDevelopment = false
        batchHosts = []
        hostStatuses = ({})
    }

    // ── Giao diện ──
    visible: false
    width: menuWidth
    height: menuColumn.implicitHeight + 8
    z: 999  // Nổi trên tất cả

    color: Theme.panelSideBarSurface
    border.color: menuBorderColor
    border.width: Theme.borderWidth
    radius: 6

    // Đổ bóng nhẹ bằng một viền ngoài rất mờ để không tạo cảm giác hai lớp border.
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: parent.radius + 2
        color: "transparent"
        border.color: contextMenu.menuShadowColor
        border.width: Theme.borderWidth
        z: -1
    }

    // Đóng menu khi click ra ngoài
    Item {
        id: outsideClickCatcher
        parent: Window.window ? Window.window.contentItem : null
        anchors.fill: parent
        visible: contextMenu.visible
        z: 998

        TapHandler {
            onTapped: contextMenu.close()
        }
    }
    // lựa chọn khii chột phải
    Column {
        id: menuColumn
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 4
        anchors.leftMargin: 4
        anchors.rightMargin: 4
        anchors.bottomMargin: 4
        spacing: 0

        Rectangle {
            visible: contextMenu.selectionMode
            width: parent.width
            height: visible ? 48 : 0
            radius: Theme.radiusSmall
            color: Theme.alertInfoSubtle

            Column {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacing8
                anchors.rightMargin: Theme.spacing8
                anchors.topMargin: Theme.spacing4
                anchors.bottomMargin: Theme.spacing4
                spacing: Theme.spacing2

                Text {
                    width: parent.width
                    text: contextMenu.batchHosts.length + " hosts selected"
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeNormal
                    font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: contextMenu.connectedBatchHosts.length + " connected · "
                          + contextMenu.waitingBatchHosts.length + " waiting"
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    elide: Text.ElideRight
                }
            }
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode
            text: "Select multiple"
            onTriggered: {
                contextMenu.startMultipleSelectionRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: contextMenu.selectionMode
            text: "Select all visible hosts"
            onTriggered: {
                contextMenu.selectAllVisibleRequested()
                contextMenu.close()
            }
        }

        ContextMenuDivider {
            visible: !contextMenu.selectionMode
            lineColor: contextMenu.menuDividerColor
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode
            text: "Edit"
            shortcutText: "F2"
            iconSource: AppAssets.actionEdit
            onTriggered: {
                contextMenu.editRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuDivider {
            visible: !contextMenu.selectionMode
            lineColor: contextMenu.menuDividerColor
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode
            text: "Ping"
            enabled: contextMenu.canPing
            reserveIconSpace: true
            shortcutText: "Ctrl+Alt+P"
            onTriggered: {
                contextMenu.pingRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode && contextMenu.isConnected
            enabled: !contextMenu.targetConnectRunning
            text: "Get running-config"
            iconSource: AppAssets.actionBackup
            reserveIconSpace: true
            onTriggered: {
                contextMenu.runningConfigRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            // NOTE: chuc nang chua phat trien xong, khong tam quan tam nieu viet bao cao
            visible: false
            enabled: !contextMenu.targetConnectRunning
            text: "Get running-config via SCP"
            iconSource: AppAssets.actionDownload
            reserveIconSpace: true
            onTriggered: {
                contextMenu.runningConfigScpRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode && contextMenu.isConnected
            enabled: !contextMenu.targetConnectRunning
            text: "Save configuration"
            iconSource: AppAssets.actionSave
            reserveIconSpace: true
            onTriggered: {
                contextMenu.saveConfigRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode && contextMenu.isConnected
            enabled: !contextMenu.targetConnectRunning
            text: "Sync"
            reserveIconSpace: true
            onTriggered: {
                contextMenu.syncRequested(contextMenu.targetHost)
                contextMenu.sysSyncRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode
                     && contextMenu.isConnected
                     && contextMenu.targetIsDevelopment
            text: "Switch to Live Connection"
            shortcutText: "Ctrl+Alt+Down"
            iconSource: AppAssets.actionMonitorStop
            onTriggered: {
                contextMenu.downDevRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            // Keep the DEV transition available to existing internal flows and
            // shortcuts, but do not expose the development-only menu action.
            visible: false
            text: "Enable Development Mode"
            shortcutText: "Ctrl+Alt+Up"
            iconSource: AppAssets.actionMonitorStart
            onTriggered: {
                contextMenu.upDevRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode && contextMenu.isWaiting
            enabled: !contextMenu.targetConnectRunning
            text: contextMenu.targetConnectRunning
                  ? "Connect (Running...)"
                  : "Connect"
            shortcutText: "Ctrl+Alt+C"
            onTriggered: {
                contextMenu.connecRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode && contextMenu.isDisconnected
            text: "Reconnect"
            shortcutText: "Ctrl+Alt+R"
            iconSource: AppAssets.actionMonitorStart
            onTriggered: {
                contextMenu.reconnectRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuDivider {
            visible: contextMenu.selectionMode
            lineColor: contextMenu.menuDividerColor
        }

        ContextMenuItem {
            visible: contextMenu.selectionMode
            enabled: contextMenu.waitingBatchHosts.length > 0
            text: "Connect waiting (" + contextMenu.waitingBatchHosts.length + ")"
            shortcutText: "Ctrl+Shift+C"
            onTriggered: {
                contextMenu.connectBatchRequested(contextMenu.waitingBatchHosts.slice(0))
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: contextMenu.selectionMode
            enabled: contextMenu.connectedBatchHosts.length > 0
            text: "Get configs from connected (" + contextMenu.connectedBatchHosts.length + ")"
            shortcutText: "Ctrl+Shift+R"
            onTriggered: {
                contextMenu.runningConfigBatchRequested(contextMenu.connectedBatchHosts.slice(0))
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: contextMenu.selectionMode
            enabled: contextMenu.connectedBatchHosts.length > 0
            text: "Disconnect connected (" + contextMenu.connectedBatchHosts.length + ")"
            shortcutText: "Ctrl+Shift+D"
            onTriggered: {
                contextMenu.disconnectBatchRequested(contextMenu.connectedBatchHosts.slice(0))
                contextMenu.close()
            }
        }

        ContextMenuItem {
            visible: contextMenu.selectionMode
            text: "Clear selection and exit"
            onTriggered: {
                contextMenu.clearSelectionRequested()
                contextMenu.close()
            }
        }

        ContextMenuDivider {
            visible: !contextMenu.selectionMode
            lineColor: contextMenu.menuDividerColor
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode
            text: "NetworkTools Terminal"
            shortcutText: "Ctrl+`"
            iconSource: AppAssets.navigationTerminal
            onTriggered: {
                contextMenu.cliRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }

        ContextMenuDivider {
            visible: !contextMenu.selectionMode
            lineColor: contextMenu.menuDividerColor
        }

        ContextMenuItem {
            visible: !contextMenu.selectionMode
            enabled: contextMenu.allowHostDeletion
            text: "Delete"
            shortcutText: contextMenu.allowHostDeletion ? "Del" : "Disabled"
            iconSource: AppAssets.actionDelete
            danger: true
            onTriggered: {
                contextMenu.deleteRequested(contextMenu.targetHost)
                contextMenu.close()
            }
        }
    }

    // Animation mở ra mượt mà
    NumberAnimation on opacity {
        id: fadeIn
        running: contextMenu.visible
        from: 0.0; to: 1.0
        duration: Theme.animationDurationFast
        easing.type: Easing.OutQuad
    }

    NumberAnimation on scale {
        running: contextMenu.visible
        from: 0.95; to: 1.0
        duration: Theme.animationDurationFast
        easing.type: Easing.OutQuad
    }

    transformOrigin: Item.TopLeft
}
