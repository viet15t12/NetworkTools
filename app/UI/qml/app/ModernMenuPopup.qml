pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Window
import UI

Popup {
    id: root

    required property var registry
    required property var itemDefinitions
    property int highlightedIndex: -1
    property var opener: null
    property var focusReturnItem: null

    signal commandInvoked(string commandId)
    signal switchMenuRequested(int direction)

    function commandAt(index) {
        if (index < 0 || index >= root.itemDefinitions.length)
            return null
        const definition = root.itemDefinitions[index]
        if (definition.type !== "command")
            return null
        return MenuDefinition.commandFor(root.registry, definition.commandId)
    }

    function isFocusable(index) {
        const action = root.commandAt(index)
        return action !== null && action.visible && action.enabled
    }

    function boundaryIndex(end) {
        if (end) {
            for (let index = root.itemDefinitions.length - 1; index >= 0; index--) {
                if (root.isFocusable(index))
                    return index
            }
        } else {
            for (let index = 0; index < root.itemDefinitions.length; index++) {
                if (root.isFocusable(index))
                    return index
            }
        }
        return -1
    }

    function focusHighlighted() {
        const loader = menuRepeater.itemAt(root.highlightedIndex)
        if (loader && loader.item)
            loader.item.forceActiveFocus(Qt.PopupFocusReason)
    }

    function setBoundary(end) {
        root.highlightedIndex = root.boundaryIndex(end)
        Qt.callLater(root.focusHighlighted)
    }

    function moveHighlight(delta) {
        const count = root.itemDefinitions.length
        if (count === 0)
            return
        let index = root.highlightedIndex
        for (let step = 0; step < count; step++) {
            index = (index + delta + count) % count
            if (root.isFocusable(index)) {
                root.highlightedIndex = index
                Qt.callLater(root.focusHighlighted)
                return
            }
        }
    }

    function openFrom(item, focusLast, returnFocusItem) {
        root.opener = item
        root.focusReturnItem = returnFocusItem
        root.highlightedIndex = root.boundaryIndex(focusLast === true)
        root.open()
    }

    function restoreFocus() {
        if (root.focusReturnItem
                && typeof root.focusReturnItem.forceActiveFocus === "function") {
            root.focusReturnItem.forceActiveFocus(Qt.PopupFocusReason)
        } else if (root.opener) {
            root.opener.forceActiveFocus(Qt.PopupFocusReason)
        }
    }

    function dismissToOpener() {
        root.close()
        root.restoreFocus()
    }

    function invokeCommand(commandId) {
        const action = MenuDefinition.commandFor(root.registry, commandId)
        if (action === null || !action.enabled)
            return false
        // Remove the overlay and release popup focus before a handler opens a
        // dialog, changes window state, or destroys the current context.
        root.close()
        root.restoreFocus()
        const invoked = root.registry.trigger(commandId)
        if (invoked)
            root.commandInvoked(commandId)
        return invoked
    }

    objectName: "modernMenuPopup"
    x: {
        if (!parent || !parent.Window.window)
            return 0
        const window = parent.Window.window
        const globalPosition = parent.mapToItem(window.contentItem, 0, 0)
        const minimum = Theme.spacing4 - globalPosition.x
        const maximum = window.width - Theme.spacing4
                        - globalPosition.x - root.width
        return Math.max(minimum, Math.min(0, maximum))
    }
    y: parent ? parent.height + Theme.spacing2 : 0
    width: parent && parent.Window.window
           ? Math.min(284, Math.max(
                 160, parent.Window.window.width - Theme.spacing8
             ))
           : 284
    height: menuColumn.implicitHeight + padding * 2
    padding: Theme.spacing4
    margins: Theme.spacing4
    leftInset: -Theme.spacing4
    rightInset: -Theme.spacing4
    topInset: -Theme.spacing4
    bottomInset: -Theme.spacing8
    focus: true
    modal: false
    dim: false
    z: 1000
    // Treat the top-level button as part of the menu interaction. Otherwise
    // Popup closes before the button's tap handler and that handler reopens it.
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
    transformOrigin: Item.TopLeft

    onOpened: Qt.callLater(root.focusHighlighted)
    onClosed: {
        root.highlightedIndex = -1
        root.opener = null
        root.focusReturnItem = null
    }

    Connections {
        target: root.parent ? root.parent.Window.window : null

        function onActiveChanged() {
            if (target && !target.active)
                root.close()
        }
    }

    background: Rectangle {
        // The title/menu bar may intentionally use the dark-sidebar palette
        // while the workspace remains light. Keep its popup in that palette.
        color: Theme.panelSideBarSurface
        border.width: Theme.borderWidth
        border.color: Theme.panelSideBarBorderColor
        radius: Theme.radiusMedium

        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.shadowColor
            shadowBlur: 0.85
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 5
            autoPaddingEnabled: true
        }
    }

    contentItem: Column {
        id: menuColumn
        width: root.availableWidth

        Repeater {
            id: menuRepeater
            // Closed popups retain no delegates, icons, or focus scopes.
            model: root.visible ? root.itemDefinitions : []

            delegate: Loader {
                id: entryLoader
                required property int index
                required property var modelData
                readonly property int entryIndex: index
                readonly property var action: modelData.type === "command"
                                              ? MenuDefinition.commandFor(
                                                    root.registry,
                                                    modelData.commandId
                                                )
                                              : null

                width: menuColumn.width
                active: MenuDefinition.entryVisible(
                            root.registry,
                            root.itemDefinitions,
                            entryIndex
                        )
                visible: active
                sourceComponent: modelData.type === "separator"
                                 ? separatorComponent : itemComponent
            }
        }
    }

    Component {
        id: separatorComponent
        ModernMenuSeparator {}
    }

    Component {
        id: itemComponent

        ModernMenuItem {
            command: parent ? parent.action : null
            menuIndex: parent ? parent.entryIndex : -1
            highlighted: root.highlightedIndex === menuIndex
            onHoveredRequested: function(menuIndex) {
                root.highlightedIndex = menuIndex
            }
            onMoveRequested: function(delta) { root.moveHighlight(delta) }
            onBoundaryRequested: function(end) { root.setBoundary(end) }
            onDismissRequested: root.dismissToOpener()
            onSwitchMenuRequested: function(direction) {
                root.switchMenuRequested(direction)
            }
            onActivated: root.invokeCommand(command.commandId)
        }
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation {
                property: "opacity"
                from: 0.0
                to: 1.0
                duration: Theme.animationDurationFast
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                property: "scale"
                from: 0.97
                to: 1.0
                duration: Theme.animationDurationFast
                easing.type: Easing.OutCubic
            }
        }
    }

    exit: Transition {
        NumberAnimation {
            property: "opacity"
            to: 0.0
            duration: Theme.animationDurationFast
            easing.type: Easing.InCubic
        }
    }
}
