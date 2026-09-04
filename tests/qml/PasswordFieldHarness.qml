import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 420
    height: 160
    visible: true

    readonly property bool passwordVisible: passwordField.passwordVisible
    readonly property string displayText: passwordField.displayText
    readonly property int cursorPosition: passwordField.cursorPosition
    readonly property bool inputHasFocus: passwordField.inputActiveFocus

    function togglePassword() {
        passwordField.togglePasswordVisibility()
    }

    StandardPasswordField {
        id: passwordField
        objectName: "testPasswordField"
        anchors.centerIn: parent
        width: 280
        labelText: "Password"
        placeholderText: "Enter password"
    }

    Component.onCompleted: {
        passwordField.text = "secret-value"
        passwordField.forceActiveFocus()
        passwordField.cursorPosition = 4
    }
}
