pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// Shared batch preview/push dialog used by Routing Group, FHRP and VTP.
StandardDialog {
    id: dialog

    property string controllerName: "routing"
    property string moduleName: "all"
    property string featureLabel: controllerName.toUpperCase()
    property var hosts: []
    property var pendingHosts: ({})
    property var results: []
    property var previewResults: ({})
    property var pendingPreviews: ({})
    property string previewText: ""
    property string messageText: ""
    property bool isPushing: false
    property int pushTargetCount: 0
    property var ownerForm: null
    readonly property int pendingPreviewCount:
        Object.keys(pendingPreviews).length
    readonly property int completedStepCount: isPushing || pushTargetCount > 0
                                              ? results.length
                                              : Math.max(0, hosts.length
                                                             - pendingPreviewCount)
    readonly property int totalStepCount: Math.max(
        1, isPushing || pushTargetCount > 0 ? pushTargetCount : hosts.length)

    signal pushCompleted(bool ok, string message)

    preferredWidth: 880
    height: Math.min(parent ? parent.height - 48 : 650, 680)
    title: "View & Push " + featureLabel
    subtitle: hosts.length + " target device(s)"
    closeEnabled: !isPushing

    function notify(message, type) {
        if (ownerForm && ownerForm.notify)
            ownerForm.notify(message, type)
    }

    function openPreview(targetHosts, module) {
        hosts = targetHosts || []
        moduleName = String(module || "all").toLowerCase()
        results = []
        pushTargetCount = 0
        pendingHosts = ({})
        previewResults = ({})
        const pending = {}
        for (let i = 0; i < hosts.length; i++)
            pending[String(hosts[i])] = true
        pendingPreviews = pending
        previewText = ""
        messageText = "Preparing previews for " + hosts.length + " device(s)..."
        open()
        for (let j = 0; j < hosts.length; j++) {
            const host = String(hosts[j])
            if (!dbManager.previewViewPushAsync(controllerName, host, moduleName))
                recordPreview(host, false, "Preview task could not start.", "")
        }
    }

    function recordPreview(host, ok, message, commands) {
        if (pendingPreviews[String(host)] !== true)
            return
        const pending = Object.assign({}, pendingPreviews)
        delete pending[String(host)]
        pendingPreviews = pending
        const next = Object.assign({}, previewResults)
        next[String(host)] = {
            ok: Boolean(ok),
            message: String(message || ""),
            commands: String(commands || "")
        }
        previewResults = next
        const previews = []
        const errors = []
        const keys = Object.keys(next)
        for (let i = 0; i < keys.length; i++) {
            const item = next[keys[i]]
            if (item.ok)
                previews.push("# Device: " + keys[i] + "\n" + (item.commands || "# No commands"))
            else
                errors.push(keys[i] + ": " + (item.message || "Preview failed"))
        }
        previewText = previews.join("\n\n")
        if (Object.keys(pending).length === 0)
            messageText = errors.length === 0
                    ? "Review the commands below, then press Push."
                    : "Some previews failed: " + errors.join("; ")
    }

    function pushNow() {
        if (isPushing)
            return
        const readyHosts = hosts.filter(host => previewResults[String(host)]
                                        && previewResults[String(host)].ok)
        if (readyHosts.length === 0)
            return
        const pending = {}
        results = []
        pushTargetCount = readyHosts.length
        for (let i = 0; i < readyHosts.length; i++)
            pending[String(readyHosts[i])] = true
        pendingHosts = pending
        isPushing = true
        messageText = "Pushing configuration to " + readyHosts.length + " device(s)..."
        if (!dbManager.pushViewPushBatchAsync(controllerName, readyHosts, moduleName)) {
            for (let j = 0; j < readyHosts.length; j++)
                recordResult(String(readyHosts[j]), false, "Batch Push task could not start.")
        }
    }

    function recordResult(host, ok, message) {
        if (pendingHosts[String(host)] !== true)
            return
        const pending = Object.assign({}, pendingHosts)
        delete pending[String(host)]
        pendingHosts = pending
        const next = results.slice()
        next.push({host: String(host), ok: Boolean(ok), message: String(message || "")})
        results = next
        if (Object.keys(pending).length === 0) {
            isPushing = false
            const succeeded = next.filter(item => item.ok)
            const failed = next.filter(item => !item.ok)
            messageText = "Push completed: " + succeeded.length + " succeeded, "
                    + failed.length + " failed."
            if (failed.length > 0)
                messageText += " Failed: "
                        + failed.map(item => item.host).join(", ") + "."
            notify(messageText, failed.length === 0 ? "success" : "warning")
            if (ownerForm && ownerForm.reloadData)
                ownerForm.reloadData("pushCompleted")
            pushCompleted(failed.length === 0, messageText)
            close()
        }
    }

    Connections {
        target: typeof dbManager !== "undefined" ? dbManager : null
        ignoreUnknownSignals: true
        function onViewPushPreviewFinished(controller, host, module, ok, message, commands) {
            if (String(controller) === dialog.controllerName
                    && String(module) === dialog.moduleName)
                dialog.recordPreview(String(host), ok, message, commands)
        }
        function onViewPushFinished(controller, host, module, ok, message) {
            if (String(controller) === dialog.controllerName
                    && String(module) === dialog.moduleName)
                dialog.recordResult(String(host), ok, message)
        }
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacing12
        InlineMessage {
            Layout.fillWidth: true
            message: dialog.messageText
            busy: dialog.isPushing
            severity: dialog.results.some(item => !item.ok) ? "warning" : "info"
        }
        RowLayout {
            Layout.fillWidth: true
            visible: dialog.hosts.length > 0
            spacing: Theme.spacing8

            ProgressBar {
                id: batchProgress
                objectName: "multiHostViewPushProgress"
                Layout.fillWidth: true
                from: 0
                to: dialog.totalStepCount
                value: dialog.completedStepCount
            }
            Text {
                text: dialog.completedStepCount + " / " + dialog.totalStepCount
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
        }
        ConfigurationPreviewPane {
            objectName: "multiHostViewPushConfigurationPreview"
            Layout.fillWidth: true
            Layout.fillHeight: true
            previewText: dialog.previewText
            emptyText: "Waiting for configuration previews..."
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            StandardButton {
                objectName: "multiHostViewPushCloseButton"
                text: "Close"
                type: "Text"
                enabled: !dialog.isPushing
                onClicked: dialog.close()
            }
            StandardButton {
                objectName: "multiHostViewPushPushButton"
                text: dialog.isPushing ? "Pushing..." : "Push"
                icon.source: AppAssets.actionPush
                type: "Primary"
                enabled: !dialog.isPushing
                         && Object.keys(dialog.pendingPreviews).length === 0
                         && Object.keys(dialog.previewResults).some(
                             host => dialog.previewResults[host].ok)
                onClicked: dialog.pushNow()
            }
        }
    }
}
