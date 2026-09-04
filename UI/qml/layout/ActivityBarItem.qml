pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: root

    property string iconSource: ""
    property string tooltipText: ""
    property bool isActive: false
    property real inactiveIconOpacity: 0.68

    width: Theme.activityBarWidth
    height: Theme.activityBarWidth // Hình vuông
    color: "transparent"

    signal clicked()

    // ── HIỆU ỨNG NỀN KHI HOVER (Phản hồi ngay lập tức, không delay) ──
    Rectangle {
        anchors.fill: parent
        color: Theme.activityBarItemHover
        visible: itemHover.hovered && !isActive
    }

    // ── VẠCH TRẠNG THÁI (Sắc nét, xuất hiện ngay không cần mọc từ giữa) ──
    Rectangle {
        id: activeIndicator
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 2 // Rất mỏng và tinh tế
        height: parent.height
        color: Theme.accentColor
        visible: root.isActive
    }

    ThemedIcon {
        id: activityIcon
        anchors.centerIn: parent
        iconSource: root.iconSource
        iconSize: 28
        iconColor: root.isActive || itemHover.hovered ? Theme.activityBarTextPrimary : Theme.activityBarTextSecondary
        opacity: !root.enabled || root.isActive || itemHover.hovered
                 ? 1.0
                 : root.inactiveIconOpacity

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.animationDurationFast
                easing.type: Easing.OutCubic
            }
        }
    }

    HoverHandler {
        id: itemHover
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
        onTapped: root.clicked()
    }

    // Tooltip mang phong cách VS Code (Bám sát lề phải)
    ToolTip {
        visible: itemHover.hovered
        text: root.tooltipText
        delay: 600
        x: root.width + 5
        y: (root.height - height) / 2
    }
}
