pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import UI as App

Item {
    id: root

    required property string host
    property string viewName: "portCounters"
    property var allRows: []
    property int dataRevision: 0
    property string filterText: ""
    property string message: ""

    readonly property bool showingMacTable: viewName === "macTable"
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property bool compactColumns: width < 760
    readonly property string pageTitle: showingMacTable ? "MAC Address Table" : "Port Counters"
    readonly property string pageSubtitle: showingMacTable
        ? "Inspect learned addresses by VLAN and source interface."
        : "Read traffic volume, errors, discards and link transitions at a glance."
    readonly property var summaryMetrics: {
        const revision = root.dataRevision
        return root.buildSummaryMetrics()
    }

    ListModel { id: rowsModel }

    function normalizedCounterRow(row) {
        const source = row || ({})
        return {
            if_name: source.if_name === undefined || source.if_name === null
                     ? "" : String(source.if_name),
            oper_status: source.oper_status === undefined || source.oper_status === null
                         ? "unknown" : String(source.oper_status),
            in_octets: Number(source.in_octets || 0),
            out_octets: Number(source.out_octets || 0),
            in_errors: Number(source.in_errors || 0),
            out_errors: Number(source.out_errors || 0),
            in_discards: Number(source.in_discards || 0),
            out_discards: Number(source.out_discards || 0),
            last_flap: source.last_flap === undefined || source.last_flap === null
                       ? "never" : String(source.last_flap),
            polled_at: source.polled_at === undefined || source.polled_at === null
                       ? "" : String(source.polled_at)
        }
    }

    function normalizedMacRow(row) {
        const source = row || ({})
        return {
            id: Number(source.id || 0),
            mac_addr: source.mac_addr === undefined || source.mac_addr === null
                      ? "" : String(source.mac_addr),
            vlan_id: Number(source.vlan_id || 0),
            if_name: source.if_name === undefined || source.if_name === null
                     ? "" : String(source.if_name),
            mac_type: source.mac_type === undefined || source.mac_type === null
                      ? "unknown" : String(source.mac_type),
            learned_at: source.learned_at === undefined || source.learned_at === null
                        ? "" : String(source.learned_at)
        }
    }

    function normalizedRow(row) {
        return showingMacTable ? normalizedMacRow(row) : normalizedCounterRow(row)
    }

    function formatBytes(value) {
        const amount = Number(value || 0)
        if (!isFinite(amount) || amount <= 0) return "0 B"
        const units = ["B", "KB", "MB", "GB", "TB"]
        const order = Math.min(units.length - 1, Math.floor(Math.log(amount) / Math.log(1024)))
        const scaled = amount / Math.pow(1024, order)
        return (order === 0 ? Math.round(scaled) : scaled.toFixed(scaled >= 10 ? 1 : 2))
                + " " + units[order]
    }

    function uniqueCount(field) {
        const values = ({})
        for (let i = 0; i < allRows.length; i++) {
            const value = String(allRows[i][field] || "")
            if (value !== "") values[value] = true
        }
        return Object.keys(values).length
    }

    function buildSummaryMetrics() {
        if (showingMacTable) {
            let dynamicCount = 0
            for (let i = 0; i < allRows.length; i++) {
                if (String(allRows[i].mac_type || "").toLocaleLowerCase() === "dynamic")
                    dynamicCount += 1
            }
            return [
                { label: "Learned entries", value: allRows.length, tone: "neutral" },
                { label: "VLANs", value: uniqueCount("vlan_id"), tone: "accent" },
                { label: "Interfaces", value: uniqueCount("if_name"), tone: "neutral" },
                { label: "Dynamic", value: dynamicCount, tone: "success" }
            ]
        }

        let linksUp = 0
        let traffic = 0
        let problems = 0
        for (let i = 0; i < allRows.length; i++) {
            const row = allRows[i]
            if (row.oper_status === "up") linksUp += 1
            traffic += Number(row.in_octets || 0) + Number(row.out_octets || 0)
            problems += Number(row.in_errors || 0) + Number(row.out_errors || 0)
                      + Number(row.in_discards || 0) + Number(row.out_discards || 0)
        }
        return [
            { label: "Monitored ports", value: allRows.length, tone: "neutral" },
            { label: "Links up", value: linksUp, tone: "success" },
            { label: "Total traffic", value: formatBytes(traffic), tone: "accent" },
            { label: "Errors + discards", value: problems, tone: problems > 0 ? "danger" : "neutral" }
        ]
    }

    function rowMatches(row, query) {
        if (query === "") return true
        const haystack = showingMacTable
            ? [row.mac_addr, row.vlan_id, row.if_name, row.mac_type, row.learned_at]
            : [row.if_name, row.oper_status, row.last_flap, row.polled_at]
        return haystack.join(" ").toLocaleLowerCase().indexOf(query) !== -1
    }

    function rebuildVisibleRows() {
        const query = String(filterText || "").trim().toLocaleLowerCase()
        rowsModel.clear()
        for (let i = 0; i < allRows.length; i++) {
            const row = normalizedRow(allRows[i])
            if (rowMatches(row, query)) rowsModel.append(row)
        }
        dataRevision += 1
    }

    function load(reason) {
        const rows = showingMacTable
                   ? dbManager.getSwitchMacTable(host)
                   : dbManager.getSwitchPortCounters(host)
        const values = []
        for (let i = 0; i < rows.length; i++) values.push(rows[i])
        allRows = values
        rebuildVisibleRows()
        if (reason === "manual")
            message = showingMacTable ? "MAC table refreshed." : "Port counters refreshed."
    }

    Component.onCompleted: load()
    onHostChanged: load()
    onViewNameChanged: {
        filterText = ""
        load("view-change")
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: root.pageTitle
            subtitle: root.pageSubtitle

            StandardButton {
                text: "Reload UI"
                icon.source: AppAssets.actionDatabaseReload
                autoCompact: false
                Layout.minimumWidth: expandedImplicitWidth
                onClicked: root.load("manual")
            }
        }

        InlineMessage {
            Layout.fillWidth: true
            visible: root.message !== ""
            message: root.message
            severity: "success"
        }

        SwitchSummaryBar {
            Layout.fillWidth: true
            metrics: root.summaryMetrics
        }

        SwitchTableToolbar {
            Layout.fillWidth: true
            title: root.showingMacTable ? "Forwarding entries" : "Interface telemetry"
            totalCount: root.allRows.length
            visibleCount: rowsModel.count
            searchText: root.filterText
            searchPlaceholder: root.showingMacTable
                               ? "Filter MAC, VLAN, interface..."
                               : "Filter interfaces..."
            onSearchEdited: value => {
                root.filterText = value
                root.rebuildVisibleRows()
            }
        }

        DataTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            count: rowsModel.count
            bodyMargins: 0
            emptyTitle: root.filterText !== "" ? "No matching rows"
                        : root.showingMacTable ? "No learned MAC addresses" : "No port counters"
            emptyDescription: root.filterText !== ""
                              ? "Try a broader filter."
                              : "Reload after the selected device has produced monitoring data."
            headerComponent: Component {
                DataTableHeader {
                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 160
                            header: true
                            text: "Interface"
                        }
                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 88
                            header: true
                            text: "Link"
                        }
                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 112
                            header: true
                            text: "Inbound"
                            horizontalAlignment: Text.AlignRight
                        }
                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 112
                            header: true
                            text: "Outbound"
                            horizontalAlignment: Text.AlignRight
                        }
                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 76
                            header: true
                            text: "Errors"
                            horizontalAlignment: Text.AlignRight
                        }
                        DataTableCell {
                            visible: !root.showingMacTable && !root.compactColumns
                            Layout.preferredWidth: 76
                            header: true
                            text: "Discards"
                            horizontalAlignment: Text.AlignRight
                        }
                        DataTableCell {
                            visible: !root.showingMacTable && !root.compactColumns
                            Layout.fillWidth: true
                            header: true
                            text: "Last Flap"
                        }

                        DataTableCell {
                            visible: root.showingMacTable
                            Layout.preferredWidth: 170
                            header: true
                            text: "MAC Address"
                        }
                        DataTableCell {
                            visible: root.showingMacTable
                            Layout.preferredWidth: 74
                            header: true
                            text: "VLAN"
                            horizontalAlignment: Text.AlignHCenter
                        }
                        DataTableCell {
                            visible: root.showingMacTable
                            Layout.fillWidth: true
                            header: true
                            text: "Interface"
                        }
                        DataTableCell {
                            visible: root.showingMacTable
                            Layout.preferredWidth: 96
                            header: true
                            text: "Type"
                        }
                        DataTableCell {
                            visible: root.showingMacTable && !root.compactColumns
                            Layout.preferredWidth: 174
                            header: true
                            text: "Learned At"
                        }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: rowsModel
                spacing: 0
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: DataTableRow {
                    id: row
                    required property int index
                    required property var model

                    width: ListView.view.width
                    height: Theme.tableRowHeight
                    rowIndex: index
                    interactive: false

                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 160
                            primary: true
                            text: String(row.model.if_name || "—")
                        }
                        App.StatusBadge {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 88
                            value: String(row.model.oper_status || "unknown")
                        }
                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 112
                            monospaced: true
                            text: root.formatBytes(row.model.in_octets)
                            horizontalAlignment: Text.AlignRight
                        }
                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 112
                            monospaced: true
                            text: root.formatBytes(row.model.out_octets)
                            horizontalAlignment: Text.AlignRight
                        }
                        DataTableCell {
                            visible: !root.showingMacTable
                            Layout.preferredWidth: 76
                            text: String(Number(row.model.in_errors || 0) + Number(row.model.out_errors || 0))
                            color: Number(row.model.in_errors || 0) + Number(row.model.out_errors || 0) > 0
                                   ? Theme.alertError : Theme.textSecondary
                            horizontalAlignment: Text.AlignRight
                        }
                        DataTableCell {
                            visible: !root.showingMacTable && !root.compactColumns
                            Layout.preferredWidth: 76
                            text: String(Number(row.model.in_discards || 0) + Number(row.model.out_discards || 0))
                            color: Number(row.model.in_discards || 0) + Number(row.model.out_discards || 0) > 0
                                   ? Theme.alertWarning : Theme.textSecondary
                            horizontalAlignment: Text.AlignRight
                        }
                        DataTableCell {
                            visible: !root.showingMacTable && !root.compactColumns
                            Layout.fillWidth: true
                            text: String(row.model.last_flap || "Never")
                        }

                        DataTableCell {
                            visible: root.showingMacTable
                            Layout.preferredWidth: 170
                            primary: true
                            monospaced: true
                            text: String(row.model.mac_addr || "—")
                        }
                        DataTableCell {
                            visible: root.showingMacTable
                            Layout.preferredWidth: 74
                            text: String(row.model.vlan_id || "—")
                            horizontalAlignment: Text.AlignHCenter
                        }
                        DataTableCell {
                            visible: root.showingMacTable
                            Layout.fillWidth: true
                            primary: true
                            text: String(row.model.if_name || "—")
                        }
                        DataTableCell {
                            visible: root.showingMacTable
                            Layout.preferredWidth: 96
                            text: String(row.model.mac_type || "—")
                        }
                        DataTableCell {
                            visible: root.showingMacTable && !root.compactColumns
                            Layout.preferredWidth: 174
                            text: String(row.model.learned_at || "—")
                        }
                    }
                }
            }
        }
    }
}
