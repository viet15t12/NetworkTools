import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 1120
    height: 780
    visible: true

    SftpView {
        objectName: "sftpNavigationWorkspace"
        anchors.fill: parent
        backend: typeof sftpController !== "undefined" ? sftpController : null
    }
}
