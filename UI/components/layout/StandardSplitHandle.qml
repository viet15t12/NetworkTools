pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: root

    property int orientation: Qt.Horizontal

    implicitWidth: orientation === Qt.Horizontal
                   ? Theme.splitHandleHitWidth : Theme.splitHandleWidth
    implicitHeight: orientation === Qt.Vertical
                    ? Theme.splitHandleHitWidth : Theme.splitHandleWidth
    color: "transparent"

    Rectangle {
        anchors.centerIn: parent
        width: root.orientation === Qt.Horizontal
               ? Theme.splitHandleWidth : parent.width
        height: root.orientation === Qt.Vertical
                ? Theme.splitHandleWidth : parent.height
        color: SplitHandle.hovered || SplitHandle.pressed
               ? Theme.splitHandleHoverColor : Theme.splitHandleColor
    }
}
