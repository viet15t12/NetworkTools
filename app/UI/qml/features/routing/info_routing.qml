pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    property string currentHostIp: ""
    property bool isLoading: false
    property string lastError: ""
    property string searchText: ""
    property string activeInfoPage: "Overview"
    property var protocolOptions: ["All protocols"]
    property var protocolBuckets: []
    property int totalRoutes: allRoutes.count
    property int visibleRouteCount: visibleRoutes.count
    property int bestRouteCount: 0
    property string lastCollectedAt: ""
    property string backupConfigText: ""
    property string backupConfigPath: ""
    property string backupConfigError: ""

    color: Theme.contentBackground
    clip: true

    ListModel { id: allRoutes }
    ListModel { id: visibleRoutes }

    function protocolColor(code) {
        const key = String(code || "").toUpperCase()
        if (key === "C") return Theme.alertSuccess
        if (key === "S") return Theme.accentColor
        if (key.indexOf("O") === 0) return Theme.logoOrange
        if (key.indexOf("D") === 0) return Theme.alertWarning
        if (key.indexOf("B") === 0) return Theme.logoBlue
        if (key === "R") return Theme.alertInfo
        return Theme.textSecondary
    }

    function protocolLabel(row) {
        const code = String(row.protocol_code || "").trim()
        const name = String(row.protocol_name || "").trim()
        if (code !== "" && name !== "")
            return code + " · " + name
        return code !== "" ? code : (name !== "" ? name : "Unknown")
    }

    function routePrefix(row) {
        const dest = String(row.destination || "").trim()
        const prefix = String(row.prefix_length || "").trim()
        return prefix === "" ? dest : dest + "/" + prefix
    }

    function routePath(row) {
        const hop = String(row.next_hop || "").trim()
        const iface = String(row.exit_interface || "").trim()
        if (hop !== "" && iface !== "")
            return hop + " via " + iface
        if (hop !== "")
            return hop
        if (iface !== "")
            return iface
        return "connected"
    }

    function adMetricText(row) {
        const ad = String(row.administrative_distance || "")
        const metricText = String(row.metric || "")
        if (ad === "" && metricText === "")
            return "-"
        return ad + "/" + (metricText === "" ? "0" : metricText)
    }

    function rowMatches(row) {
        const protocolFilter = String(protocolFilterBox.currentText || "All protocols")
        const query = root.searchText.toLowerCase().trim()

        if (protocolFilter !== "All protocols" && protocolLabel(row) !== protocolFilter)
            return false
        if (query === "")
            return true

        const haystack = [
            row.protocol_code,
            row.protocol_name,
            row.destination,
            row.prefix_length,
            row.next_hop,
            row.exit_interface,
            row.route_age,
            row.raw_line
        ].join(" ").toLowerCase()
        return haystack.indexOf(query) !== -1
    }

    function rebuildStats() {
        const protocolMap = ({})
        let best = 0
        let latest = ""

        for (let i = 0; i < allRoutes.count; i++) {
            const row = allRoutes.get(i)
            const label = protocolLabel(row)
            protocolMap[label] = (protocolMap[label] || 0) + 1
            if (Number(row.is_best || 0) === 1)
                best += 1
            if (String(row.collected_at || "") > latest)
                latest = String(row.collected_at || "")
        }

        const protocols = Object.keys(protocolMap).sort()
        let maxCount = 1
        for (let p = 0; p < protocols.length; p++)
            maxCount = Math.max(maxCount, protocolMap[protocols[p]])

        root.protocolOptions = ["All protocols"].concat(protocols)
        root.protocolBuckets = protocols.map(function(label) {
            const code = label.split(" ")[0]
            return {
                label: label,
                count: protocolMap[label],
                color: protocolColor(code),
                ratio: protocolMap[label] / maxCount
            }
        })
        root.bestRouteCount = best
        root.lastCollectedAt = latest
    }

    function applyFilters() {
        visibleRoutes.clear()
        for (let i = 0; i < allRoutes.count; i++) {
            const row = allRoutes.get(i)
            if (rowMatches(row))
                visibleRoutes.append(row)
        }
    }

    function loadFromDatabase() {
        allRoutes.clear()
        visibleRoutes.clear()
        root.lastError = ""
        root.backupConfigText = ""
        root.backupConfigPath = ""
        root.backupConfigError = ""
        root.bestRouteCount = 0
        root.lastCollectedAt = ""
        root.protocolBuckets = []
        root.protocolOptions = ["All protocols"]

        const host = String(root.currentHostIp || "").trim()
        if (host === "")
            return

        root.isLoading = true
        const backupPayload = dbManager.getLatestRunningConfig(host)
        const backupOk = backupPayload && (backupPayload.ok === undefined || backupPayload.ok === true)
        root.backupConfigPath = backupPayload && backupPayload.path ? String(backupPayload.path) : ""
        if (backupOk) {
            root.backupConfigText = backupPayload && backupPayload.content ? String(backupPayload.content) : ""
        } else {
            root.backupConfigError = backupPayload && backupPayload.message ? String(backupPayload.message) : "Load running-config backup failed."
        }

        const payload = dbManager.getRoutingInfo(host)
        const ok = payload && (payload.ok === undefined || payload.ok === true)

        if (!ok) {
            root.lastError = payload && payload.message ? String(payload.message) : "Load routing table failed."
            root.isLoading = false
            return
        }

        const rows = payload.routes ? payload.routes : []
        for (let i = 0; i < rows.length; i++)
            allRoutes.append(rows[i])

        rebuildStats()
        applyFilters()
        root.isLoading = false
    }

    onCurrentHostIpChanged: loadFromDatabase()
    Component.onCompleted: loadFromDatabase()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            height: 58
            color: Theme.contentSurface
            border.width: 0

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.borderWidth
                color: Theme.borderColor
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                spacing: Theme.spacing12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "Routing Information"
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeLarge
                        font.family: Theme.fontFamily
                        font.bold: true
                    }

                    Text {
                        text: String(root.currentHostIp || "").trim() === ""
                            ? "No device selected"
                            : root.currentHostIp + (root.lastCollectedAt !== "" ? " · collected " + root.lastCollectedAt : "")
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                StandardButton {
                    text: "Overview"
                    type: root.activeInfoPage === "Overview" ? "Primary" : "Secondary"
                    onClicked: root.activeInfoPage = "Overview"
                }

                StandardButton {
                    text: "Routes"
                    type: root.activeInfoPage === "Routes" ? "Primary" : "Secondary"
                    onClicked: root.activeInfoPage = "Routes"
                }

                StandardButton {
                    text: "Config"
                    type: root.activeInfoPage === "Config" ? "Primary" : "Secondary"
                    onClicked: root.activeInfoPage = "Config"
                }

                StandardButton {
                    text: "Reload UI"
                    icon.source: AppAssets.actionDatabaseReload
                    type: "Secondary"
                    autoCompact: false
                    Layout.minimumWidth: expandedImplicitWidth
                    enabled: !root.isLoading && String(root.currentHostIp || "").trim() !== ""
                    onClicked: root.loadFromDatabase()
                }
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            ColumnLayout {
                width: parent.width
                spacing: Theme.spacing16

                GridLayout {
                    visible: root.activeInfoPage === "Overview"
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.topMargin: visible ? 18 : 0
                    columns: width < 980 ? 2 : 4
                    columnSpacing: Theme.spacing12
                    rowSpacing: Theme.spacing12

                    Repeater {
                        model: [
                            { label: "Routes", value: String(root.totalRoutes), accent: Theme.accentColor },
                            { label: "Visible", value: String(root.visibleRouteCount), accent: Theme.alertInfo },
                            { label: "Best", value: String(root.bestRouteCount), accent: Theme.alertSuccess },
                            { label: "Protocols", value: String(Math.max(0, root.protocolOptions.length - 1)), accent: Theme.logoOrange }
                        ]

                        delegate: Rectangle {
                            required property var modelData

                            Layout.fillWidth: true
                            Layout.preferredHeight: 82
                            radius: Theme.radiusSmall
                            color: Theme.contentPanelSurface
                            border.color: Theme.contentPanelBorder
                            border.width: Theme.borderWidth

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing12
                                spacing: Theme.spacing12

                                Rectangle {
                                    Layout.preferredWidth: 4
                                    Layout.fillHeight: true
                                    radius: 2
                                    color: modelData.accent
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4

                                    Text {
                                        text: modelData.label
                                        color: Theme.textSecondary
                                        font.pixelSize: Theme.fontSizeSmall
                                        font.family: Theme.fontFamily
                                    }

                                    Text {
                                        text: modelData.value
                                        color: Theme.textPrimary
                                        font.pixelSize: Theme.fontSizeTitle
                                        font.family: Theme.fontFamily
                                        font.bold: true
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeInfoPage === "Overview"
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    implicitHeight: chartLayout.implicitHeight + Theme.spacing24
                    radius: Theme.radiusSmall
                    color: Theme.contentPanelSurface
                    border.color: Theme.contentPanelBorder
                    border.width: Theme.borderWidth

                    ColumnLayout {
                        id: chartLayout
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: Theme.spacing12
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Theme.spacing8

                        Text {
                            text: "Protocol Distribution"
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeNormal
                            font.family: Theme.fontFamily
                            font.bold: true
                        }

                        Text {
                            visible: root.protocolBuckets.length === 0
                            text: "No routing entries available."
                            color: Theme.textDisabled
                            font.pixelSize: Theme.fontSizeNormal
                            font.family: Theme.fontFamily
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            topPadding: Theme.spacing12
                            bottomPadding: Theme.spacing12
                        }

                        Repeater {
                            model: root.protocolBuckets

                            delegate: RowLayout {
                                required property var modelData

                                Layout.fillWidth: true
                                spacing: Theme.spacing8

                                Text {
                                    Layout.preferredWidth: 120
                                    text: modelData.label
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    elide: Text.ElideRight
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 10
                                    radius: 5
                                    color: Theme.inputBackground

                                    Rectangle {
                                        anchors.left: parent.left
                                        anchors.top: parent.top
                                        anchors.bottom: parent.bottom
                                        width: Math.max(6, parent.width * Number(modelData.ratio || 0))
                                        radius: 5
                                        color: modelData.color
                                    }
                                }

                                Text {
                                    Layout.preferredWidth: 42
                                    text: String(modelData.count)
                                    color: Theme.textPrimary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    horizontalAlignment: Text.AlignRight
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeInfoPage === "Config"
                    Layout.fillWidth: true
                    Layout.fillHeight: visible
                    Layout.maximumHeight: visible ? 99999 : 0
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.topMargin: visible ? 18 : 0
                    radius: Theme.radiusSmall
                    color: Theme.contentPanelSurface
                    border.color: Theme.contentPanelBorder
                    border.width: Theme.borderWidth

                    ColumnLayout {
                        id: configLayout
                        anchors.fill: parent
                        anchors.margins: Theme.spacing12
                        spacing: Theme.spacing8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing8

                            Text {
                                text: "Running Config Backup"
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fontSizeNormal
                                font.family: Theme.fontFamily
                                font.bold: true
                            }

                            Text {
                                Layout.fillWidth: true
                                text: root.backupConfigPath
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeSmall
                                font.family: Theme.fontFamily
                                elide: Text.ElideLeft
                                horizontalAlignment: Text.AlignRight
                            }

                            StandardButton {
                                objectName: "routingConfigCopyAllButton"
                                Layout.preferredWidth: 104
                                text: routingConfigViewer.copyFeedbackVisible ? "Copied" : "Copy All"
                                icon.source: AppAssets.actionCopy
                                type: "Secondary"
                                enabled: root.backupConfigText !== ""
                                onClicked: routingConfigViewer.copyAll()
                            }
                        }

                        ConfigTextViewer {
                            id: routingConfigViewer
                            objectName: "routingConfigViewer"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 500
                            text: root.backupConfigText
                            sourceLabel: root.backupConfigPath !== ""
                                         ? "Running Config Backup · " + root.backupConfigPath
                                         : "Running Config Backup"
                            errorText: root.backupConfigError
                            emptyText: "No running-config backup is available."
                        }
                    }
                }

                Rectangle {
                    visible: root.activeInfoPage === "Routes"
                    Layout.fillWidth: true
                    Layout.fillHeight: visible
                    Layout.maximumHeight: visible ? 99999 : 0
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.topMargin: visible ? 18 : 0
                    radius: Theme.radiusSmall
                    color: Theme.contentPanelSurface
                    border.color: Theme.contentPanelBorder
                    border.width: Theme.borderWidth

                    ColumnLayout {
                        id: tableLayout
                        anchors.fill: parent
                        spacing: 0

                        GridLayout {
                            Layout.fillWidth: true
                            Layout.margins: Theme.spacing12
                            columns: width < 900 ? 2 : 3
                            columnSpacing: Theme.spacing12
                            rowSpacing: Theme.spacing8

                            StandardTextField {
                                id: searchField
                                Layout.fillWidth: true
                                labelText: "Search"
                                placeholderText: "Destination, next-hop, interface"
                                onTextChanged: {
                                    root.searchText = text
                                    root.applyFilters()
                                }
                            }

                            StandardComboBox {
                                id: protocolFilterBox
                                Layout.fillWidth: true
                                labelText: "Protocol"
                                model: root.protocolOptions
                                onActivated: root.applyFilters()
                            }

                            StandardButton {
                                Layout.alignment: Qt.AlignBottom
                                text: "Clear"
                                type: "Secondary"
                                onClicked: {
                                    searchField.clear()
                                    protocolFilterBox.currentIndex = 0
                                    root.searchText = ""
                                    root.applyFilters()
                                }
                            }
                        }

                        SavedListHeader {
                            Layout.fillWidth: true

                            RowLayout {
                                anchors.fill: parent
                                spacing: Theme.spacing8

                                DataTableCell { Layout.preferredWidth: 104; header: true; text: "Protocol" }
                                DataTableCell { Layout.fillWidth: true; header: true; text: "Prefix" }
                                DataTableCell { Layout.fillWidth: true; header: true; text: "Path" }
                                DataTableCell { Layout.preferredWidth: 80; header: true; text: "AD / Metric"; horizontalAlignment: Text.AlignRight }
                                DataTableCell { Layout.preferredWidth: 74; header: true; text: "Age" }
                                DataTableCell { Layout.preferredWidth: 44; header: true; text: "Best"; horizontalAlignment: Text.AlignHCenter }
                            }
                        }

                        Text {
                            visible: !root.isLoading && visibleRoutes.count === 0
                            Layout.fillWidth: true
                            text: root.lastError !== "" ? root.lastError : "No routing entries match the current view."
                            color: root.lastError !== "" ? Theme.alertError : Theme.textDisabled
                            font.pixelSize: Theme.fontSizeNormal
                            font.family: Theme.fontFamily
                            horizontalAlignment: Text.AlignHCenter
                            topPadding: Theme.spacing24
                            bottomPadding: Theme.spacing24
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0

                            Repeater {
                                model: visibleRoutes

                                delegate: SavedListRow {
                                    id: row
                                    required property var protocol_code
                                    required property var protocol_name
                                    required property var destination
                                    required property var prefix_length
                                    required property var administrative_distance
                                    required property var metric
                                    required property var next_hop
                                    required property var route_age
                                    required property var exit_interface
                                    required property var is_best
                                    required property int index

                                    rowIndex: index
                                    width: tableLayout.width

                                    RowLayout {
                                        anchors.fill: parent
                                        spacing: Theme.spacing8

                                        RowLayout {
                                            Layout.preferredWidth: 104
                                            spacing: Theme.spacing8

                                            Rectangle {
                                                Layout.preferredWidth: 8
                                                Layout.preferredHeight: 8
                                                radius: 4
                                                color: root.protocolColor(row.protocol_code)
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: root.protocolLabel(row)
                                                color: Theme.textPrimary
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.family: Theme.fontFamily
                                                elide: Text.ElideRight
                                            }
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: root.routePrefix(row)
                                            color: Theme.accentColor
                                            font.pixelSize: Theme.fontSizeNormal
                                            font.family: Theme.fontFamily
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: root.routePath(row)
                                            color: Theme.textPrimary
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            Layout.preferredWidth: 80
                                            text: root.adMetricText(row)
                                            color: Theme.textSecondary
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: Theme.fontFamily
                                            horizontalAlignment: Text.AlignRight
                                        }

                                        Text {
                                            Layout.preferredWidth: 74
                                            text: String(row.route_age || "-")
                                            color: Theme.textSecondary
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            Layout.preferredWidth: 44
                                            text: Number(row.is_best || 0) === 1 ? "yes" : ""
                                            color: Theme.alertSuccess
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: Theme.fontFamily
                                            font.bold: true
                                            horizontalAlignment: Text.AlignHCenter
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 18 }
            }
        }
    }
}
