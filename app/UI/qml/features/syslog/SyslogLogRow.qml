pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

DataTableRow {
    id: root

    property var rowData: ({})
    property bool compactColumns: false
    property bool narrowColumns: false
    property int timeColumnWidth: 210
    property int hostColumnWidth: 126
    property int sourceColumnWidth: 130
    property int severityColumnWidth: 164
    property int mnemonicColumnWidth: 112
    signal selectedRequested()
    signal activated(var rowData)

    function rowValue(name, fallbackValue) {
        const data = root.rowData
        if (data === null || data === undefined || typeof data !== "object")
            return fallbackValue
        const value = data[name]
        return value === null || value === undefined ? fallbackValue : value
    }

    readonly property int severity: Number(root.rowValue("severity", 6))
    readonly property color severityColor: severity <= 3 ? Theme.alertError
                                           : severity === 4 ? Theme.alertWarning
                                           : severity === 5 ? Theme.accentColor
                                           : Theme.textSecondary
    readonly property var severityNames: [
        "Emergency", "Alert", "Critical", "Error",
        "Warning", "Notice", "Info", "Debug"
    ]

    height: Theme.tableRowHeight

    RowLayout {
        anchors.fill: parent
        spacing: Theme.spacing8

        DataTableCell {
            visible: !root.narrowColumns
            Layout.minimumWidth: root.timeColumnWidth
            Layout.preferredWidth: root.timeColumnWidth
            Layout.maximumWidth: root.timeColumnWidth
            monospaced: true
            text: String(root.rowValue("device_time", "")
                         || root.rowValue("received_at", "") || "—")
        }
        DataTableCell {
            Layout.minimumWidth: root.hostColumnWidth
            Layout.preferredWidth: root.hostColumnWidth
            Layout.maximumWidth: root.hostColumnWidth
            primary: true
            text: String(root.rowValue("device_host", "")
                         || root.rowValue("source_ip", "") || "—")
        }
        DataTableCell {
            visible: !root.compactColumns
            Layout.minimumWidth: root.sourceColumnWidth
            Layout.preferredWidth: root.sourceColumnWidth
            Layout.maximumWidth: root.sourceColumnWidth
            monospaced: true
            text: String(root.rowValue("source_ip", "") || "—")
        }
        DataTableCell {
            Layout.minimumWidth: root.severityColumnWidth
            Layout.preferredWidth: root.severityColumnWidth
            Layout.maximumWidth: root.severityColumnWidth
            color: root.severityColor
            text: "%1 / %2 %3".arg(root.rowValue("cisco_facility", "")
                                      || root.rowValue("facility", "") || "—")
                               .arg(root.severity)
                               .arg(root.severityNames[root.severity] || "Unknown")
        }
        DataTableCell {
            visible: !root.compactColumns
            Layout.minimumWidth: root.mnemonicColumnWidth
            Layout.preferredWidth: root.mnemonicColumnWidth
            Layout.maximumWidth: root.mnemonicColumnWidth
            monospaced: true
            text: String(root.rowValue("mnemonic", "") || "—")
        }
        DataTableCell {
            Layout.fillWidth: true
            Layout.minimumWidth: 120
            primary: true
            text: String(root.rowValue("message", "") || "—")
        }
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: root.selectedRequested()
        onDoubleTapped: {
            const data = root.rowData
            root.activated(data !== null && data !== undefined
                           && typeof data === "object" ? data : ({}))
        }
    }
}
