pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "sftpWorkspace"
    color: Theme.contentBackground
    property var backend: typeof sftpController !== "undefined"
                          ? sftpController : null
    property string activeSide: "local"
    readonly property bool textInputActive: connectionBar.anyInputFocus
                                            || localPanel.pathInputFocused
                                            || remotePanel.pathInputFocused
    readonly property bool interactionEnabled: root.visible && !UiState.windowLock
    readonly property bool shortcutsEnabled: root.interactionEnabled
                                             && !root.textInputActive
    readonly property bool pointerNavigationEnabled: root.interactionEnabled

    function activePanel() {
        return activeSide === "remote" ? remotePanel : localPanel
    }
    function goBack() { activePanel().goBack() }
    function goForward() { activePanel().goForward() }
    function goUp() { activePanel().goUp() }
    function refreshActive() { activePanel().refresh() }
    function createFolder() { activePanel().beginEdit("create") }
    function renameSelected() {
        if (activePanel().selectedIndex >= 0)
            activePanel().beginEdit("rename")
    }
    function deleteSelected() { activePanel().requestDelete() }
    function openSelected() { activePanel().openSelected() }
    function selectAll() { activePanel().selectAll() }
    function clearSelection() { activePanel().clearSelection() }
    function openContextMenu() { activePanel().openContextForSelection() }

    Connections {
        target: root.backend
        function onErrorOccurred(message) {
            errorDialog.messageText = message
            errorDialog.open()
        }
        function onHostKeyConfirmationRequired(host, keyType, fingerprint) {
            hostKeyDialog.messageText = "Host: " + host
                + "\nKey type: " + keyType
                + "\nFingerprint: " + fingerprint
                + "\n\nContinue only if this fingerprint matches the server you manage."
            hostKeyDialog.open()
        }
        function onConnectedChanged() {
            if (!root.backend || !root.backend.connected)
                root.activeSide = "local"
        }
    }

    SftpMessageDialog {
        id: errorDialog
        objectName: "sftpErrorDialog"
        titleText: "SFTP Error"
    }
    SftpMessageDialog {
        id: hostKeyDialog
        objectName: "sftpHostKeyDialog"
        titleText: "Confirm SSH Host Key"
        confirmation: true
        acceptText: "Trust and Connect"
        onAccepted: {
            if (root.backend)
                root.backend.confirmHostKey(true)
        }
        onRejected: {
            if (root.backend)
                root.backend.confirmHostKey(false)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing12
        spacing: Theme.spacing8

        SftpConnectionBar {
            id: connectionBar
            Layout.fillWidth: true
            backend: root.backend
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: root.width >= 900 ? 2 : 1
            columnSpacing: Theme.spacing8
            rowSpacing: Theme.spacing8

            SftpFilePanel {
                id: localPanel
                objectName: "sftpLocalPanel"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 260
                backend: root.backend
                fileModel: root.backend ? root.backend.localModel : null
                currentPath: root.backend ? root.backend.localPath : ""
                activePane: root.activeSide === "local"
                onActivated: root.activeSide = "local"
            }
            SftpFilePanel {
                id: remotePanel
                objectName: "sftpRemotePanel"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 260
                backend: root.backend
                fileModel: root.backend ? root.backend.remoteModel : null
                currentPath: root.backend ? root.backend.remotePath : ""
                remoteSide: true
                activePane: root.activeSide === "remote"
                onActivated: root.activeSide = "remote"
            }
        }

        SftpTransferQueue {
            id: transferQueue
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 132 : 0
            visible: root.backend !== null
                     && root.backend.transferModel.count > 0
            backend: root.backend
        }

        SftpLogPanel {
            id: logPanel
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 108 : 0
            visible: entryCount > 0
            backend: root.backend
        }
    }

    Text {
        anchors.centerIn: parent
        visible: root.backend === null
        text: "SFTP backend is unavailable"
        color: Theme.alertError
        font.family: Theme.fontFamily
    }

    Shortcut {
        sequence: "Alt+Left"
        enabled: root.shortcutsEnabled
        onActivated: root.goBack()
    }
    Shortcut {
        sequence: "Alt+Right"
        enabled: root.shortcutsEnabled
        onActivated: root.goForward()
    }
    Shortcut {
        sequence: "Alt+Up"
        enabled: root.shortcutsEnabled
        onActivated: root.goUp()
    }
    Shortcut {
        sequence: "Backspace"
        enabled: root.shortcutsEnabled
        onActivated: root.goBack()
    }
    Shortcut {
        sequence: "F5"
        enabled: root.shortcutsEnabled
        onActivated: root.refreshActive()
    }
    Shortcut {
        sequence: "Ctrl+Shift+N"
        enabled: root.shortcutsEnabled
        onActivated: root.createFolder()
    }
    Shortcut {
        sequence: "F2"
        enabled: root.shortcutsEnabled
        onActivated: root.renameSelected()
    }
    Shortcut {
        sequence: "Delete"
        enabled: root.shortcutsEnabled
        onActivated: root.deleteSelected()
    }
    Shortcut {
        sequence: "Return"
        enabled: root.shortcutsEnabled
        onActivated: root.openSelected()
    }
    Shortcut {
        sequence: StandardKey.SelectAll
        enabled: root.shortcutsEnabled
        onActivated: root.selectAll()
    }
    Shortcut {
        sequence: "Escape"
        enabled: root.shortcutsEnabled
        onActivated: root.clearSelection()
    }
    Shortcut {
        sequence: "Shift+F10"
        enabled: root.shortcutsEnabled
        onActivated: root.openContextMenu()
    }

    TapHandler {
        acceptedButtons: Qt.BackButton | Qt.ForwardButton
        enabled: root.pointerNavigationEnabled
        gesturePolicy: TapHandler.ReleaseWithinBounds
        onTapped: function(eventPoint, button) {
            if (button === Qt.BackButton)
                root.goBack()
            else if (button === Qt.ForwardButton)
                root.goForward()
        }
    }
}
