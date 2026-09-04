pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

ApplicationWindow {
    width: 280
    height: 180
    visible: true

    SplitFormPane {
        objectName: "splitFormPaneUnderTest"
        anchors.fill: parent
        paneMargins: Theme.spacing12
        paneTopMargin: Theme.spacing12

        Repeater {
            model: 8
            delegate: Rectangle {
                required property int index
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                color: index % 2 === 0
                       ? Theme.contentPanelSurface : Theme.inputBackground
            }
        }
    }
}
