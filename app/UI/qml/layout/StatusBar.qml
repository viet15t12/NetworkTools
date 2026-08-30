pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    width: parent ? parent.width : 800
    height: StatusBarState.isVisible ? Theme.statusBarHeight : 0
    visible: StatusBarState.isVisible
    clip: true
    color: Theme.statusBarBackground

    property int unreadCount: 0
    property bool isDND: false
    property bool isNotificationOpen: false
    property string pythonStatusText: "STARTING..."
    property string pythonStatusType: "idle"
    property string pythonStatusDetail: ""
    property bool pythonStatusBusy: false
    property bool taskVisible: false
    property bool taskBusy: false
    property bool taskOk: true
    property string taskMessage: ""
    property real taskProgress: -1
    property date currentDateTime: new Date()
    readonly property bool notificationShouldBlink: root.isDND
                                                    && root.unreadCount > 0
                                                    && !root.isNotificationOpen

    readonly property bool netConnected: networkMonitor ? networkMonitor.isConnected : false
    readonly property string netType: networkMonitor ? networkMonitor.connectionType : "none"
    readonly property string netName: networkMonitor ? networkMonitor.networkName : ""
    readonly property var virtualLabs: networkMonitor ? networkMonitor.virtualLabs : []
    readonly property int virtualLabCount: networkMonitor ? networkMonitor.virtualLabCount : 0
    readonly property string virtualLabName: networkMonitor ? networkMonitor.virtualLabName : ""
    readonly property string virtualLabState: networkMonitor ? networkMonitor.virtualLabState : "offline"
    readonly property bool virtualLabActive: networkMonitor ? networkMonitor.virtualLabActive : false
    readonly property string virtualLabPlatform: networkMonitor ? networkMonitor.virtualLabPlatform : ""
    readonly property string virtualLabServerIp: networkMonitor ? networkMonitor.virtualLabServerIp : ""
    readonly property string virtualLabUrl: networkMonitor ? networkMonitor.virtualLabUrl : ""
    readonly property string virtualLabDetectedName: networkMonitor ? networkMonitor.virtualLabNameDetected : ""
    readonly property string virtualLabDetail: networkMonitor ? networkMonitor.virtualLabDetail : ""
    readonly property int virtualLabRunningNodeCount: networkMonitor ? networkMonitor.virtualLabRunningNodeCount : 0
    readonly property int ramUsagePct: networkMonitor
                                       ? Math.max(0, Math.min(100, networkMonitor.ramUsagePercent))
                                       : 0

    readonly property string normalizedNetType: (root.netType || "").toLowerCase()
    readonly property bool ramSectionVisible: StatusBarState.showRam
                                              && (StatusBarState.showRamBar || StatusBarState.showRamText)
    readonly property bool dateTimeSectionVisible: StatusBarState.showDate || StatusBarState.showTime
    readonly property int ramWarningThreshold: Math.max(1, Math.min(100, StatusBarState.ramWarningThreshold))
    readonly property bool ramHigh: StatusBarState.ramWarningEnabled
                                    && root.ramUsagePct >= root.ramWarningThreshold

    readonly property color pythonStatusColor: {
        if (root.pythonStatusBusy || root.pythonStatusType === "checking")
            return Theme.alertWarning
        if (root.pythonStatusType === "success")
            return Theme.buttonTextSolid
        if (root.pythonStatusType === "error")
            return Theme.alertError
        return Theme.statusBarDimText
    }

    readonly property color networkColor: {
        if (root.hasVirtualLab()) {
            if (root.virtualLabActive)
                return Theme.buttonTextSolid
            if (root.virtualLabState === "starting")
                return Theme.statusBarWarningText
            return Theme.statusBarDimText
        }
        return root.netConnected ? Theme.buttonTextSolid : Theme.statusBarDimText
    }
    readonly property color ramBarColor: Theme.buttonTextSolid
    readonly property color ramTextColor: Theme.buttonTextSolid

    signal bellClicked()
    signal pythonStatusClicked()

    function isWifiConnection() {
        return root.normalizedNetType === "wifi" || root.normalizedNetType === "wireless"
    }

    function isEthernetConnection() {
        return root.normalizedNetType === "ethernet" || root.normalizedNetType === "wired"
    }

    function isVpnConnection() {
        return root.normalizedNetType === "vpn"
    }

    function hasVirtualLab() {
        return root.virtualLabCount > 0
    }

    function labColor(lab) {
        const state = String(lab.state || "offline")
        if (state === "active")
            return Theme.buttonTextSolid
        if (state === "starting")
            return Theme.statusBarWarningText
        return Theme.statusBarDimText
    }

    function labText(lab) {
        const platform = String(lab.platform || "Virtual Lab")
        const state = String(lab.state || "offline")
        if (!StatusBarState.showNetworkName)
            return platform
        if (state === "starting")
            return platform + " · Starting..."
        if (state === "active") {
            const labName = String(lab.labName || "").trim()
            const namePart = labName ? " · " + labName : ""
            return platform + namePart + " · " + Number(lab.runningNodeCount || 0) + " running"
        }
        if (state === "idle")
            return platform + " · Idle"
        return platform + " · Online"
    }

    function labDetailText(lab) {
        const lines = []
        lines.push(String(lab.detail || root.labText(lab)))
        if (lab.serverIp)
            lines.push("Server: " + lab.serverIp)
        if (lab.serverUrl)
            lines.push("Click to open this lab in your browser.")
        return lines.join("\n")
    }

    function connectionLabel() {
        if (!root.netConnected || root.normalizedNetType === "none")
            return "No Connection"
        if (root.isWifiConnection())
            return "Wi-Fi"
        if (root.isEthernetConnection())
            return "Ethernet"
        if (root.isVpnConnection())
            return "VPN"
        if (root.normalizedNetType === "lab")
            return "Virtual Lab"
        return "Network Interface"
    }

    function networkText() {
        if (root.hasVirtualLab()) {
            if (!StatusBarState.showNetworkName)
                return root.virtualLabActive ? "Virtual Lab Active" : "Virtual Lab"
            const platform = (root.virtualLabPlatform || "Virtual Lab").trim()
            if (root.virtualLabState === "starting")
                return platform + " · Starting..."
            const identity = (root.virtualLabDetectedName || root.virtualLabServerIp || "Server").trim()
            if (root.virtualLabActive)
                return platform + " · " + identity + " · " + root.virtualLabRunningNodeCount + " running"
            if (root.virtualLabState === "online")
                return platform + " · " + identity + " · Online"
            return platform + " · " + identity + " · Idle"
        }
        const label = root.connectionLabel()
        const name = (root.netName || "").trim()
        if (!root.netConnected || !StatusBarState.showNetworkName || name === "" || name === label)
            return label
        return label + " - " + name
    }

    function networkDetailText() {
        if (!root.netConnected)
            return "No active network adapter was detected."
        if (!root.hasVirtualLab())
            return root.networkText()
        const lines = []
        lines.push(root.virtualLabDetail || root.networkText())
        if (root.virtualLabServerIp)
            lines.push("Server: " + root.virtualLabServerIp)
        if (root.virtualLabUrl)
            lines.push("Click to open lab in your browser.")
        const primaryName = (root.netName || "").trim()
        if (primaryName !== "" && root.normalizedNetType !== "lab")
            lines.push("Primary connection: " + root.connectionLabel() + " · " + primaryName)
        return lines.join("\n")
    }

    function formatDateText(value) {
        const customFormat = (StatusBarState.customDateFormat || "").trim()
        if (StatusBarState.dateTimeFormatMode === 1 && customFormat !== "")
            return Qt.formatDate(value, customFormat)
        return value.toLocaleDateString(Qt.locale())
    }

    function formatTimeText(value) {
        const customFormat = (StatusBarState.customTimeFormat || "").trim()
        if (StatusBarState.dateTimeFormatMode === 1 && customFormat !== "")
            return Qt.formatTime(value, customFormat)
        return value.toLocaleTimeString(Qt.locale())
    }

    Timer {
        interval: 1000
        running: StatusBarState.isVisible
        repeat: true
        onTriggered: root.currentDateTime = new Date()
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 16

        RowLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: 6
            visible: StatusBarState.showPythonStatus

            HoverHandler {
                id: pythonStatusHover
                cursorShape: root.pythonStatusBusy ? Qt.ArrowCursor : Qt.PointingHandCursor
            }

            TapHandler {
                enabled: !root.pythonStatusBusy
                onTapped: root.pythonStatusClicked()
            }

            ThemedIcon {
                id: pythonStatusIcon
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredWidth: 14
                Layout.preferredHeight: 14
                iconSource: AppAssets.statusPython
                iconSize: 14
                iconColor: root.pythonStatusColor

                SequentialAnimation on opacity {
                    running: root.pythonStatusBusy
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: 700; easing.type: Easing.InOutQuad }
                    NumberAnimation { to: 1.0; duration: 700; easing.type: Easing.InOutQuad }
                }

                Binding {
                    target: pythonStatusIcon
                    property: "opacity"
                    value: 1.0
                    when: !root.pythonStatusBusy
                }
            }

            Text {
                Layout.alignment: Qt.AlignVCenter
                text: root.pythonStatusText
                color: root.pythonStatusColor
                font.pixelSize: Theme.fontSizeSmall
                font.family: Theme.fontFamily
                font.weight: Font.DemiBold
            }

            ToolTip {
                visible: pythonStatusHover.hovered
                text: root.pythonStatusDetail === ""
                      ? "Click to check Python runtime and database schemas."
                      : root.pythonStatusDetail
                delay: 400
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignVCenter
            Layout.maximumWidth: 520
            spacing: Theme.spacing8
            visible: root.taskVisible

            ProgressBar {
                id: taskProgressBar
                objectName: "statusBarTaskProgress"
                Layout.preferredWidth: 112
                Layout.preferredHeight: 8
                readonly property bool hasMeasuredProgress:
                    root.taskProgress >= 0 && root.taskProgress <= 1
                readonly property color progressColor:
                    root.taskBusy ? Theme.buttonTextSolid
                                  : (root.taskOk ? Theme.alertSuccess
                                                 : Theme.alertError)
                indeterminate: root.taskBusy && !hasMeasuredProgress
                from: 0
                to: 1
                value: hasMeasuredProgress ? root.taskProgress
                                           : (root.taskBusy ? 0 : 1)

                background: Rectangle {
                    implicitWidth: 112
                    implicitHeight: 6
                    radius: height / 2
                    color: Qt.rgba(1, 1, 1, 0.20)
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.16)
                }

                contentItem: Item {
                    implicitWidth: 112
                    implicitHeight: 6
                    clip: true

                    Rectangle {
                        id: measuredProgress
                        visible: !taskProgressBar.indeterminate
                        width: taskProgressBar.visualPosition * parent.width
                        height: parent.height
                        radius: height / 2
                        color: taskProgressBar.progressColor

                        Behavior on width {
                            NumberAnimation {
                                duration: Theme.animationDurationSlow
                                easing.type: Easing.OutCubic
                            }
                        }
                    }

                    Rectangle {
                        id: progressRunner
                        visible: taskProgressBar.indeterminate
                        x: -width
                        width: Math.max(34, parent.width * 0.38)
                        height: parent.height
                        radius: height / 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.05) }
                            GradientStop { position: 0.5; color: Theme.buttonTextSolid }
                            GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.05) }
                        }

                        SequentialAnimation on x {
                            running: taskProgressBar.indeterminate
                                     && taskProgressBar.visible
                            loops: Animation.Infinite
                            NumberAnimation {
                                from: -progressRunner.width
                                to: taskProgressBar.width
                                duration: 1150
                                easing.type: Easing.InOutCubic
                            }
                        }
                    }
                }
            }

            Text {
                visible: root.taskBusy && taskProgressBar.hasMeasuredProgress
                Layout.preferredWidth: visible ? 34 : 0
                text: Math.round(root.taskProgress * 100) + "%"
                color: Theme.buttonTextSolid
                font.pixelSize: Theme.fontSizeSmall
                font.family: Theme.monoFontFamily
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignRight
            }

            Text {
                Layout.fillWidth: true
                text: root.taskMessage
                color: root.taskBusy
                       ? Theme.statusBarWarningText
                       : (root.taskOk ? Theme.buttonTextSolid : Theme.alertError)
                font.pixelSize: Theme.fontSizeSmall
                font.family: Theme.fontFamily
                font.weight: Font.Medium
                elide: Text.ElideRight
            }
        }

        Item {
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: 10

            RowLayout {
                spacing: 4
                Layout.alignment: Qt.AlignVCenter
                visible: StatusBarState.showNetwork && !root.hasVirtualLab()

                HoverHandler {
                    id: networkHover
                    cursorShape: Qt.ArrowCursor
                }

                ThemedIcon {
                    id: netIcon
                    Layout.alignment: Qt.AlignVCenter
                    Layout.preferredWidth: 14
                    Layout.preferredHeight: 14
                    iconSize: 14

                    iconSource: {
                        if (!root.netConnected || root.normalizedNetType === "none")
                            return AppAssets.deviceNetworkDisconnected
                        if (root.hasVirtualLab())
                            return AppAssets.deviceNetworkVirtualLab
                        if (root.isVpnConnection())
                            return AppAssets.deviceNetworkVpn
                        if (root.isWifiConnection())
                            return AppAssets.deviceNetworkWifi
                        return AppAssets.deviceNetworkEthernet
                    }

                    iconColor: root.networkColor

                    SequentialAnimation on opacity {
                        running: !root.netConnected
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.4; duration: 800; easing.type: Easing.InOutQuad }
                        NumberAnimation { to: 1.0; duration: 800; easing.type: Easing.InOutQuad }
                    }

                    Binding {
                        target: netIcon
                        property: "opacity"
                        value: 1.0
                        when: root.netConnected
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignVCenter
                    text: root.networkText()
                    color: root.networkColor
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    font.weight: Font.Medium
                }

                ToolTip {
                    visible: networkHover.hovered
                    text: root.netConnected
                          ? root.networkDetailText()
                          : "No active network adapter was detected."
                    delay: 400
                }
            }

            Repeater {
                objectName: "virtualLabRepeater"
                model: StatusBarState.showNetwork ? root.virtualLabs : []

                delegate: RowLayout {
                    id: labIndicator
                    required property var modelData
                    required property int index
                    objectName: "virtualLabIndicator" + index
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 4

                    HoverHandler {
                        id: labHover
                        cursorShape: labIndicator.modelData.serverUrl
                                     ? Qt.PointingHandCursor
                                     : Qt.ArrowCursor
                    }

                    TapHandler {
                        enabled: String(labIndicator.modelData.serverUrl || "") !== ""
                        onTapped: Qt.openUrlExternally(labIndicator.modelData.serverUrl)
                    }

                    ThemedIcon {
                        Layout.alignment: Qt.AlignVCenter
                        Layout.preferredWidth: 14
                        Layout.preferredHeight: 14
                        iconSize: 14
                        iconSource: AppAssets.deviceNetworkVirtualLab
                        iconColor: root.labColor(labIndicator.modelData)

                        SequentialAnimation on opacity {
                            running: String(labIndicator.modelData.state || "") === "starting"
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.4; duration: 800; easing.type: Easing.InOutQuad }
                            NumberAnimation { to: 1.0; duration: 800; easing.type: Easing.InOutQuad }
                        }
                    }

                    Text {
                        objectName: "virtualLabIndicatorText" + labIndicator.index
                        Layout.alignment: Qt.AlignVCenter
                        text: root.labText(labIndicator.modelData)
                        color: root.labColor(labIndicator.modelData)
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                        font.weight: Font.Medium
                    }

                    ToolTip {
                        visible: labHover.hovered
                        text: root.labDetailText(labIndicator.modelData)
                        delay: 400
                    }

                    Rectangle {
                        Layout.alignment: Qt.AlignVCenter
                        Layout.leftMargin: 6
                        Layout.rightMargin: 6
                        width: 1
                        height: 12
                        color: Theme.statusBarSepColor
                        visible: labIndicator.index < root.virtualLabCount - 1
                    }
                }
            }

            Rectangle {
                Layout.alignment: Qt.AlignVCenter
                width: 1
                height: 12
                color: Theme.statusBarSepColor
                visible: StatusBarState.showNetwork
                         && (root.ramSectionVisible || root.dateTimeSectionVisible || StatusBarState.showNotifications)
            }

            RowLayout {
                spacing: 5
                Layout.alignment: Qt.AlignVCenter
                visible: root.ramSectionVisible

                HoverHandler {
                    id: ramHover
                    cursorShape: Qt.ArrowCursor
                }

                Text {
                    Layout.alignment: Qt.AlignVCenter
                    visible: StatusBarState.showRamText
                    text: "RAM"
                    color: root.ramTextColor
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    font.weight: Font.Medium
                }

                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    Layout.preferredWidth: 72
                    Layout.preferredHeight: 8
                    visible: StatusBarState.showRamBar
                    radius: height / 2
                    color: Theme.statusBarSepColor
                    clip: true

                    Rectangle {
                        id: ramFill
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: Math.max(root.ramUsagePct > 0 ? 2 : 0,
                                        parent.width * root.ramUsagePct / 100)
                        radius: height / 2
                        color: root.ramBarColor

                        SequentialAnimation on opacity {
                            running: root.ramHigh && StatusBarState.ramBlinkOnHigh
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.35; duration: 450; easing.type: Easing.InOutQuad }
                            NumberAnimation { to: 1.0; duration: 450; easing.type: Easing.InOutQuad }
                        }

                        Binding {
                            target: ramFill
                            property: "opacity"
                            value: 1.0
                            when: !(root.ramHigh && StatusBarState.ramBlinkOnHigh)
                        }
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignVCenter
                    visible: StatusBarState.showRamText
                    text: root.ramUsagePct + "%"
                    color: root.ramTextColor
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    font.weight: Font.Medium
                }

                ToolTip {
                    visible: ramHover.hovered
                    text: "RAM usage: %1%, warning at %2%"
                          .arg(root.ramUsagePct)
                          .arg(root.ramWarningThreshold)
                    delay: 400
                }
            }

            Rectangle {
                Layout.alignment: Qt.AlignVCenter
                width: 1
                height: 12
                color: Theme.statusBarSepColor
                visible: root.ramSectionVisible
                         && (root.dateTimeSectionVisible || StatusBarState.showNotifications)
            }

            RowLayout {
                Layout.alignment: Qt.AlignVCenter
                spacing: 8
                visible: root.dateTimeSectionVisible

                Text {
                    Layout.alignment: Qt.AlignVCenter
                    visible: StatusBarState.showDate
                    text: root.formatDateText(root.currentDateTime)
                    color: Theme.buttonTextSolid
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    font.weight: Font.Medium
                }

                Text {
                    Layout.alignment: Qt.AlignVCenter
                    visible: StatusBarState.showTime
                    text: root.formatTimeText(root.currentDateTime)
                    color: Theme.buttonTextSolid
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    font.weight: Font.Medium
                }
            }

            Rectangle {
                Layout.alignment: Qt.AlignVCenter
                width: 1
                height: 12
                color: Theme.statusBarSepColor
                visible: root.dateTimeSectionVisible && StatusBarState.showNotifications
            }

            IconButton {
                id: notificationButton
                objectName: "statusBarNotificationButton"
                Layout.alignment: Qt.AlignVCenter
                visible: StatusBarState.showNotifications
                buttonSize: 20
                iconSize: 14
                idleColor: Theme.buttonTextSolid
                activeColor: Theme.buttonTextSolid
                hoverBackground: Theme.statusBarSepColor
                iconSource: {
                    if (root.isDND)
                        return AppAssets.statusDoNotDisturb
                    if (root.unreadCount > 0)
                        return AppAssets.statusNotificationUnread
                    return AppAssets.statusNotification
                }
                tooltip: root.isNotificationOpen ? "" :
                         (root.isDND ? (root.unreadCount > 0
                                        ? LanguageState.text("Do Not Disturb - ON (%1 unread)".arg(root.unreadCount))
                                        : LanguageState.text("Do Not Disturb - ON")) :
                          (root.unreadCount > 0
                           ? LanguageState.text("%1 Unread Notifications".arg(root.unreadCount))
                           : LanguageState.text("No New Notifications")))
                onClicked: root.bellClicked()

                SequentialAnimation on opacity {
                    running: root.notificationShouldBlink
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.25; duration: 450; easing.type: Easing.InOutQuad }
                    NumberAnimation { to: 1.0; duration: 450; easing.type: Easing.InOutQuad }
                }

                Binding {
                    target: notificationButton
                    property: "opacity"
                    value: 1.0
                    when: !root.notificationShouldBlink
                }
            }
        }
    }
}
