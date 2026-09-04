import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 1120
    height: 780
    visible: true

    property int reloadCount: 0

    // Main keeps the sidebar stack alive while SFTP is active. This hidden
    // instance reproduces conflicts from shortcuts that forget their panel
    // visibility guard.
    DevicesPanel {
        anchors.fill: parent
        visible: false
    }

    SftpView {
        id: workspace
        objectName: "sftpShortcutWorkspace"
        anchors.fill: parent
        backend: typeof sftpController !== "undefined" ? sftpController : null
    }

    CommandRegistry {
        reloadAvailable: true
        reloadHandler: function() {
            root.reloadCount++
            workspace.refreshActive()
            return true
        }
    }
}
