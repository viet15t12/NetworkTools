pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root
    objectName: "panelGroupContextMenu"

    property bool canCollapseAll: true
    property bool canExpandAll: true
    property bool connectAllVisible: false
    property bool connectAllRunning: false
    readonly property color menuBorderColor: Theme.isHighContrast
                                             ? Theme.panelSideBarBorderColor
                                             : Theme.isDarkMode
                                               ? Qt.rgba(1, 1, 1, 0.12)
                                               : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.12)

    signal collapseAllRequested()
    signal expandAllRequested()
    signal connectAllRequested()

    function openAt(xPosition, yPosition) {
        const window = Window.window
        if (window) {
            x = Math.max(Theme.spacing4,
                         Math.min(xPosition, window.width - width - Theme.spacing4))
            y = Math.max(Theme.spacing4,
                         Math.min(yPosition, window.height - height - Theme.spacing4))
        } else {
            x = xPosition
            y = yPosition
        }
        visible = true
    }

    function close() {
        visible = false
    }

    visible: false
    width: 220
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

        TapHandler {
            onTapped: root.close()
        }
    }

    Column {
        id: menuColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.spacing4

        ContextMenuItem {
            objectName: "panelGroupCollapseAll"
            text: "Collapse All"
            iconSource: AppAssets.navigationListCollapse
            enabled: root.canCollapseAll
            onTriggered: {
                root.close()
                root.collapseAllRequested()
            }
        }

        ContextMenuItem {
            objectName: "panelGroupConnectAll"
            visible: root.connectAllVisible
            enabled: root.connectAllVisible
            text: root.connectAllRunning ? "Connect All Waiting (tasks running)" : "Connect All Waiting"
            iconSource: AppAssets.actionMonitorStart
            onTriggered: {
                root.close()
                root.connectAllRequested()
            }
        }

        ContextMenuItem {
            objectName: "panelGroupExpandAll"
            text: "Expand All"
            iconSource: AppAssets.navigationListExpand
            enabled: root.canExpandAll
            onTriggered: {
                root.close()
                root.expandAllRequested()
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
