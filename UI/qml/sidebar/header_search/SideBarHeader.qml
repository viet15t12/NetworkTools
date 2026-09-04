pragma ComponentBehavior: Bound

import QtQuick
import UI

Item {
    id: root
    width: parent.width
    height: 36

    signal filterClicked()
    signal refreshClicked()
    signal addMultipleClicked()
    signal addClicked()

    property bool isFilterActive: false

    Text {
        anchors.left: parent.left; anchors.leftMargin: 16
        anchors.right: actionRow.left; anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: "DEVICES"
        elide: Text.ElideRight
        color: Theme.panelSideBarTextSecondary; font.pixelSize: Theme.fontSizeSmall
        font.family: Theme.fontFamily; font.capitalization: Font.AllUppercase; font.weight: Font.Medium
    }

    Row {
        id: actionRow
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        anchors.rightMargin: 8; spacing: 2

        IconButton {
            buttonSize: Theme.sideBarFeatureIcon
            iconSource: AppAssets.actionFilter
            selected: root.isFilterActive
            idleColor: Theme.panelSideBarTextSecondary
            activeColor: Theme.panelSideBarTextPrimary
            selectedBackground: Theme.panelSideBarItemSelected
            hoverBackground: Theme.panelSideBarItemHover
            tooltip: "Filter Devices"
            onClicked: root.filterClicked()
        }

        IconButton {
            buttonSize: Theme.sideBarFeatureIcon
            iconSource: AppAssets.actionRefresh
            idleColor: Theme.panelSideBarTextSecondary
            activeColor: Theme.panelSideBarTextPrimary
            selectedBackground: Theme.panelSideBarItemSelected
            hoverBackground: Theme.panelSideBarItemHover
            tooltip: "Refresh List"
            onClicked: root.refreshClicked()
        }

        IconButton {
            buttonSize: Theme.sideBarFeatureIcon
            iconSource: AppAssets.actionListAdd
            idleColor: Theme.panelSideBarTextSecondary
            activeColor: Theme.panelSideBarTextPrimary
            selectedBackground: Theme.panelSideBarItemSelected
            hoverBackground: Theme.panelSideBarItemHover
            tooltip: "Add Multiple Devices (Ctrl+Alt+N)"
            onClicked: root.addMultipleClicked()
        }

        IconButton {
            buttonSize: Theme.sideBarFeatureIcon
            iconSource: AppAssets.actionAdd
            idleColor: Theme.panelSideBarTextSecondary
            activeColor: Theme.panelSideBarTextPrimary
            selectedBackground: Theme.panelSideBarItemSelected
            hoverBackground: Theme.panelSideBarItemHover
            tooltip: "Add New Device (Ctrl+N)"
            onClicked: root.addClicked()
        }
    }
}
