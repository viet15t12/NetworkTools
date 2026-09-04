pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

ApplicationWindow {
    width: 520
    height: 620
    visible: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing12
        spacing: Theme.spacing12

        StandardButton {
            objectName: "responsiveCompactButton"
            Layout.preferredWidth: 34
            Layout.maximumWidth: 34
            text: "Reload"
            icon.source: AppAssets.actionRefresh
            type: "Secondary"
        }

        SyslogControlBar {
            objectName: "responsiveSyslogControlBar"
            Layout.fillWidth: true
            listenerState: "stopped"
            statusText: "System Logs listener is stopped."
            receivedCount: 12
        }

        SyslogFilterBar {
            objectName: "responsiveSyslogFilterBar"
            Layout.fillWidth: true
        }

        Item { Layout.fillHeight: true }
    }
}
