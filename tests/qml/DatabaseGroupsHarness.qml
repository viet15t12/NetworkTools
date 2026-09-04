pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 360
    height: 680
    visible: true

    DatabaseTablesPanel {
        objectName: "databaseGroupsPanel"
        anchors.fill: parent
    }
}
