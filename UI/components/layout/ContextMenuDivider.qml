pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    property int sideMargin: 10
    property color lineColor: Theme.panelSideBarBorderColor
    property real lineOpacity: Theme.isHighContrast ? 1.0 : 0.45

    width: parent ? parent.width - (sideMargin * 2) : 0
    height: Theme.borderWidth
    x: parent ? (parent.width - width) / 2 : 0
    color: lineColor
    opacity: lineOpacity
}
