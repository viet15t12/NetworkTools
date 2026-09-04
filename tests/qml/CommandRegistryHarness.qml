import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 480
    height: 320
    visible: true

    property int reloadCount: 0
    property int dashboardCount: 0
    property int sftpCount: 0
    property int systemLogsCount: 0
    property int databaseCount: 0
    property int settingsCount: 0
    property int shortcutGuideCount: 0
    property int newProjectCount: 0
    property int openProjectCount: 0
    property int saveCount: 0
    property int sidebarToggleCount: 0
    property int aboutCount: 0
    readonly property int commandCount: registry.commandCount
    property alias inputFocusActive: registry.inputFocusActive
    property alias shortcutDispatchEnabled: registry.shortcutDispatchEnabled
    property alias shortcutContextActive: registry.shortcutContextActive
    property alias navigationCommandsVisible: registry.navigationCommandsVisible
    property alias reloadAvailable: registry.reloadAvailable
    property alias databaseAvailable: registry.databaseAvailable
    property alias saveAvailable: registry.saveAvailable

    CommandRegistry {
        id: registry
        objectName: "testCommandRegistry"
        reloadAvailable: true
        databaseAvailable: true
        workspaceAvailable: true
        saveAvailable: true
        newProjectHandler: function() { root.newProjectCount++; return true }
        openProjectHandler: function() { root.openProjectCount++; return true }
        saveHandler: function() { root.saveCount++; return true }
        toggleSidebarHandler: function() { root.sidebarToggleCount++; return true }
        aboutHandler: function() { root.aboutCount++; return true }
        reloadHandler: function() { root.reloadCount++; return true }
        dashboardHandler: function() { root.dashboardCount++; return true }
        sftpHandler: function() { root.sftpCount++; return true }
        systemLogsHandler: function() { root.systemLogsCount++; return true }
        databaseHandler: function() { root.databaseCount++; return true }
        settingsHandler: function() { root.settingsCount++; return true }
        shortcutGuideHandler: function() { root.shortcutGuideCount++; return true }
    }
}
