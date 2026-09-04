pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 720
    height: 420
    visible: true

    property int newProjectCount: 0
    property int saveCount: 0
    property int settingsCount: 0
    property alias saveAvailable: registry.saveAvailable
    readonly property int activeMenuIndex: menuBar.activeMenuIndex

    function openFileMenu() {
        return menuBar.openMenuById("file")
    }

    function openViewMenu() {
        return menuBar.openMenuById("view")
    }

    function openHelpMenu() {
        return menuBar.openMenuById("help")
    }

    function focusContent() {
        focusProbe.forceActiveFocus(Qt.OtherFocusReason)
        return focusProbe.activeFocus
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: Theme.windowTitleHeight
        color: Theme.activityBarBackground

        ModernMenuBar {
            id: menuBar
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            registry: registry
        }
    }

    TextField {
        id: focusProbe
        objectName: "modernMenuFocusProbe"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: 24
        anchors.topMargin: 72
        width: 240
        placeholderText: "Focus return probe"
    }

    CommandRegistry {
        id: registry
        objectName: "modernMenuRegistry"
        workspaceAvailable: true
        saveAvailable: true
        reloadAvailable: true
        databaseAvailable: true
        newProjectHandler: function() {
            root.newProjectCount++
            return true
        }
        saveHandler: function() {
            root.saveCount++
            return true
        }
        settingsHandler: function() {
            root.settingsCount++
            return true
        }
    }
}
