pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

RowLayout {
    id: root
    property string rowNextHop: ""
    property bool rowCanEdit: true
    property int rowRouteId: 0
    property string rowSyncStatus: StatusValues.pendingApply
    signal nextHopChanged(string value)
    signal changeClicked()
    signal cancelClicked()
    signal deleteClicked()
    signal accepted()
    spacing: Theme.spacing8

    Text {
        text: "ip route 0.0.0.0 0.0.0.0"
        color: Theme.textSecondary
        font.pixelSize: Theme.fontSizeSmall
        font.family: Theme.fontFamily
    }

    StandardNetworkField {
        Layout.fillWidth: true
        inputKind: "ipv4"
        placeholderText: "Next-hop IP"
        text: root.rowNextHop
        readOnly: !root.rowCanEdit
        onTextEdited: function(value) { root.nextHopChanged(value) }
        onAccepted: root.accepted()
    }

    StatusIcon {
        visible: !root.rowCanEdit && root.rowRouteId > 0
        statusType: root.rowSyncStatus === StatusValues.synchronizedValue ? "success" : "warning"
    }
    StandardButton {
        visible: !root.rowCanEdit
        text: "Change"
        type: "Secondary"
        onClicked: root.changeClicked()
    }
    StandardButton {
        visible: root.rowCanEdit
        text: "Cancel"
        type: "Text"
        onClicked: root.cancelClicked()
    }
    StandardButton {
        text: "Delete"
        type: "Danger"
        onClicked: root.deleteClicked()
    }
}
