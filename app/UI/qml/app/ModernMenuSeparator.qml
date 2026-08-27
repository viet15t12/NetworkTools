pragma ComponentBehavior: Bound

import QtQuick
import UI

Item {
    implicitWidth: 240
    implicitHeight: Theme.spacing8 + Theme.borderWidth

    Accessible.role: Accessible.Separator

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: Theme.spacing8
        anchors.rightMargin: Theme.spacing8
        anchors.verticalCenter: parent.verticalCenter
        height: Theme.borderWidth
        color: Theme.panelSideBarBorderColor
        opacity: Theme.isHighContrast ? 1.0 : 0.68
    }
}
