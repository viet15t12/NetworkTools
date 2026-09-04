pragma ComponentBehavior: Bound

import QtQuick
import UI

Item {
    id: root

    required property var registry
    property var menuDefinitions: MenuDefinition.menus
    property int activeMenuIndex: -1
    property bool acceleratorsEnabled: Qt.platform.os !== "osx"
    property var focusReturnItem: null

    function normalizedIndex(index) {
        const count = menuDefinitions.length
        return count > 0 ? (index % count + count) % count : -1
    }

    function buttonAt(index) {
        return menuRepeater.itemAt(root.normalizedIndex(index))
    }

    function menuAvailable(index) {
        const normalized = root.normalizedIndex(index)
        return normalized >= 0
                && MenuDefinition.hasVisibleCommand(
                    root.registry, root.menuDefinitions[normalized].items
                )
    }

    function adjacentMenuIndex(index, direction) {
        const count = root.menuDefinitions.length
        if (count === 0)
            return -1
        let candidate = root.normalizedIndex(index)
        for (let step = 0; step < count; step++) {
            candidate = root.normalizedIndex(candidate + direction)
            if (root.menuAvailable(candidate))
                return candidate
        }
        return -1
    }

    function closeAllMenus() {
        for (let index = 0; index < menuDefinitions.length; index++) {
            const button = menuRepeater.itemAt(index)
            if (button)
                button.closeMenu()
        }
        root.activeMenuIndex = -1
        root.focusReturnItem = null
    }

    function openMenuAt(index, focusLast) {
        const normalized = root.normalizedIndex(index)
        if (normalized < 0 || !root.menuAvailable(normalized))
            return false
        const previous = root.buttonAt(root.activeMenuIndex)
        if (previous && root.activeMenuIndex !== normalized)
            previous.closeMenu()
        const button = root.buttonAt(normalized)
        if (!button)
            return false
        if (root.activeMenuIndex < 0 && root.Window.window)
            root.focusReturnItem = root.Window.window.activeFocusItem
        root.activeMenuIndex = normalized
        button.openMenu(focusLast === true)
        return true
    }

    function openMenuById(menuId) {
        for (let index = 0; index < menuDefinitions.length; index++) {
            if (menuDefinitions[index].menuId === menuId)
                return root.openMenuAt(index, false)
        }
        return false
    }

    function focusMenuAt(index) {
        if (!root.menuAvailable(index))
            return false
        const button = root.buttonAt(index)
        if (!button)
            return false
        button.forceActiveFocus(Qt.TabFocusReason)
        return true
    }

    function openAdjacentMenu(index, direction) {
        const adjacent = root.adjacentMenuIndex(index, direction)
        return adjacent >= 0 && root.openMenuAt(adjacent, false)
    }

    function focusAdjacentMenu(index, direction) {
        const adjacent = root.adjacentMenuIndex(index, direction)
        return adjacent >= 0 && root.focusMenuAt(adjacent)
    }

    objectName: "modernMenuBar"
    implicitWidth: menuRow.implicitWidth + Theme.spacing4
    implicitHeight: Theme.windowTitleHeight

    Accessible.role: Accessible.MenuBar
    Accessible.name: qsTr("Application menu")

    Component.onCompleted: MenuDefinition.validate(root.registry)

    Shortcut {
        sequence: "Alt+F"
        context: Qt.WindowShortcut
        enabled: root.acceleratorsEnabled && root.visible && root.enabled
        autoRepeat: false
        onActivated: root.openMenuById("file")
    }

    Shortcut {
        sequence: "Alt+V"
        context: Qt.WindowShortcut
        enabled: root.acceleratorsEnabled && root.visible && root.enabled
        autoRepeat: false
        onActivated: root.openMenuById("view")
    }

    Shortcut {
        sequence: "Alt+H"
        context: Qt.WindowShortcut
        enabled: root.acceleratorsEnabled && root.visible && root.enabled
        autoRepeat: false
        onActivated: root.openMenuById("help")
    }

    Row {
        id: menuRow
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        leftPadding: Theme.spacing2
        spacing: 0

        Repeater {
            id: menuRepeater
            model: root.menuDefinitions

            delegate: ModernMenuButton {
                required property int index
                required property var modelData
                menuData: modelData
                registry: root.registry
                menuIndex: index
                menuBar: root
                onPopupOpened: function(menuIndex) {
                    root.activeMenuIndex = menuIndex
                }
                onPopupClosed: function(menuIndex) {
                    if (root.activeMenuIndex === menuIndex) {
                        root.activeMenuIndex = -1
                        root.focusReturnItem = null
                    }
                }
                onSwitchMenuRequested: function(direction) {
                    root.openAdjacentMenu(index, direction)
                }
            }
        }
    }
}
