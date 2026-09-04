pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

RowLayout {
    id: root

    property string title: ""
    property string subtitle: ""
    property string closeTooltip: "Close"
    property color titleColor: Theme.textPrimary
    property bool closeEnabled: true

    signal closeRequested()

    spacing: Theme.spacing12
    implicitHeight: Math.max(titleBlock.implicitHeight, closeButton.implicitHeight)

    ColumnLayout {
        id: titleBlock
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignVCenter
        spacing: Theme.spacing2

        Text {
            Layout.fillWidth: true
            text: root.title
            color: root.titleColor
            font.pixelSize: Theme.fontSizeTitle
            font.bold: true
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        Text {
            Layout.fillWidth: true
            visible: root.subtitle !== ""
            text: root.subtitle
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }
    }

    CloseButton {
        id: closeButton
        Layout.alignment: Qt.AlignTop
        enabled: root.closeEnabled
        tooltip: root.closeTooltip
        onClicked: root.closeRequested()
    }
}
