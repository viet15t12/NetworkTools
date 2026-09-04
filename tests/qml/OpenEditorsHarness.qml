pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 320
    height: 420
    visible: true

    DeviceTabs {
        id: tabs
        objectName: "openEditorsDeviceTabs"
        visible: false
    }

    OpenEditorsSection {
        id: openEditors
        objectName: "openEditorsTestSection"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: implicitHeight
        editors: tabs.openEditorsSnapshot
        activeUid: tabs.activeUid
        onEditorSelected: uid => tabs.openTabByUid(uid)
        onEditorCloseRequested: uid => tabs.closeTabByUid(uid)
        onCloseAllRequested: tabs.closeAllTabs()
    }

    Component.onCompleted: {
        tabs.initializeTabs([])
        tabs.openTab("192.0.2.1", "Router A", "router", "connected")
        tabs.openTab("192.0.2.2", "Switch B", "switch", "waiting")
        tabs.openTab("192.0.2.3", "Router C", "router", "disconnected")
    }
}
