pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: root

    property string projectPath: ""
    property string errorMessage: ""

    signal unlockRequested(string password)

    title: LanguageState.text("Unlock Project")
    subtitle: projectPath
    preferredWidth: 520
    implicitHeight: errorMessage === "" ? 330 : 390

    onOpened: {
        errorMessage = ""
        passwordField.clear()
        passwordField.forceActiveFocus()
    }
    onClosed: passwordField.clear()

    contentItem: ColumnLayout {
        spacing: Theme.spacing16

        StandardPasswordField {
            id: passwordField
            objectName: "welcomeUnlockProjectPasswordField"
            Layout.fillWidth: true
            labelText: LanguageState.text("Project password")
            placeholderText: LanguageState.text("Enter the project password")
            onAccepted: if (unlockButton.enabled) unlockButton.clicked()
        }

        InlineMessage {
            Layout.fillWidth: true
            visible: root.errorMessage !== ""
            message: root.errorMessage
            severity: "warning"
        }

        InlineMessage {
            Layout.fillWidth: true
            visible: root.errorMessage === ""
            message: LanguageState.text("CAMS does not store project passwords.")
            severity: "info"
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            Item { Layout.fillWidth: true }

            StandardButton {
                text: LanguageState.text("Cancel")
                type: "Text"
                onClicked: root.reject()
            }

            StandardButton {
                id: unlockButton
                objectName: "welcomeUnlockProjectButton"
                text: LanguageState.text("Unlock")
                type: "Primary"
                enabled: passwordField.text.length > 0
                onClicked: {
                    root.errorMessage = ""
                    root.unlockRequested(passwordField.text)
                }
            }
        }
    }
}
