pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import UI

Rectangle {
    id: panelSideBar
    color: Theme.panelSideBarBackground
    implicitWidth: 0

    // ── 1. KẾT NỐI VỚI ACTIVITY BAR ───────────────────────────────────────────
    property string appMode: "devices"

    // ── 2. CẦU NỐI (PROXY) BẢO VỆ MAIN.QML KHÔNG BỊ LỖI ───────────────────────
    // Chuyển hướng mọi yêu cầu từ Main.qml thẳng vào DevicesPanel
    property alias allDevices: devicesPanel.allDevices
    property alias pythonDepsChecking: devicesPanel.pythonDepsChecking
    property alias pythonDepsStatus: devicesPanel.pythonDepsStatus
    property alias pythonDepsStatusText: devicesPanel.pythonDepsStatusText
    property alias pythonDepsStatusDetail: devicesPanel.pythonDepsStatusDetail
    property alias backendConnectRunning: devicesPanel.isConnectRunning
    property alias activeHost: devicesPanel.activeHost
    property alias selectedHosts: devicesPanel.selectedHosts
    property alias selectedHostList: devicesPanel.selectedHostList
    property bool hasActiveTabs: false // Main.qml đang truyền biến này vào

    signal deviceSelected(string ip, string name, string deviceType, string status)
    signal deviceActivated(string host, string name, string deviceType, string status)
    signal deviceSelectionChanged(var hosts)
    signal deviceDeleted(string ip)
    signal devicesLoaded(var devices)
    signal settingSelected(string key)
    signal databaseTableSelected(string tableName)
    signal syslogHostSelected(string host)
    signal syslogOperationFinished(bool ok, string message)

    function selectDeviceByIp(ip) { devicesPanel.selectDeviceByIp(ip) }
    function activateDevice(host) { devicesPanel.activateDevice(host) }
    function clearDeviceSelection() { devicesPanel.clearSelection() }
    function triggerPythonCheck() { devicesPanel.triggerPythonCheck() }
    function openNewDeviceWindow() { devicesPanel.openNewDeviceWindow() }
    function openBatchDeviceWindow() { devicesPanel.openBatchDeviceWindow() }
    function reloadDevices() { devicesPanel.reloadDevices() }
    function selectSyslogHost(host) { syslogPanel.selectedHost = String(host || "") }
    function selectSetting(key) { return settingsPanel.selectSetting(key) }

    // ── 3. CONTAINER CHUYỂN TAB ───────────────────────────────────────────────
        StackLayout {
            anchors.fill: parent

        currentIndex: {
            if (panelSideBar.appMode === "devices") return 0
            if (panelSideBar.appMode === "settings") return 1
            if (panelSideBar.appMode === "database") return 2
            if (panelSideBar.appMode === "syslog") return 3
            if (panelSideBar.appMode === "sftp") return 4
            return 0
        }

        // [0] GIAO DIỆN DEVICES (Đã tách file)
        DevicesPanel {
            id: devicesPanel
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Lắng nghe tín hiệu từ DevicesPanel và phát ngược lên Main.qml
            onDeviceSelected: (ip, name, deviceType, status) => panelSideBar.deviceSelected(ip, name, deviceType, status)
            onDeviceActivated: (host, name, deviceType, status) => panelSideBar.deviceActivated(host, name, deviceType, status)
            onDeviceSelectionChanged: hosts => panelSideBar.deviceSelectionChanged(hosts)
            onDeviceDeleted: (ip) => panelSideBar.deviceDeleted(ip)
            onDevicesLoaded: (devices) => panelSideBar.devicesLoaded(devices)
        }

        // [1] GIAO DIỆN SETTINGS
        SettingsPanel {
            id: settingsPanel
            Layout.fillWidth: true
            Layout.fillHeight: true
            onSettingSelected: function(key) {
                panelSideBar.settingSelected(key)
            }
        }

        // [2] DATABASE BROWSER TABLE LIST
        DatabaseTablesPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            onTableSelected: function(tableName) {
                panelSideBar.databaseTableSelected(tableName)
            }
        }

        // [3] SYSLOG CONNECTED-ONLY HOST LIST (kept out of DevicesPanel)
        SyslogDevicesPanel {
            id: syslogPanel
            Layout.fillWidth: true
            Layout.fillHeight: true
            onHostSelected: host => panelSideBar.syslogHostSelected(host)
            onOperationFinished: (ok, message) => panelSideBar.syslogOperationFinished(ok, message)
        }

        // [4] SFTP SAVED CONNECTIONS
        SftpConnectionsPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            backend: typeof sftpController !== "undefined" ? sftpController : null
        }
    }
}
