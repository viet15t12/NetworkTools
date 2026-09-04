pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "externalToolCatalogSettings"
    color: Theme.contentBackground

    property var catalog: []
    property var configuredTools: []
    property var applicationRows: []
    property string selectedCategory: "SSH Client"
    property string query: ""

    readonly property bool compactLayout: width < 920
    readonly property var backend: typeof externalTools !== "undefined" && externalTools !== null
                                   ? externalTools
                                   : null
    readonly property var categoryModel: [
        {
            "type": "SSH Client",
            "title": "SSH Client",
            "description": "Remote access applications",
            "icon": AppAssets.navigationTerminal
        },
        {
            "type": "DB Browser",
            "title": "DB Browser",
            "description": "SQLite inspection applications",
            "icon": AppAssets.navigationDatabaseSearch
        },
        {
            "type": "Terminal",
            "title": "Terminal",
            "description": "Terminal hosts",
            "icon": AppAssets.navigationTerminal
        },
        {
            "type": "SFTP Client",
            "title": "SFTP Client",
            "description": "File transfer applications",
            "icon": AppAssets.navigationSftp
        },
        {
            "type": "Packet Capture",
            "title": "Packet Capture",
            "description": "Traffic analysis applications",
            "icon": AppAssets.navigationLogs
        }
    ]
    readonly property var visibleRows: applicationRows
    readonly property int installedCount: catalog.filter(function(row) {
        return row.installed === true
    }).length
    readonly property int configuredCount: catalog.filter(function(row) {
        return row.configured === true
    }).length

    function safeText(value) {
        return value === undefined || value === null ? "" : String(value)
    }

    function categoryIcon(category) {
        for (let i = 0; i < categoryModel.length; i++) {
            if (categoryModel[i].type === category)
                return categoryModel[i].icon
        }
        return AppAssets.navigationTerminal
    }

    function categoryTotal(category) {
        let count = 0
        for (let i = 0; i < catalog.length; i++) {
            if (catalog[i].category === category)
                count += 1
        }
        return count
    }

    function categoryInstalled(category) {
        let count = 0
        for (let i = 0; i < catalog.length; i++) {
            if (catalog[i].category === category && catalog[i].installed === true)
                count += 1
        }
        return count
    }

    function activeApplicationForCategory(category) {
        for (let i = 0; i < configuredTools.length; i++) {
            const tool = configuredTools[i]
            if (tool.type === category && (tool.enabled === 1 || tool.enabled === true))
                return safeText(tool.app)
        }
        return ""
    }

    function hasBuiltInSupport(category) {
        return category === "DB Browser" || category === "SFTP Client"
    }

    function selectCategory(category) {
        selectedCategory = category
        rebuildRows()
    }

    function rebuildRows() {
        const rows = []
        const needle = query.toLowerCase().trim()
        for (let i = 0; i < catalog.length; i++) {
            const source = catalog[i]
            if (source.category !== selectedCategory)
                continue
            const haystack = [source.app, source.summary, source.status]
                .join(" ").toLowerCase()
            if (needle !== "" && haystack.indexOf(needle) === -1)
                continue
            const row = ({})
            for (const key in source)
                row[key] = source[key]
            row.section = source.enabled === true
                    ? "In use"
                    : (source.installed === true ? "Installed apps" : "Not installed")
            rows.push(row)
        }
        rows.sort(function(left, right) {
            const leftRank = left.enabled ? 0 : (left.installed ? 1 : 2)
            const rightRank = right.enabled ? 0 : (right.installed ? 1 : 2)
            if (leftRank !== rightRank)
                return leftRank - rightRank
            return safeText(left.app).localeCompare(safeText(right.app))
        })
        applicationRows = rows
    }

    function reloadCatalog() {
        catalog = root.backend ? (root.backend.getExternalToolCatalog() || []) : []
        configuredTools = root.backend ? (root.backend.getTools() || []) : []
        rebuildRows()
    }

    Connections {
        target: root.backend
        function onToolsChanged() { root.reloadCatalog() }
    }

    onBackendChanged: reloadCatalog()
    Component.onCompleted: reloadCatalog()

    SplitView {
        id: catalogSplit
        objectName: "externalToolCatalogSplit"
        anchors.fill: parent
        orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
        handle: StandardSplitHandle {}

        Rectangle {
            SplitView.preferredWidth: root.compactLayout ? catalogSplit.width : 280
            SplitView.minimumWidth: root.compactLayout ? catalogSplit.width : 240
            SplitView.maximumWidth: root.compactLayout ? catalogSplit.width : 340
            SplitView.preferredHeight: root.compactLayout ? 250 : catalogSplit.height
            color: Theme.sideBarBackground

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacing16
                spacing: Theme.spacing12

                Text {
                    text: "Suggestion"
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeLarge
                    font.family: Theme.fontFamily
                    font.bold: true
                }
                Text {
                    Layout.fillWidth: true
                    text: "Browse supported applications by purpose and installation state."
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    wrapMode: Text.WordWrap
                }

                ListView {
                    id: categoryList
                    objectName: "externalToolCatalogCategoryList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Theme.spacing4
                    clip: true
                    model: root.categoryModel

                    delegate: Rectangle {
                        id: categoryRow
                        required property int index
                        required property var modelData
                        readonly property int installed: root.categoryInstalled(modelData.type)
                        readonly property int total: root.categoryTotal(modelData.type)
                        readonly property string activeApplication: root.activeApplicationForCategory(modelData.type)
                        readonly property bool builtInAvailable: root.hasBuiltInSupport(modelData.type)
                        width: ListView.view.width
                        height: 86
                        radius: Theme.radiusSmall
                        color: root.selectedCategory === modelData.type
                               ? Theme.sideBarItemSelected
                               : (categoryHover.hovered ? Theme.sideBarItemHover : "transparent")
                        border.color: root.selectedCategory === modelData.type
                                      ? Theme.accentColor : "transparent"
                        border.width: Theme.borderWidth
                        Accessible.role: Accessible.ListItem
                        Accessible.name: modelData.title
                        Accessible.description: installed + " of " + total + " installed"
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
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: categoryRow.installed + " of " + categoryRow.total + " installed"
                                    color: categoryRow.installed > 0 ? Theme.textSecondary : Theme.textDisabled
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
                                                 ? "Built into CAMS" : "No app in use")
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
                id: catalogScroll
                anchors.fill: parent
                clip: true
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                ColumnLayout {
                    width: catalogScroll.availableWidth
                    spacing: Theme.spacing16

                    Item { Layout.preferredHeight: Theme.spacing4 }

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
                                text: "Installed applications are listed first. Missing applications only link to their official vendor page."
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeSmall
                                font.family: Theme.fontFamily
                                wrapMode: Text.WordWrap
                            }
                        }
                        StandardBadge {
                            text: root.categoryInstalled(root.selectedCategory)
                                  + " of " + root.categoryTotal(root.selectedCategory) + " installed"
                            badgeColor: root.categoryInstalled(root.selectedCategory) > 0
                                        ? Theme.alertSuccess : Theme.textDisabled
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.spacing24
                        Layout.rightMargin: Theme.spacing24
                        Layout.preferredHeight: 38
                        color: Theme.alertInfoSubtle
                        border.color: Theme.contentPanelBorder
                        border.width: Theme.borderWidth
                        radius: Theme.radiusSmall
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacing12
                            anchors.rightMargin: Theme.spacing12
                            text: "CAMS does not install packages, run package managers, or change operating-system defaults."
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSmall
                            font.family: Theme.fontFamily
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.spacing24
                        Layout.rightMargin: Theme.spacing24
                        spacing: Theme.spacing8
                        StandardTextField {
                            id: catalogSearch
                            objectName: "externalToolCatalogSearchField"
                            Layout.fillWidth: true
                            placeholderText: "Search " + root.selectedCategory.toLowerCase() + "…"
                            onTextEdited: {
                                root.query = text
                                root.rebuildRows()
                            }
                        }
                        StandardButton {
                            text: "Refresh Detection"
                            type: "Secondary"
                            icon.source: AppAssets.actionRefresh
                            onClicked: root.reloadCatalog()
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.spacing24
                        Layout.rightMargin: Theme.spacing24
                        visible: root.applicationRows.length === 0
                        text: root.query.trim() !== ""
                              ? "No applications match the current search."
                              : "No applications are available in this category."
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeNormal
                        font.family: Theme.fontFamily
                        horizontalAlignment: Text.AlignHCenter
                    }

                    ListView {
                        id: applicationList
                        objectName: "externalToolCatalogApplicationList"
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
                            id: toolRow
                            required property int index
                            required property var modelData
                            width: ListView.view.width
                            height: 112
                            radius: Theme.radiusMedium
                            color: modelData.enabled === true
                                   ? Theme.alertSuccessSubtle : Theme.contentSurface
                            border.color: modelData.enabled === true
                                          ? Theme.alertSuccess : Theme.borderColor
                            border.width: Theme.borderWidth
                            opacity: modelData.installed === true ? 1.0 : 0.68

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing12
                                spacing: Theme.spacing12
                                Rectangle {
                                    Layout.preferredWidth: 42
                                    Layout.preferredHeight: 42
                                    radius: Theme.radiusSmall
                                    color: Theme.contentPanelSurface
                                    border.color: Theme.contentPanelBorder
                                    border.width: Theme.borderWidth
                                    ThemedIcon {
                                        anchors.centerIn: parent
                                        iconSource: root.categoryIcon(toolRow.modelData.category)
                                        iconSize: Theme.iconSizeNormal
                                        iconColor: toolRow.modelData.installed === true
                                                   ? Theme.textPrimary : Theme.textDisabled
                                    }
                                }
                                ColumnLayout {
                                    id: toolDetails
                                    Layout.fillWidth: true
                                    spacing: 3
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            Layout.maximumWidth: Math.max(
                                                120,
                                                toolDetails.width - toolStatus.implicitWidth - Theme.spacing24
                                            )
                                            text: root.safeText(toolRow.modelData.app)
                                            color: toolRow.modelData.installed === true
                                                   ? Theme.textPrimary : Theme.textDisabled
                                            font.pixelSize: Theme.fontSizeNormal
                                            font.family: Theme.fontFamily
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        StandardBadge {
                                            id: toolStatus
                                            text: toolRow.modelData.enabled === true
                                                  ? "In use" : root.safeText(toolRow.modelData.status)
                                            badgeColor: toolRow.modelData.enabled === true
                                                        ? Theme.alertSuccess
                                                        : (toolRow.modelData.installed === true
                                                           ? Theme.accentEmphasis : Theme.textDisabled)
                                        }
                                        Item { Layout.fillWidth: true }
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.safeText(toolRow.modelData.summary)
                                        color: toolRow.modelData.installed === true
                                               ? Theme.textSecondary : Theme.textDisabled
                                        font.pixelSize: Theme.fontSizeSmall
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: Theme.spacing8
                                        Text {
                                            Layout.fillWidth: true
                                            text: toolRow.modelData.installed === true
                                                  ? (root.safeText(toolRow.modelData.detectionSource)
                                                     + (root.safeText(toolRow.modelData.executable) !== ""
                                                        ? " · " + root.safeText(toolRow.modelData.executable) : ""))
                                                  : "Not detected on this computer"
                                            color: Theme.textDisabled
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideMiddle
                                        }
                                        StandardButton {
                                            objectName: "externalToolOfficialPageButton"
                                            text: "Official Page"
                                            type: "TextIcon"
                                            icon.source: AppAssets.statusInfo
                                            onClicked: Qt.openUrlExternally(
                                                root.safeText(toolRow.modelData.officialUrl)
                                            )
                                        }
                                    }
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
