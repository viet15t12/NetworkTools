pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: root
    preferredWidth: 460
    implicitHeight: 238

    property string titleText: "Create folder"
    property string fieldLabel: "Name"
    property string acceptText: "Create"
    property alias value: nameField.text

    title: root.titleText
    closeTooltip: "Close " + root.titleText.toLowerCase()

    contentItem: ColumnLayout {
        spacing: Theme.spacing8
        StandardTextField {
            id: nameField
            Layout.fillWidth: true
            labelText: root.fieldLabel
            onAccepted: {
                if (text.trim() !== "")
                    root.accept()
            }
        }
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
                text: "Cancel"
                type: "Text"
                onClicked: root.reject()
            }
            StandardButton {
                text: root.acceptText
                type: "Primary"
                enabled: nameField.text.trim() !== ""
                onClicked: root.accept()
            }
        }
    }

    onOpened: {
        nameField.selectAll()
        nameField.forceActiveFocus()
    }
}
