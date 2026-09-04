pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: activityBar
    color: Theme.activityBarBackground

    property int activeIndex: 0
    property string appMode: "devices"
    readonly property var toolsBackend: typeof externalTools !== "undefined" && externalTools !== null
                                        ? externalTools
                                        : null
    readonly property var sftpBackend: typeof sftpController !== "undefined" && sftpController !== null
                                       ? sftpController
                                       : null
    readonly property bool canActivateDatabase: toolsBackend !== null
    readonly property bool usesExternalSftp: toolsBackend !== null
                                             && toolsBackend.hasEnabledSftpClient === true

    // ── Signals ───────────────────────────────────────────────────────────────

    // Signal toggle sidebar — phát khi click vào item đang active
    // Main.qml lắng nghe để show/hide PanelSideBar
    signal toggleSidebarRequested()
    signal showSidebarRequested()
    signal databaseOpenMessage(string message, string type, string settingsKey)
    signal sftpOpenMessage(string message, string type, string settingsKey)

    // ── Hàm xử lý click item ─────────────────────────────────────────────────
    // Trả về true nếu đã toggle sidebar (item đang active được click lại)
    // Trả về false nếu chuyển sang tab mới
    function handleItemClick(index, mode) {
        if (activityBar.activeIndex === index && activityBar.appMode === mode) {
            // Click vào item đang active → toggle sidebar
            activityBar.toggleSidebarRequested()
        } else {
            // Click vào item khác → chuyển tab bình thường
            activityBar.activeIndex = index
            activityBar.appMode = mode
            activityBar.showSidebarRequested()
        }
    }

    function selectItem(index, mode) {
        activityBar.activeIndex = index
        activityBar.appMode = mode
        activityBar.showSidebarRequested()
        return true
    }

    function activateDevices() {
        return activityBar.selectItem(0, "devices")
    }

    function activateSystemLogs() {
        return activityBar.selectItem(4, "syslog")
    }

    function activateSettings() {
        return activityBar.selectItem(2, "settings")
    }

    function activateDatabase(toggleSidebarWhenActive) {
        if (!activityBar.canActivateDatabase)
            return false
        const result = activityBar.toolsBackend.openDeviceDatabase()
        activityBar.databaseOpenMessage(
            result.message || "",
            result.ok ? "info" : "warning",
            String(result.settingsKey || "")
        )
        if (result.mode === "default") {
            if (toggleSidebarWhenActive === true)
                activityBar.handleItemClick(1, "database")
            else
                activityBar.selectItem(1, "database")
        }
        return result.ok !== false
    }

    function activateSftp(toggleSidebarWhenActive) {
        let result = null
        if (activityBar.toolsBackend !== null
                && activityBar.toolsBackend.openSftpClient) {
            const profile = activityBar.sftpBackend !== null
                    ? activityBar.sftpBackend.selectedConnection : ({})
            result = activityBar.toolsBackend.openSftpClient(
                profile && profile.host ? String(profile.host) : "",
                profile && profile.port ? Number(profile.port) : 22,
                profile && profile.username ? String(profile.username) : "",
                profile && profile.remotePath ? String(profile.remotePath) : "/"
            )
        }

        if (result && result.mode === "external") {
            activityBar.sftpOpenMessage(
                result.message || "External SFTP Client launched.",
                result.ok === false ? "warning" : "info",
                String(result.settingsKey || "")
            )
            return result.ok !== false
        }
        if (result && result.ok === false) {
            activityBar.sftpOpenMessage(
                result.message || "External SFTP Client failed.",
                "warning",
                String(result.settingsKey || "")
            )
        }

        if (toggleSidebarWhenActive === true
                && activityBar.activeIndex === 3
                && activityBar.appMode === "sftp") {
            activityBar.handleItemClick(3, "sftp")
        } else {
            activityBar.selectItem(3, "sftp")
        }
        return true
    }

    // ── Icons Khối Trên (Điều hướng chính) ───────────────────────────────────
    Column {
        id: topGroup
        objectName: "activityTopGroup"
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter

        ActivityBarItem {
            iconSource:  AppAssets.navigationDashboard
            tooltipText: "Dashboard (Ctrl+Alt+D)"
            isActive:    activityBar.activeIndex === 0

            onClicked: activityBar.handleItemClick(0, "devices")
        }

        ActivityBarItem {
            objectName:  "sftpActivityItem"
            iconSource:  AppAssets.navigationSftp
            tooltipText: (activityBar.usesExternalSftp
                          ? "Open external SFTP Client"
                          : "SFTP") + " (Ctrl+Alt+F)"
            enabled:     true
            isActive:    activityBar.appMode === "sftp"
            opacity:     1.0

            onClicked: activityBar.activateSftp(true)
        }

        ActivityBarItem {
            objectName: "syslogActivityItem"
            iconSource: AppAssets.navigationSyslog
            tooltipText: "System Logs (Ctrl+Alt+L)"
            enabled: true
            isActive: activityBar.appMode === "syslog"
            opacity: 1.0

            onClicked: activityBar.activateSystemLogs()
        }

    }

    // ── Separator giữa top và bottom group ───────────────────────────────────
    Rectangle {
        anchors.bottom: bottomGroup.top
        anchors.bottomMargin: 4
        anchors.horizontalCenter: parent.horizontalCenter
        width:  Theme.activityBarWidth - 16
        height: Theme.borderWidth
        color:  Theme.activityBarBorderColor
        opacity: 0.6
    }

    // ── Icons Khối Dưới (Hệ thống & Cài đặt) ─────────────────────────────────
    Column {
        id: bottomGroup
        objectName: "activityBottomGroup"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter

        ActivityBarItem {
            objectName:  "databaseActivityItem"
            iconSource:  AppAssets.navigationDatabase
            tooltipText: "Database (Ctrl+Alt+B)"
            isActive:    activityBar.activeIndex === 1
            enabled:     activityBar.canActivateDatabase
            opacity:     enabled ? 1.0 : 0.35

            onClicked: {
                activityBar.activateDatabase(true)
            }
        }

        ActivityBarItem {
            objectName:  "settingsActivityItem"
            iconSource:  AppAssets.navigationSettings
            tooltipText: "Settings (Ctrl+,)"
            isActive:    activityBar.activeIndex === 2

            onClicked: activityBar.handleItemClick(2, "settings")
        }
    }

    // ── Đường viền phải ───────────────────────────────────────────────────────
    Rectangle {
        anchors.right:  parent.right
        width:          Theme.borderWidth
        height:         parent.height
        color:          Theme.activityBarBorderColor
    }
}
