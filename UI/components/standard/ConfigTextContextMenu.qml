pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: contextMenu

    property bool hasSelection: false
    readonly property int menuWidth: 260
    readonly property color menuBorderColor: Theme.isHighContrast
                                             ? Theme.panelSideBarBorderColor
                                             : (Theme.isDarkMode ? Qt.rgba(1, 1, 1, 0.12)
                                                                 : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.12))
    readonly property color menuDividerColor: Theme.isHighContrast
                                              ? Theme.panelSideBarBorderColor
                                              : (Theme.isDarkMode ? Qt.rgba(1, 1, 1, 0.14)
                                                                  : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.14))
    readonly property color menuShadowColor: Theme.isDarkMode ? Qt.rgba(0, 0, 0, 0.24)
                                                              : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.06)

    signal copyRequested()
    signal findRequested()

    function openAt(localX, localY) {
        const host = contextMenu.parent
        const rightEdge = host ? Math.max(4, host.width - contextMenu.width - 4) : localX
        const bottomEdge = host ? Math.max(4, host.height - contextMenu.height - 4) : localY
        contextMenu.x = Math.max(4, Math.min(Number(localX || 0), rightEdge))
        contextMenu.y = Math.max(4, Math.min(Number(localY || 0), bottomEdge))
        contextMenu.visible = true
    }

    function close() {
        contextMenu.visible = false
    }

    visible: false
    width: menuWidth
    height: menuColumn.implicitHeight + 8
    z: 999
    color: Theme.panelSideBarSurface
    border.color: menuBorderColor
    border.width: Theme.borderWidth
    radius: 6
    transformOrigin: Item.TopLeft

    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: parent.radius + 2
        color: "transparent"
        border.color: contextMenu.menuShadowColor
        border.width: Theme.borderWidth
        z: -1
    }

    Item {
        id: outsideClickCatcher
        parent: contextMenu.parent
        anchors.fill: parent
        visible: contextMenu.visible
        z: contextMenu.z - 1

        TapHandler {
            onTapped: contextMenu.close()
        }
    }

    Column {
        id: menuColumn
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 4
        anchors.leftMargin: 4
        anchors.rightMargin: 4
        anchors.bottomMargin: 4
        spacing: 0

        ContextMenuItem {
            objectName: "configViewerContextCopyItem"
            text: "Copy"
            shortcutText: "Ctrl+C"
            iconSource: AppAssets.actionCopy
            enabled: contextMenu.hasSelection
            onTriggered: {
                contextMenu.copyRequested()
                contextMenu.close()
            }
        }

        ContextMenuDivider {
            lineColor: contextMenu.menuDividerColor
        }

        ContextMenuItem {
            objectName: "configViewerContextFindItem"
            text: "Find"
            shortcutText: "Ctrl+F"
            iconSource: AppAssets.actionSearch
            enabled: contextMenu.hasSelection
            onTriggered: {
                contextMenu.findRequested()
                contextMenu.close()
            }
        }
    }

    NumberAnimation on opacity {
        running: contextMenu.visible
        from: 0.0
        to: 1.0
        duration: Theme.animationDurationFast
        easing.type: Easing.OutQuad
    }

    NumberAnimation on scale {
        running: contextMenu.visible
        from: 0.95
        to: 1.0
        duration: Theme.animationDurationFast
        easing.type: Easing.OutQuad
    }
}
