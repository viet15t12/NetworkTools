pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Item {
    id: root

    property string text: ""
    property string helpTitle: text + " parameters"
    property string helpText: ""

    implicitWidth: titleRow.implicitWidth
    implicitHeight: titleRow.implicitHeight

    RowLayout {
        id: titleRow
        anchors.fill: parent
        spacing: Theme.spacing8

        Text {
            Layout.fillWidth: true
            text: root.text
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLarge
            font.family: Theme.fontFamily
            font.bold: true
            elide: Text.ElideRight
        }

        ParameterHelpButton {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            visible: root.helpText.trim() !== ""
            helpTitle: root.helpTitle
            helpText: root.helpText
        }
    }
}
