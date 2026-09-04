pragma ComponentBehavior: Bound

import QtQuick
import UI

Item {
    id: textFeatureItem

    property string label: ""
    property bool isActive: false
    property bool selectable: true

    signal clicked()

    width: labelText.implicitWidth + 24
    height: parent.height

    // Chỉ báo active ở mép trên, đồng bộ phong cách với SubBar
    Rectangle {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
        height: 2
        color: Theme.accentColor
        visible: isActive
    }

    Rectangle {
        anchors.fill: parent
        color: itemHover.hovered && !isActive && textFeatureItem.selectable ? Theme.sideBarItemHover : "transparent"
    }

    Text {
        id: labelText
        anchors.centerIn: parent
        text: textFeatureItem.label
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily
        font.bold: isActive
        color: !textFeatureItem.selectable ? Theme.textDisabled
              : isActive ? Theme.textPrimary : Theme.textSecondary
        opacity: textFeatureItem.selectable ? 1.0 : 0.55
    }

    HoverHandler {
        id: itemHover
        cursorShape: textFeatureItem.selectable ? Qt.PointingHandCursor : Qt.ArrowCursor
    }
    TapHandler {
        enabled: textFeatureItem.selectable
        onTapped: textFeatureItem.clicked()
    }
}
