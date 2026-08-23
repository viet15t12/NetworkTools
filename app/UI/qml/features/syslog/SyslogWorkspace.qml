pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "syslogWorkspace"

    property string selectedHost: ""
    property var activeFilters: ({"host": "", "search": "", "severities": [], "protocols": []})
    property bool hasMore: false
    property string requestId: ""
    property int requestSerial: 0
    property int maximumEntries: 2000
    property int pageSize: 200
    property bool activatedOnce: false
    readonly property var backend: typeof syslogManager !== "undefined" && syslogManager !== null
                                   ? syslogManager : null

    signal operationMessage(bool ok, string message)
    signal resetHostRequested()

    color: Theme.contentBackground

    function nextRequestId() {
        requestSerial += 1
        requestId = String(requestSerial)
        return requestId
    }

    function containsMessage(idValue) {
        const expected = Number(idValue || 0)
        if (expected <= 0)
            return false
        for (let i = 0; i < logModel.count; ++i) {
            if (Number(logModel.get(i).id || 0) === expected)
                return true
        }
        return false
    }

    function matchesFilters(row) {
        const host = String(activeFilters.host || "")
        if (host !== "" && String(row.device_host || "") !== host)
            return false

        const severities = activeFilters.severities || []
        if (severities.length > 0
                && severities.indexOf(Number(row.severity)) < 0)
            return false

        const protocols = activeFilters.protocols || []
        if (protocols.length > 0
                && protocols.indexOf(String(row.protocol || "").toLowerCase()) < 0)
            return false

        const query = String(activeFilters.search || "").trim().toLowerCase()
        if (query === "")
            return true
        return String(row.message || "").toLowerCase().indexOf(query) >= 0
            || String(row.mnemonic || "").toLowerCase().indexOf(query) >= 0
    }

    function normalizedLogRow(source) {
        const row = source || ({})
        return {
            id: Number(row.id || 0),
            device_host: String(row.device_host || ""),
            source_ip: String(row.source_ip || ""),
            device_time: String(row.device_time || ""),
            sequence_number: row.sequence_number === undefined || row.sequence_number === null
                             ? -1 : Number(row.sequence_number),
            clock_unsynchronized: Boolean(row.clock_unsynchronized),
            received_at: String(row.received_at || ""),
            syslog_pri: row.syslog_pri === undefined || row.syslog_pri === null
                        ? -1 : Number(row.syslog_pri),
            syslog_facility: row.syslog_facility === undefined || row.syslog_facility === null
                             ? -1 : Number(row.syslog_facility),
            cisco_facility: String(row.cisco_facility || ""),
            cisco_subfacility: String(row.cisco_subfacility || ""),
            facility: String(row.facility || ""),
            severity: Number(row.severity === undefined ? 6 : row.severity),
            mnemonic: String(row.mnemonic || ""),
            message: String(row.message || ""),
            raw_message: String(row.raw_message || ""),
            protocol: String(row.protocol || "").toLowerCase(),
            parse_status: String(row.parse_status || "raw")
        }
    }

    function reload() {
        logModel.clear()
        hasMore = false
        const id = nextRequestId()
        if (backend !== null)
            backend.queryMessages(id, activeFilters, 0, pageSize)
    }

    function loadOlder() {
        if (backend === null || logModel.count === 0
                || logModel.count >= maximumEntries)
            return
        const lastId = Number(logModel.get(logModel.count - 1).id || 0)
        backend.queryMessages(nextRequestId(), activeFilters, lastId, pageSize)
    }

    function activateWorkspace() {
        if (!visible || backend === null)
            return
        activatedOnce = true
        reload()
    }

    ListModel { id: logModel }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: "System Logs"
            subtitle: root.selectedHost === ""
                      ? "Receive, filter, and inspect Syslog messages from connected devices."
                      : "Showing messages for " + root.selectedHost
        }

        SyslogControlBar {
            Layout.fillWidth: true
            listenerState: root.backend !== null ? root.backend.listenerState : "unavailable"
            statusText: root.backend !== null
                        ? root.backend.statusMessage
                        : "System Logs backend is unavailable."
            receivedCount: root.backend !== null ? root.backend.receivedCount : 0
            droppedCount: root.backend !== null ? root.backend.droppedCount : 0
            onStartRequested: {
                if (root.backend === null)
                    return
                const result = root.backend.startServer()
                root.operationMessage(Boolean(result.ok), String(result.message || ""))
            }
            onStopRequested: {
                if (root.backend === null)
                    return
                const result = root.backend.stopServer()
                root.operationMessage(Boolean(result.ok), String(result.message || ""))
            }
        }

        SyslogFilterBar {
            Layout.fillWidth: true
            selectedHost: root.selectedHost
            onFiltersChanged: function(filters) {
                root.activeFilters = filters
                root.reload()
            }
            onResetHostRequested: root.resetHostRequested()
        }

        SyslogLogTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: logModel
            hasMore: root.hasMore
            limitReached: logModel.count >= root.maximumEntries
            paused: false
            onLoadOlderRequested: root.loadOlder()
            onMessageActivated: function(data) {
                details.rowData = data
                details.open()
            }
        }
    }

    SyslogMessageDetails { id: details }

    onSelectedHostChanged: {
        activeFilters = {
            "host": selectedHost,
            "search": activeFilters.search || "",
            "severities": activeFilters.severities || [],
            "protocols": activeFilters.protocols || []
        }
        if (activatedOnce && visible)
            reload()
    }

    onVisibleChanged: {
        if (visible)
            activateWorkspace()
    }

    Component.onCompleted: {
        if (!activatedOnce)
            activateWorkspace()
    }

    Connections {
        target: root.backend

        function onMessagesInserted(rows) {
            for (let i = 0; i < rows.length; ++i) {
                const row = rows[i]
                if (root.matchesFilters(row) && !root.containsMessage(row.id))
                    logModel.insert(0, root.normalizedLogRow(row))
            }
            while (logModel.count > root.maximumEntries)
                logModel.remove(logModel.count - 1)
        }

        function onQueryFinished(id, rows, more) {
            if (id !== root.requestId)
                return
            for (let i = 0; i < rows.length
                    && logModel.count < root.maximumEntries; ++i) {
                if (!root.containsMessage(rows[i].id))
                    logModel.append(root.normalizedLogRow(rows[i]))
            }
            root.hasMore = Boolean(more) && logModel.count < root.maximumEntries
        }

        function onErrorOccurred(message) {
            root.operationMessage(false, String(message || "System Logs operation failed."))
        }
    }
}
