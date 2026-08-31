pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    color: Theme.contentBackground

    Column {
        anchors.centerIn: parent
        spacing: 24

        // Logo nhạt màu
        ThemedIcon {
            anchors.horizontalCenter: parent.horizontalCenter
            iconSource: AppAssets.brandLogo
            iconSize: 360
            iconColor: Theme.textDisabled
            opacity: 0.3
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "CAMS"
            color: Theme.textDisabled
            font.pixelSize: 32
            font.family: Theme.fontFamily
            font.bold: true
            opacity: 0.4
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Ctrl+N to add New Device\nOr select a device on the side bar to start"
            color: Theme.textDisabled
            font.pixelSize: 15
            font.family: Theme.fontFamily
            horizontalAlignment: Text.AlignHCenter
            opacity: 0.6
            lineHeight: 1.5
        }
    }
}
