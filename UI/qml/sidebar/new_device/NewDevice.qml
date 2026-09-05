pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Effects
import UI

Window {
    id: addDeviceWindow
    width: 480; height: 620
    minimumWidth: 480; maximumWidth: 480
    minimumHeight: 620; maximumHeight: 620
    color: "transparent"
    modality: Qt.ApplicationModal
    flags: Qt.Dialog | Qt.FramelessWindowHint

    onVisibleChanged: {
        if (!visible) {
            UiState.windowLock = false
            escPressCount = 0
        }
    }

    onClosing: (close) => {
        UiState.windowLock = false
        escPressCount = 0
    }

    property bool isEditMode: false
    property var editDeviceData: null
    property int escPressCount: 0
    property var osOptions: ["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa", "mikrotik_routeros"]
    property var roleOptions: ["rou", "sw2", "sw3"]
    property bool sshTestRunning: false

    signal deviceAdded(var deviceData)
    signal deviceEdited(var originalIp, var deviceData)

    Connections {
        target: typeof dbManager !== "undefined" ? dbManager : null
        function onSshTestFinished(host, ok, message, diagnostic) {
            if (String(host) !== hostInput.text.trim())
                return
            addDeviceWindow.sshTestRunning = false
            const detail = diagnostic
                    ? "\nCode: " + String(diagnostic.code || "")
                      + "\nPython " + String(diagnostic.python || "")
                      + " · Paramiko " + String(diagnostic.paramiko || "")
                      + " · Netmiko " + String(diagnostic.netmiko || "")
                    : ""
            errorDialog.isError = !ok
            errorDialog.messageText = String(message || "") + detail
            errorDialog.openAlert()
        }
    }

    CustomAlert {
        id: errorDialog
        titleText: "Error"
        isError: true
    }

    // ── ESC TIMER ─────────────────────────────────────────
    Timer {
        id: escResetTimer
        interval: 250
        repeat: false
        onTriggered: escPressCount = 0
    }

    // ── HELPERS ───────────────────────────────────────────
    function isAnyDialogOpen() {
        return errorDialog.visible || sshCompatibilityDialog.opened
    }

    function comboIndex(options, value, fallbackIndex) {
        const idx = options.indexOf(value || "")
        return idx >= 0 ? idx : fallbackIndex
    }
    function handleEnterAction() {
        if (errorDialog.visible) {
            errorDialog.accepted()
            errorDialog.close()
            return
        }

        if (sshCompatibilityDialog.opened)
            return

        if (addDeviceWindow.visible && addButton.enabled) {
            addDeviceWindow.submit()
        }
    }

    function handleEscapeAction() {
        if (errorDialog.visible) {
            errorDialog.close()
            return
        }

        if (sshCompatibilityDialog.opened) {
            sshCompatibilityDialog.close()
            return
        }

        if (!addDeviceWindow.visible)
            return

        escPressCount++

        if (escPressCount >= 2) {
            escPressCount = 0
            escResetTimer.stop()
            addDeviceWindow.close()
            return
        }

        escResetTimer.restart()
    }

    // ── SHORTCUTS ──
    Shortcut {
        sequence: "Return"
        onActivated: addDeviceWindow.handleEnterAction()
    }

    Shortcut {
        sequence: "Enter"
        onActivated: addDeviceWindow.handleEnterAction()
    }

    Shortcut {
        sequence: "Escape"
        onActivated: addDeviceWindow.handleEscapeAction()
    }

    // ── INIT ──
    function resetAndOpen(editMode, data) {
        isEditMode = editMode
        editDeviceData = data

        if (isEditMode && editDeviceData) {
            nameInput.text  = editDeviceData.name || ""
            hostInput.text  = editDeviceData.ip || ""
            portInput.text  = editDeviceData.port || "22"
            userField.text  = editDeviceData.user || ""
            passField.text  = editDeviceData.pass || ""
            osCombo.currentIndex = comboIndex(osOptions, editDeviceData.os || "cisco_ios", 0)
            roleCombo.currentIndex = comboIndex(roleOptions, editDeviceData.role || "rou", 0)

            const protocols = ["SSH", "TELNET", "NETCONF", "RESTCONF"]
            const idx = protocols.indexOf(editDeviceData.protocol || "SSH")
            if (idx !== -1)
                protocolCombo.currentIndex = idx
            const ssh = dbManager.getSshAlgorithmSettings(editDeviceData.ip)
            kexField.text = ssh.kex_algorithms || ""
            hostKeyField.text = ssh.host_key_algorithms || ""
            cipherField.text = ssh.ciphers || ""
            macField.text = ssh.macs || ""
            sshNoteField.text = ssh.note || ""
        } else {
            nameInput.text = ""
            hostInput.text = ""
            portInput.text = "22"
            userField.text = ""
            passField.text = ""
            protocolCombo.currentIndex = 0
            osCombo.currentIndex = 0
            roleCombo.currentIndex = 0
            kexField.text = ""
            hostKeyField.text = ""
            cipherField.text = ""
            macField.text = ""
            sshNoteField.text = ""
        }

        escPressCount = 0
        escResetTimer.stop()

        x = Screen.width / 2 - width / 2
        y = Screen.height / 2 - height / 2
        addDeviceWindow.show()

        hostInput.forceActiveFocus()
    }

    // ── VALIDATION ────────────────────────────────────────────────
    function validate() {
        const reDomain   = /^(?=.{1,253}$)(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/i
        const reIPv4     = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/
        const reUsername = /^[A-Za-z0-9_.-]+$/
        const rePass     = /^[^\s]+$/

        const host = hostInput.text.trim()
        const isDomain = reDomain.test(host)
        const isIPv4 = reIPv4.test(host)

        if (!isDomain && !isIPv4) {
            errorDialog.messageText = "Host must be a valid domain name or IPv4 address."
            errorDialog.openAlert()
            hostInput.text = ""
            hostInput.forceActiveFocus()
            return false
        }

        if (isIPv4) {
            const octets = host.split(".").map(Number)
            const isPrivateIPv4 =
                octets[0] === 10 ||
                (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) ||
                (octets[0] === 192 && octets[1] === 168)

            if (!isPrivateIPv4) {
                errorDialog.messageText = "IPv4 address must be private (10.x.x.x, 172.16-31.x.x, 192.168.x.x)."
                errorDialog.openAlert()
                hostInput.forceActiveFocus()
                return false
            }
        }

        if (userField.text !== "" && !reUsername.test(userField.text)) {
            errorDialog.messageText = "Invalid username."
            errorDialog.openAlert()
            userField.forceActiveFocus()
            return false
        }

        if (passField.text !== "" && !rePass.test(passField.text)) {
            errorDialog.messageText = "Invalid password."
            errorDialog.openAlert()
            passField.forceActiveFocus()
            return false
        }
        return true
    }

    // ── SUBMIT ──
    function submit() {
        if (!validate())
            return
        const ok = isEditMode
            ? dbManager.updateDevice(
                hostInput.text.trim(), nameInput.text,
                protocolCombo.currentText, portInput.text,
                userField.text, passField.text,
                osCombo.currentText, roleCombo.currentText, deviceTypeForRole(roleCombo.currentText)
            )
            : dbManager.addDevice(
                hostInput.text.trim(), nameInput.text,
                protocolCombo.currentText, portInput.text,
                userField.text, passField.text,
                osCombo.currentText, roleCombo.currentText, deviceTypeForRole(roleCombo.currentText)
            )
        if (ok) {
            const sshResult = dbManager.saveSshAlgorithmSettings(
                hostInput.text.trim(), {
                    kex_algorithms: kexField.text,
                    host_key_algorithms: hostKeyField.text,
                    ciphers: cipherField.text,
                    macs: macField.text,
                    note: sshNoteField.text
                })
            if (!sshResult.ok) {
                errorDialog.messageText = "Device saved, but SSH compatibility settings failed:\n"
                        + String(sshResult.message || "")
                errorDialog.openAlert()
                return
            }
            const foldersOk = true
            const newDeviceObj = {
                ip:       hostInput.text.trim(),
                name:     nameInput.text,
                protocol: protocolCombo.currentText,
                port:     portInput.text,
                user:     userField.text,
                pass:     passField.text,
                os:       osCombo.currentText,
                role:     roleCombo.currentText,
                status:   "disconnected",
                type:     deviceTypeForRole(roleCombo.currentText)
            }

            if (isEditMode)
                addDeviceWindow.deviceEdited(editDeviceData.ip, newDeviceObj)
            else
                addDeviceWindow.deviceAdded(newDeviceObj)

            let msg = isEditMode ? "Device updated successfully:\n" : "Device added successfully:\n"
            msg += hostInput.text
            if (!foldersOk) {
                msg += "\nBackup folder creation failed."
            }
            if (typeof statusBar !== "undefined") {
                statusBar.showMessage(msg, "success")
            }
            addDeviceWindow.close()
        } else {
            errorDialog.messageText = isEditMode
                ? "Could not update device:\n" + hostInput.text
                : "Device already exists in the database:\n" + hostInput.text
            errorDialog.openAlert()
        }
    }

    function deviceTypeForRole(role) {
        return String(role) === "rou" ? "router" : String(role)
    }

    // ── UI ──
    Rectangle {
        id: mainContent
        anchors.fill: parent
        anchors.margins: 10
        color: Theme.contentBackground
        border.color: addDeviceWindow.active ? Theme.borderColor2 : Theme.textDisabled
        border.width: 1
        radius: 8

        DragHandler {
            onActiveChanged: if (active) addDeviceWindow.startSystemMove()
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16

            DialogTitleBar {
                Layout.fillWidth: true
                Layout.bottomMargin: 4
                title: isEditMode ? "Edit Device" : "Add New Device"
                closeTooltip: "Close device form"
                onCloseRequested: addDeviceWindow.close()
            }

            DeviceFormInput {
                id: hostInput
                labelText: "Host:"
                placeholder: "IP or Domain (192.168.1.1)"
                readOnly: isEditMode
                validator: RegularExpressionValidator { regularExpression: /^[^\s]+$/ }
            }

            DeviceFormInput {
                id: nameInput
                labelText: "Device Name:"
                placeholder: "Core-Switch-01"
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "Protocol:"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeNormal
                    font.family: Theme.fontFamily
                    Layout.preferredWidth: 100
                }

                ProtocolComboBox {
                    id: protocolCombo
                    isEditMode: addDeviceWindow.isEditMode
                    onPortAutoChanged: (newPort) => { portInput.text = newPort }
                }

                Text {
                    text: "Port:"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeNormal
                    font.family: Theme.fontFamily
                    Layout.leftMargin: 8
                }

                StandardTextField {
                    id: portInput
                    text: "22"
                    Layout.preferredWidth: 50
                    horizontalAlignment: Text.AlignHCenter
                    validator: IntValidator {
                        bottom: 1
                        top: 65535
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "OS:"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeNormal
                    font.family: Theme.fontFamily
                    Layout.preferredWidth: 100
                }

                StandardComboBox {
                    id: osCombo
                    Layout.fillWidth: true
                    model: addDeviceWindow.osOptions
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "Role:"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeNormal
                    font.family: Theme.fontFamily
                    Layout.preferredWidth: 100
                }

                StandardComboBox {
                    id: roleCombo
                    Layout.fillWidth: true
                    model: addDeviceWindow.roleOptions
                }
            }

            DeviceFormInput {
                id: userField
                labelText: "Username:"
                placeholder: "admin"
                validator: RegularExpressionValidator { regularExpression: /^[^\s]+$/ }
            }

            StandardPasswordField {
                id: passField
                labelText: "Password:"
                placeholderText: "••••••••"
                validator: RegularExpressionValidator { regularExpression: /^[^\s]+$/ }
            }

            StandardButton {
                Layout.fillWidth: true
                text: "SSH Compatibility — Legacy devices only"
                type: "Secondary"
                enabled: protocolCombo.currentText === "SSH"
                onClicked: sshCompatibilityDialog.open()
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                StandardButton {
                    Layout.preferredWidth: 90
                    Layout.preferredHeight: 32
                    text: "Cancel"
                    type: "Text"
                    onClicked: addDeviceWindow.close()
                }

                StandardButton {
                    id: addButton
                    Layout.preferredWidth: isEditMode ? 170 : 120
                    Layout.preferredHeight: 32
                    text: isEditMode ? "Save Changes" : "Add Device"
                    icon.source: isEditMode
                                 ? AppAssets.actionSave
                                 : ""
                    type: "Primary"

                    property bool canAdd: hostInput.text.trim().length > 0

                    enabled: canAdd
                    opacity: canAdd ? 1.0 : 0.6
                    onClicked: addDeviceWindow.submit()
                }
            }
        }
    }

    StandardDialog {
        id: sshCompatibilityDialog
        preferredWidth: 440
        implicitHeight: 455
        title: "SSH Compatibility"
        subtitle: "Legacy devices only · Per-device overrides"
        closeTooltip: "Close SSH compatibility settings"
        lockApplication: false

        onOpened: Qt.callLater(kexField.forceActiveFocus)

        contentItem: GridLayout {
            columns: 2
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing12

            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                text: "Warning: legacy algorithms weaken SSH security. Add only algorithms required by this device; values are comma-separated."
                wrapMode: Text.WordWrap
                color: Theme.alertWarning
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
            }

            StandardTextField {
                id: kexField
                Layout.fillWidth: true
                labelText: "Key exchange algorithms"
                placeholderText: "diffie-hellman-group14-sha1"
            }

            StandardTextField {
                id: hostKeyField
                Layout.fillWidth: true
                labelText: "Host key algorithms"
                placeholderText: "ssh-rsa"
            }

            StandardTextField {
                id: cipherField
                Layout.fillWidth: true
                labelText: "Ciphers"
                placeholderText: "aes128-cbc"
            }

            StandardTextField {
                id: macField
                Layout.fillWidth: true
                labelText: "MAC algorithms"
                placeholderText: "hmac-sha1"
            }

            StandardTextField {
                id: sshNoteField
                Layout.columnSpan: 2
                Layout.fillWidth: true
                labelText: "Note"
                placeholderText: "Reason for this override"
            }
        }

        footer: Item {
            implicitHeight: 58

            RowLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: Theme.spacing16
                anchors.rightMargin: Theme.spacing16
                spacing: Theme.spacing8

                StandardButton {
                    text: "Reset to default"
                    type: "Text"
                    onClicked: {
                        kexField.text = ""
                        hostKeyField.text = ""
                        cipherField.text = ""
                        macField.text = ""
                        sshNoteField.text = ""
                        if (addDeviceWindow.isEditMode)
                            dbManager.resetSshAlgorithmSettings(hostInput.text.trim())
                    }
                }

                Item { Layout.fillWidth: true }

                StandardButton {
                    text: "Close"
                    type: "Text"
                    onClicked: sshCompatibilityDialog.close()
                }

                StandardButton {
                    text: addDeviceWindow.sshTestRunning ? "Testing SSH..." : "Test SSH"
                    type: "Secondary"
                    enabled: addDeviceWindow.isEditMode && !addDeviceWindow.sshTestRunning
                    onClicked: {
                        const saved = dbManager.saveSshAlgorithmSettings(hostInput.text.trim(), {
                            kex_algorithms: kexField.text,
                            host_key_algorithms: hostKeyField.text,
                            ciphers: cipherField.text,
                            macs: macField.text,
                            note: sshNoteField.text
                        })
                        if (!saved.ok) {
                            errorDialog.isError = true
                            errorDialog.messageText = saved.message
                            errorDialog.openAlert()
                            return
                        }
                        addDeviceWindow.sshTestRunning = dbManager.testDeviceSshAsync(
                                    hostInput.text.trim())
                    }
                }
            }
        }
    }

    // ── Hiệu ứng bóng đổ ─────────────────────────────────────────────
    MultiEffect {
        source: mainContent
        anchors.fill: mainContent
        shadowEnabled: true
        shadowColor: Theme.shadowColor
        shadowBlur: 0.8
        shadowHorizontalOffset: 0
        shadowVerticalOffset: 4
    }
}
