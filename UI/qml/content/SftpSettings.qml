pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "sftpSettings"
    color: Theme.contentBackground
    property var backend: typeof sftpController !== "undefined" ? sftpController : null
    property string resultMessage: ""
    property bool resultOk: true
    property string securityMessage: ""
    property bool securityResultOk: true

    function syncFields() {
        if (!backend)
            return
        localField.text = backend.defaultLocalPath
        remoteField.text = backend.defaultRemotePath
        autoSavePasswordCheck.checked = backend.autoSavePasswords
    }

    FolderDialog {
        id: localFolderDialog
        title: "Choose default local SFTP directory"
        onAccepted: localField.text = selectedFolder.toString()
    }

    Connections {
        target: root.backend
        function onSettingsChanged() { root.syncFields() }
    }

    ScrollView {
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: parent.availableWidth
            spacing: Theme.spacing16

            Item { Layout.fillWidth: true; Layout.preferredHeight: Theme.spacing8 }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: Theme.spacing4
                Text {
                    text: "SFTP"
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeLarge
                    font.family: Theme.fontFamily
                    font.weight: Font.Bold
                }
                Text {
                    Layout.fillWidth: true
                    text: "Choose the initial directories used for new SFTP connections. Saved connections can keep their own local and remote directories."
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.preferredHeight: pathsLayout.implicitHeight + 24
                color: Theme.searchBackground2
                radius: Theme.borderRadius
                border.width: Theme.borderWidth
                border.color: Theme.borderColor

                ColumnLayout {
                    id: pathsLayout
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing12

                    Text {
                        text: "Default directories"
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.weight: Font.Medium
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        StandardTextField {
                            id: localField
                            Layout.fillWidth: true
                            labelText: "Local directory"
                            placeholderText: "Home directory"
                        }
                        StandardButton {
                            Layout.alignment: Qt.AlignBottom
                            text: "Browse"
                            icon.source: AppAssets.fileFolder
                            onClicked: localFolderDialog.open()
                        }
                    }
                    StandardTextField {
                        id: remoteField
                        Layout.fillWidth: true
                        labelText: "Remote directory"
                        placeholderText: "/"
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.resultMessage !== ""
                        text: root.resultMessage
                        color: root.resultOk ? Theme.alertSuccess : Theme.alertError
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Item { Layout.fillWidth: true }
                        StandardButton {
                            text: "Reset"
                            type: "Text"
                            enabled: root.backend !== null
                            onClicked: {
                                root.backend.resetDefaultPaths()
                                root.resultOk = true
                                root.resultMessage = "SFTP default paths reset."
                            }
                        }
                        StandardButton {
                            text: "Save"
                            type: "Primary"
                            icon.source: AppAssets.actionSave
                            enabled: root.backend !== null
                            onClicked: {
                                const result = root.backend.setDefaultPaths(
                                    localField.text,
                                    remoteField.text
                                )
                                root.resultOk = result && result.ok === true
                                root.resultMessage = result && result.message
                                    ? String(result.message) : "Unable to save SFTP paths."
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.preferredHeight: securityLayout.implicitHeight + 24
                color: Theme.alertWarningSubtle
                radius: Theme.borderRadius
                border.width: Theme.borderWidth
                border.color: Theme.alertWarning

                ColumnLayout {
                    id: securityLayout
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: "Password storage"
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.weight: Font.Medium
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Not recommended: saved credentials can still be used "
                              + "by malicious software running as your Windows user. "
                              + "Prefer private keys and an SSH agent."
                        color: Theme.alertWarning
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        wrapMode: Text.WordWrap
                    }
                    StandardCheckBox {
                        id: autoSavePasswordCheck
                        objectName: "sftpAutoSavePasswordCheck"
                        text: "Automatically save passwords after successful connections"
                        enabled: root.backend !== null
                                 && root.backend.passwordStorageAvailable
                        onToggled: {
                            if (!root.backend)
                                return
                            const result = root.backend.setAutoSavePasswords(checked)
                            root.securityResultOk = result && result.ok === true
                            root.securityMessage = result && result.message
                                ? String(result.message)
                                : "Unable to change password storage setting."
                            if (!root.securityResultOk)
                                checked = root.backend.autoSavePasswords
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.backend && root.backend.passwordStorageAvailable
                              ? "Off by default. Passwords are protected with Windows "
                                + "DPAPI for the current user and are never stored in "
                                + "the saved-connections JSON."
                              : "Secure password storage is unavailable on this system."
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        wrapMode: Text.WordWrap
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.securityMessage !== ""
                        text: root.securityMessage
                        color: root.securityResultOk
                               ? Theme.alertSuccess : Theme.alertError
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        wrapMode: Text.WordWrap
                    }
                }
            }
            Item { Layout.fillWidth: true; Layout.preferredHeight: Theme.spacing8 }
        }
    }

    Component.onCompleted: syncFields()
}
