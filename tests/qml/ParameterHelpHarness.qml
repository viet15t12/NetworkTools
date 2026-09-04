pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

ApplicationWindow {
    width: 640
    height: 480
    visible: true

    FormSection {
        anchors.centerIn: parent
        width: 520
        title: "Destination"
        helpText: "Server IP: Reachable collector address.\n\nPort: Value from 1 to 65535."

        StandardTextField {
            labelText: "Server IP"
            placeholderText: "192.0.2.100"
        }
    }
}
