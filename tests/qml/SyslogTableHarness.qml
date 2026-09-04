import QtQuick
import UI

Item {
    width: 1000
    height: 400

    function churnRows() {
        for (let i = 0; i < 80; ++i) {
            rows.append({
                idValue: i + 2,
                device_host: "192.0.2.1",
                source_ip: "192.0.2.1",
                received_at: "2026-07-18T10:00:00",
                facility: "SYS",
                severity: i % 8,
                mnemonic: "CONFIG_I",
                message: "Configured " + i
            })
        }
        rows.remove(0, 70)
        rows.clear()
    }

    function exerciseNullRow() {
        nullRow.rowData = null
        nullRow.rowData = undefined
        nullRow.rowData = ""
        nullRow.rowData = ({
            source_ip: "192.0.2.2",
            severity: 4,
            message: "Recovered"
        })
        details.rowData = null
        details.rowData = undefined
        details.rowData = ""
        details.rowData = ({
            source_ip: "192.0.2.2",
            syslog_pri: 36,
            message: "Recovered details"
        })
    }

    ListModel {
        id: rows
        ListElement {
            idValue: 1
            device_host: "192.0.2.1"
            source_ip: "192.0.2.1"
            received_at: "2026-07-18T10:00:00"
            facility: "SYS"
            severity: 5
            mnemonic: "CONFIG_I"
            message: "Configured"
        }
    }

    SyslogLogTable {
        anchors.fill: parent
        model: rows
    }

    SyslogLogRow {
        id: nullRow
        visible: false
    }

    SyslogMessageDetails {
        id: details
    }
}
