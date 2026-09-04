pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: root
    preferredWidth: 520
    implicitHeight: 300
    title: "Source Interface Required"
    subtitle: root.targetHost
    closeTooltip: "Close source interface dialog"

    property string targetHost: ""
    property string reasonText: ""
    signal pushRequested(string host, string sourceInterface)

    function openFor(host, reason) {
        targetHost = host
        reasonText = reason
        interfaceField.text = ""
        validationText.text = ""
        open()
        Qt.callLater(interfaceField.forceActiveFocus)
    }

    function submit() {
        const value = interfaceField.text.trim()
        if (!/^[A-Za-z][A-Za-z0-9./:_-]{0,63}$/.test(value)) {
            validationText.text = "Enter a valid Cisco interface, for example GigabitEthernet0/0 or Loopback0."
            return
        }
        pushRequested(targetHost, value)
        close()
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacing12
        Text {
            Layout.fillWidth: true
            text: root.reasonText
            color: Theme.textSecondary
            wrapMode: Text.WordWrap
            font.family: Theme.fontFamily
        }
        Text {
            Layout.fillWidth: true
            text: "Device: " + root.targetHost
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.bold: true
        }
        StandardTextField {
            id: interfaceField
            Layout.fillWidth: true
            labelText: "Cisco source interface"
            placeholderText: "GigabitEthernet0/0"
            onAccepted: root.submit()
        }
        Text {
            id: validationText
            Layout.fillWidth: true
            color: Theme.alertError
            wrapMode: Text.WordWrap
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
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
            StandardButton { text: "Cancel"; type: "Text"; onClicked: root.close() }
            StandardButton {
                text: "Apply Configuration"
                type: "Primary"
                icon.source: AppAssets.actionPush
                onClicked: root.submit()
            }
        }
    }
}
