pragma ComponentBehavior: Bound

import QtQuick
import UI

FocusScope {
    id: root

    required property var menuData
    required property var registry
    required property int menuIndex
    required property var menuBar

    readonly property bool popupVisible: menuPopup.opened

    signal popupOpened(int menuIndex)
    signal popupClosed(int menuIndex)
    signal switchMenuRequested(int direction)

    function openMenu(focusLast) {
        menuPopup.openFrom(
            root, focusLast === true, root.menuBar.focusReturnItem
        )
    }

    function closeMenu() {
        menuPopup.close()
    }

    function toggleMenu() {
        if (menuPopup.opened)
            menuPopup.close()
        else
            root.openMenu(false)
    }

    objectName: "modernMenuButton"
                + menuData.menuId.charAt(0).toUpperCase()
                + menuData.menuId.slice(1)
    implicitWidth: Math.max(44, menuLabel.implicitWidth + Theme.spacing16)
    implicitHeight: Theme.windowTitleHeight - Theme.spacing4
    visible: MenuDefinition.hasVisibleCommand(root.registry, menuData.items)

    onVisibleChanged: if (!visible) root.closeMenu()

    Accessible.role: Accessible.MenuItem
    Accessible.name: menuData.title
    Accessible.description: qsTr("Open %1 menu").arg(menuData.title)
    Accessible.focusable: true
    Accessible.focused: activeFocus
    Accessible.onPressAction: root.toggleMenu()

    Rectangle {
        anchors.fill: parent
        color: root.popupVisible
               ? Theme.activityBarItemActive
               : (menuHover.hovered ? Theme.activityBarItemHover : "transparent")
    }

    Text {
        id: menuLabel
        anchors.centerIn: parent
        text: root.menuData.title
        color: Theme.activityBarTextPrimary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSmall
        font.weight: root.popupVisible ? Font.DemiBold : Font.Normal
    }

    Rectangle {
        visible: root.popupVisible || root.activeFocus
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 2
        color: Theme.accentColor
    }

    HoverHandler {
        id: menuHover
        cursorShape: Qt.PointingHandCursor
        onHoveredChanged: {
            if (hovered && root.menuBar.activeMenuIndex >= 0
                    && root.menuBar.activeMenuIndex !== root.menuIndex) {
                root.menuBar.openMenuAt(root.menuIndex, false)
            }
        }
    }

    TapHandler {
        onTapped: root.toggleMenu()
    }

    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Return
                || event.key === Qt.Key_Enter
                || event.key === Qt.Key_Space
                || event.key === Qt.Key_Down) {
            root.openMenu(false)
        } else if (event.key === Qt.Key_Up) {
            root.openMenu(true)
        } else if (event.key === Qt.Key_Left) {
            root.menuBar.focusAdjacentMenu(root.menuIndex, -1)
        } else if (event.key === Qt.Key_Right) {
            root.menuBar.focusAdjacentMenu(root.menuIndex, 1)
        } else if (event.key === Qt.Key_Escape) {
            root.closeMenu()
        } else {
            return
        }
        event.accepted = true
    }

    ModernMenuPopup {
        id: menuPopup
        objectName: "modernMenuPopup"
                    + root.menuData.menuId.charAt(0).toUpperCase()
                    + root.menuData.menuId.slice(1)
        registry: root.registry
        itemDefinitions: root.menuData.items
        onOpened: root.popupOpened(root.menuIndex)
        onClosed: root.popupClosed(root.menuIndex)
        onSwitchMenuRequested: function(direction) {
            root.switchMenuRequested(direction)
        }
    }
}
