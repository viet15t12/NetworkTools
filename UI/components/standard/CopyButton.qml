pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Button {
    id: root

    property string textToCopy: ""
    property string copyTooltip: "Copy"
    property bool copied: false
    property int feedbackDuration: 1400

    signal copySucceeded(string copiedText)

    function copyText() {
        const value = String(root.textToCopy || "")
        if (value === "")
            return false

        clipboardProxy.text = value
        clipboardProxy.selectAll()
        clipboardProxy.copy()
        clipboardProxy.deselect()

        root.copied = true
        feedbackTimer.restart()
        root.copySucceeded(value)
        return true
    }

    enabled: textToCopy !== ""
    implicitWidth: 28
    implicitHeight: 28
    padding: 0
    focusPolicy: Qt.StrongFocus

    Accessible.role: Accessible.Button
    Accessible.name: copied ? "Copied" : copyTooltip
    Accessible.description: copyTooltip

    onClicked: copyText()
    onTextToCopyChanged: {
        copied = false
        feedbackTimer.stop()
    }

    HoverHandler {
        id: hoverHandler
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
    }

    background: Rectangle {
        radius: Theme.radiusSmall
        color: {
            if (!root.enabled)
                return "transparent"
            if (root.copied)
                return Theme.alertSuccessSubtle
            if (root.down || hoverHandler.hovered || root.activeFocus)
                return Theme.sideBarItemHover
            return "transparent"
        }
        border.color: root.activeFocus ? Theme.accentColor : "transparent"
        border.width: root.activeFocus ? Theme.borderWidth : 0
    }

    contentItem: ThemedIcon {
        iconSource: root.copied
                    ? AppAssets.statusSuccess
                    : AppAssets.actionCopy
        iconSize: Theme.iconSizeSmall
        iconColor: root.copied
                   ? Theme.alertSuccess
                   : (root.enabled && (root.down || hoverHandler.hovered || root.activeFocus)
                      ? Theme.textPrimary
                      : Theme.textSecondary)
    }

    ToolTip {
        visible: root.copied || hoverHandler.hovered
        text: root.copied ? "Copied" : root.copyTooltip
        delay: root.copied ? 0 : 400
    }

    TextEdit {
        id: clipboardProxy
        visible: false
        readOnly: false
        textFormat: TextEdit.PlainText
    }

    Timer {
        id: feedbackTimer
        interval: root.feedbackDuration
        repeat: false
        onTriggered: root.copied = false
    }
}
