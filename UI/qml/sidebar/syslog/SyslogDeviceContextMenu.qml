pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    property string targetHost: ""
    property bool configured: false
    property bool busy: false
    property bool selectionMode: false
    property var batchHosts: []
    readonly property int menuWidth: 310
    readonly property color menuBorderColor: Theme.isHighContrast
                                             ? Theme.panelSideBarBorderColor
                                             : Theme.isDarkMode
                                               ? Qt.rgba(1, 1, 1, 0.12)
                                               : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.12)

    signal configureRequested(string host)
    signal cancelRequested(string host)
    signal groupRequested(var hosts)
    signal clearSelectionRequested()

    function openAt(xPosition, yPosition, host, isConfigured, selectedHosts) {
        targetHost = String(host || "")
        configured = Boolean(isConfigured)
        batchHosts = (selectedHosts || [targetHost]).slice(0)
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
        targetHost = ""
        batchHosts = []
    }

    visible: false
    width: menuWidth
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
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.spacing4

        Rectangle {
            visible: root.selectionMode
            width: parent.width
            height: visible ? 42 : 0
            radius: Theme.radiusSmall
            color: Theme.alertInfoSubtle
            Text {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacing8
                anchors.rightMargin: Theme.spacing8
                text: root.batchHosts.length + " connected hosts selected"
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.bold: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }

        ContextMenuItem {
            visible: !root.selectionMode
            text: root.configured
                  ? "Remove System Logs Configuration"
                  : "Configure System Logs"
            iconSource: root.configured
                        ? AppAssets.actionDisconnect
                        : AppAssets.actionPush
            enabled: !root.busy && root.targetHost !== ""
            onTriggered: {
                if (root.configured)
                    root.cancelRequested(root.targetHost)
                else
                    root.configureRequested(root.targetHost)
                root.close()
            }
        }

        ContextMenuItem {
            visible: root.selectionMode
            text: "Configure as Syslog Group (" + root.batchHosts.length + ")"
            iconSource: AppAssets.actionPush
            enabled: !root.busy && root.batchHosts.length >= 2
                     && root.batchHosts.length <= 5
            onTriggered: {
                root.groupRequested(root.batchHosts.slice(0))
                root.close()
            }
        }

        ContextMenuItem {
            visible: root.selectionMode
            text: "Clear selection and exit"
            onTriggered: {
                root.clearSelectionRequested()
                root.close()
            }
        }
    }

    NumberAnimation on opacity {
        running: root.visible
        from: 0
        to: 1
        duration: Theme.animationDurationFast
        easing.type: Easing.OutQuad
    }

    NumberAnimation on scale {
        running: root.visible
        from: 0.96
        to: 1
        duration: Theme.animationDurationFast
        easing.type: Easing.OutQuad
    }

    transformOrigin: Item.TopLeft
}
