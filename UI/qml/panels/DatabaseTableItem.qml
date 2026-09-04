pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: root
    objectName: "databaseTableItem"

    property string tableName: ""
    property string groupKey: ""
    property url domainIcon: AppAssets.fileTypeDatabase
    property color domainColor: Theme.panelSideBarTextSecondary
    property bool isSelected: false

    readonly property url tableIconSource: {
        const normalized = root.tableName.toLowerCase()
        if (root.groupKey === "05") {
            if (normalized.indexOf("nat") !== -1)
                return AppAssets.deviceNetworkVpn
            if (normalized.indexOf("route_map") !== -1)
                return AppAssets.navigationTopology
            return AppAssets.fileTypeKey
        }
        if (root.groupKey === "06" || root.groupKey === "09")
            return AppAssets.deviceSwitch
        if (root.groupKey === "11")
            return AppAssets.deviceNetworkVpn
        if (root.groupKey === "04")
            return AppAssets.navigationTopology
        if (root.groupKey === "02")
            return AppAssets.navigationInterface
        if (root.groupKey === "01" || root.groupKey === "08")
            return AppAssets.deviceRouter
        if (root.groupKey === "10")
            return AppAssets.fileTypeKey
        return root.domainIcon
    }

    signal clicked()

    height: Theme.listItemHeight
    color: isSelected
           ? Theme.panelSideBarItemSelected
           : (itemHover.hovered ? Theme.panelSideBarItemHover : "transparent")

    ToolTip.visible: itemHover.hovered
    ToolTip.text: tableName
    ToolTip.delay: 400

    Rectangle {
        width: 3
        height: parent.height
        anchors.left: parent.left
        color: Theme.panelSideBarAccentColor
        opacity: root.isSelected ? 1.0 : 0.0
    }

    ThemedIcon {
        id: tableIcon
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        iconSource: root.tableIconSource
        iconSize: 16
        iconColor: root.domainColor
        opacity: root.isSelected ? 1.0 : 0.82
    }

    Text {
        anchors.left: tableIcon.right
        anchors.leftMargin: 10
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: root.tableName
        color: root.isSelected
               ? Theme.panelSideBarTextPrimary
               : Theme.panelSideBarTextSecondary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeNormal
        elide: Text.ElideRight
    }

    HoverHandler { id: itemHover }
    TapHandler { onTapped: root.clicked() }
}
