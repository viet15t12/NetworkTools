pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: mainFeatureItem

    property string iconSource: ""
    property string tooltipText: ""
    property bool isActive: false

    // Biến trạng thái để làm hiệu ứng chớp nháy
    property bool isFlashing: false

    signal clicked()

    width: Theme.featureBarHeight
    height: Theme.featureBarHeight

    // Màu nền và độ mờ ưu tiên trạng thái isFlashing
    color: (isActive || isFlashing) ? Theme.featureMainActive :
           itemHover.hovered ? Theme.featureMainHover : "transparent"

    Rectangle {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
        height: 2
        color: Theme.accentColor
        visible: isActive
    }

    ThemedIcon {
        anchors.centerIn: parent
        iconSource: mainFeatureItem.iconSource
        iconSize: 18
        iconColor: (mainFeatureItem.isActive || mainFeatureItem.isFlashing) ? Theme.accentColor : Theme.textPrimary
    }

    HoverHandler { id: itemHover }
    TapHandler { onTapped: mainFeatureItem.clicked() }

    ToolTip {
        visible: itemHover.hovered
        text: tooltipText
        delay: 500
    }

    Timer {
        id: flashTimer
        interval: 150
        onTriggered: mainFeatureItem.isFlashing = false
    }

    function triggerFlash() {
        mainFeatureItem.isFlashing = true
        flashTimer.restart()
    }
}
