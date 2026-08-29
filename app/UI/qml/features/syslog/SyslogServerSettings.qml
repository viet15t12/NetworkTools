pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "syslogServerSettings"

    property string validationMessage: ""
    property bool validationOk: false
    readonly property var backend: typeof syslogSettings !== "undefined" && syslogSettings !== null
                                   ? syslogSettings : null
    readonly property var manager: typeof syslogManager !== "undefined" && syslogManager !== null
                                   ? syslogManager : null
    readonly property bool listenerActive: manager !== null
                                           && manager.listenerState === "listening"
    property var resetOptions: []
    property string resetHost: ""
    property int resetCount: 0

    color: Theme.contentBackground

    function validateSettings() {
        if (backend === null) {
            validationOk = false
            validationMessage = "System Logs settings backend is unavailable."
            return
        }
        const result = backend.validate()
        validationOk = Boolean(result.ok)
        validationMessage = String(result.message || "")
    }

    function restartListener() {
        if (manager === null)
            return
        const stopped = manager.stopServer()
        if (!stopped || !stopped.ok) {
            validationOk = false
            validationMessage = String(stopped && stopped.message
                                       ? stopped.message : "Could not stop the listener.")
            return
        }
        const started = manager.startServer()
        validationOk = Boolean(started && started.ok)
        validationMessage = String(started && started.message
                                   ? started.message : "Listener restart finished.")
    }

    function loadResetOptions() {
        if (manager === null)
            return
        const result = manager.getLogResetOptions()
        if (!result || !result.ok) {
            validationOk = false
            validationMessage = String(result && result.message
                                       ? result.message : "Could not load Syslog data summary.")
            return
        }
        resetOptions = result.options || []
        if (resetOptions.length > 0) {
            resetScope.currentIndex = 0
            resetHost = String(resetOptions[0].host || "")
            resetCount = Number(resetOptions[0].count || 0)
        }
    }

    function openResetConfirmation() {
        if (resetCount <= 0)
            return
        confirmationField.text = ""
        irreversibleCheck.checked = false
        resetDialog.open()
    }

    function performReset() {
        if (manager === null)
            return
        const result = manager.resetLogData(resetHost, confirmationField.text)
        validationOk = Boolean(result && result.ok)
        validationMessage = String(result && result.message
                                   ? result.message : "Syslog data reset failed.")
        if (result && result.ok) {
            resetDialog.close()
            loadResetOptions()
        }
    }

    ScrollView {
        id: settingsScroll
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: ScrollBar.AsNeeded

        ColumnLayout {
            width: settingsScroll.availableWidth
            spacing: Theme.spacing12

            Item { Layout.fillWidth: true; Layout.preferredHeight: Theme.spacing12 }

            WorkspaceHeader {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                title: "System Logs"
                subtitle: "Configure the local Syslog listener, the destination advertised to devices, and retention. Changes are saved automatically."
            }

            InlineMessage {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                severity: "info"
                message: "Settings controls how the collector listens and stores data. Use the System Logs workspace to start or stop normal collection, filter messages, and inspect logs."
            }

            Rectangle {
                visible: root.listenerActive
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                implicitHeight: restartRow.implicitHeight + Theme.spacing16
                color: Theme.alertWarningSubtle
                border.color: Theme.contentPanelBorder
                border.width: Theme.borderWidth
                radius: Theme.radiusSmall

                RowLayout {
                    id: restartRow
                    anchors.fill: parent
                    anchors.margins: Theme.spacing8
                    spacing: Theme.spacing8

                    Text {
                        Layout.fillWidth: true
                        text: "Listener is running. Restart it after changing listener or capacity settings."
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        elide: Text.ElideRight
                    }

                    StandardButton {
                        objectName: "syslogSettingsRestartButton"
                        text: "Restart Listener"
                        icon.source: AppAssets.actionRefresh
                        type: "Secondary"
                        onClicked: root.restartListener()
                    }
                }
            }

            FormSection {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                title: "Listener"
                helpText: "Start on launch: Automatically starts the local Syslog collector when NetworkTools opens.\n\nListener transports: The collector receives UDP and TCP simultaneously.\n\nListener port: Local destination port, from 1 to 65535. Devices must send to the same port.\n\nBind address: Local address used by the socket. 0.0.0.0 listens on every IPv4 interface. Restart the listener after changing the bind address or port."

                StandardCheckBox {
                    Layout.fillWidth: true
                    text: "Start the listener when NetworkTools starts"
                    enabled: root.backend !== null
                    checked: root.backend !== null ? root.backend.enabledOnStartup : false
                    onToggled: if (root.backend !== null) root.backend.enabledOnStartup = checked
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 680 ? 2 : 1
                    columnSpacing: Theme.spacing12
                    rowSpacing: Theme.spacing8

                    StandardTextField {
                        Layout.fillWidth: true
                        labelText: "Listener transports"
                        text: "UDP + TCP (simultaneous)"
                        readOnly: true
                    }

                    StandardSpinBox {
                        Layout.fillWidth: true
                        labelText: "Listener port"
                        from: 1
                        to: 65535
                        stepSize: 1
                        enabled: root.backend !== null
                        value: root.backend !== null ? root.backend.port : 5514
                        onValueChanged: {
                            if (root.backend !== null && root.backend.port !== value)
                                root.backend.port = value
                        }
                    }

                    StandardTextField {
                        Layout.fillWidth: true
                        labelText: "Bind address"
                        enabled: root.backend !== null
                        text: root.backend !== null ? root.backend.bindIp : "0.0.0.0"
                        placeholderText: "0.0.0.0"
                        onEditingFinished: if (root.backend !== null) root.backend.bindIp = text
                    }

                    Item { Layout.fillWidth: true; Layout.preferredHeight: 1 }
                }
            }

            FormSection {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                title: "Capacity and safety"
                helpText: "Maximum message size: Largest accepted UDP datagram or TCP Syslog frame in bytes. The practical default is 16384 bytes. Oversized messages are dropped to protect memory.\n\nMaximum TCP clients: Number of simultaneous TCP Syslog connections accepted by the collector. Keep 64 for a small or medium lab; increase only when many devices use TCP. Restart the listener after changing either value."

                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 680 ? 2 : 1
                    columnSpacing: Theme.spacing12
                    rowSpacing: Theme.spacing8

                    StandardSpinBox {
                        Layout.fillWidth: true
                        labelText: "Maximum message size (bytes)"
                        from: 1024
                        to: 1048576
                        stepSize: 1024
                        editable: true
                        enabled: root.backend !== null
                        value: root.backend !== null ? root.backend.maxMessageBytes : 16384
                        onValueChanged: {
                            if (root.backend !== null
                                    && root.backend.maxMessageBytes !== value)
                                root.backend.maxMessageBytes = value
                        }
                    }

                    StandardSpinBox {
                        Layout.fillWidth: true
                        labelText: "Maximum TCP clients"
                        from: 1
                        to: 4096
                        stepSize: 1
                        editable: true
                        enabled: root.backend !== null
                        value: root.backend !== null ? root.backend.maxTcpClients : 64
                        onValueChanged: {
                            if (root.backend !== null
                                    && root.backend.maxTcpClients !== value)
                                root.backend.maxTcpClients = value
                        }
                    }
                }
            }

            FormSection {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                title: "Device destination"
                helpText: "Advertised server address: Active IPv4 address that routers and switches can reach. This address is written into the Cisco logging host command. Do not choose 127.0.0.1 or an address that exists only on an isolated adapter.\n\nRefresh Addresses: Reloads active local IPv4 addresses after a network adapter, VPN, or lab bridge changes."

                Text {
                    Layout.fillWidth: true
                    text: "Choose an active local address that connected devices can reach. This address is used when NetworkTools pushes Syslog configuration."
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    StandardComboBox {
                        Layout.fillWidth: true
                        labelText: "Advertised server address"
                        enabled: root.backend !== null
                        model: root.backend !== null ? root.backend.availableAdvertisedIps : []
                        currentIndex: root.backend !== null
                                      ? root.backend.availableAdvertisedIps.indexOf(root.backend.advertisedIp)
                                      : -1
                        emptyText: "No active local IPv4 address"
                        emptyWarningText: "Connect a network adapter, then refresh the address list."
                        onActivated: if (root.backend !== null) root.backend.advertisedIp = currentText
                    }

                    StandardButton {
                        Layout.alignment: Qt.AlignBottom
                        text: "Refresh Addresses"
                        icon.source: AppAssets.actionRefresh
                        type: "Secondary"
                        enabled: root.backend !== null
                        onClicked: root.backend.refreshLocalIps()
                    }
                }
            }

            FormSection {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                title: "Storage"
                helpText: "Retention period: Number of days received Syslog messages remain in the information database. The minimum is 1 day and maximum is 3650 days. Expired rows are removed by retention maintenance; device Syslog configuration is not deleted."

                StandardSpinBox {
                    Layout.preferredWidth: 260
                    labelText: "Retention period (days)"
                    from: 1
                    to: 3650
                    stepSize: 1
                    enabled: root.backend !== null
                    value: root.backend !== null ? root.backend.retentionDays : 30
                    onValueChanged: {
                        if (root.backend !== null && root.backend.retentionDays !== value)
                            root.backend.retentionDays = value
                    }
                }
            }

            FormSection {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                title: "Reset log data"
                helpText: "Permanently delete received Syslog messages for one host or every host. Device Syslog configuration is not affected. Export an Excel backup first if the records may be needed later. Deletion requires both an acknowledgement and the exact confirmation phrase."

                InlineMessage {
                    Layout.fillWidth: true
                    severity: "warning"
                    message: "Deleted log data cannot be recovered. The listener is paused during deletion and restarted automatically."
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    StandardComboBox {
                        id: resetScope
                        objectName: "syslogResetScope"
                        Layout.fillWidth: true
                        labelText: "Data scope"
                        enabled: root.manager !== null && root.resetOptions.length > 0
                        model: root.resetOptions.map(function(row) { return String(row.label || "") })
                        valueModel: root.resetOptions.map(function(row) { return String(row.host || "") })
                        emptyText: "No Syslog messages"
                        onActivated: function(index) {
                            const option = root.resetOptions[index]
                            root.resetHost = option ? String(option.host || "") : ""
                            root.resetCount = option ? Number(option.count || 0) : 0
                        }
                    }

                    StandardButton {
                        objectName: "syslogResetExportButton"
                        Layout.alignment: Qt.AlignBottom
                        text: "Export Excel"
                        type: "Secondary"
                        enabled: root.manager !== null && root.resetCount > 0
                        onClicked: resetExportDialog.open()
                    }

                    StandardButton {
                        objectName: "syslogResetDataButton"
                        Layout.alignment: Qt.AlignBottom
                        text: "Reset Data"
                        type: "Danger"
                        enabled: root.manager !== null && root.resetCount > 0
                        onClicked: root.openResetConfirmation()
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacing24
                Layout.rightMargin: Theme.spacing24
                spacing: Theme.spacing12

                Rectangle {
                    visible: root.validationMessage !== ""
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    color: root.validationOk ? Theme.alertSuccessSubtle : Theme.alertErrorSubtle
                    border.color: Theme.contentPanelBorder
                    border.width: Theme.borderWidth
                    radius: Theme.radiusSmall

                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing12
                        anchors.rightMargin: Theme.spacing12
                        text: root.validationMessage
                        color: root.validationOk ? Theme.alertSuccess : Theme.alertError
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }

                Item {
                    visible: root.validationMessage === ""
                    Layout.fillWidth: true
                }

                StandardButton {
                    text: "Validate Settings"
                    type: "Primary"
                    enabled: root.backend !== null
                    onClicked: root.validateSettings()
                }
            }

            Item { Layout.fillWidth: true; Layout.preferredHeight: Theme.spacing24 }
        }
    }

    FileDialog {
        id: resetExportDialog
        title: root.resetHost === "" ? "Export All Syslog Logs Before Reset"
                                     : "Export Syslog Logs for " + root.resetHost
        fileMode: FileDialog.SaveFile
        defaultSuffix: "xlsx"
        nameFilters: ["Excel workbook (*.xlsx)"]
        onAccepted: {
            if (root.manager === null)
                return
            const result = root.manager.exportLogResetScope(selectedFile, root.resetHost)
            root.validationOk = Boolean(result && result.ok)
            root.validationMessage = String(result && result.message
                                            ? result.message : "Syslog export failed.")
        }
    }

    StandardDialog {
        id: resetDialog
        objectName: "syslogResetConfirmationDialog"
        preferredWidth: 520
        title: root.resetHost === "" ? "Delete all Syslog data?"
                                     : "Delete Syslog data for " + root.resetHost + "?"
        closeTooltip: "Cancel log data reset"

        readonly property string confirmationPhrase: root.resetHost === ""
                                                     ? "DELETE ALL SYSLOG DATA"
                                                     : "DELETE " + root.resetHost
        readonly property bool confirmed: irreversibleCheck.checked
                                          && confirmationField.text === confirmationPhrase

        contentItem: ColumnLayout {
            spacing: Theme.spacing12

            InlineMessage {
                Layout.fillWidth: true
                severity: "error"
                message: "This permanently deletes %1 messages. This action cannot be undone."
                         .arg(root.resetCount)
            }

            StandardCheckBox {
                id: irreversibleCheck
                objectName: "syslogResetAcknowledgement"
                Layout.fillWidth: true
                text: "I understand that the selected log data will be permanently deleted."
            }

            Text {
                Layout.fillWidth: true
                text: "Type “" + resetDialog.confirmationPhrase + "” to confirm:"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                wrapMode: Text.WordWrap
            }

            StandardTextField {
                id: confirmationField
                objectName: "syslogResetConfirmationField"
                Layout.fillWidth: true
                placeholderText: resetDialog.confirmationPhrase
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

                StandardButton {
                    text: "Cancel"
                    type: "Text"
                    onClicked: resetDialog.close()
                }
                StandardButton {
                    objectName: "syslogResetConfirmButton"
                    text: "Permanently Delete"
                    type: "Danger"
                    enabled: resetDialog.confirmed
                    onClicked: root.performReset()
                }
            }
        }
    }

    onVisibleChanged: {
        if (visible && backend !== null) {
            backend.refreshLocalIps()
            loadResetOptions()
        }
    }
}
