pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 520
    height: 700
    visible: true

    InformationView {
        anchors.fill: parent
        currentHostIp: ""
    }
}
