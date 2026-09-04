pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls.Basic
import QtQuick.Effects
import UI

StatefulWindow {
    id: root
    visible: true
    title: (workspaceDisplayName !== ""
            ? workspaceDisplayName
              + (workspaceBackend !== null && workspaceBackend.dirty ? " *" : "")
              + " - CAMS"
            : "CAMS")

    // =====================================================================
    // 1. PROPERTIES (Trạng thái và Cờ điều khiển)
    // =====================================================================
    property bool sidebarVisible: true
    property int unreadNotifications: 0
    property bool isDoNotDisturb: false
    readonly property int notificationHistoryCount: notificationHistoryModel.count
    property string activeSettingKey: "theme"
    property bool statusTaskVisible: false
    property bool statusTaskBusy: false
    property bool statusTaskOk: true
    property string statusTaskMessage: ""
    property real statusTaskProgress: -1
    property string activeDatabaseTable: ""
    // Populated only after a real .ntp project has been opened or created.
    property string workspaceDisplayName: ""
    property string workspacePath: ""
    property string pendingRollbackSnapshotId: ""
    property string pendingWelcomeMode: ""
    property bool pendingQuit: false
    property bool allowWindowClose: false
    property bool nativePresenterFailed: false
    property var terminalStates: ({})

    readonly property var welcomeBackend:
        typeof welcomeController !== "undefined" ? welcomeController : null
    readonly property var workspaceBackend:
        typeof workspaceSaveController !== "undefined" ? workspaceSaveController : null
    readonly property bool backendWantsNativeMenu:
        typeof menuPresentation !== "undefined"
        && menuPresentation !== null
        && menuPresentation.isGlobalActive
    readonly property bool useModernCustomMenu:
        !root.backendWantsNativeMenu || root.nativePresenterFailed
    readonly property bool nativeMenuOwnsShortcuts:
        root.backendWantsNativeMenu
        && !root.nativePresenterFailed
        && nativeMenuHost.ready

    function requestWelcome(mode) {
        if (root.welcomeBackend === null)
            return false
        root.welcomeBackend.requestWelcome(mode)
        return true
    }

    function transitionToWelcome(mode) {
        if (root.pendingQuit)
            return false
        root.pendingWelcomeMode = mode || ""
        if (root.workspaceBackend !== null && root.workspaceBackend.hasWorkspace) {
            const accepted = root.workspaceBackend.requestCloseWorkspace()
            if (!accepted)
                root.pendingWelcomeMode = ""
            return accepted
        }
        return root.requestWelcome(root.pendingWelcomeMode)
    }

    function requestQuit() {
        if (root.pendingQuit)
            return true
        if (root.workspaceBackend !== null && root.workspaceBackend.hasWorkspace) {
            root.pendingQuit = true
            root.pendingWelcomeMode = ""
            const accepted = root.workspaceBackend.requestCloseWorkspace()
            if (!accepted)
                root.pendingQuit = false
            return accepted
        }
        root.allowWindowClose = true
        Qt.quit()
        return true
    }

    function prepareForWindowHide() {
        // Move focus away from TextInput/TextEdit while the Wayland surface is
        // still valid, before Python hides this top-level window.
        titleDragArea.forceActiveFocus(Qt.OtherFocusReason)
    }

    function toggleMaximized() {
        if (root.visibility === Window.Maximized)
            root.showNormal()
        else
            root.showMaximized()
    }

    SnapshotHistoryDialog {
        id: snapshotHistoryDialog
        snapshots: root.workspaceBackend !== null
                   ? root.workspaceBackend.snapshots
                   : []
        onCreateRequested: label => {
            if (root.workspaceBackend !== null)
                root.workspaceBackend.createSnapshot(label)
        }
        onRollbackRequested: (snapshotId, label) => {
            root.pendingRollbackSnapshotId = snapshotId
            rollbackConfirmationDialog.messageText =
                "Roll back the workspace to ‘" + label + "’? "
                + "CAMS will create a pinned safety snapshot first."
            rollbackConfirmationDialog.open()
        }
    }

    SftpMessageDialog {
        id: rollbackConfirmationDialog
        titleText: "Roll Back Workspace"
        confirmation: true
        acceptText: "Roll Back"
        onAccepted: {
            if (root.workspaceBackend !== null)
                root.workspaceBackend.rollbackSnapshot(root.pendingRollbackSnapshotId)
            root.pendingRollbackSnapshotId = ""
        }
        onRejected: root.pendingRollbackSnapshotId = ""
    }

    Connections {
        target: root.workspaceBackend
        enabled: root.workspaceBackend !== null

        function onNotificationRequested(message, type) {
            root.recordNotification(message, type, true)
        }

        function onWorkspaceCloseCompleted() {
            if (root.pendingQuit) {
                root.pendingQuit = false
                root.allowWindowClose = true
                Qt.quit()
                return
            }
            const mode = root.pendingWelcomeMode
            root.pendingWelcomeMode = ""
            root.requestWelcome(mode)
        }

        function onSaveFailed(_message) {
            root.pendingQuit = false
            root.pendingWelcomeMode = ""
        }
    }

    // VS Code SidebarPart uses a 170 px minimum and snap=true. Its SplitView
    // collapses/restores after crossing half that minimum instead of rendering
    // unusably narrow intermediate widths.
    property real savedSidebarWidth: Math.max(Theme.sideBarWidth, minSidebarWidth)
    property real sidebarWidth: savedSidebarWidth
    readonly property real minSidebarWidth: 170
    readonly property real maxSidebarWidth: 600
    readonly property real effectiveMaxSidebarWidth: Math.max(
        minSidebarWidth,
        Math.min(
            maxSidebarWidth,
            root.width - Theme.activityBarWidth
            - Theme.splitHandleWidth - Theme.minimumWorkspaceWidth
        )
    )
    readonly property real workspaceContentWidth: Math.max(
        0,
        root.width - Theme.activityBarWidth
        - (root.sidebarVisible ? root.sidebarWidth + Theme.splitHandleWidth : 0)
    )
    readonly property real sidebarSnapThreshold: minSidebarWidth / 2
    property string selectedSyslogHost: ""
    property bool syslogWorkspaceLoaded: false

    readonly property bool isDeviceMode: activityBar.appMode === "devices"
    readonly property bool isSftpMode: activityBar.appMode === "sftp"
    readonly property bool isSyslogMode: activityBar.appMode === "syslog"
    readonly property bool isIndependentMode: false
    readonly property int visibleStatusBarHeight: StatusBarState.isVisible ? Theme.statusBarHeight : 0
    readonly property bool textInputHasFocus: root.activeFocusItem !== null
                                              && (root.activeFocusItem instanceof TextInput
                                                  || root.activeFocusItem instanceof TextEdit)

    onIsSyslogModeChanged: {
        if (root.isSyslogMode)
            root.syslogWorkspaceLoaded = true
    }

    function attachPersistentSettingsBackends() {
        ThemeState.backend = typeof themeSettings !== "undefined" ? themeSettings : null
        StatusBarState.backend = typeof statusBarSettings !== "undefined" ? statusBarSettings : null
        LanguageState.backend = typeof languageSettings !== "undefined" ? languageSettings : null
    }

    function clampSidebarWidth(width) {
        return Math.min(
            effectiveMaxSidebarWidth,
            Math.max(minSidebarWidth, Number(width))
        )
    }

    function showSidebar() {
        if (isIndependentMode)
            return
        sidebarWidth = clampSidebarWidth(savedSidebarWidth)
        sidebarVisible = true
    }

    function hideSidebar(rememberCurrentWidth) {
        if (rememberCurrentWidth !== false && sidebarVisible) {
            savedSidebarWidth = clampSidebarWidth(sidebarWidth)
        }
        sidebarVisible = false
        sidebarWidth = savedSidebarWidth
    }

    function toggleSidebar() {
        if (sidebarVisible)
            hideSidebar(true)
        else
            showSidebar()
    }

    function applySidebarDragWidth(desiredWidth) {
        const desired = Number(desiredWidth)
        if (!isFinite(desired))
            return

        if (desired < sidebarSnapThreshold) {
            hideSidebar(false)
            return
        }

        sidebarWidth = clampSidebarWidth(desired)
        sidebarVisible = true
    }

    function finishSidebarResize(desiredWidth) {
        if (sidebarVisible) {
            const desired = Number(desiredWidth)
            savedSidebarWidth = isFinite(desired)
                ? clampSidebarWidth(desired)
                : clampSidebarWidth(sidebarWidth)
            sidebarWidth = savedSidebarWidth
        } else {
            sidebarWidth = savedSidebarWidth
        }
    }

    onEffectiveMaxSidebarWidthChanged: {
        if (root.sidebarVisible)
            root.sidebarWidth = root.clampSidebarWidth(root.savedSidebarWidth)
    }

    function setDoNotDisturb(enabled) {
        const nextState = enabled === true
        if (root.isDoNotDisturb === nextState)
            return
        root.isDoNotDisturb = nextState
        if (nextState)
            root.dismissVisibleToasts()
    }

    function dismissVisibleToasts() {
        toastManager.clearToasts()
    }

    function canShowToast() {
        return !root.isDoNotDisturb && !notificationPanel.visible
    }

    function recordNotificationEntry(msg, type, showToast, actionLabel, actionId, actionData, source) {
        const message = LanguageState.text(String(msg || ""))
        if (message === "")
            return
        const normalizedType = String(type !== undefined ? type : "info").toLowerCase()
        const normalizedActionLabel = LanguageState.text(String(actionLabel || ""))
        const normalizedActionId = String(actionId || "")
        const normalizedActionData = String(actionData || "")
        const normalizedSource = String(source || "")
        const hasPrimaryAction = normalizedActionLabel !== "" && normalizedActionId !== ""
        const timestamp = new Date().toLocaleTimeString(Qt.locale(), "HH:mm:ss")
        notificationHistoryModel.insert(0, {
            "msgText": message,
            "msgType": normalizedType,
            "timestamp": timestamp,
            "actionLabel": normalizedActionLabel,
            "actionId": normalizedActionId,
            "actionData": normalizedActionData,
            "sourceText": normalizedSource
        })
        if (!notificationPanel.visible)
            root.unreadNotifications++
        if (showToast !== false && root.canShowToast()) {
            if (hasPrimaryAction) {
                toastManager.showActionToast(
                    message,
                    normalizedType,
                    normalizedActionLabel,
                    normalizedActionId,
                    normalizedActionData,
                    normalizedSource
                )
            } else {
                toastManager.showToast(message, normalizedType)
            }
        }
    }

    function recordNotification(msg, type, showToast) {
        root.recordNotificationEntry(msg, type, showToast, "", "", "", "")
    }

    function recordActionNotification(msg, type, showToast, actionLabel, actionId, actionData, source) {
        root.recordNotificationEntry(
            msg,
            type,
            showToast,
            actionLabel,
            actionId,
            actionData,
            source
        )
    }

    function openSettingsSection(settingKey) {
        const key = String(settingKey || "")
        if (key === "")
            return false
        activityBar.activateSettings()
        root.activeSettingKey = key
        panelSideBar.selectSetting(key)
        if (notificationPanel.visible)
            notificationPanel.close()
        return true
    }

    function executeNotificationAction(actionId, actionData) {
        const normalizedActionId = String(actionId || "")
        if (normalizedActionId === "open-settings")
            return root.openSettingsSection(actionData)
        return false
    }

    function executeHistoryNotificationAction(actionId, actionData, notificationIndex) {
        const handled = root.executeNotificationAction(actionId, actionData)
        if (notificationIndex >= 0 && notificationIndex < notificationHistoryModel.count)
            notificationHistoryModel.remove(notificationIndex)
        return handled
    }

    function executeToastNotificationAction(actionId, actionData) {
        const handled = root.executeNotificationAction(actionId, actionData)
        for (let i = 0; i < notificationHistoryModel.count; i++) {
            const item = notificationHistoryModel.get(i)
            if (item.actionId === actionId && item.actionData === actionData) {
                notificationHistoryModel.remove(i)
                root.unreadNotifications = Math.max(0, root.unreadNotifications - 1)
                break
            }
        }
        return handled
    }

    function showExternalToolsConfigurationNotification(message, type) {
        root.recordActionNotification(
            message,
            type,
            true,
            "Open External Tools",
            "open-settings",
            "external_tools",
            "External Tools"
        )
    }

    function handleTaskStarted(source, message) {
        taskStatusClearTimer.stop()
        root.statusTaskVisible = true
        root.statusTaskBusy = true
        root.statusTaskOk = true
        root.statusTaskMessage = LanguageState.text(String(message || ""))
        root.statusTaskProgress = -1
    }

    function handleTaskProgress(source, message) {
        root.statusTaskVisible = true
        root.statusTaskBusy = true
        root.statusTaskMessage = LanguageState.text(String(message || ""))
    }

    function handleTaskFinished(source, ok, message) {
        const type = ok ? "success" : "error"
        recordNotification(message, type, false)
        root.statusTaskVisible = true
        root.statusTaskBusy = false
        root.statusTaskOk = ok
        root.statusTaskMessage = LanguageState.text(String(message || ""))
        root.statusTaskProgress = 1
        taskStatusClearTimer.restart()
    }

    function openDeviceCli(host) {
        const targetHost = String(host || "").trim()
        if (targetHost === "") {
            statusBar.showMessage("Select a device before opening CLI.", "warning")
            return false
        }
        if (typeof cli === "undefined" || cli === null || !cli.openDeviceTerminal) {
            statusBar.showMessage("CAMS Terminal backend is not available.", "error")
            return false
        }

        // The backend starts or focuses the separately rendered companion terminal.
        const result = cli.openDeviceTerminal(targetHost)
        const ok = result && result.ok === true
        const message = result && result.message
                      ? String(result.message)
                      : (ok
                         ? "CAMS Terminal opened for " + targetHost + "."
                         : "Failed to open CAMS Terminal for " + targetHost + ".")
        statusBar.showMessage(message, ok ? "success" : "error")
        return ok
    }

    function terminalStateFor(host) {
        const targetHost = String(host || "").trim()
        if (targetHost === "")
            return "closed"
        if (terminalStates[targetHost] !== undefined)
            return String(terminalStates[targetHost])
        if (typeof cli !== "undefined" && cli !== null && cli.deviceTerminalState)
            return String(cli.deviceTerminalState(targetHost) || "closed")
        return "closed"
    }

    function recordTerminalState(host, state) {
        const next = Object.assign({}, terminalStates)
        next[String(host || "")] = String(state || "closed")
        terminalStates = next
    }

    readonly property bool activeHostConfigEnabled: {
        if (deviceTabs.activeUid === "") return false
        for (let i = 0; i < panelSideBar.allDevices.length; i++) {
            if (panelSideBar.allDevices[i].ip === deviceTabs.activeUid) {
                return panelSideBar.allDevices[i].status !== "waiting"
            }
        }
        return true
    }

    // =====================================================================
    // 2. NON-VISUAL COMPONENTS (Models, Shortcuts, Dialogs, Toasts)
    // =====================================================================
    ListModel {
        id: notificationHistoryModel
    }

    Timer {
        id: taskStatusClearTimer
        interval: 5000
        repeat: false
        onTriggered: {
            root.statusTaskVisible = false
            root.statusTaskMessage = ""
            root.statusTaskProgress = -1
        }
    }

    CommandRegistry {
        id: commandRegistry
        objectName: "appCommandRegistry"
        commandsEnabled: !UiState.windowLock
        shortcutDispatchEnabled: !root.nativeMenuOwnsShortcuts
        shortcutContextActive: root.visible && root.active
        inputFocusActive: root.textInputHasFocus
        workspaceAvailable: root.workspaceBackend !== null
                            && root.workspaceBackend.hasWorkspace
        workspaceBusy: root.workspaceBackend !== null
                       && root.workspaceBackend.busy
        saveAvailable: workspaceAvailable
        snapshotAvailable: workspaceAvailable
        reloadAvailable: root.isSftpMode || contentArea.reloadCommandEnabled
        sidebarAvailable: !root.isIndependentMode
        sftpAvailable: true
        systemLogsAvailable: true
        databaseAvailable: activityBar.canActivateDatabase

        newProjectHandler: function() { return root.transitionToWelcome("create") }
        openProjectHandler: function() { return root.transitionToWelcome("open") }
        saveHandler: function() { return root.workspaceBackend.requestManualSave() }
        createSnapshotHandler: function() {
            snapshotHistoryDialog.openForCreate()
            return true
        }
        snapshotHistoryHandler: function() {
            snapshotHistoryDialog.open()
            return true
        }
        closeWorkspaceHandler: function() {
            return root.transitionToWelcome("")
        }
        quitHandler: function() { return root.requestQuit() }
        reloadHandler: function() {
            if (root.isSftpMode && sftpWorkspaceLoader.item)
                return sftpWorkspaceLoader.item.refreshActive()
            return contentArea.triggerReloadCommand()
        }
        toggleSidebarHandler: function() {
            root.toggleSidebar()
            return true
        }
        dashboardHandler: function() { return activityBar.activateDevices() }
        sftpHandler: function() { return activityBar.activateSftp(false) }
        systemLogsHandler: function() { return activityBar.activateSystemLogs() }
        databaseHandler: function() { return activityBar.activateDatabase(false) }
        settingsHandler: function() { return activityBar.activateSettings() }
        shortcutGuideHandler: function() {
            shortcutReferenceDialog.open()
            return true
        }
        aboutHandler: function() {
            aboutWindow.open()
            return true
        }
    }

    onClosing: close => {
        root.saveWindowState()
        if (root.allowWindowClose)
            return
        close.accepted = false
        root.requestQuit()
    }

    Shortcut {
        sequence: "Ctrl+`"
        context: Qt.ApplicationShortcut
        enabled: root.isDeviceMode && deviceTabs.activeUid !== "" && !UiState.windowLock
        onActivated: root.openDeviceCli(deviceTabs.activeUid)
    }

    NativeMenuHost {
        id: nativeMenuHost
        registry: commandRegistry
        ownerWindow: root
        requested: root.backendWantsNativeMenu

        onLoadFailed: function(failureMessage) {
            root.nativePresenterFailed = true
            if (typeof menuPresentation !== "undefined"
                    && menuPresentation !== null
                    && typeof menuPresentation.reportNativeFailure === "function") {
                menuPresentation.reportNativeFailure(failureMessage)
            }
        }
    }

    AboutWindow {
        id: aboutWindow
        transientParent: root
    }

    ShortcutReferenceDialog {
        id: shortcutReferenceDialog
    }

    ToastManager {
        id: toastManager
        objectName: "mainToastManager"
        onActionTriggered: function(actionId, actionData) {
            root.executeToastNotificationAction(actionId, actionData)
        }
    }

    Component.onCompleted: attachPersistentSettingsBackends()

    NotificationPanel {
        id: notificationPanel
        x: root.width - width - 12
        y: root.height - height - root.visibleStatusBarHeight - 8
        model: notificationHistoryModel
        doNotDisturb: root.isDoNotDisturb

        onAboutToShow: {
            root.unreadNotifications = 0
            root.dismissVisibleToasts()
        }
        onClearAllRequested: {
            notificationHistoryModel.clear()
            root.unreadNotifications = 0
        }
        onToggleDndRequested: root.setDoNotDisturb(!root.isDoNotDisturb)
        onActionTriggered: function(actionId, actionData, notificationIndex) {
            root.executeHistoryNotificationAction(
                actionId,
                actionData,
                notificationIndex
            )
        }
        onDismissRequested: function(notificationIndex) {
            if (notificationIndex >= 0
                    && notificationIndex < notificationHistoryModel.count) {
                notificationHistoryModel.remove(notificationIndex)
            }
        }
    }

    Connections {
        target: typeof cli !== "undefined" ? cli : null
        function onTaskStarted(message) { root.handleTaskStarted("cli", message) }
        function onTaskProgress(message) { root.handleTaskProgress("cli", message) }
        function onTaskFinished(ok, message) { root.handleTaskFinished("cli", ok, message) }
        function onTerminalStateChanged(host, state) {
            root.recordTerminalState(host, state)
            if (state === "open")
                statusBar.showMessage("CAMS Terminal is ready for " + host + ".", "success")
            else if (state === "error")
                statusBar.showMessage("CAMS Terminal failed for " + host + ".", "error")
        }
        function onTerminalError(host, message) {
            root.recordNotification(
                "Terminal " + host + ": " + String(message || "Unknown error"),
                "error",
                false
            )
        }
        function onBatchProgress(batchId, completed, success, failed, total) {
            const count = Math.max(0, Number(total || 0))
            if (count <= 0)
                return
            const done = Math.max(0, Math.min(count, Number(completed || 0)))
            root.statusTaskVisible = true
            root.statusTaskBusy = true
            root.statusTaskProgress = done / count
            root.statusTaskMessage = "Processing devices · " + done + " of " + count
        }
    }

    Connections {
        target: typeof dbManager !== "undefined" ? dbManager : null
        function onTaskStarted(message) { root.handleTaskStarted("db", message) }
        function onTaskProgress(message) { root.handleTaskProgress("db", message) }
        function onTaskFinished(ok, message) { root.handleTaskFinished("db", ok, message) }
    }

    // =====================================================================
    // 3. MAIN UI LAYOUT
    // =====================================================================
    ColumnLayout {
        id: mainWorkspace
        anchors.fill: parent
        spacing: 0
        layer.enabled: UiState.windowLock
        layer.smooth: true
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: 0.28
            blurMax: 32
            saturation: -0.10
        }

        Rectangle {
            id: customTitleBar
            objectName: "workspaceTitleBar"
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.windowTitleHeight
            color: Theme.activityBarBackground

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.borderWidth
                color: Theme.activityBarBorderColor
            }

            RowLayout {
                anchors.fill: parent
                spacing: 0

                Loader {
                    id: modernMenuLoader
                    objectName: "modernMenuLoader"
                    active: root.useModernCustomMenu
                    visible: active
                    Layout.preferredWidth: active && item ? item.implicitWidth : 0
                    Layout.fillHeight: true

                    sourceComponent: Component {
                        ModernMenuBar {
                            objectName: "modernMenuBar"
                            width: implicitWidth
                            height: parent ? parent.height : implicitHeight
                            registry: commandRegistry
                        }
                    }
                }

                Item {
                    id: titleDragArea
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    Text {
                        anchors.centerIn: parent
                        width: Math.min(implicitWidth, parent.width - Theme.spacing16)
                        text: root.title
                        color: Theme.activityBarTextSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        elide: Text.ElideMiddle
                        horizontalAlignment: Text.AlignHCenter
                    }

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        onDoubleClicked: root.toggleMaximized()
                    }

                    DragHandler {
                        target: null
                        acceptedButtons: Qt.LeftButton
                        onActiveChanged: if (active) root.startSystemMove()
                    }
                }

                Button {
                    id: minimizeButton
                    objectName: "windowMinimizeButton"
                    Layout.preferredWidth: 46
                    Layout.fillHeight: true
                    padding: 0
                    hoverEnabled: true
                    Accessible.name: "Minimize window"
                    onClicked: root.showMinimized()
                    contentItem: ThemedIcon {
                        iconSource: AppAssets.windowControlMinimize
                        iconSize: Theme.iconSizeNormal
                        iconColor: Theme.activityBarTextPrimary
                    }
                    background: Rectangle {
                        color: minimizeButton.hovered || minimizeButton.down
                               ? Theme.activityBarItemHover : "transparent"
                    }
                }

                Button {
                    id: maximizeButton
                    objectName: "windowMaximizeButton"
                    Layout.preferredWidth: 46
                    Layout.fillHeight: true
                    padding: 0
                    hoverEnabled: true
                    Accessible.name: root.visibility === Window.Maximized
                                     ? "Restore window" : "Maximize window"
                    onClicked: root.toggleMaximized()
                    contentItem: ThemedIcon {
                        iconSource: AppAssets.windowControlRestore
                        iconSize: Theme.iconSizeNormal
                        iconColor: Theme.activityBarTextPrimary
                    }
                    background: Rectangle {
                        color: maximizeButton.hovered || maximizeButton.down
                               ? Theme.activityBarItemHover : "transparent"
                    }
                }

                Button {
                    id: closeWindowButton
                    objectName: "windowCloseButton"
                    Layout.preferredWidth: 46
                    Layout.fillHeight: true
                    padding: 0
                    hoverEnabled: true
                    Accessible.name: "Close window"
                    onClicked: root.close()
                    contentItem: ThemedIcon {
                        iconSource: AppAssets.windowControlClose
                        iconSize: Theme.iconSizeNormal
                        iconColor: closeWindowButton.hovered
                                   ? "#FFFFFF" : Theme.activityBarTextPrimary
                    }
                    background: Rectangle {
                        color: closeWindowButton.hovered || closeWindowButton.down
                               ? "#C42B1C" : "transparent"
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            ActivityBar {
                id: activityBar
                Layout.preferredWidth: Theme.activityBarWidth
                Layout.fillHeight: true
                onToggleSidebarRequested: root.toggleSidebar()
                onShowSidebarRequested: root.showSidebar()
                onSftpOpenMessage: function(message, type, settingsKey) {
                    if (settingsKey === "external_tools")
                        root.showExternalToolsConfigurationNotification(message, type)
                    else
                        statusBar.showMessage(message, type)
                }
                onDatabaseOpenMessage: function(message, type, settingsKey) {
                    if (message === "")
                        return
                    if (settingsKey === "external_tools")
                        root.showExternalToolsConfigurationNotification(message, type)
                    else
                        statusBar.showMessage(message, type)
                }

            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: !root.isIndependentMode

                PanelSideBar {
                    id: panelSideBar
                    objectName: "mainPanelSideBar"
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: root.sidebarVisible ? root.sidebarWidth : 0

                    // Keep the component alive at width 0 while collapsed so
                    // its view state survives snap and Ctrl+B toggles.
                    visible: true
                    enabled: root.sidebarVisible
                    opacity: root.sidebarVisible ? 1.0 : 0.0
                    clip: true
                    Accessible.ignored: !root.sidebarVisible

                    appMode: activityBar.appMode
                    hasActiveTabs: deviceTabs.tabCount > 0

                    onDevicesLoaded: function(devices) {
                        const rows = devices || []
                        const validIps = rows.map(function(d) { return d && d.ip ? d.ip : d })
                        deviceTabs.initializeTabs(validIps)
                        deviceTabs.updateDeviceMetadata(rows)
                    }
                    onDeviceSelected: (ip, name, deviceType, status) => deviceTabs.openTab(ip, name, deviceType, status)
                    onDeviceDeleted: (ip) => deviceTabs.closeTabByUid(ip)
                    onSettingSelected: function(key) {
                        root.activeSettingKey = key
                    }
                    onDatabaseTableSelected: function(tableName) {
                        root.activeDatabaseTable = tableName
                    }
                    onSyslogHostSelected: host => root.selectedSyslogHost = host
                    onSyslogOperationFinished: function(ok, message) {
                        statusBar.showMessage(message, ok ? "success" : "error")
                    }
                }

                Rectangle {
                    id: sidebarDivider
                    x: root.sidebarVisible ? root.sidebarWidth : 0
                    width: root.sidebarVisible ? Theme.splitHandleWidth : 0
                    height: parent.height
                    visible: root.sidebarVisible
                    color: Theme.contentBackground

                    Rectangle {
                        anchors.left: parent.left
                        width: 1
                        height: parent.height
                        color: Theme.borderColor
                    }

                    Rectangle {
                        anchors.left: parent.left
                        width: 2
                        height: parent.height
                        color: Theme.statusBarBackground
                        visible: sidebarResizeArea.containsMouse
                                 || sidebarResizeArea.pressed
                    }
                }

    ColumnLayout {
                    anchors.left: sidebarDivider.right
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    spacing: 0

                    DeviceTabs {
                        id: deviceTabs
                        Layout.fillWidth: true
                        Layout.preferredHeight: (tabCount > 0 && root.isDeviceMode) ? Theme.tabBarHeight : 0
                        visible: Layout.preferredHeight > 0
                        clip: true
                        activeContentLoading: contentArea.activeViewLoading

                        Behavior on Layout.preferredHeight {
                            NumberAnimation { duration: Theme.animationDurationSlow; easing.type: Easing.OutQuad }
                        }

                        onTabCountChanged: {
                            if (tabCount === 0)
                                panelSideBar.activeHost = ""
                        }
                        onOpenNewDeviceRequested: {
                            if (!UiState.windowLock) {
                                UiState.windowLock = true
                                panelSideBar.openNewDeviceWindow()
                            }
                        }
                        onActiveTabChanged: function(uid) {
                            panelSideBar.selectDeviceByIp(uid)
                        }
                    }

                    FeatureBar {
                        id: featureBar
                        Layout.fillWidth: true
                        Layout.preferredHeight: Theme.featureBarHeight
                        visible: deviceTabs.tabCount > 0 && root.isDeviceMode
                        enabled: root.activeHostConfigEnabled
                        opacity: root.activeHostConfigEnabled ? 1.0 : 0.45

                        Behavior on Layout.preferredHeight { NumberAnimation { duration: Theme.animationDurationSlow; easing.type: Easing.OutQuad } }

                        activeMain: deviceTabs.currentFMain
                        activeText: deviceTabs.currentFText
                        deviceType: deviceTabs.activeDeviceType
                        terminalState: root.terminalStateFor(deviceTabs.activeUid)

                        onUserChangedFeature: function(mIdx, tIdx) {
                            deviceTabs.setFeatureForActiveTab(mIdx, tIdx)
                            Qt.callLater(function() {
                                contentArea.requestActivationReload("feature-bar")
                            })
                        }
                        onCliOpenRequested: root.openDeviceCli(deviceTabs.activeUid)
                    }

                    ContentArea {
                        id: contentArea
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: !root.isSyslogMode && !root.isSftpMode

                        tabCount: deviceTabs.tabCount
                        activeMainFeature: deviceTabs.currentFMain
                        activeTextFeature: deviceTabs.currentFText
                        currentHostIp: deviceTabs.activeUid
                        deviceRole: deviceTabs.activeDeviceType
                        appMode: activityBar.appMode
                        hostConfigEnabled: root.activeHostConfigEnabled
                        activeSettingKey: root.activeSettingKey
                        activeDatabaseTable: root.activeDatabaseTable
                    }

                    Loader {
                        id: syslogWorkspaceLoader
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        active: root.syslogWorkspaceLoaded
                        asynchronous: true
                        visible: root.isSyslogMode
                        sourceComponent: Component {
                            SyslogWorkspace {
                                selectedHost: root.selectedSyslogHost
                                onResetHostRequested: {
                                    root.selectedSyslogHost = ""
                                    panelSideBar.selectSyslogHost("")
                                }
                                onOperationMessage: function(ok, message) {
                                    statusBar.showMessage(message, ok ? "success" : "error")
                                }
                            }
                        }
                    }

                    Loader {
                        id: sftpWorkspaceLoader
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        active: root.isSftpMode
                        visible: active
                        sourceComponent: Component {
                            SftpView {
                                backend: typeof sftpController !== "undefined"
                                         ? sftpController : null
                            }
                        }
                    }
                }
            }
        }

        StatusBar {
            id: statusBar
            Layout.fillWidth: true
            Layout.preferredHeight: root.visibleStatusBarHeight
            visible: StatusBarState.isVisible

            unreadCount: root.unreadNotifications
            isDND: root.isDoNotDisturb
            isNotificationOpen: notificationPanel.visible
            pythonStatusText: panelSideBar.pythonDepsStatusText
            pythonStatusType: panelSideBar.pythonDepsStatus
            pythonStatusDetail: panelSideBar.pythonDepsStatusDetail
            pythonStatusBusy: panelSideBar.pythonDepsChecking
            taskVisible: root.statusTaskVisible
            taskBusy: root.statusTaskBusy
            taskOk: root.statusTaskOk
            taskMessage: root.statusTaskMessage
            taskProgress: root.statusTaskProgress

            onBellClicked: {
                if (notificationPanel.visible)
                    notificationPanel.close()
                else
                    notificationPanel.open()
            }
            onPythonStatusClicked: panelSideBar.triggerPythonCheck()

            function showMessage(msg, type) {
                root.recordNotification(msg, type !== undefined ? type : "info", true)
            }

            function showActionMessage(msg, type, actionLabel, actionId, actionData, source) {
                root.recordActionNotification(
                    msg,
                    type !== undefined ? type : "info",
                    true,
                    actionLabel,
                    actionId,
                    actionData,
                    source
                )
            }
        }
    }

    // A persistent grab area spans both visible and collapsed states. This
    // lets one drag gesture cross the snap threshold in either direction,
    // matching VS Code's SplitView behavior.
    MouseArea {
        id: sidebarResizeArea
        objectName: "sidebarResizeArea"
        x: activityBar.x + activityBar.width
           + (root.sidebarVisible ? root.sidebarWidth : 0) - width / 2
        y: customTitleBar.height
        width: 8
        height: activityBar.height
        z: 700
        visible: !root.isIndependentMode
        enabled: visible && !UiState.windowLock
        hoverEnabled: true
        cursorShape: Qt.SplitHCursor

        property real dragStartPointerX: 0
        property real dragStartSidebarWidth: 0
        property real dragDesiredSidebarWidth: 0

        function pointerSceneX(mouse) {
            const point = sidebarResizeArea.mapToItem(null, mouse.x, mouse.y)
            return point.x
        }

        onPressed: function(mouse) {
            dragStartPointerX = pointerSceneX(mouse)
            dragStartSidebarWidth = root.sidebarVisible ? root.sidebarWidth : 0
            dragDesiredSidebarWidth = dragStartSidebarWidth
            if (root.sidebarVisible)
                root.savedSidebarWidth = root.clampSidebarWidth(root.sidebarWidth)
        }

        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            dragDesiredSidebarWidth = dragStartSidebarWidth
                                      + pointerSceneX(mouse) - dragStartPointerX
            root.applySidebarDragWidth(dragDesiredSidebarWidth)
        }

        onReleased: root.finishSidebarResize(dragDesiredSidebarWidth)
        onCanceled: root.finishSidebarResize(dragDesiredSidebarWidth)

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 2
            height: parent.height
            color: Theme.statusBarBackground
            visible: sidebarResizeArea.containsMouse || sidebarResizeArea.pressed
        }
    }

    Rectangle {
        id: modalWindowScrim
        anchors.fill: parent
        z: 800
        visible: UiState.windowLock && !root.active
        color: Theme.dialogOverlay
        opacity: visible ? 0.46 : 0.0

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.animationDurationFast
                easing.type: Easing.OutCubic
            }
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
        }
    }

    // Frameless windows retain native resize behavior through Qt's system
    // resize API. Corners sit above edges so diagonal resizing wins there.
    MouseArea {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: 5
        z: 1000
        enabled: root.visibility === Window.Windowed
        cursorShape: Qt.SizeHorCursor
        onPressed: root.startSystemResize(Qt.LeftEdge)
    }
    MouseArea {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: 5
        z: 1000
        enabled: root.visibility === Window.Windowed
        cursorShape: Qt.SizeHorCursor
        onPressed: root.startSystemResize(Qt.RightEdge)
    }
    MouseArea {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 5
        z: 1000
        enabled: root.visibility === Window.Windowed
        cursorShape: Qt.SizeVerCursor
        onPressed: root.startSystemResize(Qt.TopEdge)
    }
    MouseArea {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 5
        z: 1000
        enabled: root.visibility === Window.Windowed
        cursorShape: Qt.SizeVerCursor
        onPressed: root.startSystemResize(Qt.BottomEdge)
    }
    MouseArea {
        anchors { left: parent.left; top: parent.top }
        width: 8
        height: 8
        z: 1001
        enabled: root.visibility === Window.Windowed
        cursorShape: Qt.SizeFDiagCursor
        onPressed: root.startSystemResize(Qt.LeftEdge | Qt.TopEdge)
    }
    MouseArea {
        anchors { right: parent.right; top: parent.top }
        width: 8
        height: 8
        z: 1001
        enabled: root.visibility === Window.Windowed
        cursorShape: Qt.SizeBDiagCursor
        onPressed: root.startSystemResize(Qt.RightEdge | Qt.TopEdge)
    }
    MouseArea {
        anchors { left: parent.left; bottom: parent.bottom }
        width: 8
        height: 8
        z: 1001
        enabled: root.visibility === Window.Windowed
        cursorShape: Qt.SizeBDiagCursor
        onPressed: root.startSystemResize(Qt.LeftEdge | Qt.BottomEdge)
    }
    MouseArea {
        anchors { right: parent.right; bottom: parent.bottom }
        width: 8
        height: 8
        z: 1001
        enabled: root.visibility === Window.Windowed
        cursorShape: Qt.SizeFDiagCursor
        onPressed: root.startSystemResize(Qt.RightEdge | Qt.BottomEdge)
    }
}
