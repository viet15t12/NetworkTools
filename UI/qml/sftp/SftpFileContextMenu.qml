pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    property int selectedCount: 0
    property bool singleDirectory: false
    property bool remoteSide: false
    property bool connected: false
    readonly property bool primaryEnabled: selectedCount > 0
                                                   && (singleDirectory || connected)
    readonly property string primaryText: selectedCount === 1 && singleDirectory
                                           ? "Open"
                                           : (remoteSide ? "Download" : "Upload")
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
    readonly property color menuShadowColor: Theme.isDarkMode
                                             ? Qt.rgba(0, 0, 0, 0.24)
                                             : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.06)

    signal primaryRequested()
    signal renameRequested()
    signal deleteRequested()
    signal createFolderRequested()
    signal selectAllRequested()
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
        visible = true
    }

    function close() {
        visible = false
    }

    objectName: "sftpFileContextMenu"
    visible: false
    width: 280
    height: menuColumn.implicitHeight + Theme.spacing8
    z: 999
    color: Theme.panelSideBarSurface
    border.color: menuBorderColor
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall
    transformOrigin: Item.TopLeft

    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: parent.radius + 2
        color: "transparent"
        border.color: root.menuShadowColor
        border.width: Theme.borderWidth
        z: -1
    }

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
            objectName: "sftpContextPrimary"
            text: root.primaryText
            shortcutText: "Enter"
            iconSource: root.selectedCount === 1 && root.singleDirectory
                        ? AppAssets.fileFolder
                        : (root.remoteSide
                           ? AppAssets.actionDownload : AppAssets.actionUpload)
            enabled: root.primaryEnabled
            onTriggered: {
                root.close()
                root.primaryRequested()
            }
        }
        ContextMenuItem {
            objectName: "sftpContextRename"
            text: "Rename"
            shortcutText: "F2"
            iconSource: AppAssets.actionEdit
            enabled: root.selectedCount === 1
            onTriggered: {
                root.close()
                root.renameRequested()
            }
        }
        ContextMenuItem {
            objectName: "sftpContextDelete"
            text: root.selectedCount > 1
                  ? "Delete " + root.selectedCount + " entries" : "Delete"
            shortcutText: "Del"
            iconSource: AppAssets.actionDelete
            danger: true
            enabled: root.selectedCount > 0
            onTriggered: {
                root.close()
                root.deleteRequested()
            }
        }

        ContextMenuDivider {
            lineColor: root.menuDividerColor
        }

        ContextMenuItem {
            objectName: "sftpContextNewFolder"
            text: "New folder"
            shortcutText: "Ctrl+Shift+N"
            iconSource: AppAssets.actionAdd
            onTriggered: {
                root.close()
                root.createFolderRequested()
            }
        }
        ContextMenuItem {
            objectName: "sftpContextSelectAll"
            text: "Select all"
            shortcutText: "Ctrl+A"
            onTriggered: {
                root.close()
                root.selectAllRequested()
            }
        }
        ContextMenuItem {
            objectName: "sftpContextRefresh"
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
