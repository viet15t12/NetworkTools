pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

DataTableRow {
    id: root

    property var rowData: ({})
    property bool compactColumns: false
    property bool narrowColumns: false
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
            Layout.preferredWidth: root.compactColumns ? 110 : 150
            monospaced: true
            text: String(root.rowValue("device_time", "")
                         || root.rowValue("received_at", "") || "—")
        }
        DataTableCell {
            Layout.preferredWidth: root.compactColumns ? 104 : 120
            primary: true
            text: String(root.rowValue("device_host", "")
                         || root.rowValue("source_ip", "") || "—")
        }
        DataTableCell {
            visible: !root.compactColumns
            Layout.preferredWidth: 120
            monospaced: true
            text: String(root.rowValue("source_ip", "") || "—")
        }
        DataTableCell {
            Layout.preferredWidth: root.compactColumns ? 116 : 132
            color: root.severityColor
            text: "%1 / %2 %3".arg(root.rowValue("cisco_facility", "")
                                      || root.rowValue("facility", "") || "—")
                               .arg(root.severity)
                               .arg(root.severityNames[root.severity] || "Unknown")
        }
        DataTableCell {
            visible: !root.compactColumns
            Layout.preferredWidth: 120
            monospaced: true
            text: String(root.rowValue("mnemonic", "") || "—")
        }
        DataTableCell {
            Layout.fillWidth: true
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
