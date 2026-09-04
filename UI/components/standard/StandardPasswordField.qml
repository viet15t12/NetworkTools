pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// Password input with the same field contract as StandardTextField.
// Passwords are always masked by default; the trailing action only changes
// presentation and never mutates the stored text.
ColumnLayout {
    id: root
    spacing: Theme.spacing4
    Layout.minimumWidth: Theme.inputMinimumWidth

    property string labelText: ""
    property color labelColor: Theme.textSecondary
    property color textColor: Theme.textPrimary
    property color placeholderColor: Theme.placeholderTextColor
    property color backgroundColor: Theme.inputBackground
    property color borderColor: Theme.inputBorderColor
    property color focusBorderColor: Theme.inputBorderFocusColor
    property bool passwordVisible: false
    property int inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText

    property alias text: inputField.text
    property alias placeholderText: inputField.placeholderText
    property alias readOnly: inputField.readOnly
    property alias validator: inputField.validator
    property alias inputActiveFocus: inputField.activeFocus
    property alias acceptableInput: inputField.acceptableInput
    property alias selectedText: inputField.selectedText
    property alias selectionStart: inputField.selectionStart
    property alias selectionEnd: inputField.selectionEnd
    property alias cursorPosition: inputField.cursorPosition
    property alias displayText: inputField.displayText
    property alias horizontalAlignment: inputField.horizontalAlignment

    signal accepted()
    signal editingFinished()
    signal textEdited(string text)

    function forceActiveFocus() { inputField.forceActiveFocus() }
    function selectAll() { inputField.selectAll() }
    function clear() { inputField.clear() }
    function togglePasswordVisibility() {
        const savedCursorPosition = inputField.cursorPosition
        root.passwordVisible = !root.passwordVisible
        inputField.forceActiveFocus()
        inputField.cursorPosition = Math.min(savedCursorPosition, inputField.length)
    }

    Text {
        visible: root.labelText !== ""
        text: root.labelText
        color: root.labelColor
        font.pixelSize: Theme.fontSizeSmall
        font.family: Theme.fontFamily
    }

    TextField {
        id: inputField
        objectName: "passwordInputField"
        Layout.fillWidth: true

        Accessible.role: Accessible.EditableText
        Accessible.name: root.labelText !== "" ? root.labelText : inputField.placeholderText
        Accessible.description: root.passwordVisible ? "Password is visible" : "Password is hidden"

        color: root.textColor
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily
        placeholderTextColor: root.placeholderColor
        selectionColor: Theme.selectionBackground
        selectedTextColor: Theme.selectionForeground
        echoMode: root.passwordVisible ? TextInput.Normal : TextInput.Password
        inputMethodHints: root.inputMethodHints
        opacity: (enabled && !readOnly) ? 1.0 : 0.6

        leftPadding: Theme.spacing12
        rightPadding: revealButton.visible
                      ? revealButton.width + Theme.spacing8
                      : Theme.spacing12

        background: Rectangle {
            color: root.backgroundColor
            border.color: inputField.activeFocus
                          ? root.focusBorderColor
                          : root.borderColor
            border.width: Theme.borderWidth
            radius: Theme.radiusSmall
        }

        IconButton {
            id: revealButton
            objectName: "passwordRevealButton"
            visible: inputField.enabled && !inputField.readOnly
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacing4
            anchors.verticalCenter: parent.verticalCenter
            buttonSize: 28
            iconSize: Theme.iconSizeSmall
            radius: Theme.radiusSmall
            iconSource: root.passwordVisible
                        ? AppAssets.actionVisibilityOff
                        : AppAssets.actionVisibilityOn
            tooltip: root.passwordVisible ? "Hide password" : "Show password"

            Accessible.role: Accessible.Button
            Accessible.name: tooltip
            Accessible.description: root.passwordVisible
                                    ? "Mask the password"
                                    : "Reveal the password"
            Accessible.onPressAction: root.togglePasswordVisibility()

            onClicked: root.togglePasswordVisibility()
        }

        onEditingFinished: root.editingFinished()
        onAccepted: root.accepted()
        onTextEdited: root.textEdited(inputField.text)
    }
}
