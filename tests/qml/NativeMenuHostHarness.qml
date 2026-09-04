pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root

    width: 480
    height: 320
    visible: true

    readonly property bool nativeMenuReady: nativeMenuHost.ready
    readonly property bool nativeMenuFailed: nativeMenuHost.failed
    readonly property bool nativeMenuHasOwner:
        nativeMenuHost.ready
        && nativeMenuHost.ownerWindow === root

    CommandRegistry {
        id: commandRegistry
        objectName: "nativeMenuCommandRegistry"
        workspaceAvailable: true
        saveAvailable: true
    }

    NativeMenuHost {
        id: nativeMenuHost
        registry: commandRegistry
        ownerWindow: root
        requested: true
    }

}
