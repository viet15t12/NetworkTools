pragma ComponentBehavior: Bound

import QtQuick
import UI

FocusScope {
    id: root

    property var command: null
    property int menuIndex: -1
    readonly property bool hasCommand: command !== null && command !== undefined
    property bool highlighted: false
    readonly property string shortcutText: shortcutFormatter.nativeText

    signal activated()
    signal hoveredRequested(int menuIndex)
    signal moveRequested(int delta)
    signal boundaryRequested(bool end)
    signal dismissRequested()
    signal switchMenuRequested(int direction)

    function activate() {
        if (!root.hasCommand || !root.command.enabled)
            return false
        root.activated()
        return true
    }

    objectName: root.hasCommand
                ? "modernMenuItem" + root.command.commandId
                    .split(".").map(function(part) {
                        return part.charAt(0).toUpperCase() + part.slice(1)
                    }).join("")
                : "modernMenuItemMissing"
    implicitWidth: 276
    implicitHeight: 34
    focus: highlighted
    visible: hasCommand && command.visible
    enabled: hasCommand && command.enabled

    Accessible.role: Accessible.MenuItem
    Accessible.name: hasCommand ? command.text : ""
    Accessible.description: hasCommand ? command.description : ""
    Accessible.focusable: enabled
    Accessible.focused: activeFocus
    Accessible.checkable: hasCommand && command.checkable
    Accessible.checked: hasCommand && command.checked
    Accessible.onPressAction: root.activate()

    // This disabled Shortcut is only a native key-sequence formatter. Global
    // dispatch remains exclusively owned by CommandRegistry.
    Shortcut {
        id: shortcutFormatter
        sequence: root.hasCommand ? root.command.shortcut : ""
        enabled: false
        autoRepeat: false
    }

    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing4
        anchors.rightMargin: Theme.spacing4
        radius: Theme.radiusSmall
        color: root.highlighted && root.enabled
               ? Theme.panelSideBarItemHover
               : "transparent"
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing12
        anchors.rightMargin: Theme.spacing12
        spacing: Theme.spacing8

        Item {
            width: 18
            height: parent.height

            Text {
                visible: root.hasCommand
                         && root.command.checkable
                         && root.command.checked
                anchors.centerIn: parent
                text: "✓"
                color: Theme.panelSideBarAccentColor
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
                font.weight: Font.DemiBold
            }

            ThemedIcon {
                visible: root.hasCommand
                         && !root.command.checkable
                         && String(root.command.iconSource) !== ""
                anchors.centerIn: parent
                iconSource: root.hasCommand ? root.command.iconSource : ""
                iconSize: Theme.iconSizeNormal
                iconColor: root.enabled
                           ? Theme.panelSideBarTextSecondary
                           : Theme.panelSideBarTextDisabled
            }
        }

        Text {
            width: Math.max(0, parent.width - 18 - shortcutLabel.width
                            - parent.spacing * 2)
            height: parent.height
            text: root.hasCommand ? root.command.text : ""
            color: root.enabled
                   ? Theme.panelSideBarTextPrimary
                   : Theme.panelSideBarTextDisabled
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            font.weight: Font.Normal
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        Text {
            id: shortcutLabel
            width: 82
            height: parent.height
            text: root.shortcutText
            color: root.enabled
                   ? Theme.panelSideBarTextSecondary
                   : Theme.panelSideBarTextDisabled
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignRight
        }
    }

    HoverHandler {
        enabled: root.enabled
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onHoveredChanged: if (hovered) root.hoveredRequested(root.menuIndex)
    }

    TapHandler {
        enabled: root.enabled
        onTapped: root.activate()
    }

    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Down) {
            root.moveRequested(1)
        } else if (event.key === Qt.Key_Up) {
            root.moveRequested(-1)
        } else if (event.key === Qt.Key_Home) {
            root.boundaryRequested(false)
        } else if (event.key === Qt.Key_End) {
            root.boundaryRequested(true)
        } else if (event.key === Qt.Key_Escape) {
            root.dismissRequested()
        } else if (event.key === Qt.Key_Left) {
            root.switchMenuRequested(-1)
        } else if (event.key === Qt.Key_Right) {
            root.switchMenuRequested(1)
        } else if (event.key === Qt.Key_Return
                   || event.key === Qt.Key_Enter
                   || event.key === Qt.Key_Space) {
            root.activate()
        } else {
            return
        }
        event.accepted = true
    }
}
