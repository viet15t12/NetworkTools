pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    default property alias content: contentHost.data

    implicitHeight: Theme.tableHeaderHeight
    color: Theme.inputBackground
    border.color: Theme.inputBorderColor
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall

    Item {
        id: contentHost
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing12
        anchors.rightMargin: Theme.spacing12
    }
}
