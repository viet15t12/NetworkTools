pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: root
    preferredWidth: 520
    implicitHeight: 230

    property string titleText: "SFTP"
    property string messageText: ""
    property bool confirmation: false
    property string rejectText: "Cancel"
    property string acceptText: confirmation ? "Confirm" : "Close"

    title: root.titleText
    closeTooltip: "Close SFTP message"

    contentItem: Text {
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.Wrap
        text: root.messageText
        color: Theme.textPrimary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeNormal
    }
    footer: Rectangle {
        implicitHeight: 58
        color: "transparent"
        RowLayout {
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacing16
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacing8
            StandardButton {
                visible: root.confirmation
                text: root.rejectText
                type: "Text"
                onClicked: root.reject()
            }
            StandardButton {
                text: root.acceptText
                type: "Primary"
                onClicked: root.accept()
            }
        }
    }
}
