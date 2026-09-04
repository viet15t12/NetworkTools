pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Item {
    id: root

    property string title: "No data"
    property string description: ""
    property bool emphasized: true

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.max(0, Math.min(parent.width - Theme.spacing32, 460))
        spacing: Theme.spacing4

        Text {
            Layout.fillWidth: true
            text: root.title
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            font.bold: root.emphasized
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            visible: root.description !== ""
            text: root.description
            color: Theme.textDisabled
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
    }
}
