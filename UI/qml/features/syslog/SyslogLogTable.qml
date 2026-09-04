pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

DataTable {
    id: root
    objectName: "syslogLogTable"

    property alias model: list.model
    property bool hasMore: false
    property bool limitReached: false
    property bool paused: false
    property int selectedIndex: -1
    readonly property bool compactColumns: width < 1120
    readonly property bool narrowColumns: width < 720
    readonly property int timeColumnWidth: compactColumns ? 184 : 210
    readonly property int hostColumnWidth: compactColumns ? 112 : 126
    readonly property int sourceColumnWidth: 130
    readonly property int severityColumnWidth: compactColumns ? 148 : 164
    readonly property int mnemonicColumnWidth: 112
    signal loadOlderRequested()
    signal messageActivated(var rowData)

    count: list.count
    bodyMargins: 0
    emptyTitle: root.paused ? "Live updates are paused" : "No System Log messages"
    emptyDescription: root.paused
                      ? "Resume live updates to reload messages received while paused."
                      : "Start the listener, then configure a connected device to send Syslog messages."

    headerComponent: Component {
        DataTableHeader {
            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacing8

                DataTableCell {
                    visible: !root.narrowColumns
                    Layout.minimumWidth: root.timeColumnWidth
                    Layout.preferredWidth: root.timeColumnWidth
                    Layout.maximumWidth: root.timeColumnWidth
                    header: true
                    text: "Time"
                }
                DataTableCell {
                    Layout.minimumWidth: root.hostColumnWidth
                    Layout.preferredWidth: root.hostColumnWidth
                    Layout.maximumWidth: root.hostColumnWidth
                    header: true
                    text: "Host"
                }
                DataTableCell {
                    visible: !root.compactColumns
                    Layout.minimumWidth: root.sourceColumnWidth
                    Layout.preferredWidth: root.sourceColumnWidth
                    Layout.maximumWidth: root.sourceColumnWidth
                    header: true
                    text: "Source IP"
                }
                DataTableCell {
                    Layout.minimumWidth: root.severityColumnWidth
                    Layout.preferredWidth: root.severityColumnWidth
                    Layout.maximumWidth: root.severityColumnWidth
                    header: true
                    text: "Facility / Severity"
                }
                DataTableCell {
                    visible: !root.compactColumns
                    Layout.minimumWidth: root.mnemonicColumnWidth
                    Layout.preferredWidth: root.mnemonicColumnWidth
                    Layout.maximumWidth: root.mnemonicColumnWidth
                    header: true
                    text: "Mnemonic"
                }
                DataTableCell {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 120
                    header: true
                    text: "Message"
                }
            }
        }
    }

    ListView {
        id: list
        anchors.fill: parent
        clip: true
        reuseItems: true
        spacing: 0
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        delegate: SyslogLogRow {
            required property int index
            required property var model

            width: ListView.view.width
            rowIndex: index
            rowData: model
            selected: root.selectedIndex === index
            compactColumns: root.compactColumns
            narrowColumns: root.narrowColumns
            timeColumnWidth: root.timeColumnWidth
            hostColumnWidth: root.hostColumnWidth
            sourceColumnWidth: root.sourceColumnWidth
            severityColumnWidth: root.severityColumnWidth
            mnemonicColumnWidth: root.mnemonicColumnWidth
            onSelectedRequested: root.selectedIndex = index
            onActivated: function(data) {
                root.selectedIndex = index
                root.messageActivated(data)
            }
        }

        footer: Item {
            width: list.width
            height: root.hasMore || root.limitReached ? 48 : 0

            StandardButton {
                visible: root.hasMore
                anchors.centerIn: parent
                text: "Load Older Messages"
                type: "Secondary"
                onClicked: root.loadOlderRequested()
            }

            Text {
                visible: root.limitReached
                anchors.centerIn: parent
                text: "Showing the newest 2,000 messages. Refine the filters to narrow the view."
                color: Theme.textDisabled
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
        }
    }
}
