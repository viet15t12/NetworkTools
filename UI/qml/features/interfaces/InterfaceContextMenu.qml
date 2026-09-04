pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    property bool hasTarget: false
    property bool canDeleteTarget: false
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

    signal editRequested()
    signal deleteRequested()
    signal refreshRequested()

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

    objectName: "interfaceContextMenu"
    visible: false
    width: 260
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
            objectName: "interfaceContextEdit"
            text: "Edit"
            shortcutText: "F2"
            iconSource: AppAssets.actionEdit
            enabled: root.hasTarget
            onTriggered: {
                root.close()
                root.editRequested()
            }
        }
        ContextMenuItem {
            objectName: "interfaceContextDelete"
            text: "Delete"
            shortcutText: "Del"
            iconSource: AppAssets.actionDelete
            danger: true
            enabled: root.hasTarget && root.canDeleteTarget
            onTriggered: {
                root.close()
                root.deleteRequested()
            }
        }

        ContextMenuDivider {
            lineColor: root.menuDividerColor
        }

        ContextMenuItem {
            objectName: "interfaceContextRefresh"
            text: "Refresh"
            shortcutText: "F5"
            iconSource: AppAssets.actionRefresh
            onTriggered: {
                root.close()
                root.refreshRequested()
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
