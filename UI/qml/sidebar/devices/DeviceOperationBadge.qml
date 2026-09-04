pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: root
    property string state: "idle"
    property string message: ""
    readonly property string normalizedState: String(state || "idle").toLowerCase()
    readonly property bool knownState:
        normalizedState === "queued"
        || normalizedState === "running"
        || normalizedState === "success"
        || normalizedState === "warning"
        || normalizedState === "error"
        || normalizedState === "cancelled"
    readonly property string symbol: {
        if (normalizedState === "queued") return "…"
        if (normalizedState === "running") return "↻"
        if (normalizedState === "success") return "✓"
        if (normalizedState === "warning") return "!"
        if (normalizedState === "cancelled") return "–"
        return "×"
    }

    visible: knownState
    implicitWidth: 14
    implicitHeight: 14
    radius: width / 2
    color: {
        if (normalizedState === "success") return Theme.statusConnected
        if (normalizedState === "error" || normalizedState === "cancelled")
            return Theme.statusDisconnected
        if (normalizedState === "warning") return Theme.alertWarning
        return Theme.panelSideBarAccentColor
    }

    Text {
        anchors.centerIn: parent
        text: root.symbol
        color: root.normalizedState === "warning"
               ? Theme.badgeWarningText : Theme.buttonTextSolid
        font.family: Theme.fontFamily
        font.pixelSize: 10
        font.bold: true
    }

    ToolTip.visible: badgeHover.hovered && root.visible
    ToolTip.text: root.message !== ""
                  ? root.message
                  : (root.normalizedState === "queued" ? "Operation queued"
                     : root.normalizedState === "running" ? "Operation in progress"
                     : root.normalizedState === "success" ? "Operation succeeded"
                     : root.normalizedState === "warning" ? "Operation completed with a warning"
                     : root.normalizedState === "cancelled" ? "Operation cancelled"
                     : "Operation failed")
    ToolTip.delay: 300
    HoverHandler { id: badgeHover }

    SequentialAnimation on opacity {
        running: root.normalizedState === "running"
                 || root.normalizedState === "queued"
        loops: Animation.Infinite
        NumberAnimation { from: 0.35; to: 1.0; duration: 500 }
        NumberAnimation { from: 1.0; to: 0.35; duration: 500 }
    }
}
