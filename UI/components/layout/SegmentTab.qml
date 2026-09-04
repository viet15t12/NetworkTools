pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    property string label: ""
    property bool selected: false
    property int minWidth: 92
    property color idleBorderColor: Theme.borderColor
    property color selectedTextColor: Theme.accentColor
    property color idleTextColor: Theme.textSecondary

    signal clicked()

    implicitWidth: Math.max(minWidth, labelText.implicitWidth + 28)
    implicitHeight: 28
    radius: Theme.radiusRound
    color: selected ? Theme.sideBarItemSelected
                    : (tabHover.hovered ? Theme.sideBarItemHover : "transparent")
    border.color: selected ? Theme.accentColor : idleBorderColor
    border.width: Theme.borderWidth

    Text {
        id: labelText
        anchors.centerIn: parent
        text: root.label
        color: root.selected ? root.selectedTextColor : root.idleTextColor
        font.pixelSize: Theme.fontSizeSmall
        font.family: Theme.fontFamily
        font.bold: root.selected
    }

    HoverHandler {
        id: tabHover
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler { onTapped: root.clicked() }
}
