pragma ComponentBehavior: Bound

import QtQuick

Item {
    id: root

    required property var registry
    required property var ownerWindow
    property bool requested: false
    property bool failed: false
    property bool loadScheduled: false
    readonly property bool ownerReady: root.ownerWindow !== null
                                       && root.ownerWindow !== undefined
                                       && root.ownerWindow.visible
                                       && root.ownerWindow.active
    readonly property bool ready: nativeMenuLoader.status === Loader.Ready
                                  && nativeMenuLoader.item !== null
                                  && nativeMenuLoader.item.window === root.ownerWindow

    signal loadFailed(string message)

    function detectFailure() {
        if (nativeMenuLoader.status !== Loader.Error || root.failed)
            return
        root.failed = true
        const message =
            "The Native Global menu presenter could not be loaded; "
            + "CAMS is using the in-window menu."
        root.loadFailed(message)
        console.warn(message)
    }

    function scheduleLoad() {
        if (root.loadScheduled || root.failed || !root.requested
                || nativeMenuLoader.item !== null)
            return
        root.loadScheduled = true
        Qt.callLater(function() {
            root.loadScheduled = false
            root.loadWhenWindowIsReady()
        })
    }

    function loadWhenWindowIsReady() {
        if (root.failed || !root.requested || !root.ownerReady
                || nativeMenuLoader.item !== null)
            return false

        // Initial properties are applied before component completion. This is
        // essential on Wayland: the native menubar must never complete with a
        // null QWindow and then be rebound to a live surface afterwards.
        nativeMenuLoader.setSource(
            Qt.resolvedUrl("NativeGlobalMenuBar.qml"),
            {
                "registry": root.registry,
                "window": root.ownerWindow
            }
        )
        return true
    }

    objectName: "nativeMenuHost"
    visible: false
    width: 0
    height: 0

    onRequestedChanged: root.scheduleLoad()
    onOwnerWindowChanged: root.scheduleLoad()

    Connections {
        target: root.ownerWindow
        enabled: root.ownerWindow !== null && root.ownerWindow !== undefined

        function onVisibleChanged() { root.scheduleLoad() }
        function onActiveChanged() { root.scheduleLoad() }
    }

    Loader {
        id: nativeMenuLoader
        objectName: "nativeMenuLoader"
        active: true
        asynchronous: false
        source: ""

        onStatusChanged: root.detectFailure()
        Component.onCompleted: Qt.callLater(root.detectFailure)
    }

    Component.onCompleted: root.scheduleLoad()
}
