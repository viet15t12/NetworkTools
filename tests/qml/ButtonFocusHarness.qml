import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

ApplicationWindow {
    id: root
    width: 360
    height: 120
    visible: true

    readonly property bool cancelVisualFocus: cancelButton.visualFocus
    readonly property real cancelBorderWidth: cancelButton.background.border.width
    readonly property color cancelBorderColor: cancelButton.background.border.color
    readonly property color accentColor: Theme.accentColor

    function focusCancelWithTabReason() {
        cancelButton.forceActiveFocus(Qt.TabFocusReason)
    }

    RowLayout {
        anchors.centerIn: parent

        StandardButton {
            id: cancelButton
            objectName: "testCancelChangesButton"
            text: "Cancel Changes"
            type: "Text"
        }

        StandardButton {
            text: "Save"
            type: "Primary"
        }
    }
}
