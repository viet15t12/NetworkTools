pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    property bool canCloseOthers: false
    property bool canCloseToRight: false
    property bool canReopenClosed: false
    readonly property color menuBorderColor: Theme.isHighContrast
                                             ? Theme.panelSideBarBorderColor
                                             : Theme.isDarkMode
                                               ? Qt.rgba(1, 1, 1, 0.12)
                                               : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.12)
    readonly property color menuDividerColor: Theme.isHighContrast
                                              ? Theme.panelSideBarBorderColor
                                              : Theme.isDarkMode
                                                ? Qt.rgba(1, 1, 1, 0.14)
                                                : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.14)

    signal closeRequested()
    signal closeOthersRequested()
    signal closeToRightRequested()
    signal closeAllRequested()
    signal reopenClosedRequested()
    signal newDeviceRequested()

    function openAt(xPosition, yPosition) {
        const window = Window.window
        if (window) {
            x = Math.max(4, Math.min(xPosition, window.width - width - 4))
            y = Math.max(4, Math.min(yPosition, window.height - height - 4))
        } else {
            x = xPosition
            y = yPosition
        }
        UiState.windowLock = true
        visible = true
    }

    function close() {
        visible = false
        UiState.windowLock = false
    }

    objectName: "deviceTabContextMenu"
    visible: false
    width: 286
    height: menuColumn.implicitHeight + Theme.spacing8
    z: 999
    color: Theme.panelSideBarSurface
    border.color: menuBorderColor
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall
    transformOrigin: Item.TopLeft

    Item {
        parent: Window.window ? Window.window.contentItem : root.parent
        anchors.fill: parent
        visible: root.visible
        z: 998
        TapHandler { onTapped: root.close() }
    }

    Column {
        id: menuColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.spacing4

        ContextMenuItem {
            objectName: "deviceTabContextClose"
            text: "Close"
            shortcutText: "Ctrl+W"
            iconSource: AppAssets.actionClose
            onTriggered: {
                root.close()
                root.closeRequested()
            }
        }
        ContextMenuItem {
            objectName: "deviceTabContextCloseOthers"
            text: "Close Others"
            enabled: root.canCloseOthers
            onTriggered: {
                root.close()
                root.closeOthersRequested()
            }
        }
        ContextMenuItem {
            objectName: "deviceTabContextCloseRight"
            text: "Close to the Right"
            enabled: root.canCloseToRight
            onTriggered: {
                root.close()
                root.closeToRightRequested()
            }
        }
        ContextMenuItem {
            objectName: "deviceTabContextCloseAll"
            text: "Close All"
            shortcutText: "Ctrl+K Ctrl+W"
            onTriggered: {
                root.close()
                root.closeAllRequested()
            }
        }

        ContextMenuDivider {
            lineColor: root.menuDividerColor
        }

        ContextMenuItem {
            objectName: "deviceTabContextReopen"
            text: "Reopen Closed"
            shortcutText: "Ctrl+Shift+T"
            enabled: root.canReopenClosed
            onTriggered: {
                root.close()
                root.reopenClosedRequested()
            }
        }
        ContextMenuItem {
            objectName: "deviceTabContextNew"
            text: "New Device"
            shortcutText: "Ctrl+T"
            iconSource: AppAssets.actionAdd
            onTriggered: {
                root.close()
                root.newDeviceRequested()
            }
        }
    }

    NumberAnimation on opacity {
        running: root.visible
        from: 0.0
        to: 1.0
        duration: Theme.animationDurationFast
        easing.type: Easing.OutQuad
    }

    NumberAnimation on scale {
        running: root.visible
        from: 0.95
        to: 1.0
        duration: Theme.animationDurationFast
        easing.type: Easing.OutQuad
    }
}
