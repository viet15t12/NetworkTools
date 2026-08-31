pragma ComponentBehavior: Bound

import QtQuick
import QtQml.Models
import UI

Item {
    id: root

    width: 0
    height: 0

    property bool commandsEnabled: true
    property bool shortcutDispatchEnabled: true
    property bool shortcutContextActive: true
    property bool inputFocusActive: false
    property bool workspaceCommandsVisible: true
    property bool navigationCommandsVisible: true
    property bool workspaceAvailable: false
    property bool workspaceBusy: false
    property bool saveAvailable: false
    property bool snapshotAvailable: saveAvailable
    property bool reloadAvailable: false
    property bool sidebarAvailable: true
    property bool dashboardAvailable: true
    property bool sftpAvailable: true
    property bool systemLogsAvailable: true
    property bool databaseAvailable: false
    property bool settingsAvailable: true
    property bool shortcutGuideAvailable: true
    property bool aboutAvailable: true

    property var newProjectHandler: null
    property var openProjectHandler: null
    property var saveHandler: null
    property var createSnapshotHandler: null
    property var snapshotHistoryHandler: null
    property var closeWorkspaceHandler: null
    property var quitHandler: function() {
        const ownerWindow = root.Window.window
        if (ownerWindow)
            ownerWindow.close()
        else
            Qt.quit()
        return true
    }
    property var reloadHandler: null
    property var toggleSidebarHandler: null
    property var dashboardHandler: null
    property var sftpHandler: null
    property var systemLogsHandler: null
    property var databaseHandler: null
    property var settingsHandler: null
    property var shortcutGuideHandler: null
    property var aboutHandler: null

    readonly property string reloadLabel: qsTr("Reload UI")
    readonly property string reloadShortcut: "Ctrl+R"
    readonly property string dashboardLabel: qsTr("Dashboard")
    readonly property string dashboardShortcut: "Ctrl+Alt+D"
    readonly property string sftpLabel: qsTr("SFTP")
    readonly property string sftpShortcut: "Ctrl+Alt+F"
    readonly property string systemLogsLabel: qsTr("System Logs")
    readonly property string systemLogsShortcut: "Ctrl+Alt+L"
    readonly property string databaseLabel: qsTr("Database")
    readonly property string databaseShortcut: "Ctrl+Alt+B"
    readonly property string settingsLabel: qsTr("Settings")
    readonly property string settingsShortcut: "Ctrl+,"
    readonly property string shortcutGuideLabel: qsTr("Keyboard Shortcuts")
    readonly property string shortcutGuideShortcut: "Ctrl+K, Ctrl+S"

    readonly property bool contextualCommandsEnabled: commandsEnabled && !inputFocusActive
    readonly property bool reloadEnabled: contextualCommandsEnabled && reloadAvailable
    readonly property bool dashboardEnabled: contextualCommandsEnabled && dashboardAvailable
    readonly property bool sftpEnabled: contextualCommandsEnabled && sftpAvailable
    readonly property bool systemLogsEnabled: contextualCommandsEnabled && systemLogsAvailable
    readonly property bool databaseEnabled: contextualCommandsEnabled && databaseAvailable
    readonly property bool settingsEnabled: commandsEnabled && settingsAvailable
    readonly property bool shortcutGuideEnabled: commandsEnabled && shortcutGuideAvailable

    AppCommand {
        id: newProjectCommand
        objectName: "commandProjectNew"
        commandId: "project.new"
        text: qsTr("New Project...")
        iconSource: AppAssets.actionAdd
        enabled: root.commandsEnabled
        scope: "application"
        handler: root.newProjectHandler
    }

    AppCommand {
        id: openProjectCommand
        objectName: "commandProjectOpen"
        commandId: "project.open"
        text: qsTr("Open Project...")
        iconSource: AppAssets.fileFolder
        shortcut: "Ctrl+O"
        enabled: root.commandsEnabled
        scope: "application"
        handler: root.openProjectHandler
    }

    AppCommand {
        id: saveWorkspaceCommand
        objectName: "commandWorkspaceSave"
        commandId: "workspace.save"
        text: qsTr("Save Workspace")
        iconSource: AppAssets.actionSave
        shortcut: "Ctrl+S"
        enabled: root.commandsEnabled && root.saveAvailable
        visible: root.workspaceCommandsVisible
        handler: root.saveHandler
    }

    AppCommand {
        id: createSnapshotCommand
        objectName: "commandSnapshotCreate"
        commandId: "workspace.snapshot.create"
        text: qsTr("Create Snapshot…")
        iconSource: AppAssets.actionBackup
        enabled: root.commandsEnabled && root.snapshotAvailable
        visible: root.workspaceCommandsVisible
        handler: root.createSnapshotHandler
    }

    AppCommand {
        id: snapshotHistoryCommand
        objectName: "commandSnapshotHistory"
        commandId: "workspace.snapshot.history"
        text: qsTr("Snapshot History…")
        iconSource: AppAssets.navigationLogs
        enabled: root.commandsEnabled && root.snapshotAvailable
        visible: root.workspaceCommandsVisible
        handler: root.snapshotHistoryHandler
    }

    AppCommand {
        id: closeWorkspaceCommand
        objectName: "commandWorkspaceClose"
        commandId: "workspace.close"
        text: qsTr("Close Workspace")
        iconSource: AppAssets.actionClose
        enabled: root.commandsEnabled && root.workspaceAvailable && !root.workspaceBusy
        visible: root.workspaceCommandsVisible
        handler: root.closeWorkspaceHandler
    }

    AppCommand {
        id: quitCommand
        objectName: "commandAppQuit"
        commandId: "app.quit"
        text: qsTr("Quit")
        shortcut: "Alt+F4"
        enabled: root.commandsEnabled
        nativeRole: "quit"
        scope: "application"
        handler: root.quitHandler
    }

    AppCommand {
        id: reloadCommand
        objectName: "commandViewReload"
        commandId: "view.reload"
        text: root.reloadLabel
        iconSource: AppAssets.actionRefresh
        shortcut: root.reloadShortcut
        enabled: root.reloadEnabled
        visible: root.navigationCommandsVisible
        handler: root.reloadHandler
    }

    AppCommand {
        id: toggleSidebarCommand
        objectName: "commandSidebarToggle"
        commandId: "view.sidebar.toggle"
        text: qsTr("Toggle Sidebar")
        iconSource: AppAssets.navigationListCollapse
        shortcut: "Ctrl+B"
        enabled: root.commandsEnabled && root.sidebarAvailable
        visible: root.navigationCommandsVisible
        handler: root.toggleSidebarHandler
    }

    AppCommand {
        id: dashboardCommand
        objectName: "commandViewDashboard"
        commandId: "view.dashboard"
        text: root.dashboardLabel
        iconSource: AppAssets.navigationDashboard
        shortcut: root.dashboardShortcut
        enabled: root.dashboardEnabled
        visible: root.navigationCommandsVisible
        handler: root.dashboardHandler
    }

    AppCommand {
        id: sftpCommand
        objectName: "commandViewSftp"
        commandId: "view.sftp"
        text: root.sftpLabel
        iconSource: AppAssets.navigationSftp
        shortcut: root.sftpShortcut
        enabled: root.sftpEnabled
        visible: root.navigationCommandsVisible
        handler: root.sftpHandler
    }

    AppCommand {
        id: systemLogsCommand
        objectName: "commandViewSystemLogs"
        commandId: "view.systemLogs"
        text: root.systemLogsLabel
        iconSource: AppAssets.navigationSyslog
        shortcut: root.systemLogsShortcut
        enabled: root.systemLogsEnabled
        visible: root.navigationCommandsVisible
        handler: root.systemLogsHandler
    }

    AppCommand {
        id: databaseCommand
        objectName: "commandViewDatabase"
        commandId: "view.database"
        text: root.databaseLabel
        iconSource: AppAssets.navigationDatabase
        shortcut: root.databaseShortcut
        enabled: root.databaseEnabled
        visible: root.navigationCommandsVisible
        handler: root.databaseHandler
    }

    AppCommand {
        id: settingsCommand
        objectName: "commandSettingsOpen"
        commandId: "settings.open"
        text: root.settingsLabel
        iconSource: AppAssets.navigationSettings
        shortcut: root.settingsShortcut
        enabled: root.settingsEnabled
        nativeRole: "preferences"
        scope: "application"
        handler: root.settingsHandler
    }

    AppCommand {
        id: shortcutGuideCommand
        objectName: "commandHelpShortcuts"
        commandId: "help.shortcuts"
        text: root.shortcutGuideLabel
        iconSource: AppAssets.navigationInformation
        shortcut: root.shortcutGuideShortcut
        enabled: root.shortcutGuideEnabled
        scope: "application"
        handler: root.shortcutGuideHandler
    }

    AppCommand {
        id: aboutCommand
        objectName: "commandAppAbout"
        commandId: "app.about"
        text: qsTr("About CAMS")
        iconSource: AppAssets.brandLogo
        enabled: root.commandsEnabled && root.aboutAvailable
        nativeRole: "about"
        scope: "application"
        handler: root.aboutHandler
    }

    readonly property var commands: [
        newProjectCommand,
        openProjectCommand,
        saveWorkspaceCommand,
        createSnapshotCommand,
        snapshotHistoryCommand,
        closeWorkspaceCommand,
        quitCommand,
        reloadCommand,
        toggleSidebarCommand,
        dashboardCommand,
        sftpCommand,
        systemLogsCommand,
        databaseCommand,
        settingsCommand,
        shortcutGuideCommand,
        aboutCommand
    ]
    readonly property int commandCount: commands.length

    function command(commandId) {
        for (let index = 0; index < root.commands.length; index++) {
            if (root.commands[index].commandId === commandId)
                return root.commands[index]
        }
        return null
    }

    function commandText(commandId) {
        const action = root.command(commandId)
        return action !== null ? action.text : ""
    }

    function trigger(commandId) {
        const action = root.command(commandId)
        return action !== null && action.invoke()
    }

    function triggerNewProject() { return root.trigger("project.new") }
    function triggerOpenProject() { return root.trigger("project.open") }
    function triggerSave() { return root.trigger("workspace.save") }
    function triggerCreateSnapshot() { return root.trigger("workspace.snapshot.create") }
    function triggerSnapshotHistory() { return root.trigger("workspace.snapshot.history") }
    function triggerCloseWorkspace() { return root.trigger("workspace.close") }
    function triggerReload() { return root.trigger("view.reload") }
    function triggerToggleSidebar() { return root.trigger("view.sidebar.toggle") }
    function triggerDashboard() { return root.trigger("view.dashboard") }
    function triggerSftp() { return root.trigger("view.sftp") }
    function triggerSystemLogs() { return root.trigger("view.systemLogs") }
    function triggerDatabase() { return root.trigger("view.database") }
    function triggerSettings() { return root.trigger("settings.open") }
    function triggerShortcutGuide() { return root.trigger("help.shortcuts") }
    function triggerAbout() { return root.trigger("app.about") }

    Instantiator {
        model: root.commands

        delegate: Shortcut {
            required property var modelData

            objectName: "commandShortcut"
                        + modelData.commandId.split(".").map(function(part) {
                            return part.charAt(0).toUpperCase() + part.slice(1)
                        }).join("")
            sequence: modelData.shortcut
            context: modelData.scope === "application"
                     ? Qt.ApplicationShortcut : Qt.WindowShortcut
            enabled: root.shortcutDispatchEnabled
                     && root.shortcutContextActive
                     && modelData.enabled
                     && modelData.visible
                     && String(modelData.shortcut) !== ""
            autoRepeat: false
            onActivated: root.trigger(modelData.commandId)
        }
    }
}
