pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: dialog

    property string controllerName: "routing"
    property string hostIp: ""
    property string moduleName: "all"
    property string previewText: ""
    property string messageText: ""
    property bool isPreviewing: false
    property bool isPushing: false
    property var ownerForm: null

    signal pushCompleted(bool ok, string message)

    preferredWidth: 860
    height: Math.min(parent ? parent.height - 48 : 620, 640)
    title: "View & Push " + dialog.controllerTitle()
    subtitle: dialog.hostIp
    closeTooltip: "Close configuration preview"
    closeEnabled: !dialog.isPushing && !dialog.isPreviewing

    function controllerTitle() {
        const controller = String(controllerName || "").toLowerCase()
        if (controller === "dhcp")
            return "DHCP"
        return String(moduleName || "all").toUpperCase()
    }

    function notify(message, type) {
        if (ownerForm && ownerForm.notify)
            ownerForm.notify(message, type)
        else if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function openPreview() {
        const host = String(hostIp || "").trim()
        if (host === "") {
            notify("Select a device tab before previewing configuration push.", "warning")
            return
        }

        if (!dbManager.previewViewPushAsync) {
            notify("Async preview backend is not available.", "error")
            return
        }

        previewText = ""
        messageText = "Preparing configuration preview..."
        isPreviewing = true
        open()

        const accepted = dbManager.previewViewPushAsync(controllerName, host, moduleName)
        if (!accepted) {
            isPreviewing = false
            messageText = "Cannot start configuration preview."
            notify(messageText, "error")
        }
    }

    function pushNow() {
        if (isPushing)
            return
        const host = String(hostIp || "").trim()
        if (host === "")
            return

        isPushing = true
        if (!dbManager.pushViewPushAsync) {
            isPushing = false
            notify("Async push backend is not available.", "error")
            return
        }

        const accepted = dbManager.pushViewPushAsync(controllerName, host, moduleName)
        if (!accepted) {
            isPushing = false
            notify("Configuration push could not start.", "error")
        }
    }

    function finishPush(ok, message) {
        const msg = String(message || (ok
                           ? "Configuration push completed."
                           : "Configuration push failed."))
        isPushing = false
        if (ok) {
            messageText = msg
        } else {
            // Device output can contain hundreds of CLI lines. Keep it in the
            // bounded, scrollable preview pane instead of allowing the status
            // Text to grow beyond the dialog frame.
            messageText = "Configuration push failed. Review the device output below."
            previewText = msg
        }
        pushCompleted(ok, msg)
        if (ownerForm && ownerForm.reloadData)
            ownerForm.reloadData("pushCompleted")
        notify(ok ? msg : "Configuration push failed.",
               ok ? "success" : "warning")
        close()
    }

    Connections {
        target: typeof dbManager !== "undefined" ? dbManager : null
        function onViewPushPreviewFinished(controller, host, module, ok, message, commands) {
            if (String(controller || "") !== String(dialog.controllerName || "").toLowerCase())
                return
            if (String(host || "") !== String(dialog.hostIp || "").trim())
                return
            if (String(module || "all") !== String(dialog.moduleName || "all").toLowerCase())
                return
            if (!dialog.isPreviewing)
                return

            dialog.isPreviewing = false
            dialog.previewText = String(commands || "")
            dialog.messageText = String(message || "")

            if (!ok)
                notify(dialog.messageText || "Cannot preview configuration.", "error")
        }

        function onViewPushFinished(controller, host, module, ok, message) {
            if (String(controller || "") !== String(dialog.controllerName || "").toLowerCase())
                return
            if (String(host || "") !== String(dialog.hostIp || "").trim())
                return
            if (String(module || "all") !== String(dialog.moduleName || "all").toLowerCase())
                return
            if (!dialog.isPushing)
                return

            dialog.finishPush(ok, message)
        }
    }

    contentItem: ColumnLayout {
        clip: true
        spacing: 14

        Text {
            objectName: "viewPushStatusMessage"
            Layout.fillWidth: true
            text: dialog.messageText
            color: dialog.previewText === "" ? Theme.textDisabled : Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
            clip: true
        }

        ProgressBar {
            objectName: "viewPushProgress"
            Layout.fillWidth: true
            visible: dialog.isPreviewing || dialog.isPushing
            indeterminate: true
        }

        ConfigurationPreviewPane {
            objectName: "viewPushConfigurationPreview"
            Layout.fillWidth: true
            Layout.fillHeight: true
            previewText: dialog.isPreviewing
                         ? "Preparing configuration preview..."
                         : dialog.previewText
            emptyText: "No configuration required for Push."
            previewColor: dialog.isPreviewing || dialog.previewText !== ""
                          ? Theme.textPrimary : Theme.textDisabled
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                Layout.fillWidth: true
                text: dialog.hostIp
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                elide: Text.ElideRight
            }

            StandardButton {
                objectName: "viewPushCancelButton"
                text: "Cancel"
                type: "Text"
                enabled: !dialog.isPushing && !dialog.isPreviewing
                onClicked: dialog.reject()
            }

            StandardButton {
                text: "Refresh"
                icon.source: AppAssets.actionDatabaseReload
                type: "Secondary"
                enabled: !dialog.isPushing && !dialog.isPreviewing
                onClicked: dialog.openPreview()
            }

            StandardButton {
                text: dialog.isPushing ? "Pushing..." : (dialog.isPreviewing ? "Preparing..." : "Push")
                icon.source: AppAssets.actionPush
                type: "Primary"
                enabled: !dialog.isPushing && !dialog.isPreviewing && dialog.previewText !== ""
                onClicked: dialog.pushNow()
            }
        }
    }
}
