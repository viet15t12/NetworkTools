pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

ColumnLayout {
    id: root

    property string title: ""
    property string description: ""
    property string helpTitle: title + " parameters"
    property string helpText: ""
    property bool showDivider: true
    default property alias content: sectionBody.data

    spacing: Theme.spacing8

    RowLayout {
        Layout.fillWidth: true

        Text {
            Layout.fillWidth: true
            text: root.title
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }

        ParameterHelpButton {
            visible: root.helpText !== ""
            helpTitle: root.helpTitle
            helpText: root.helpText
        }
    }

    Text {
        visible: root.description !== ""
        Layout.fillWidth: true
        text: root.description
        color: Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSmall
        wrapMode: Text.WordWrap
    }

    ColumnLayout {
        id: sectionBody
        Layout.fillWidth: true
        spacing: Theme.spacing8
    }

    Rectangle {
        visible: root.showDivider
        Layout.fillWidth: true
        Layout.topMargin: Theme.spacing4
        Layout.preferredHeight: Theme.borderWidth
        color: Theme.contentPanelBorder
    }
}
