pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    required property var deviceData
    property bool selected: false
    readonly property string host: String(deviceData.host || "")
    readonly property string deviceName: String(deviceData.device_name || "").trim()
    readonly property string displayLabel: deviceName !== "" && host !== ""
                                           && deviceName !== host
                                           ? "%1(%2)".arg(deviceName).arg(host)
                                           : (deviceName || host)
    readonly property string deviceType: String(deviceData.device_type || "").toLowerCase()
    readonly property url deviceIcon: deviceType === "router" ? AppAssets.deviceRouter
                                      : deviceType === "sw2" || deviceType === "sw3"
                                        ? AppAssets.deviceSwitch : AppAssets.deviceStatusDot

    signal clicked(string host)

    height: 52
    color: selected ? Theme.panelSideBarItemSelected
                    : itemHover.hovered ? Theme.panelSideBarItemHover
                    : "transparent"

    ToolTip.visible: itemHover.hovered
    ToolTip.text: "%1 · Connected log source".arg(displayLabel)
    ToolTip.delay: 400

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 3
        visible: root.selected
        color: Theme.panelSideBarAccentColor
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing16
        anchors.rightMargin: Theme.spacing8
        spacing: Theme.spacing8

        ThemedIcon {
            Layout.preferredWidth: Theme.iconSizeNormal
            Layout.preferredHeight: Theme.iconSizeNormal
            iconSource: root.deviceIcon
            iconSize: root.deviceType === "" ? 28 : Theme.iconSizeNormal
            iconColor: Theme.statusConnected
        }

        Text {
            Layout.fillWidth: true
            text: root.displayLabel
            color: Theme.panelSideBarTextPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            elide: Text.ElideRight
        }

        Text {
            text: "Connected"
            color: Theme.statusConnected
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
        }
    }

    HoverHandler { id: itemHover }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: root.clicked(root.host)
    }

}
