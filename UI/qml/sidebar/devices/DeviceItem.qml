pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: deviceItem

    required property int index
    required property var modelData

    property string deviceName: ""
    property string deviceIp:   ""
    property string deviceType: ""
    property bool isActive: false
    property bool isBatchSelected: false
    property bool selectionMode: false
    property string operationState: "idle"
    property string operationMessage: ""
    property string displayFormat: "name"
    property string status: "connected"

    readonly property bool blockedByStatus: status === "waiting"

    // ── Logic hiển thị text ───────────────────────────────────────────────────
    function preferredHostLabel() {
        const name = String(deviceName || "").trim()
        const ip = String(deviceIp || "").trim()

        if (name !== "" && ip !== "" && name !== ip)
            return name + " - " + ip
        return name !== "" ? name : ip
    }

    property string displayText: {
        if (displayFormat === "ip")
            return String(deviceIp || "").trim()
        if (displayFormat === "name") {
            const name = String(deviceName || "").trim()
            return name !== "" ? name : String(deviceIp || "").trim()
        }
        return preferredHostLabel()
    }

    // ── Logic icon ────────────────────────────────────────────────────────────
    // "unknown" hoặc "" → không có icon → hiển thị dot
    property string iconSource: {
        if (deviceType === "router")
            return AppAssets.deviceRouter
        if (deviceType === "sw2" || deviceType === "sw3")
            return AppAssets.deviceSwitch
        return ""   // unknown / chưa xác định → dot
    }

    // ── Logic màu status ──────────────────────────────────────────────────────
    property color statusColor: {
        if (status === "connected")    return Theme.statusConnected
        if (status === "waiting")      return Theme.statusWaiting
        return Theme.statusDisconnected
    }

    readonly property string statusLabel: {
        if (status === "connected") return "Connected"
        if (status === "waiting") return "Waiting"
        return "Disconnected"
    }

    // ── Màu dot riêng cho unknown ─────────────────────────────────────────────
    // Unknown device dùng màu muted hơn để phân biệt với disconnected
    property color dotColor: statusColor

    ToolTip.visible: itemHover.hovered
    ToolTip.text:    preferredHostLabel()
                       + (deviceType !== "" && deviceType !== "unknown"
                                     ? "  ·  " + deviceType
                                     : "  ·  unknown")
                       + "\nConnection: " + statusLabel
    ToolTip.delay:   400

    width:   parent.width
    height:  Theme.listItemHeight
    opacity: 1.0

    color: isActive          ? Theme.panelSideBarItemSelected :
           isBatchSelected   ? Qt.rgba(Theme.panelSideBarAccentColor.r,
                                      Theme.panelSideBarAccentColor.g,
                                      Theme.panelSideBarAccentColor.b, 0.16) :
           itemHover.hovered ? Theme.panelSideBarItemHover    : "transparent"

    signal activated(string host)
    signal toggleSelectionRequested(string host)
    signal rangeSelectionRequested(string host)
    signal rightClicked(string ip, int mouseX, int mouseY)

    // ── Active border bên trái ────────────────────────────────────────────────
    Rectangle {
        width:  3
        height: parent.height
        anchors.left: parent.left
        color:   Theme.panelSideBarAccentColor
        opacity: isActive ? 1.0 : 0.0
    }

    // ── Icon / Status dot ─────────────────────────────────────────────────────
    Item {
        id: iconContainer
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        width:  16
        height: 16

        // Icon SVG — chỉ hiện khi có iconSource
        ThemedIcon {
            visible:          deviceItem.iconSource !== ""
            anchors.centerIn: parent
            iconSource: deviceItem.iconSource
            iconSize: 16
            iconColor: deviceItem.statusColor
        }

        // Dot SVG — hiện khi không có icon (unknown/rỗng)
        ThemedIcon {
            visible:          deviceItem.iconSource === ""
            anchors.centerIn: parent
            iconSource: AppAssets.deviceStatusDot
            iconSize: 32
            iconColor: deviceItem.dotColor
        }
    }

    // ── Text ─────────────────────────────────────────────────────────────────
    Text {
        anchors.left:           iconContainer.right
        anchors.leftMargin:     10
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: deviceItem.selectionMode
                       ? selectionIndicator.left : operationBadge.left
        anchors.rightMargin: 6

        text:           deviceItem.displayText
        color:          isActive ? Theme.panelSideBarTextPrimary
                                 : (blockedByStatus ? Theme.panelSideBarTextDisabled
                                                    : Theme.panelSideBarTextSecondary)
        font.pixelSize: Theme.fontSizeNormal
        font.family:    Theme.fontFamily
        elide:          Text.ElideRight
    }

    Rectangle {
        id: selectionIndicator
        visible: deviceItem.selectionMode
        anchors.right: operationBadge.left
        anchors.rightMargin: Theme.spacing4
        anchors.verticalCenter: parent.verticalCenter
        width: 18
        height: 18
        radius: 4
        color: deviceItem.isBatchSelected
               ? Theme.panelSideBarAccentColor : "transparent"
        border.color: deviceItem.isBatchSelected
                      ? Theme.panelSideBarAccentColor : Theme.panelSideBarTextSecondary
        border.width: Theme.borderWidth

        Text {
            anchors.centerIn: parent
            text: "✓"
            visible: deviceItem.isBatchSelected
            color: Theme.selectionForeground
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            font.bold: true
        }
    }

    DeviceOperationBadge {
        id: operationBadge
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        state: deviceItem.operationState
        message: deviceItem.operationMessage
    }

    HoverHandler { id: itemHover }

    TapHandler {
        enabled: deviceItem.selectionMode || !deviceItem.blockedByStatus
        acceptedButtons: Qt.LeftButton
        acceptedModifiers: Qt.NoModifier
        onTapped: deviceItem.activated(deviceItem.deviceIp)
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        acceptedModifiers: Qt.ControlModifier
        onTapped: deviceItem.toggleSelectionRequested(deviceItem.deviceIp)
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        acceptedModifiers: Qt.ShiftModifier
        onTapped: deviceItem.rangeSelectionRequested(deviceItem.deviceIp)
    }

    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: (eventPoint) => {
            const globalPos = deviceItem.mapToItem(
                null,
                eventPoint.position.x,
                eventPoint.position.y
            )
            deviceItem.rightClicked(
                deviceIp,
                globalPos.x,
                globalPos.y
            )
        }
    }
}
