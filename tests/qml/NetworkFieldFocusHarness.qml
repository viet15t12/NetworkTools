import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

ApplicationWindow {
    id: root
    width: 520
    height: 220
    visible: true

    readonly property string subnetText: subnetField.text
    readonly property string wildcardText: wildcardField.text

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        StandardNetworkField {
            id: subnetField
            objectName: "networkFocusSubnetField"
            Layout.fillWidth: true
            inputKind: "subnet"
            labelText: "Subnet Mask"
        }

        StandardNetworkField {
            id: wildcardField
            objectName: "networkFocusWildcardField"
            Layout.fillWidth: true
            inputKind: "wildcard"
            labelText: "Wildcard"
        }

        StandardTextField {
            id: nextField
            objectName: "networkFocusNextField"
            Layout.fillWidth: true
            labelText: "Next field"
        }
    }
}
