pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 760
    height: 180
    visible: true

    DeviceTabs {
        id: tabs
        objectName: "deviceTabsContextTarget"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
    }

    Component.onCompleted: {
        tabs.initializeTabs([])
        tabs.openTab("192.0.2.1", "Router A", "router", "disconnected")
        tabs.openTab("192.0.2.2", "Router B", "router", "disconnected")
        tabs.openTab("192.0.2.3", "Router C", "router", "disconnected")
    }
}
