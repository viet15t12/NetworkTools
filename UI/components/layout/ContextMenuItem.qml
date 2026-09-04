pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    property string text: ""
    property string iconSource: ""
    property string shortcutText: ""
    property bool reserveIconSpace: true
    property bool danger: false
    property int itemHeight: Theme.listItemHeight
    property int iconSize: Theme.iconSizeNormal
    property int leftMargin: 10
    property int rightMargin: 10
    property int iconColumnWidth: 20
    property int shortcutColumnWidth: 104
    property int columnSpacing: 8

    readonly property bool hovered: itemHover.hovered && root.enabled
    readonly property color activeTextColor: root.danger ? Theme.alertError : Theme.panelSideBarTextPrimary
    readonly property color idleTextColor: Theme.panelSideBarTextSecondary
    readonly property color shortcutColor: Theme.panelSideBarTextDisabled

    signal triggered()

    width: parent ? parent.width : implicitWidth
    height: itemHeight
    radius: Theme.radiusSmall
    opacity: root.enabled ? 1.0 : 0.45
    color: root.hovered
           ? (root.danger ? Theme.alertErrorSubtle : Theme.panelSideBarItemHover)
           : "transparent"

    Item {
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.leftMargin: root.leftMargin
        anchors.right: parent.right
        anchors.rightMargin: root.rightMargin

        Item {
            id: iconColumn
            visible: root.reserveIconSpace || root.iconSource !== ""
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: root.iconColumnWidth
            height: root.iconSize

            ThemedIcon {
                visible: root.iconSource !== ""
                anchors.centerIn: parent
                iconSource: root.iconSource
                iconSize: root.iconSize
                iconColor: root.hovered ? root.activeTextColor : root.idleTextColor
            }
        }

        Text {
            id: labelText
            anchors.left: iconColumn.visible ? iconColumn.right : parent.left
            anchors.leftMargin: iconColumn.visible ? root.columnSpacing : 0
            anchors.right: shortcutLabel.visible ? shortcutLabel.left : parent.right
            anchors.rightMargin: shortcutLabel.visible ? root.columnSpacing : 0
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            font.pixelSize: Theme.fontSizeNormal
            font.family: Theme.fontFamily
            color: root.hovered ? root.activeTextColor : root.idleTextColor
            elide: Text.ElideRight
        }

        Text {
            id: shortcutLabel
            visible: root.shortcutText !== ""
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: root.shortcutColumnWidth
            text: root.shortcutText
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            color: root.shortcutColor
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
        }
    }

    HoverHandler {
        id: itemHover
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
        enabled: root.enabled
        onTapped: root.triggered()
    }
}
