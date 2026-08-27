pragma ComponentBehavior: Bound

import QtQuick
import UI

Column {
    id: deviceSection

    property string sectionTitle: ""
    property bool expanded: false
    property var devices: []
    property string activeHost: ""
    property var selectedHosts: ({})
    property var hostOperations: ({})
    property bool selectionMode: false
    property string displayFormat: "name"
    property bool autoExpand: true

    visible: devices.length > 0

    onDevicesChanged: {
        if (autoExpand && devices.length > 0) {
            expanded = true
        }
    }
    signal deviceActivated(string host)
    signal deviceToggleSelectionRequested(string host)
    signal deviceRangeSelectionRequested(string host)
    signal deviceContextRequested(string host, string status, real sceneX, real sceneY)
    signal groupContextRequested(real sceneX, real sceneY)

    width: parent.width

    // ── Header section ──
    Rectangle {
        width: parent.width
        height: Theme.listItemHeight
        color: headerHover.hovered ? Theme.panelSideBarItemHover : "transparent"

        Row {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 8
            spacing: 4

            ThemedIcon {
                anchors.verticalCenter: parent.verticalCenter
                iconSource: deviceSection.expanded
                            ? AppAssets.navigationChevronDown
                            : AppAssets.navigationChevronRight
                iconSize: Theme.iconSizeSmall
                iconColor: Theme.panelSideBarTextSecondary
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: deviceSection.sectionTitle + " (" + deviceSection.devices.length + ")"
                font.pixelSize: Theme.fontSizeSmall
                font.family: Theme.fontFamily
                font.capitalization: Font.AllUppercase
                font.weight: Font.Medium
                color: Theme.panelSideBarTextSecondary
            }
        }

        HoverHandler {
            id: headerHover
            cursorShape: Qt.PointingHandCursor
        }
        TapHandler {
            acceptedButtons: Qt.LeftButton
            onTapped: deviceSection.expanded = !deviceSection.expanded
        }
        TapHandler {
            acceptedButtons: Qt.RightButton
            onTapped: function(eventPoint) {
                deviceSection.groupContextRequested(
                    eventPoint.scenePosition.x,
                    eventPoint.scenePosition.y
                )
            }
        }
    }

    // ── Danh sách thiết bị ──
    Column {
        width: parent.width
        visible: deviceSection.expanded

        Repeater {
            model: deviceSection.devices
            delegate: DeviceItem {
                width: deviceSection.width
                deviceName: modelData.name
                deviceIp:   modelData.ip

                deviceType: modelData.type !== undefined ? modelData.type : ""

                status:     modelData.status
                isActive: deviceSection.activeHost === String(modelData.ip || "")
                isBatchSelected: deviceSection.selectedHosts[String(modelData.ip || "")] === true
                selectionMode: deviceSection.selectionMode
                operationState: {
                    const state = deviceSection.hostOperations[String(modelData.ip || "")]
                    return state ? String(state.state || "idle") : "idle"
                }
                operationMessage: {
                    const state = deviceSection.hostOperations[String(modelData.ip || "")]
                    return state ? String(state.message || "") : ""
                }

                displayFormat: deviceSection.displayFormat

                onActivated: host => deviceSection.deviceActivated(host)
                onToggleSelectionRequested: host =>
                    deviceSection.deviceToggleSelectionRequested(host)
                onRangeSelectionRequested: host =>
                    deviceSection.deviceRangeSelectionRequested(host)
                onRightClicked: (ip, mx, my) => deviceSection.deviceContextRequested(
                    ip, modelData.status, mx, my
                )
            }
        }
    }
}
