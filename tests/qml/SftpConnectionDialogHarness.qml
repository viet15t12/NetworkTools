import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 760
    height: 680
    visible: true

    SftpConnectionDialog {
        objectName: "sftpConnectionDialogHarnessDialog"
        anchors.centerIn: parent
        backend: typeof sftpController !== "undefined" ? sftpController : null
    }
}
