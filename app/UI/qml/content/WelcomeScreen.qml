pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    color: Theme.contentBackground

    Column {
        anchors.centerIn: parent
        spacing: 24

        Image {
            id: welcomeLogo
            objectName: "emptyWorkspaceLogo"
            anchors.horizontalCenter: parent.horizontalCenter
            width: 360
            height: 360
            source: AppAssets.brandLogo
            sourceSize: Qt.size(width, height)
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            cache: true
            smooth: true
            opacity: 0.3

            // Flatten the full-color brand artwork to the subdued monochrome
            // treatment used by the empty Workspace, while retaining its alpha
            // and every detail from the source SVG.
            layer.enabled: true
            layer.smooth: true
            layer.effect: MultiEffect {
                colorization: 1.0
                colorizationColor: Theme.textDisabled
            }
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
