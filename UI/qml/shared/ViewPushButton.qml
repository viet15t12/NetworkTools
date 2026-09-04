pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import UI

StandardButton {
    id: root

    property string controllerName: "routing"
    property string hostIp: ""
    property string moduleName: "all"
    property string availability: "ready"
    property string unavailableMessage: "View & Push for router interfaces is Coming soon."
    property int refreshKey: 0
    property bool hasPendingConfig: false
    property bool isCheckingPending: false
    property var ownerForm: null
    property var pushDialog: null
    readonly property bool backendAvailable:
        typeof dbManager !== "undefined"
        && dbManager !== null
    readonly property bool backendShuttingDown:
        backendAvailable
        && typeof dbManager.shuttingDown !== "undefined"
        && Boolean(dbManager.shuttingDown)

    signal pushCompleted(bool ok, string message)

    text: "View & Push"
    // Available actions use the accent; disabled actions retain StandardButton's
    // neutral light/dark/high-contrast surface instead of a misleading color.
    type: "Primary"
    icon.source: AppAssets.actionPush
    enabled: String(hostIp || "").trim() !== ""
             && (availability === "comingSoon"
                 || (!isCheckingPending && hasPendingConfig))
    tooltip: availability === "comingSoon"
             ? unavailableMessage
             : (enabled ? "" : "No configuration required for Push.")

    function refreshPending() {
        if (!backendAvailable || backendShuttingDown) {
            hasPendingConfig = false
            return
        }
        if (availability === "comingSoon") {
            hasPendingConfig = false
            return
        }
        const host = String(hostIp || "").trim()
        if (host === "") {
            hasPendingConfig = false
            return
        }

        isCheckingPending = true
        hasPendingConfig = dbManager.hasPendingViewPush(controllerName, host, moduleName)
        isCheckingPending = false
    }

    function openPushPreview() {
        if (!enabled)
            return
        if (availability === "comingSoon") {
            if (ownerForm && ownerForm.notify)
                ownerForm.notify(unavailableMessage, "info")
            else if (typeof statusBar !== "undefined")
                statusBar.showMessage(unavailableMessage, "info")
            return
        }
        if (!pushDialog) {
            const dialogParent = Overlay.overlay || root
            pushDialog = pushDialogComponent.createObject(dialogParent, {
                controllerName: root.controllerName,
                hostIp: root.hostIp,
                moduleName: root.moduleName,
                ownerForm: root.ownerForm
            })
            pushDialog.pushCompleted.connect(function(ok, message) {
                root.refreshPending()
                root.pushCompleted(ok, message)
            })
        }
        pushDialog.controllerName = root.controllerName
        pushDialog.hostIp = root.hostIp
        pushDialog.moduleName = root.moduleName
        pushDialog.ownerForm = root.ownerForm
        pushDialog.openPreview()
    }

    onClicked: openPushPreview()
    onHostIpChanged: refreshPending()
    onModuleNameChanged: refreshPending()
    onControllerNameChanged: refreshPending()
    onRefreshKeyChanged: refreshPending()
    onAvailabilityChanged: refreshPending()
    Component.onCompleted: refreshPending()

    Timer {
        interval: 1200
        repeat: true
        running: root.visible && root.availability === "ready"
                 && root.backendAvailable
                 && !root.backendShuttingDown
                 && String(root.hostIp || "").trim() !== ""
        onTriggered: root.refreshPending()
    }

    Component {
        id: pushDialogComponent
        ViewPushDialog {}
    }
}
