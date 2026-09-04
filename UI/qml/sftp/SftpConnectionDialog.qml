pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import UI

StandardDialog {
    id: root
    preferredWidth: 640
    height: Math.min(590, parent.height - Theme.spacing16 * 2)
    title: "Edit SFTP connection"
    subtitle: "Connection details and initial directories"
    closeTooltip: "Close connection editor"

    required property var backend
    property string profileId: ""
    // NOTE: chuc nang chua phat trien xong, khong tam quan tam nieu viet bao cao
    readonly property bool scpFeatureVisible: false

    function openFor(profile) {
        const value = profile || ({})
        profileId = String(value.id || "")
        nameField.text = String(value.name || "")
        hostField.text = String(value.host || "")
        portField.value = Number(value.port || 22)
        userField.text = String(value.username || "")
        passwordField.text = ""
        savePasswordCheck.checked = Boolean(value.passwordSaved)
        keyField.text = String(value.keyPath || "")
        localField.text = String(value.localPath || (backend ? backend.defaultLocalPath : ""))
        remoteField.text = String(value.remotePath || (backend ? backend.defaultRemotePath : "/"))
        modeCombo.currentIndex = scpFeatureVisible
                               && String(value.transferMode || "sftp").toLowerCase() === "scp"
                               ? 1 : 0
        open()
    }

    FileDialog {
        id: keyDialog
        title: "Select SSH private key"
        nameFilters: ["SSH keys (*.pem *.key *.ppk)", "All files (*)"]
        onAccepted: keyField.text = selectedFile.toString()
    }

    contentItem: ScrollView {
        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: parent.availableWidth
            spacing: Theme.spacing12

            Text {
                Layout.fillWidth: true
                text: "Saving a password is not recommended. Prefer a private key "
                      + "or SSH agent whenever possible."
                color: Theme.alertWarning
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                wrapMode: Text.WordWrap
            }
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: Theme.spacing8
                rowSpacing: Theme.spacing8

                StandardTextField {
                    id: nameField
                    objectName: "sftpProfileNameField"
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    labelText: "Display name"
                }
                StandardComboBox {
                    id: modeCombo
                    objectName: "sftpProfileTransferMode"
                    visible: root.scpFeatureVisible
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    labelText: "Transfer mode"
                    model: ["SFTP", "SCP"]
                    valueModel: ["sftp", "scp"]
                    currentIndex: 0
                }
                StandardTextField {
                    id: hostField
                    objectName: "sftpProfileHostField"
                    Layout.fillWidth: true
                    labelText: "Host / IP"
                }
                StandardSpinBox {
                    id: portField
                    Layout.preferredWidth: 150
                    labelText: "Port"
                    from: 1
                    to: 65535
                    value: 22
                    stepSize: 1
                    editable: true
                }
                StandardTextField {
                    id: userField
                    objectName: "sftpProfileUserField"
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    labelText: "Username"
                }
                StandardPasswordField {
                    id: passwordField
                    objectName: "sftpProfilePasswordField"
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    enabled: savePasswordCheck.checked
                    labelText: "Saved password"
                    placeholderText: savePasswordCheck.checked && root.profileId !== ""
                                     ? "Leave blank to keep the stored password"
                                     : "Password to protect"
                }
                StandardCheckBox {
                    id: savePasswordCheck
                    objectName: "sftpSavePasswordCheck"
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    text: "Save password for this connection (not recommended)"
                    enabled: root.backend && root.backend.passwordStorageAvailable
                    onToggled: {
                        if (!checked)
                            passwordField.text = ""
                    }
                }
                Text {
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    text: root.backend && root.backend.passwordStorageAvailable
                          ? "Protected for the current Windows user with DPAPI; "
                            + "the profile JSON never contains the password."
                          : "Secure password storage is unavailable on this system."
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    wrapMode: Text.WordWrap
                }
                StandardTextField {
                    id: keyField
                    Layout.fillWidth: true
                    labelText: "Private key (optional)"
                }
                StandardButton {
                    Layout.alignment: Qt.AlignBottom
                    text: "Browse"
                    icon.source: AppAssets.fileTypeKey
                    onClicked: keyDialog.open()
                }
                StandardTextField {
                    id: localField
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    labelText: "Initial local directory"
                }
                StandardTextField {
                    id: remoteField
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    labelText: "Initial remote directory (SFTP only)"
                    enabled: modeCombo.currentValue === "sftp"
                }
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
            StandardButton { text: "Cancel"; type: "Text"; onClicked: root.reject() }
            StandardButton {
                objectName: "sftpProfileSaveButton"
                text: "Save"
                type: "Primary"
                icon.source: AppAssets.actionSave
                enabled: hostField.text.trim() !== "" && userField.text.trim() !== ""
                onClicked: {
                    if (!root.backend)
                        return
                    root.backend.saveConnection(
                        root.profileId,
                        nameField.text,
                        hostField.text,
                        portField.value,
                        userField.text,
                        keyField.text,
                        localField.text,
                        remoteField.text,
                        passwordField.text,
                        savePasswordCheck.checked,
                        modeCombo.currentValue
                    )
                    root.accept()
                }
            }
        }
    }
}
