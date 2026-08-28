pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Effects
import UI

Window {
    id: batchWindow
    width: 1280; height: 700
    minimumWidth: 1080; maximumWidth: 1440
    minimumHeight: 620; maximumHeight: 820
    color: "transparent"
    modality: Qt.ApplicationModal
    flags: Qt.Dialog | Qt.FramelessWindowHint

    property int escPressCount: 0
    readonly property var protocolOptions: ["SSH", "TELNET", "NETCONF", "RESTCONF"]
    readonly property var osOptions: ["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa", "mikrotik_routeros"]
    readonly property var roleOptions: ["rou", "sw2", "sw3"]
    readonly property int tableColumnSpacing: 6
    readonly property int indexColumnWidth: 34
    readonly property int hostColumnWidth: 154
    readonly property int nameColumnWidth: 120
    readonly property int protocolColumnWidth: 106
    readonly property int portColumnWidth: 58
    readonly property int osColumnWidth: 138
    readonly property int roleColumnWidth: 76
    readonly property int usernameColumnWidth: 110
    readonly property int passwordColumnWidth: 110
    readonly property int actionColumnWidth: 34
    readonly property string defaultOs: "cisco_ios"
    readonly property string defaultRole: "rou"
    readonly property string sampleFileName: "Template_NetworkTools-MultipleDevices.xlsx"
    property int rowRevision: 0
    property string formMessage: ""
    property string formSeverity: "info"
    readonly property int inputRowCount: {
        rowRevision
        let count = 0
        for (let i = 0; i < rowModel.count; ++i) {
            const row = rowModel.get(i)
            if ((row.host || "").trim() !== "" || (row.name || "").trim() !== "")
                ++count
        }
        return count
    }

    signal devicesAdded(var addedDevices, int totalRows, int skipped, bool foldersOk)

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

    CustomAlert {
        id: errorDialog
        titleText: "Error"
        isError: true
    }

    Timer {
        id: escResetTimer
        interval: 500
        repeat: false
        onTriggered: escPressCount = 0
    }

    ListModel { id: rowModel }

    FileDialog {
        id: importDialog
        title: "Import Devices"
        nameFilters: ["Excel workbook (*.xlsx)", "JSON file (*.json)"]
        onAccepted: batchWindow.importDevices(selectedFile)
    }

    FileDialog {
        id: sampleSaveDialog
        title: "Save Sample Excel"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "xlsx"
        nameFilters: ["Excel workbook (*.xlsx)"]
        selectedFile: batchWindow.sampleFileName
        onAccepted: batchWindow.saveSampleFile(selectedFile)
    }

    function protocolIndex(protocol) {
        const idx = protocolOptions.indexOf((protocol || "SSH").toUpperCase())
        return idx >= 0 ? idx : 0
    }

    function comboIndex(options, value, fallbackIndex) {
        const idx = options.indexOf(value || "")
        return idx >= 0 ? idx : fallbackIndex
    }
    function defaultPortForProtocol(protocol) {
        const value = (protocol || "SSH").toUpperCase()
        if (value === "TELNET")
            return "23"
        if (value === "NETCONF")
            return "830"
        if (value === "RESTCONF")
            return "443"
        return "22"
    }

    function resetAndOpen() {
        initRows(1)
        escPressCount = 0
        escResetTimer.stop()

        x = Screen.width / 2 - width / 2
        y = Screen.height / 2 - height / 2
        batchWindow.show()
    }

    function initRows(count) {
        rowModel.clear()
        for (let i = 0; i < count; i++) {
            rowModel.append({
                host: "",
                name: "",
                protocol: sharedProtocol.currentText || "SSH",
                port: sharedPort.text || "22",
                username: sharedUsername.text,
                password: sharedPassword.text,
                os: sharedOs.currentText || batchWindow.defaultOs,
                role: sharedRole.currentText || batchWindow.defaultRole
            })
        }
        touchRows()
    }

    function addEmptyRow() {
        rowModel.append({
            host: "",
            name: "",
            protocol: sharedProtocol.currentText || "SSH",
            port: sharedPort.text || "22",
            username: sharedUsername.text,
            password: sharedPassword.text,
            os: sharedOs.currentText || batchWindow.defaultOs,
            role: sharedRole.currentText || batchWindow.defaultRole
        })
        touchRows()
    }

    function clearRows() {
        initRows(1)
        formMessage = ""
    }

    function touchRows() {
        rowRevision++
        if (formSeverity === "error")
            formMessage = ""
    }

    function applySharedSettings() {
        for (let i = 0; i < rowModel.count; ++i) {
            rowModel.setProperty(i, "protocol", sharedProtocol.currentText)
            rowModel.setProperty(i, "port", sharedPort.text || defaultPortForProtocol(sharedProtocol.currentText))
            rowModel.setProperty(i, "os", sharedOs.currentText)
            rowModel.setProperty(i, "role", sharedRole.currentText)
            rowModel.setProperty(i, "username", sharedUsername.text)
            rowModel.setProperty(i, "password", sharedPassword.text)
        }
        formSeverity = "success"
        formMessage = "Shared settings applied to %1 row(s). You can still override any row below.".arg(rowModel.count)
        touchRows()
    }

    function removeRow(rowIndex) {
        if (rowModel.count <= 1) {
            rowModel.setProperty(rowIndex, "host", "")
            rowModel.setProperty(rowIndex, "name", "")
            rowModel.setProperty(rowIndex, "protocol", "SSH")
            rowModel.setProperty(rowIndex, "port", "22")
            rowModel.setProperty(rowIndex, "username", "")
            rowModel.setProperty(rowIndex, "password", "")
            rowModel.setProperty(rowIndex, "os", batchWindow.defaultOs)
            rowModel.setProperty(rowIndex, "role", batchWindow.defaultRole)
            return
        }

        rowModel.remove(rowIndex)
        touchRows()
    }

    function collectRows() {
        const rows = []

        for (let i = 0; i < rowModel.count; i++) {
            const r = rowModel.get(i)
            const line = {
                lineNumber: i + 1,
                host: (r.host || "").trim(),
                name: (r.name || "").trim(),
                protocol: (r.protocol || "SSH").trim(),
                port: (r.port || "").trim(),
                username: (r.username || "").trim(),
                password: (r.password || "").trim(),
                os: (r.os || batchWindow.defaultOs).trim(),
                role: (r.role || batchWindow.defaultRole).trim()
            }

            if (line.host === "" && line.name === "" && line.username === "" && line.password === "")
                continue

            rows.push(line)
        }

        return rows
    }

    function validateAndNormalize(row) {
        const reDomain = /^(?=.{1,253}$)(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/i
        const reIPv4 = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/
        const reUsername = /^[A-Za-z0-9_.-]+$/
        const rePass = /^[^\s]+$/

        const host = row.host
        const isDomain = reDomain.test(host)
        const isIPv4 = reIPv4.test(host)

        if (!host || (!isDomain && !isIPv4)) {
            return {
                ok: false,
                message: "Line %1: Host must be a valid domain name or IPv4 address.".arg(row.lineNumber)
            }
        }

        if (isIPv4) {
            const octets = host.split(".").map(Number)
            const isPrivateIPv4 =
                octets[0] === 10 ||
                (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) ||
                (octets[0] === 192 && octets[1] === 168)

            if (!isPrivateIPv4) {
                return {
                    ok: false,
                    message: "Line %1: IPv4 address must be private (10.x.x.x, 172.16-31.x.x, 192.168.x.x).".arg(row.lineNumber)
                }
            }
        }

        const protocol = row.protocol.toUpperCase()
        if (protocol !== "SSH" && protocol !== "TELNET" && protocol !== "NETCONF" && protocol !== "RESTCONF") {
            return {
                ok: false,
                message: "Line %1: Protocol must be SSH, TELNET, NETCONF, or RESTCONF.".arg(row.lineNumber)
            }
        }

        if (row.username !== "" && !reUsername.test(row.username)) {
            return {
                ok: false,
                message: "Line %1: Invalid username.".arg(row.lineNumber)
            }
        }

        if (row.password !== "" && !rePass.test(row.password)) {
            return {
                ok: false,
                message: "Line %1: Invalid password.".arg(row.lineNumber)
            }
        }

        let portNumber = Number(row.port)
        if (row.port === "")
            portNumber = Number(defaultPortForProtocol(protocol))

        if (!Number.isInteger(portNumber) || portNumber < 1 || portNumber > 65535) {
            return {
                ok: false,
                message: "Line %1: Port must be an integer in range 1-65535.".arg(row.lineNumber)
            }
        }

        return {
            ok: true,
            row: {
                host: host,
                name: row.name,
                protocol: protocol,
                port: String(portNumber),
                username: row.username,
                password: row.password,
                os: row.os || batchWindow.defaultOs,
                role: row.role || batchWindow.defaultRole
            }
        }
    }

    function importDevices(fileUrl) {
        const result = dbManager.importDevicesFromFile(String(fileUrl))
        batchWindow.handleImportResult(result)
    }

    function handleImportResult(result) {
        const message = result && result.message ? String(result.message) : "Import finished."
        if (result && result.ok) {
            batchWindow.devicesAdded([], result.added || 0, result.skipped || 0, result.foldersOk !== false)
            if (typeof statusBar !== "undefined") {
                statusBar.showMessage(message, "success")
            }
            batchWindow.close()
        } else {
            errorDialog.messageText = message
            errorDialog.openAlert()
        }
    }

    function saveSampleFile(fileUrl) {
        const result = dbManager.saveDeviceImportSample(String(fileUrl))
        const message = result && result.message ? String(result.message) : "Sample export finished."
        if (result && result.ok) {
            if (typeof statusBar !== "undefined") {
                statusBar.showMessage(message, "success")
            }
        } else {
            errorDialog.messageText = message
            errorDialog.openAlert()
        }
    }

    function submitBatch() {
        const rows = collectRows()
        if (rows.length === 0) {
            formSeverity = "warning"
            formMessage = "Enter at least one host before adding devices."
            return
        }

        const normalizedRows = []
        const seenHosts = ({})

        for (let i = 0; i < rows.length; i++) {
            const check = validateAndNormalize(rows[i])
            if (!check.ok) {
                formSeverity = "error"
                formMessage = check.message
                return
            }
            const normalizedHost = check.row.host.toLowerCase()
            if (seenHosts[normalizedHost]) {
                formSeverity = "error"
                formMessage = "Line %1 duplicates host %2 in this list.".arg(rows[i].lineNumber).arg(check.row.host)
                return
            }
            seenHosts[normalizedHost] = true
            normalizedRows.push(check.row)
        }

        const result = dbManager.addDevicesBatch(normalizedRows)
        const message = result && result.message ? String(result.message) : "Could not add devices."
        if (result && result.ok) {
            const added = result.devices || []
            const skipped = result.skipped || 0
            const foldersOk = result.foldersOk !== false
            batchWindow.devicesAdded(added, rows.length, skipped, foldersOk)
            if (typeof statusBar !== "undefined") {
                statusBar.showMessage(message, skipped > 0 ? "warning" : "success")
            }
            batchWindow.close()
        } else {
            formSeverity = "error"
            formMessage = message
        }
    }

    function handleEscapeAction() {
        if (errorDialog.visible) {
            errorDialog.close()
            return
        }

        if (!batchWindow.visible)
            return

        escPressCount++

        if (escPressCount >= 2) {
            escPressCount = 0
            escResetTimer.stop()
            batchWindow.close()
            return
        }

        escResetTimer.restart()
    }

    Shortcut {
        sequence: "Ctrl+Alt+N"
        onActivated: if (batchWindow.visible) batchWindow.submitBatch()
    }

    Shortcut {
        sequence: "Ctrl+Enter"
        onActivated: if (batchWindow.visible) batchWindow.submitBatch()
    }

    Shortcut {
        sequence: "Escape"
        onActivated: batchWindow.handleEscapeAction()
    }

    Rectangle {
        id: mainContent
        anchors.fill: parent
        anchors.margins: 10
        color: Theme.contentBackground
        border.color: batchWindow.active ? Theme.borderColor2 : Theme.textDisabled
        border.width: 1
        radius: 8

        DragHandler {
            onActiveChanged: if (active) batchWindow.startSystemMove()
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: Theme.spacing12

            DialogTitleBar {
                Layout.fillWidth: true
                title: "Add Multiple Devices"
                closeTooltip: "Close batch device form"
                onCloseRequested: batchWindow.close()
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing4

                    Text {
                        text: "Shared connection settings"
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeNormal
                        font.bold: true
                    }
                    Text {
                        text: "New rows inherit these values. Use Apply to all after changing settings for existing rows."
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    StandardComboBox {
                        id: sharedProtocol
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        labelText: "Protocol"
                        model: batchWindow.protocolOptions
                        onActivated: (selectedIndex) => sharedPort.text = batchWindow.defaultPortForProtocol(batchWindow.protocolOptions[selectedIndex])
                    }
                    StandardTextField {
                        id: sharedPort
                        Layout.preferredWidth: 76
                        Layout.minimumWidth: 60
                        labelText: "Port"
                        text: "22"
                        horizontalAlignment: Text.AlignHCenter
                    }
                    StandardComboBox {
                        id: sharedOs
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        labelText: "OS"
                        model: batchWindow.osOptions
                    }
                    StandardComboBox {
                        id: sharedRole
                        Layout.preferredWidth: 104
                        Layout.minimumWidth: 80
                        labelText: "Role"
                        model: batchWindow.roleOptions
                    }
                    StandardTextField {
                        id: sharedUsername
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        labelText: "Username"
                        placeholderText: "admin"
                    }
                    StandardPasswordField {
                        id: sharedPassword
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        labelText: "Password"
                        placeholderText: "Optional"
                    }
                    StandardButton {
                        Layout.alignment: Qt.AlignBottom
                        text: "Apply to all"
                        type: "Secondary"
                        onClicked: batchWindow.applySharedSettings()
                    }
                }
            }

            InlineMessage {
                Layout.fillWidth: true
                message: batchWindow.formMessage
                severity: batchWindow.formSeverity
            }

            DataTableFrame {
                Layout.fillWidth: true
                Layout.fillHeight: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: Theme.spacing8

                    DataTableHeader {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Theme.tableHeaderHeight

                        RowLayout {
                            anchors.fill: parent
                            spacing: batchWindow.tableColumnSpacing

                            DataTableCell { Layout.preferredWidth: batchWindow.indexColumnWidth; header: true; text: "#"; horizontalAlignment: Text.AlignHCenter }
                            DataTableCell { Layout.preferredWidth: batchWindow.hostColumnWidth; header: true; text: "Host *" }
                            DataTableCell { Layout.preferredWidth: batchWindow.nameColumnWidth; header: true; text: "Name" }
                            DataTableCell { Layout.preferredWidth: batchWindow.protocolColumnWidth; header: true; text: "Protocol" }
                            DataTableCell { Layout.preferredWidth: batchWindow.portColumnWidth; header: true; text: "Port"; horizontalAlignment: Text.AlignHCenter }
                            DataTableCell { Layout.preferredWidth: batchWindow.osColumnWidth; header: true; text: "OS" }
                            DataTableCell { Layout.preferredWidth: batchWindow.roleColumnWidth; header: true; text: "Role" }
                            DataTableCell { Layout.preferredWidth: batchWindow.usernameColumnWidth; header: true; text: "Username" }
                            DataTableCell { Layout.preferredWidth: batchWindow.passwordColumnWidth; header: true; text: "Password" }
                            DataTableCell { Layout.preferredWidth: batchWindow.actionColumnWidth; header: true; text: "" }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 0
                        model: rowModel

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                        }

                        delegate: DataTableRow {
                            required property int index
                            required property string host
                            required property string name
                            required property string protocol
                            required property string port
                            required property string username
                            required property string password
                            required property string os
                            required property string role

                            width: ListView.view.width
                            height: Theme.tableRowHeight + Theme.spacing4
                            rowIndex: index
                            interactive: false

                            RowLayout {
                                anchors.fill: parent
                                spacing: batchWindow.tableColumnSpacing

                                DataTableCell {
                                    Layout.preferredWidth: batchWindow.indexColumnWidth
                                    text: String(index + 1)
                                    horizontalAlignment: Text.AlignHCenter
                                }

                                StandardTextField {
                                    Layout.preferredWidth: batchWindow.hostColumnWidth
                                    Layout.minimumWidth: 0
                                    text: host
                                    placeholderText: "192.168.1.10"
                                    onTextChanged: rowModel.setProperty(index, "host", text)
                                    onTextEdited: batchWindow.touchRows()
                                }

                                StandardTextField {
                                    Layout.preferredWidth: batchWindow.nameColumnWidth
                                    Layout.minimumWidth: 0
                                    text: name
                                    placeholderText: "Core-R1"
                                    onTextChanged: rowModel.setProperty(index, "name", text)
                                    onTextEdited: batchWindow.touchRows()
                                }

                                StandardComboBox {
                                    Layout.preferredWidth: batchWindow.protocolColumnWidth
                                    Layout.minimumWidth: 0
                                    model: batchWindow.protocolOptions
                                    currentIndex: batchWindow.protocolIndex(protocol)
                                    onCurrentTextChanged: rowModel.setProperty(index, "protocol", currentText)
                                    onActivated: (selectedIndex) => {
                                        const selectedProtocol = batchWindow.protocolOptions[selectedIndex]
                                        rowModel.setProperty(index, "protocol", selectedProtocol)
                                        rowModel.setProperty(index, "port", batchWindow.defaultPortForProtocol(selectedProtocol))
                                        batchWindow.touchRows()
                                    }
                                }

                                StandardTextField {
                                    Layout.preferredWidth: batchWindow.portColumnWidth
                                    Layout.minimumWidth: 0
                                    text: port
                                    placeholderText: "22"
                                    horizontalAlignment: Text.AlignHCenter
                                    onTextChanged: rowModel.setProperty(index, "port", text)
                                    onTextEdited: batchWindow.touchRows()
                                }

                                StandardComboBox {
                                    Layout.preferredWidth: batchWindow.osColumnWidth
                                    Layout.minimumWidth: 0
                                    model: batchWindow.osOptions
                                    currentIndex: batchWindow.comboIndex(batchWindow.osOptions, os, 0)
                                    onCurrentTextChanged: rowModel.setProperty(index, "os", currentText)
                                    onActivated: batchWindow.touchRows()
                                }

                                StandardComboBox {
                                    Layout.preferredWidth: batchWindow.roleColumnWidth
                                    Layout.minimumWidth: 0
                                    model: batchWindow.roleOptions
                                    currentIndex: batchWindow.comboIndex(batchWindow.roleOptions, role, 0)
                                    onCurrentTextChanged: rowModel.setProperty(index, "role", currentText)
                                    onActivated: (selectedIndex) => {
                                        const selectedRole = batchWindow.roleOptions[selectedIndex]
                                        rowModel.setProperty(index, "role", selectedRole)
                                        batchWindow.touchRows()
                                    }
                                }

                                StandardTextField {
                                    Layout.preferredWidth: batchWindow.usernameColumnWidth
                                    Layout.minimumWidth: 0
                                    text: username
                                    placeholderText: "admin"
                                    onTextChanged: rowModel.setProperty(index, "username", text)
                                    onTextEdited: batchWindow.touchRows()
                                }

                                StandardPasswordField {
                                    Layout.preferredWidth: batchWindow.passwordColumnWidth
                                    Layout.minimumWidth: 0
                                    text: password
                                    placeholderText: "••••••••"
                                    onTextChanged: rowModel.setProperty(index, "password", text)
                                    onTextEdited: batchWindow.touchRows()
                                }

                                IconButton {
                                    Layout.preferredWidth: batchWindow.actionColumnWidth
                                    Layout.alignment: Qt.AlignVCenter
                                    buttonSize: 28
                                    iconSize: Theme.iconSizeSmall
                                    radius: Theme.radiusSmall
                                    iconSource: AppAssets.actionClose
                                    tooltip: "Remove row"
                                    danger: true
                                    enabled: rowModel.count > 1
                                    opacity: enabled ? 1.0 : 0.45
                                    onClicked: batchWindow.removeRow(index)
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing8

                StandardButton {
                    text: "Add another row"
                    type: "Secondary"
                    onClicked: addEmptyRow()
                }

                StandardButton {
                    text: "Clear"
                    type: "Secondary"
                    onClicked: clearRows()
                }

                StandardButton {
                    text: "Import file"
                    type: "Secondary"
                    onClicked: importDialog.open()
                }

                StandardButton {
                    text: "Download template"
                    type: "Secondary"
                    onClicked: {
                        sampleSaveDialog.selectedFile = batchWindow.sampleFileName
                        sampleSaveDialog.open()
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: batchWindow.inputRowCount === 0
                          ? "No devices entered"
                          : "%1 device%2 ready".arg(batchWindow.inputRowCount).arg(batchWindow.inputRowCount === 1 ? "" : "s")
                    color: batchWindow.inputRowCount > 0 ? Theme.textSecondary : Theme.textDisabled
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }

                StandardButton {
                    text: "Cancel"
                    type: "Text"
                    onClicked: batchWindow.close()
                }

                StandardButton {
                    id: addAllButton
                    text: batchWindow.inputRowCount > 0
                          ? "Add %1 device%2".arg(batchWindow.inputRowCount).arg(batchWindow.inputRowCount === 1 ? "" : "s")
                          : "Add devices"
                    type: "Primary"
                    enabled: batchWindow.inputRowCount > 0
                    onClicked: batchWindow.submitBatch()
                }
            }
        }
    }

    Component.onCompleted: initRows(1)

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
