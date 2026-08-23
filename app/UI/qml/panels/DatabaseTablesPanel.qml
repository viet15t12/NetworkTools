pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import UI

Item {
    id: root
    objectName: "databaseTablesPanel"

    signal tableSelected(string tableName)

    property var tables: []
    property var tableGroups: []
    property var expandedGroups: ({})
    property string selectedTable: ""
    property int filteredTableCount: 0
    readonly property var knownGroupKeys: {
        const seen = {}
        const keys = []
        for (let i = 0; i < tables.length; ++i) {
            const key = groupMetadata(tables[i]).key
            if (!seen[key]) {
                seen[key] = true
                keys.push(key)
            }
        }
        return keys.sort()
    }
    readonly property bool allDatabaseGroupsCollapsed: {
        if (knownGroupKeys.length === 0)
            return false
        for (let i = 0; i < knownGroupKeys.length; ++i) {
            if (groupExpanded(knownGroupKeys[i]))
                return false
        }
        return true
    }
    readonly property bool allDatabaseGroupsExpanded: {
        if (knownGroupKeys.length === 0)
            return false
        for (let i = 0; i < knownGroupKeys.length; ++i) {
            if (!groupExpanded(knownGroupKeys[i]))
                return false
        }
        return true
    }
    readonly property var toolsBackend: typeof externalTools !== "undefined" && externalTools !== null
                                        ? externalTools
                                        : null

    function groupMetadata(tableName) {
        const match = /^t(\d{2})(?:_|$)/i.exec(String(tableName || ""))
        const code = match ? match[1] : "Other"
        const labels = {
            "01": "Device Inventory",
            "02": "Router Interface",
            "03": "DHCP & Helper",
            "04": "Routing",
            "05": "Security & NAT",
            "06": "Layer 2 Switching",
            "08": "FHRP",
            "09": "VTP",
            "10": "Syslog Configuration",
            "11": "NAT Insights",
            "12": "Syslog"
        }
        const icons = {
            "01": AppAssets.deviceRouter,
            "02": AppAssets.navigationInterface,
            "03": AppAssets.fileTypeDatabase,
            "04": AppAssets.navigationTopology,
            "05": AppAssets.fileTypeKey,
            "06": AppAssets.deviceSwitch,
            "07": AppAssets.deviceNetworkVpn,
            "08": AppAssets.deviceRouter,
            "09": AppAssets.deviceSwitch,
            "10": AppAssets.navigationSyslog,
            "11": AppAssets.deviceNetworkVpn,
            "12": AppAssets.navigationSyslog
        }
        const colors = {
            "01": Theme.notificationInfoAccent,
            "02": Theme.syntaxInterface,
            "03": Theme.syntaxInside,
            "04": Theme.syntaxPrefix,
            "05": Theme.alertWarning,
            "06": Theme.alertSuccess,
            "07": Theme.syntaxOutside,
            "08": Theme.syntaxBoolean,
            "09": Theme.syntaxNumber,
            "10": Theme.notificationInfoAccent,
            "11": Theme.syntaxOutside,
            "12": Theme.notificationInfoAccent
        }
        return {
            "key": code,
            "title": labels[code] ? code + " - " + labels[code] : code,
            "icon": icons[code] || AppAssets.fileTypeDatabase,
            "color": colors[code] || Theme.panelSideBarTextSecondary
        }
    }

    function rebuildGroups() {
        const query = searchBar.text.toLowerCase().trim()
        let grouped = {}
        let count = 0
        for (let i = 0; i < tables.length; i++) {
            const tableName = String(tables[i])
            const metadata = groupMetadata(tableName)
            if (query !== ""
                    && tableName.toLowerCase().indexOf(query) === -1
                    && metadata.title.toLowerCase().indexOf(query) === -1) {
                continue
            }
            if (!grouped[metadata.key])
                grouped[metadata.key] = {
                    "key": metadata.key,
                    "title": metadata.title,
                    "icon": metadata.icon,
                    "color": metadata.color,
                    "tables": []
                }
            grouped[metadata.key].tables.push(tableName)
            count++
        }

        const keys = Object.keys(grouped).sort()
        let groups = []
        for (let j = 0; j < keys.length; j++)
            groups.push(grouped[keys[j]])
        tableGroups = groups
        filteredTableCount = count
    }

    function reloadTables() {
        if (toolsBackend === null) {
            tables = []
            tableGroups = []
            selectedTable = ""
            filteredTableCount = 0
            return
        }
        tables = toolsBackend.getDatabaseTables()
        rebuildGroups()
        if (selectedTable === "" || tables.indexOf(selectedTable) === -1)
            selectedTable = tables.length > 0 ? tables[0] : ""
    }

    function groupExpanded(groupKey) {
        return expandedGroups[groupKey] === undefined ? true : expandedGroups[groupKey]
    }

    function rememberGroupExpanded(groupKey, expanded) {
        const next = Object.assign({}, expandedGroups)
        next[groupKey] = expanded
        expandedGroups = next
    }

    function setAllDatabaseGroupsExpanded(expanded) {
        const next = Object.assign({}, expandedGroups)
        for (let i = 0; i < knownGroupKeys.length; ++i)
            next[knownGroupKeys[i]] = expanded
        expandedGroups = next
    }

    function collapseAllDatabaseGroups() {
        setAllDatabaseGroupsExpanded(false)
    }

    function expandAllDatabaseGroups() {
        setAllDatabaseGroupsExpanded(true)
    }

    function openDatabaseGroupContext(sceneX, sceneY) {
        databaseGroupContextMenu.openAt(sceneX, sceneY)
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.panelSideBarBackground
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 36

            Text {
                objectName: "databasePanelHeaderTitle"
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.right: reloadButton.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: "TABLE"
                elide: Text.ElideRight
                color: Theme.panelSideBarTextSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.capitalization: Font.AllUppercase
                font.weight: Font.Medium
            }

            IconButton {
                id: reloadButton
                objectName: "databasePanelReloadButton"
                anchors.right: parent.right
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                buttonSize: Theme.sideBarFeatureIcon
                iconSource: AppAssets.actionRefresh
                idleColor: Theme.panelSideBarTextSecondary
                activeColor: Theme.panelSideBarTextPrimary
                selectedBackground: Theme.panelSideBarItemSelected
                hoverBackground: Theme.panelSideBarItemHover
                tooltip: "Reload Tables"
                enabled: root.toolsBackend !== null
                onClicked: root.reloadTables()
            }
        }

        SideBarSearch {
            id: searchBar
            Layout.fillWidth: true
            Layout.leftMargin: 8
            Layout.rightMargin: 8
            Layout.bottomMargin: 8
            placeholderText: "Search tables..."
            onTextChanged: root.rebuildGroups()
        }

        ScrollView {
            id: tableScrollView
            objectName: "databaseGroupScrollView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            padding: 0
            leftPadding: 0
            rightPadding: 0
            topPadding: 0
            bottomPadding: 0
            contentWidth: width
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            Column {
                width: tableScrollView.width

                Repeater {
                    id: databaseGroupRepeater
                    objectName: "databaseGroupRepeater"
                    model: root.tableGroups

                    delegate: DatabaseTableSection {
                        required property int index
                        required property var modelData

                        width: tableScrollView.width
                        groupKey: modelData.key
                        sectionTitle: modelData.title
                        groupIcon: modelData.icon
                        groupColor: modelData.color
                        tables: modelData.tables
                        selectedTable: root.selectedTable
                        expanded: root.groupExpanded(modelData.key)
                        onExpansionChanged: function(value) {
                            root.rememberGroupExpanded(groupKey, value)
                        }
                        onGroupContextRequested: function(sceneX, sceneY) {
                            root.openDatabaseGroupContext(sceneX, sceneY)
                        }
                        onTableClicked: function(tableName) {
                            root.selectedTable = tableName
                        }
                    }
                }

                Text {
                    visible: root.filteredTableCount === 0
                    text: root.tables.length === 0 ? "No tables found." : "No matching tables."
                    color: Theme.panelSideBarTextSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    leftPadding: 12
                    rightPadding: 12
                    topPadding: 6
                }

                Item { width: 1; height: 8 }
            }
        }
    }

    PanelGroupContextMenu {
        id: databaseGroupContextMenu
        parent: Overlay.overlay
        canCollapseAll: root.knownGroupKeys.length > 0
                        && !root.allDatabaseGroupsCollapsed
        canExpandAll: root.knownGroupKeys.length > 0
                      && !root.allDatabaseGroupsExpanded
        onCollapseAllRequested: root.collapseAllDatabaseGroups()
        onExpandAllRequested: root.expandAllDatabaseGroups()
    }

    Connections {
        target: root.toolsBackend
        function onBrowserChanged() { root.reloadTables() }
    }

    onToolsBackendChanged: reloadTables()
    onSelectedTableChanged: if (selectedTable !== "") tableSelected(selectedTable)

    Component.onCompleted: {
        reloadTables()
        if (selectedTable !== "")
            tableSelected(selectedTable)
    }
}
