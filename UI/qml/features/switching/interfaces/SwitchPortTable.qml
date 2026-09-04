pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import UI as App

Item {
    id: root

    required property var sourceModel
    property int totalCount: sourceModel ? sourceModel.count : 0
    property int selectedIndex: -1
    property bool selectionEnabled: true
    property string viewMode: "interfaces"
    property bool routedOnly: false
    property string filterText: ""
    property string emptyTitle: "No switch ports"
    property string emptyDescription: "Use Add to create the first desired-state entry."

    readonly property bool securityView: viewMode === "portSecurity"
    readonly property bool interfaceView: !securityView
    readonly property string tableTitle: securityView ? "Port policies"
                                               : routedOnly ? "Routed-port inventory"
                                               : "Port inventory"

    signal rowSelected(int index)
    signal searchEdited(string value)

    function text(value, fallback) {
        return value === undefined || value === null || String(value) === ""
             ? (fallback || "—") : String(value)
    }

    function vlanSummary(row) {
        const mode = String(row.mode || "access")
        if (mode === "access") {
            const voice = row.voice_vlan ? " · voice " + row.voice_vlan : ""
            return "Access " + (row.access_vlan || 1) + voice
        }
        if (mode === "trunk")
            return "Native " + (row.native_vlan || 1) + " · " + (row.allowed_vlans || "all")
        return "Layer 3"
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.spacing8

        SwitchTableToolbar {
            Layout.fillWidth: true
            title: root.tableTitle
            totalCount: root.totalCount
            visibleCount: root.sourceModel ? root.sourceModel.count : 0
            searchText: root.filterText
            searchPlaceholder: root.securityView
                               ? "Filter interfaces..." : "Filter ports..."
            onSearchEdited: value => root.searchEdited(value)
        }

        DataTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            count: root.sourceModel ? root.sourceModel.count : 0
            bodyMargins: 0
            emptyTitle: root.emptyTitle
            emptyDescription: root.emptyDescription
            headerComponent: Component {
                DataTableHeader {
                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.preferredWidth: 156
                            Layout.fillWidth: root.securityView
                            header: true
                            text: "Interface"
                        }
                        DataTableCell {
                            visible: root.interfaceView
                            Layout.preferredWidth: 82
                            header: true
                            text: "Mode"
                        }
                        DataTableCell {
                            visible: root.interfaceView && !root.routedOnly
                            Layout.preferredWidth: 190
                            header: true
                            text: "VLAN Membership"
                        }
                        DataTableCell {
                            visible: root.interfaceView
                            Layout.fillWidth: true
                            header: true
                            text: "Description"
                        }

                        DataTableCell {
                            visible: root.securityView
                            Layout.preferredWidth: 72
                            header: true
                            text: "Enabled"
                            horizontalAlignment: Text.AlignHCenter
                        }
                        DataTableCell {
                            visible: root.securityView
                            Layout.preferredWidth: 72
                            header: true
                            text: "Max MAC"
                            horizontalAlignment: Text.AlignHCenter
                        }
                        DataTableCell {
                            visible: root.securityView
                            Layout.preferredWidth: 92
                            header: true
                            text: "Violation"
                        }
                        DataTableCell {
                            visible: root.securityView
                            Layout.preferredWidth: 68
                            header: true
                            text: "Sticky"
                            horizontalAlignment: Text.AlignHCenter
                        }

                        DataTableCell {
                            Layout.preferredWidth: 88
                            header: true
                            text: "Link"
                        }
                    }
                }
            }

            ListView {
                anchors.fill: parent
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: root.sourceModel
                spacing: 0
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: DataTableRow {
                    id: row

                    required property int index
                    required property var model

                    width: ListView.view.width
                    height: Theme.tableRowHeight
                    rowIndex: index
                    selected: root.selectedIndex === index
                    interactive: root.selectionEnabled

                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell {
                            Layout.preferredWidth: 156
                            Layout.fillWidth: root.securityView
                            primary: true
                            text: root.text(row.model.if_name)
                        }
                        DataTableCell {
                            visible: root.interfaceView
                            Layout.preferredWidth: 82
                            primary: true
                            text: root.text(row.model.mode).toUpperCase()
                            color: String(row.model.mode || "access") === "access"
                                   ? Theme.alertSuccess
                                   : String(row.model.mode || "") === "trunk"
                                     ? Theme.alertInfo : Theme.textSecondary
                        }
                        DataTableCell {
                            visible: root.interfaceView && !root.routedOnly
                            Layout.preferredWidth: 190
                            text: root.vlanSummary(row.model)
                        }
                        DataTableCell {
                            visible: root.interfaceView
                            Layout.fillWidth: true
                            text: root.text(row.model.description)
                        }

                        DataTableCell {
                            visible: root.securityView
                            Layout.preferredWidth: 72
                            text: row.model.port_security_enabled ? "On" : "Off"
                            color: row.model.port_security_enabled ? Theme.alertSuccess : Theme.textDisabled
                            horizontalAlignment: Text.AlignHCenter
                        }
                        DataTableCell {
                            visible: root.securityView
                            Layout.preferredWidth: 72
                            text: row.model.port_security_enabled ? root.text(row.model.max_mac, "1") : "—"
                            horizontalAlignment: Text.AlignHCenter
                        }
                        DataTableCell {
                            visible: root.securityView
                            Layout.preferredWidth: 92
                            text: row.model.port_security_enabled ? root.text(row.model.violation) : "—"
                        }
                        DataTableCell {
                            visible: root.securityView
                            Layout.preferredWidth: 68
                            text: row.model.port_security_enabled && row.model.sticky ? "Yes" : "No"
                            horizontalAlignment: Text.AlignHCenter
                        }

                        App.StatusBadge {
                            Layout.preferredWidth: 88
                            value: root.text(row.model.oper_status, "unknown")
                        }
                    }

                    TapHandler {
                        enabled: root.selectionEnabled
                        onTapped: root.rowSelected(row.index)
                    }
                }
            }
        }
    }
}
