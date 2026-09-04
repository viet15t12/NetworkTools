pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    property int rowIndex: 0
    property bool zebra: true
    property bool selected: false
    property bool interactive: true
    property color alternateColor: Theme.tableRowAlternate
    property color baseColor: zebra && rowIndex % 2 !== 0 ? alternateColor : "transparent"
    property color selectedColor: Theme.tableRowSelected
    property color hoverColor: Theme.tableRowHover
    default property alias content: contentHost.data

    readonly property bool hovered: rowHover.hovered

    implicitHeight: Theme.tableRowHeight
    color: selected ? selectedColor
                    : hovered && interactive ? hoverColor : baseColor

    Item {
        id: contentHost
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing12
        anchors.rightMargin: Theme.spacing12
    }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Theme.spacing2
        visible: root.selected
        color: Theme.tableRowSelectionIndicator
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: Theme.borderWidth
        color: Theme.contentPanelBorder
        opacity: 0.65
    }

    HoverHandler {
        id: rowHover
        enabled: root.interactive
    }
}
