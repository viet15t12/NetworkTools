pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root
    property var targetProfile: ({})
    readonly property color menuBorderColor: Theme.isHighContrast
                                             ? Theme.panelSideBarBorderColor
                                             : Theme.isDarkMode
                                               ? Qt.rgba(1, 1, 1, 0.12)
                                               : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.12)

    signal useRequested(var profile)
    signal editRequested(var profile)
    signal deleteRequested(var profile)

    function openAt(xPosition, yPosition, profile) {
        targetProfile = profile || ({})
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
        targetProfile = ({})
        UiState.windowLock = false
    }

    visible: false
    width: 260
    height: menuColumn.implicitHeight + Theme.spacing8
    z: 999
    color: Theme.panelSideBarSurface
    border.color: menuBorderColor
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall

    Item {
        parent: Window.window ? Window.window.contentItem : null
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
            text: "Use connection"
            iconSource: AppAssets.actionConnect
            onTriggered: {
                const profile = root.targetProfile
                root.close()
                root.useRequested(profile)
            }
        }
        ContextMenuItem {
            text: "Edit"
            iconSource: AppAssets.actionEdit
            onTriggered: {
                const profile = root.targetProfile
                root.close()
                root.editRequested(profile)
            }
        }
        ContextMenuDivider {}
        ContextMenuItem {
            text: "Delete"
            iconSource: AppAssets.actionDelete
            onTriggered: {
                const profile = root.targetProfile
                root.close()
                root.deleteRequested(profile)
            }
        }
    }
}
