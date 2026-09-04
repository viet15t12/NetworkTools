pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Button {
    id: root

    property string variant: "standard" // standard | compact | tab
    property string tooltip: "Close"
    property string iconSource: AppAssets.actionClose

    property int buttonSize: variant === "tab" ? 22 : (variant === "compact" ? 28 : 34)
    property int iconSize: variant === "standard" ? Theme.iconSizeNormal : Theme.iconSizeSmall

    property color idleBackground: variant === "tab" ? "transparent" : Theme.alertErrorSubtle
    property color hoverBackground: variant === "tab" ? Theme.sideBarItemHover : Theme.alertError
    property color pressedBackground: variant === "tab" ? Theme.sideBarItemSelected : Qt.darker(Theme.alertError, 1.12)
    property color idleIconColor: variant === "tab" ? Theme.textSecondary : Theme.alertError
    property color activeIconColor: variant === "tab" ? Theme.textPrimary : Theme.buttonTextSolid
    property color idleBorderColor: Qt.rgba(Theme.alertError.r, Theme.alertError.g, Theme.alertError.b,
                                            variant === "tab" ? 0.45 : 0.58)
    property color activeBorderColor: variant === "tab" ? "transparent" : Theme.alertError

    implicitWidth: buttonSize
    implicitHeight: buttonSize
    padding: 0
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0
    focusPolicy: Qt.StrongFocus

    HoverHandler {
        id: hoverHandler
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
    }

    background: Rectangle {
        radius: root.variant === "tab" ? Theme.radiusSmall : Theme.radiusMedium
        color: {
            if (!root.enabled)
                return "transparent"
            if (root.down)
                return root.pressedBackground
            if (hoverHandler.hovered)
                return root.hoverBackground
            return root.idleBackground
        }
        border.color: {
            if (!root.enabled)
                return Theme.borderColor
            if (root.down || hoverHandler.hovered || root.activeFocus)
                return root.activeBorderColor
            return root.idleBorderColor
        }
        border.width: root.variant === "tab" ? 0 : Theme.borderWidth
    }

    contentItem: Item {
        implicitWidth: root.iconSize
        implicitHeight: root.iconSize

        ThemedIcon {
            anchors.centerIn: parent
            iconSource: root.iconSource
            iconSize: root.iconSize
            iconColor: root.enabled && (root.down || hoverHandler.hovered)
                       ? root.activeIconColor
                       : (root.enabled ? root.idleIconColor : Theme.textDisabled)
        }
    }

    ToolTip {
        visible: root.tooltip !== "" && hoverHandler.hovered
        text: root.tooltip
        delay: 400
    }
}
