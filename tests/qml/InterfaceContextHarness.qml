pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 1180
    height: 720
    visible: true

    InterfaceView {
        objectName: "interfaceContextTarget"
        anchors.fill: parent
        currentHostIp: "context-menu.test"
    }
}
