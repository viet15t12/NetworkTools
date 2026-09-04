pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "externalToolsSettings"
    color: Theme.contentBackground

    property string activePage: "Applications"
    property var tools: []
    property var discoveredTools: []
    property var applicationRows: []
    property var selectedCandidate: null
    property string selectedCategory: "SSH Client"
    property string selectedKey: ""
    property string selectedApp: ""
    property string editorMode: "empty" // empty | configured | detected | custom
    property string savedSignature: ""
    property string messageText: ""
    property string messageType: "info"
    property string detectionSource: ""
    property string detectionConfidence: ""
    property string detectionDefaultFor: ""
    property bool discoveryPending: false
    property bool advancedExpanded: false
    property var pathValidation: ({
        "ok": false,
        "exists": false,
        "path": "",
        "message": "Choose an application to continue."
    })

    readonly property var categoryModel: [
        {
            "type": "SSH Client",
            "title": "SSH Client",
            "description": "Open a device CLI over SSH",
            "icon": AppAssets.navigationTerminal
        },
        {
            "type": "DB Browser",
            "title": "DB Browser",
            "description": "Open the CAMS SQLite database",
            "icon": AppAssets.navigationDatabaseSearch
        },
        {
            "type": "SFTP Client",
            "title": "SFTP Client",
            "description": "Transfer files over SFTP",
            "icon": AppAssets.navigationSftp
        },
        {
            "type": "Terminal",
            "title": "Terminal",
            "description": "Choose a terminal host, not a shell",
            "icon": AppAssets.navigationTerminal
        }
    ]
    readonly property bool compactLayout: width < 920
    readonly property bool editorVisible: editorMode !== "empty"
    readonly property bool isConfiguredEditor: editorMode === "configured"
    readonly property bool argumentsUnsafe: safeText(arguments.text).toLowerCase().indexOf("{password}") !== -1
    readonly property bool duplicateName: hasDuplicateAppName(appName.text)
    readonly property bool formValid: editorVisible
                                      && safeText(appName.text).trim() !== ""
                                      && pathValidation.ok === true
                                      && !argumentsUnsafe
                                      && !duplicateName
    readonly property bool dirty: editorVisible && formSignature() !== savedSignature
    readonly property bool canSave: formValid
                                    && (dirty || editorMode === "detected" || editorMode === "custom")
                                    && toolsBackend !== null
    readonly property int suggestedCount: applicationRows.filter(function(row) {
        return row.configured !== true
    }).length
    readonly property var toolsBackend: typeof externalTools !== "undefined" && externalTools !== null
                                        ? externalTools
                                        : null

    function safeText(value) {
        return value === undefined || value === null ? "" : String(value)
    }

    function normalizedPath(value) {
        return safeText(value).replace(/\\/g, "/").toLowerCase()
    }

    function defaultArgumentsForType(toolType) {
        if (toolType === "SSH Client")
            return "{ip}"
        if (toolType === "SFTP Client")
            return "sftp://{username}@{ip}:{port}{path}"
        if (toolType === "DB Browser")
            return "{db}"
        return ""
    }

    function placeholderHelpForType(toolType) {
        if (toolType === "SSH Client")
            return "Available placeholders: {ip} and {username}. Passwords are never passed on the command line."
        if (toolType === "SFTP Client")
            return "Available placeholders: {ip}, {port}, {username}, and {path}. Passwords are never passed on the command line. CAMS uses its built-in SFTP client when no external application is active."
        if (toolType === "DB Browser")
            return "Use {db} where the database path should be inserted. CAMS includes its own database browser."
        return "Optional arguments passed when the terminal host starts."
    }

    function categoryDescription() {
        if (selectedCategory === "SSH Client")
            return "Choose the application CAMS uses to open device CLI sessions."
        if (selectedCategory === "DB Browser")
            return "Choose the application used to inspect the local SQLite database."
        if (selectedCategory === "SFTP Client")
            return "Choose an external SFTP application, or keep using the client built into CAMS."
        return "Choose one terminal host such as Windows Terminal or Command Prompt. PowerShell is a shell and is not listed separately."
    }

    function hasBuiltInSupport(toolType) {
        return toolType === "DB Browser" || toolType === "SFTP Client"
    }

    function previewCommand() {
        const rawPath = safeText(executable.text).trim()
        const quotedPath = rawPath.indexOf(" ") !== -1 ? "\"" + rawPath + "\"" : rawPath
        let previewArgs = safeText(arguments.text)
        previewArgs = previewArgs.replace(/\{ip\}/gi, "192.0.2.10")
        previewArgs = previewArgs.replace(/\{port\}/gi, "22")
        previewArgs = previewArgs.replace(/\{username\}/gi, "network-admin")
        previewArgs = previewArgs.replace(/\{path\}/gi, "/configs")
        previewArgs = previewArgs.replace(/\{db\}/gi, "C:\\…\\device_network.db")
        previewArgs = previewArgs.replace(/\{password\}/gi, "[BLOCKED]")
        return (quotedPath + (previewArgs.trim() !== "" ? " " + previewArgs.trim() : "")).trim()
    }

    function formSignature() {
        return JSON.stringify([
            safeText(appName.text).trim(),
            selectedCategory,
            safeText(executable.text).trim(),
            safeText(arguments.text),
            enabledToggle.checked === true,
            safeText(description.text)
        ])
    }

    function captureSignature() {
        savedSignature = formSignature()
    }

    function setMessage(text, type) {
        messageText = String(text || "")
        messageType = String(type || "info")
    }

    function notify(text, type) {
        setMessage(text, type)
        if (typeof statusBar !== "undefined" && statusBar !== null)
            statusBar.showMessage(text, type)
    }

    function hasDuplicateAppName(value) {
        const candidate = safeText(value).trim().toLowerCase()
        if (candidate === "")
            return false
        for (let i = 0; i < tools.length; i++) {
            const existing = safeText(tools[i].app).trim().toLowerCase()
            if (existing === candidate && existing !== safeText(selectedApp).toLowerCase())
                return true
        }
        return false
    }

    function configuredTool(app) {
        for (let i = 0; i < tools.length; i++) {
            if (safeText(tools[i].app) === safeText(app))
                return tools[i]
        }
        return null
    }

    function activeApplicationForType(appType) {
        for (let i = 0; i < tools.length; i++) {
            const tool = tools[i]
            if (tool.type === appType && (tool.enabled === 1 || tool.enabled === true))
                return safeText(tool.app)
        }
        return ""
    }

    function rowKey(row) {
        return safeText(row.type) + "|" + normalizedPath(row.executable)
                + "|" + safeText(row.app).trim().toLowerCase()
    }

    function configuredRowKey(row) {
        return normalizedPath(row.executable)
                + "|" + safeText(row.app).trim().toLowerCase()
    }

    function rebuildApplicationRows(selectPreferred) {
        const rows = []
        const paths = ({})
        const appPaths = ({})
        for (let i = 0; i < discoveredTools.length; i++) {
            const detected = discoveredTools[i]
            if (detected.type !== selectedCategory)
                continue
            const row = {
                "kind": "detected",
                "key": rowKey(detected),
                "app": detected.app,
                "type": detected.type,
                "executable": detected.executable,
                "arguments": detected.arguments || defaultArgumentsForType(detected.type),
                "description": detected.description || "",
                "source": detected.source || "Operating system",
                "confidence": detected.confidence || "",
                "isDefault": detected.isDefault === true,
                "explicitDefault": detected.explicitDefault === true,
                "defaultFor": detected.defaultFor || [],
                "configured": false,
                "enabled": false,
                "isAmbiguous": detected.isAmbiguous === true
            }
            const executablePath = normalizedPath(row.executable)
            appPaths[configuredRowKey(row)] = rows.length
            paths[executablePath] = paths[executablePath] === undefined
                    ? rows.length
                    : -1
            rows.push(row)
        }

        for (let i = 0; i < tools.length; i++) {
            const tool = tools[i]
            if (tool.type !== selectedCategory)
                continue
            const appPath = configuredRowKey(tool)
            const executablePath = normalizedPath(tool.executable)
            let rowIndex = appPaths[appPath]
            if (rowIndex === undefined && paths[executablePath] >= 0)
                rowIndex = paths[executablePath]
            if (rowIndex !== undefined && rowIndex >= 0) {
                rows[rowIndex].kind = "configured"
                rows[rowIndex].app = tool.app
                rows[rowIndex].arguments = tool.arguments || ""
                rows[rowIndex].description = tool.description || rows[rowIndex].description
                rows[rowIndex].configured = true
                rows[rowIndex].enabled = tool.enabled === 1 || tool.enabled === true
            } else {
                const row = {
                    "kind": "configured",
                    "key": rowKey(tool),
                    "app": tool.app,
                    "type": tool.type,
                    "executable": tool.executable,
                    "arguments": tool.arguments || "",
                    "description": tool.description || "",
                    "source": "Saved configuration",
                    "confidence": "",
                    "isDefault": false,
                    "explicitDefault": false,
                    "defaultFor": [],
                    "configured": true,
                    "enabled": tool.enabled === 1 || tool.enabled === true,
                    "isAmbiguous": false
                }
                appPaths[appPath] = rows.length
                if (paths[executablePath] === undefined)
                    paths[executablePath] = rows.length
                rows.push(row)
            }
        }

        rows.sort(function(left, right) {
            const leftRank = left.enabled ? 0 : (left.isDefault ? 1 : (left.configured ? 2 : 3))
            const rightRank = right.enabled ? 0 : (right.isDefault ? 1 : (right.configured ? 2 : 3))
            if (leftRank !== rightRank)
                return leftRank - rightRank
            return safeText(left.app).localeCompare(safeText(right.app))
        })
        for (let i = 0; i < rows.length; i++) {
            rows[i].section = rows[i].enabled
                    ? "Current selection"
                    : (rows[i].isDefault
                       ? "Operating system default"
                       : (rows[i].configured ? "Other configured apps" : "Suggested apps"))
        }
        applicationRows = rows

        if (editorMode === "custom" && selectPreferred !== true)
            return
        let preferred = null
        if (selectPreferred !== true && selectedKey !== "") {
            for (let i = 0; i < rows.length; i++) {
                if (rows[i].key === selectedKey) {
                    preferred = rows[i]
                    break
                }
            }
        }
        if (preferred === null) {
            for (let i = 0; i < rows.length; i++) {
                if (rows[i].enabled) {
                    preferred = rows[i]
                    break
                }
            }
        }
        if (preferred === null) {
            for (let i = 0; i < rows.length; i++) {
                if (rows[i].isDefault) {
                    preferred = rows[i]
                    break
                }
            }
        }
        if (preferred === null && rows.length > 0)
            preferred = rows[0]
        if (preferred !== null)
            loadApplication(preferred)
        else
            clearEditor()
    }

    function refreshTools() {
        tools = toolsBackend !== null ? (toolsBackend.getTools() || []) : []
        rebuildApplicationRows(false)
    }

    function discoverTools() {
        if (toolsBackend === null || !toolsBackend.discoverExternalTools) {
            discoveredTools = []
            rebuildApplicationRows(true)
            return
        }
        discoveryPending = true
        discoveryTimer.restart()
    }

    function selectCategory(category) {
        selectedCategory = category
        selectedKey = ""
        selectedApp = ""
        editorMode = "empty"
        setMessage("", "info")
        rebuildApplicationRows(true)
    }

    function clearEditor() {
        editorMode = "empty"
        selectedCandidate = null
        selectedKey = ""
        selectedApp = ""
        appName.text = ""
        executable.text = ""
        arguments.text = ""
        description.text = ""
        enabledToggle.checked = false
        advancedExpanded = false
        detectionSource = ""
        detectionConfidence = ""
        detectionDefaultFor = ""
        pathValidation = {
            "ok": false,
            "exists": false,
            "path": "",
            "message": "Choose an application to continue."
        }
        captureSignature()
    }

    function loadApplication(row) {
        if (!row)
            return
        selectedCandidate = row
        selectedKey = row.key
        selectedApp = row.configured ? safeText(row.app) : ""
        editorMode = row.configured ? "configured" : "detected"
        appName.text = safeText(row.app)
        executable.text = safeText(row.executable)
        arguments.text = safeText(row.arguments || defaultArgumentsForType(selectedCategory))
        description.text = safeText(row.description)
        enabledToggle.checked = row.enabled === true || row.configured !== true
        advancedExpanded = false
        detectionSource = safeText(row.source)
        detectionConfidence = safeText(row.confidence)
        detectionDefaultFor = (row.defaultFor || []).join(", ")
        setMessage(row.isAmbiguous ? "Multiple installations were found. Confirm the application path before saving." : "", row.isAmbiguous ? "warning" : "info")
        validatePath(false)
        Qt.callLater(captureSignature)
    }

    function newCustomApplication() {
        editorMode = "custom"
        selectedCandidate = null
        selectedKey = "custom|" + selectedCategory
        selectedApp = ""
        appName.text = ""
        executable.text = ""
        arguments.text = defaultArgumentsForType(selectedCategory)
        description.text = ""
        enabledToggle.checked = true
        advancedExpanded = false
        detectionSource = "Manual selection"
        detectionConfidence = ""
        detectionDefaultFor = ""
        setMessage("", "info")
        pathValidation = {
            "ok": false,
            "exists": false,
            "path": "",
            "message": "Choose an executable file."
        }
        captureSignature()
    }

    function cancelChanges() {
        if (selectedCandidate !== null && editorMode !== "custom") {
            loadApplication(selectedCandidate)
            return
        }
        clearEditor()
    }

    function clearForm() {
        newCustomApplication()
    }

    function validatePath(normalizePathValue) {
        if (toolsBackend === null || !toolsBackend.validateExecutable) {
            const currentPath = safeText(executable.text).trim()
            pathValidation = {
                "ok": currentPath !== "",
                "exists": false,
                "path": currentPath,
                "message": "Executable validation is not available."
            }
            return pathValidation
        }
        const result = toolsBackend.validateExecutable(safeText(executable.text))
        pathValidation = result
        if (normalizePathValue === true && result.ok && result.path)
            executable.text = result.path
        return result
    }

    function saveCurrentTool() {
        if (toolsBackend === null)
            return
        const validation = validatePath(true)
        if (!validation.ok) {
            setMessage(validation.message || "Choose a valid application.", "error")
            return
        }
        if (duplicateName || argumentsUnsafe) {
            setMessage(duplicateName
                       ? "An application with this name is already configured."
                       : "{password} is blocked because command-line credentials can be exposed.", "error")
            return
        }
        const result = toolsBackend.saveTool(
            appName.text,
            selectedCategory,
            executable.text,
            arguments.text,
            enabledToggle.checked,
            description.text
        )
        if (!result || !result.ok) {
            setMessage(result && result.message ? result.message : "The application could not be saved.", "error")
            return
        }
        const savedApp = safeText(appName.text).trim()
        selectedApp = savedApp
        editorMode = "configured"
        refreshTools()
        notify(enabledToggle.checked
               ? savedApp + " is now used for " + selectedCategory + "."
               : savedApp + " was saved but is not active.", "success")
        discoverTools()
    }

    function deleteSelectedTool() {
        if (toolsBackend === null || selectedApp === "")
            return
        const removed = selectedApp
        if (!toolsBackend.deleteTool(removed)) {
            setMessage("The configured application could not be removed.", "error")
            return
        }
        selectedKey = ""
        selectedApp = ""
        editorMode = "empty"
        refreshTools()
        discoverTools()
        notify("Removed " + removed + " from CAMS.", "success")
    }

    Connections {
        target: root.toolsBackend
        function onToolsChanged() { root.refreshTools() }
    }

    onToolsBackendChanged: {
        refreshTools()
        discoverTools()
    }

    Component.onCompleted: {
        refreshTools()
        discoverTools()
    }

    Timer {
        id: discoveryTimer
        interval: 0
        repeat: false
        onTriggered: {
            try {
                root.discoveredTools = root.toolsBackend.discoverExternalTools() || []
                root.rebuildApplicationRows(true)
            } catch (error) {
                root.discoveredTools = []
                root.setMessage("Application detection failed: " + error, "error")
                root.rebuildApplicationRows(true)
            }
            root.discoveryPending = false
        }
    }

    Timer {
        id: pathValidationTimer
        interval: 220
        repeat: false
        onTriggered: root.validatePath(false)
    }

    FileDialog {
        id: executableDialog
        title: "Choose an application"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Applications (*.exe *.com *.bat *.cmd)", "All files (*)"]
        onAccepted: {
            if (root.editorMode !== "custom")
                root.newCustomApplication()
            const result = root.toolsBackend !== null
                         ? root.toolsBackend.validateExecutable(selectedFile.toString())
                         : ({ "ok": true, "path": selectedFile.toString(), "message": "Selected file." })
            if (result.path) {
                executable.text = result.path
                if (root.safeText(appName.text).trim() === "") {
                    const normalized = root.safeText(result.path).replace(/\\/g, "/")
                    const fileName = normalized.substring(normalized.lastIndexOf("/") + 1)
                    appName.text = fileName.replace(/\.(exe|com|bat|cmd)$/i, "")
                }
            }
            root.pathValidation = result
        }
    }

    StandardDialog {
        id: deleteDialog
        preferredWidth: 420
        implicitHeight: 250
        title: "Remove external tool?"
        closeTooltip: "Close remove confirmation"

        contentItem: Text {
            text: "“%1” will be removed from CAMS. The application itself will not be uninstalled.".arg(root.selectedApp)
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            wrapMode: Text.WordWrap
        }

        footer: Rectangle {
            implicitHeight: 58
            color: "transparent"
            RowLayout {
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing16
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacing8
                StandardButton { text: "Cancel"; type: "Text"; onClicked: deleteDialog.close() }
                StandardButton {
                    text: "Remove"
                    type: "Danger"
                    onClicked: {
                        deleteDialog.close()
                        root.deleteSelectedTool()
                    }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            color: Theme.contentSurface
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacing24
                anchors.rightMargin: Theme.spacing24
                spacing: Theme.spacing16
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: "External Tools"
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeTitle
                        font.family: Theme.fontFamily
                        font.bold: true
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Use operating-system defaults or choose another installed application. CAMS never changes the system default."
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                    }
                }
                StandardButton {
                    objectName: "externalToolsScanButton"
                    text: root.discoveryPending ? "Scanning…" : "Scan again"
                    type: "Secondary"
                    icon.source: AppAssets.actionRefresh
                    enabled: root.toolsBackend !== null && !root.discoveryPending
                    visible: root.activePage === "Applications"
                    onClicked: root.discoverTools()
                }
            }
        }

        SubBar {
            objectName: "externalToolsFeatureBar"
            Layout.fillWidth: true
            tabs: ["Applications", "Suggestion"]
            activeTab: root.activePage
            leftPadding: Theme.spacing16
            onTabClicked: function(tabName) { root.activePage = tabName }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.activePage === "Applications"

            SplitView {
                id: mainSplit
                objectName: "externalToolsMainSplit"
                anchors.fill: parent
                orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
                handle: StandardSplitHandle {}

                Rectangle {
                    SplitView.preferredWidth: root.compactLayout ? mainSplit.width : 280
                    SplitView.minimumWidth: root.compactLayout ? mainSplit.width : 240
                    SplitView.maximumWidth: root.compactLayout ? mainSplit.width : 340
                    SplitView.preferredHeight: root.compactLayout ? 210 : mainSplit.height
                    color: Theme.sideBarBackground

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacing16
                        spacing: Theme.spacing12
                        Text {
                            text: "Application type"
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeLarge
                            font.family: Theme.fontFamily
                            font.bold: true
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "Select what CAMS needs. The application type is fixed by this list."
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeSmall
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                        }
                        ListView {
                            id: categoryList
                            objectName: "externalToolCategoryList"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: Theme.spacing4
                            clip: true
                            model: root.categoryModel
                            delegate: Rectangle {
                                id: categoryRow
                                required property int index
                                required property var modelData
                                width: ListView.view.width
                                height: 82
                                readonly property string activeApplication: root.activeApplicationForType(modelData.type)
                                readonly property bool builtInAvailable: root.hasBuiltInSupport(modelData.type)
                                radius: Theme.radiusSmall
                                color: root.selectedCategory === modelData.type
                                       ? Theme.sideBarItemSelected
                                       : (categoryHover.hovered ? Theme.sideBarItemHover : "transparent")
                                border.color: root.selectedCategory === modelData.type ? Theme.accentColor : "transparent"
                                border.width: Theme.borderWidth
                                Accessible.role: Accessible.ListItem
                                Accessible.name: modelData.title
                                activeFocusOnTab: visible
                                Keys.onReturnPressed: root.selectCategory(modelData.type)
                                Keys.onSpacePressed: root.selectCategory(modelData.type)
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: Theme.spacing12
                                    spacing: Theme.spacing12
                                    ThemedIcon {
                                        iconSource: categoryRow.modelData.icon
                                        iconSize: Theme.iconSizeLarge
                                        iconColor: root.selectedCategory === categoryRow.modelData.type
                                                   ? Theme.accentColor : Theme.textSecondary
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            Layout.fillWidth: true
                                            text: categoryRow.modelData.title
                                            color: Theme.textPrimary
                                            font.pixelSize: Theme.fontSizeNormal
                                            font.family: Theme.fontFamily
                                            font.bold: root.selectedCategory === categoryRow.modelData.type
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: categoryRow.modelData.description
                                            color: Theme.textSecondary
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Theme.spacing4
                                            Rectangle {
                                                Layout.preferredWidth: 6
                                                Layout.preferredHeight: 6
                                                radius: 3
                                                color: categoryRow.activeApplication !== ""
                                                       ? Theme.alertSuccess
                                                       : (categoryRow.builtInAvailable ? Theme.accentColor : Theme.textDisabled)
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: categoryRow.activeApplication !== ""
                                                      ? categoryRow.activeApplication + " in use"
                                                      : (categoryRow.builtInAvailable
                                                         ? "Built into CAMS" : "Not configured")
                                                color: categoryRow.activeApplication !== ""
                                                       ? Theme.alertSuccess
                                                       : (categoryRow.builtInAvailable ? Theme.accentColor : Theme.textDisabled)
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.family: Theme.fontFamily
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }
                                }
                                HoverHandler { id: categoryHover; cursorShape: Qt.PointingHandCursor }
                                TapHandler { onTapped: root.selectCategory(categoryRow.modelData.type) }
                            }
                        }
                    }
                }

                Rectangle {
                    SplitView.fillWidth: true
                    SplitView.fillHeight: true
                    color: Theme.contentBackground

                    ScrollView {
                        id: applicationScroll
                        anchors.fill: parent
                        clip: true
                        contentWidth: availableWidth
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        ScrollBar.vertical.policy: ScrollBar.AsNeeded

                        ColumnLayout {
                            width: applicationScroll.availableWidth
                            spacing: Theme.spacing16

                            Item {
                                Layout.preferredHeight: Theme.spacing4
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: Theme.spacing24
                                Layout.rightMargin: Theme.spacing24
                                spacing: Theme.spacing12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    Text {
                                        text: root.selectedCategory
                                        color: Theme.textPrimary
                                        font.pixelSize: Theme.fontSizeTitle
                                        font.family: Theme.fontFamily
                                        font.bold: true
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.categoryDescription()
                                        color: Theme.textSecondary
                                        font.pixelSize: Theme.fontSizeSmall
                                        font.family: Theme.fontFamily
                                        wrapMode: Text.WordWrap
                                    }
                                }
                                LoadingSpinner {
                                    objectName: "externalToolsDiscoverySpinner"
                                    Layout.preferredWidth: Theme.iconSizeLarge
                                    Layout.preferredHeight: Theme.iconSizeLarge
                                    running: root.discoveryPending
                                }
                                StandardButton {
                                    text: "Default Apps"
                                    type: "Text"
                                    visible: Qt.platform.os === "windows"
                                    onClicked: Qt.openUrlExternally("ms-settings:defaultapps")
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.leftMargin: Theme.spacing24
                                Layout.rightMargin: Theme.spacing24
                                Layout.preferredHeight: Math.max(88, emptyAppsText.implicitHeight + Theme.spacing32)
                                visible: root.applicationRows.length === 0 && !root.discoveryPending
                                color: Theme.contentSurface
                                radius: Theme.radiusMedium
                                border.color: Theme.borderColor
                                border.width: Theme.borderWidth
                                Text {
                                    id: emptyAppsText
                                    anchors.centerIn: parent
                                    width: parent.width - Theme.spacing32
                                    text: "No default or suggested application was found. Choose an executable already installed on this computer."
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeNormal
                                    font.family: Theme.fontFamily
                                    horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.WordWrap
                                }
                            }

                            ListView {
                                id: applicationList
                                objectName: "externalToolsApplicationList"
                                Layout.fillWidth: true
                                Layout.leftMargin: Theme.spacing24
                                Layout.rightMargin: Theme.spacing24
                                Layout.preferredHeight: contentHeight
                                interactive: false
                                spacing: Theme.spacing8
                                model: root.applicationRows
                                section.property: "section"
                                section.criteria: ViewSection.FullString
                                section.delegate: Text {
                                    required property string section
                                    width: ListView.view.width
                                    height: 34
                                    verticalAlignment: Text.AlignBottom
                                    bottomPadding: Theme.spacing8
                                    text: section
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    font.bold: true
                                }
                                delegate: Rectangle {
                                    id: appRow
                                    required property int index
                                    required property var modelData
                                    width: ListView.view.width
                                    height: 76
                                    radius: Theme.radiusMedium
                                    color: root.selectedKey === modelData.key
                                           ? Theme.sideBarItemSelected
                                           : (appHover.hovered ? Theme.sideBarItemHover : Theme.contentSurface)
                                    border.color: root.selectedKey === modelData.key ? Theme.accentColor : Theme.borderColor
                                    border.width: Theme.borderWidth
                                    Accessible.role: Accessible.ListItem
                                    Accessible.name: modelData.app
                                    Accessible.description: modelData.description
                                    activeFocusOnTab: visible
                                    Keys.onReturnPressed: root.loadApplication(modelData)
                                    Keys.onSpacePressed: root.loadApplication(modelData)
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing12
                                        spacing: Theme.spacing12
                                        Rectangle {
                                            Layout.preferredWidth: 38
                                            Layout.preferredHeight: 38
                                            radius: Theme.radiusSmall
                                            color: Theme.contentPanelSurface
                                            border.color: Theme.contentPanelBorder
                                            border.width: Theme.borderWidth
                                            ThemedIcon {
                                                anchors.centerIn: parent
                                                iconSource: root.selectedCategory === "DB Browser"
                                                            ? AppAssets.navigationDatabaseSearch
                                                            : AppAssets.navigationTerminal
                                                iconSize: Theme.iconSizeNormal
                                                iconColor: appRow.modelData.enabled ? Theme.accentColor : Theme.textSecondary
                                            }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 2
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: appRow.modelData.app
                                                    color: Theme.textPrimary
                                                    font.pixelSize: Theme.fontSizeNormal
                                                    font.family: Theme.fontFamily
                                                    font.bold: appRow.modelData.enabled
                                                    elide: Text.ElideRight
                                                }
                                                StandardBadge {
                                                    visible: appRow.modelData.enabled || appRow.modelData.isDefault
                                                    text: appRow.modelData.enabled ? "In use" : "Default"
                                                    badgeColor: appRow.modelData.enabled ? Theme.alertSuccess : Theme.accentEmphasis
                                                }
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: appRow.modelData.isDefault && appRow.modelData.defaultFor.length > 0
                                                      ? "Default for " + appRow.modelData.defaultFor.join(", ")
                                                      : (appRow.modelData.source || appRow.modelData.executable)
                                                color: Theme.textSecondary
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.family: Theme.fontFamily
                                                elide: Text.ElideMiddle
                                            }
                                        }
                                        ThemedIcon {
                                            iconSource: AppAssets.navigationChevronRight
                                            iconSize: Theme.iconSizeSmall
                                            iconColor: Theme.textSecondary
                                        }
                                    }
                                    HoverHandler { id: appHover; cursorShape: Qt.PointingHandCursor }
                                    TapHandler { onTapped: root.loadApplication(appRow.modelData) }
                                }
                            }

                            StandardButton {
                                id: chooseOtherButton
                                objectName: "externalToolsNewButton"
                                Layout.leftMargin: Theme.spacing24
                                text: "Choose another app"
                                type: "Secondary"
                                onClicked: {
                                    root.newCustomApplication()
                                    executableDialog.open()
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.leftMargin: Theme.spacing24
                                Layout.rightMargin: Theme.spacing24
                                Layout.preferredHeight: editorLayout.implicitHeight + Theme.spacing32
                                visible: root.editorVisible
                                color: Theme.contentSurface
                                radius: Theme.radiusMedium
                                border.color: Theme.borderColor
                                border.width: Theme.borderWidth

                                ColumnLayout {
                                    id: editorLayout
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: Theme.spacing16
                                    spacing: Theme.spacing12

                                    RowLayout {
                                        Layout.fillWidth: true
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 2
                                            Text {
                                                text: root.editorMode === "custom" ? "Other application" : root.safeText(appName.text)
                                                color: Theme.textPrimary
                                                font.pixelSize: Theme.fontSizeLarge
                                                font.family: Theme.fontFamily
                                                font.bold: true
                                            }
                                            Text {
                                                text: root.selectedCategory + (root.detectionDefaultFor !== "" ? " · Default for " + root.detectionDefaultFor : "")
                                                color: Theme.textSecondary
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.family: Theme.fontFamily
                                            }
                                            Text {
                                                visible: root.detectionSource !== ""
                                                text: "Detected via " + root.detectionSource
                                                      + (root.detectionConfidence !== ""
                                                         ? " · " + root.detectionConfidence + " confidence" : "")
                                                color: Theme.textDisabled
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.family: Theme.fontFamily
                                            }
                                        }
                                    }

                                    StandardTextField {
                                        id: appName
                                        objectName: "externalToolAppName"
                                        Layout.fillWidth: true
                                        labelText: "Application name"
                                        placeholderText: "Application name"
                                        readOnly: root.editorMode !== "custom"
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: Theme.spacing8
                                        StandardTextField {
                                            id: executable
                                            objectName: "externalToolExecutable"
                                            Layout.fillWidth: true
                                            labelText: "Application path"
                                            placeholderText: "Choose an executable"
                                            onTextEdited: {
                                                root.pathValidation = {
                                                    "ok": false,
                                                    "exists": false,
                                                    "path": text,
                                                    "message": "Checking executable…"
                                                }
                                                pathValidationTimer.restart()
                                            }
                                            onAccepted: root.validatePath(true)
                                        }
                                        StandardButton {
                                            Layout.alignment: Qt.AlignBottom
                                            text: "Browse"
                                            type: "Secondary"
                                            onClicked: executableDialog.open()
                                        }
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: root.pathValidation.message || "Choose an executable."
                                        color: root.pathValidation.ok ? Theme.textSecondary : Theme.alertError
                                        font.pixelSize: Theme.fontSizeSmall
                                        font.family: Theme.fontFamily
                                        wrapMode: Text.WordWrap
                                    }

                                    StandardTextField {
                                        id: description
                                        objectName: "externalToolDescription"
                                        Layout.fillWidth: true
                                        labelText: "Description"
                                        placeholderText: "Optional description"
                                    }

                                    StandardToggleButton {
                                        id: enabledToggle
                                        objectName: "externalToolEnabledToggle"
                                        Layout.fillWidth: true
                                        text: "Use this application for " + root.selectedCategory
                                        description: checked
                                                     ? "Saving makes this the only active application in this category."
                                                     : "Keep the application configured without using it."
                                    }

                                    StandardButton {
                                        text: root.advancedExpanded ? "Hide launch options" : "Launch options"
                                        type: "TextIcon"
                                        icon.source: root.advancedExpanded
                                                     ? AppAssets.navigationChevronDown
                                                     : AppAssets.navigationChevronRight
                                        onClicked: root.advancedExpanded = !root.advancedExpanded
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        visible: root.advancedExpanded
                                        spacing: Theme.spacing8
                                        StandardTextField {
                                            id: arguments
                                            objectName: "externalToolArguments"
                                            Layout.fillWidth: true
                                            labelText: "Arguments"
                                            placeholderText: root.defaultArgumentsForType(root.selectedCategory)
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: root.placeholderHelpForType(root.selectedCategory)
                                            color: root.argumentsUnsafe ? Theme.alertError : Theme.textSecondary
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: Theme.fontFamily
                                            wrapMode: Text.WordWrap
                                        }
                                        StandardButton {
                                            visible: root.defaultArgumentsForType(root.selectedCategory) !== ""
                                            text: "Use recommended"
                                            type: "Text"
                                            onClicked: arguments.text = root.defaultArgumentsForType(root.selectedCategory)
                                        }
                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: Math.max(50, previewText.implicitHeight + Theme.spacing24)
                                            radius: Theme.radiusSmall
                                            color: Theme.contentPanelSurface
                                            border.color: root.argumentsUnsafe ? Theme.alertError : Theme.contentPanelBorder
                                            border.width: Theme.borderWidth
                                            Text {
                                                id: previewText
                                                anchors.fill: parent
                                                anchors.margins: Theme.spacing12
                                                text: root.previewCommand() || "Command preview will appear here."
                                                color: root.argumentsUnsafe ? Theme.alertError : Theme.textSecondary
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.family: "Cascadia Mono"
                                                wrapMode: Text.WrapAnywhere
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: messageRow.implicitHeight + Theme.spacing16
                                        visible: root.messageText !== ""
                                        color: Theme.contentPanelSurface
                                        radius: Theme.radiusSmall
                                        RowLayout {
                                            id: messageRow
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacing8
                                            Text {
                                                Layout.fillWidth: true
                                                text: root.messageText
                                                color: root.messageType === "error" ? Theme.alertError : Theme.textPrimary
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.family: Theme.fontFamily
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: Theme.spacing8
                                        StandardButton {
                                            visible: root.isConfiguredEditor
                                            text: "Remove"
                                            type: "Danger"
                                            onClicked: deleteDialog.open()
                                        }
                                        Item { Layout.fillWidth: true }
                                        StandardButton {
                                            text: "Cancel Changes"
                                            type: "Text"
                                            enabled: root.dirty
                                            onClicked: root.cancelChanges()
                                        }
                                        StandardButton {
                                            objectName: "externalToolSaveButton"
                                            text: enabledToggle.checked ? "Use application" : "Save"
                                            type: "Primary"
                                            icon.source: AppAssets.actionSave
                                            enabled: root.canSave
                                            onClicked: root.saveCurrentTool()
                                        }
                                    }
                                }
                            }

                            Item { Layout.preferredHeight: Theme.spacing24 }
                        }
                    }
                }
            }
        }

        ExternalToolCatalogSettings {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.activePage === "Suggestion"
        }
    }
}
