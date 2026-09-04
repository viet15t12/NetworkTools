pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 640
    height: 96
    visible: true

    property bool activeContentLoading: false
    readonly property int tabCount: 1

    DeviceTabItem {
        id: deviceTab
        objectName: "loadingDeviceTabItem"
        model: ({
            "title": "Router 1",
            "deviceType": "router",
            "status": "disconnected",
            "isActive": true,
            "sessionState": "pending",
            "contentLoading": root.activeContentLoading
        })
        index: 0
        anchors.top: parent.top
    }
}
