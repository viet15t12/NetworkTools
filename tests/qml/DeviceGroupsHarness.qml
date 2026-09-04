pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 360
    height: 600
    visible: true

    DevicesPanel {
        id: panel
        objectName: "deviceGroupsPanel"
        anchors.fill: parent
        openEditors: [
            {
                "uid": "192.0.2.1",
                "title": "Router A",
                "deviceType": "router",
                "status": "connected"
            }
        ]
    }

    Component.onCompleted: {
        panel.allDevices = [
            { "ip": "192.0.2.1", "name": "Router A", "type": "router", "status": "connected" },
            { "ip": "192.0.2.2", "name": "Switch B", "type": "switch", "status": "waiting" },
            { "ip": "192.0.2.3", "name": "Router C", "type": "router", "status": "disconnected" }
        ]
        panel.applyFilters()
    }
}
