pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import UI

Controls.MenuBar {
    id: root

    implicitHeight: Theme.windowTitleHeight - 1
    spacing: 0
    padding: 0

    background: Rectangle {
        color: "transparent"
    }

    delegate: Controls.MenuBarItem {
        id: menuBarItem
        implicitWidth: Math.max(42, menuBarLabel.implicitWidth + Theme.spacing16)
        implicitHeight: root.implicitHeight
        leftPadding: Theme.spacing8
        rightPadding: Theme.spacing8
        topPadding: 0
        bottomPadding: 0

        contentItem: Text {
            id: menuBarLabel
            text: menuBarItem.text.replace("&", "")
            color: menuBarItem.enabled
                   ? Theme.activityBarTextPrimary
                   : Theme.activityBarTextSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }

        background: Rectangle {
            color: menuBarItem.highlighted
                   ? Theme.activityBarItemHover
                   : "transparent"
            radius: Theme.radiusSmall
        }
    }

    property var newProjectHandler: null
    property var openProjectHandler: null
    property var saveHandler: null
    property var createSnapshotHandler: null
    property var snapshotHistoryHandler: null
    property var closeWorkspaceHandler: null
    property var toggleSidebarHandler: null
    property var dashboardHandler: null
    property var databaseHandler: null
    property var settingsHandler: null
    property var shortcutsHandler: null
    property var aboutHandler: null

    property bool saveAvailable: false
    property bool databaseAvailable: false

    function invoke(handler) {
        if (typeof handler !== "function")
            return false
        const result = handler()
        return result === undefined ? true : result !== false
    }

    Controls.Action {
        id: newProjectAction
        text: qsTr("New Project...")
        onTriggered: root.invoke(root.newProjectHandler)
    }

    Controls.Action {
        id: createSnapshotAction
        text: qsTr("Create Snapshot…")
        enabled: root.saveAvailable
        onTriggered: root.invoke(root.createSnapshotHandler)
    }

    Controls.Action {
        id: snapshotHistoryAction
        text: qsTr("Snapshot History…")
        enabled: root.saveAvailable
        onTriggered: root.invoke(root.snapshotHistoryHandler)
    }

    Controls.Action {
        id: openProjectAction
        text: qsTr("Open Project...")
        shortcut: "Ctrl+O"
        onTriggered: root.invoke(root.openProjectHandler)
    }

    Controls.Action {
        id: saveAction
        text: qsTr("Save Workspace")
        shortcut: StandardKey.Save
        enabled: root.saveAvailable
        onTriggered: root.invoke(root.saveHandler)
    }

    Controls.Action {
        id: closeWorkspaceAction
        text: qsTr("Close Workspace")
        onTriggered: root.invoke(root.closeWorkspaceHandler)
    }

    Controls.Action {
        id: quitAction
        text: qsTr("Quit")
        shortcut: "Alt+F4"
        onTriggered: {
            const ownerWindow = root.Window.window
            if (ownerWindow)
                ownerWindow.close()
            else
                Qt.quit()
        }
    }

    Controls.Menu {
        title: qsTr("&File")

        Controls.MenuItem { action: newProjectAction }
        Controls.MenuItem { action: openProjectAction }
        Controls.MenuSeparator {}
        Controls.MenuItem { action: saveAction }
        Controls.MenuItem { action: createSnapshotAction }
        Controls.MenuItem { action: snapshotHistoryAction }
        Controls.MenuSeparator {}
        Controls.MenuItem { action: closeWorkspaceAction }
        Controls.MenuItem { action: quitAction }
    }

    Controls.Menu {
        title: qsTr("&View")

        Controls.MenuItem {
            text: qsTr("Toggle Sidebar")
            onTriggered: root.invoke(root.toggleSidebarHandler)
        }
        Controls.MenuSeparator {}
        Controls.MenuItem {
            text: qsTr("Dashboard")
            onTriggered: root.invoke(root.dashboardHandler)
        }
        Controls.MenuItem {
            text: qsTr("Database")
            enabled: root.databaseAvailable
            onTriggered: root.invoke(root.databaseHandler)
        }
        Controls.MenuItem {
            text: qsTr("Settings")
            onTriggered: root.invoke(root.settingsHandler)
        }
    }

    Controls.Menu {
        title: qsTr("&Help")

        Controls.MenuItem {
            text: qsTr("Keyboard Shortcuts")
            onTriggered: root.invoke(root.shortcutsHandler)
        }
        Controls.MenuSeparator {}
        Controls.MenuItem {
            text: qsTr("About CAMS")
            onTriggered: root.invoke(root.aboutHandler)
        }
    }
}
