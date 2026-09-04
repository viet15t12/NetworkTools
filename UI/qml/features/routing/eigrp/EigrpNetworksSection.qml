pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Item {
    id: root
    required property var form

    visible: String(form.currentHostIp || "").trim() !== ""
        && form.activeRoutingSection === "Networks"
        && form.processCount > 0
    Layout.fillWidth: true
    implicitHeight: content.implicitHeight

    ColumnLayout {
        id: content
        width: parent.width
        spacing: Theme.spacing12

        DataTableFrame {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            implicitHeight: layout.implicitHeight + Theme.spacing32
            ColumnLayout {
                id: layout
                anchors.fill: parent
                anchors.margins: Theme.spacing16
                spacing: Theme.spacing12

                SectionTitle {
                    text: "EIGRP NETWORKS"
                    helpText: "Process: EIGRP AS/process to update.\n\n" +
                              "Network: IPv4 network or interface address that enables EIGRP.\n\n" +
                              "Wildcard: optional inverse subnet mask; CIDR shorthand such as -/24 is accepted. Leave empty for IOS classful matching behavior.\n\n" +
                              "Interface: optional explicit interface association used by this application."
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: width < 760 ? 2 : 4
                    columnSpacing: Theme.spacing12
                    rowSpacing: Theme.spacing8

                    RoutingProcessComboBox { form: root.form; protocol: "EIGRP" }
                    StandardNetworkField { id: networkField; Layout.fillWidth: true; inputKind: "ipv4"; labelText: "Network"; placeholderText: "10.0.0.0" }
                    StandardNetworkField { id: wildcardField; Layout.fillWidth: true; inputKind: "wildcard"; labelText: "Wildcard"; placeholderText: "optional, e.g. -/24" }
                    StandardTextField { id: ifaceField; Layout.fillWidth: true; labelText: "Interface"; placeholderText: "optional" }
                }

                RowLayout {
                    Layout.fillWidth: true
                    StandardButton {
                        text: "+ Add Network"
                        type: "Primary"
                        onClicked: {
                            if (root.form.addNetworkToSelectedProcess(networkField.text, wildcardField.text, ifaceField.text)) {
                                networkField.clear()
                                wildcardField.clear()
                                ifaceField.clear()
                            }
                        }
                    }
                    StandardButton { text: "Clear"; type: "Secondary"; onClicked: { networkField.clear(); wildcardField.clear(); ifaceField.clear() } }
                    Item { Layout.fillWidth: true }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            implicitHeight: table.implicitHeight
            radius: Theme.cardRadius
            color: Theme.contentPanelSurface
            border.color: Theme.contentPanelBorder
            border.width: Theme.borderWidth

            ColumnLayout {
                id: table
                width: parent.width
                spacing: 0

                DataTableHeader {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Theme.tableHeaderHeight
                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8
                        DataTableCell { Layout.fillWidth: true; header: true; text: "Process" }
                        DataTableCell { Layout.fillWidth: true; header: true; text: "Network" }
                        DataTableCell { Layout.fillWidth: true; header: true; text: "Wildcard" }
                        DataTableCell { Layout.fillWidth: true; header: true; text: "Interface" }
                        DataTableCell { Layout.preferredWidth: 40; header: true; text: "" }
                    }
                }

                EmptyState {
                    visible: !root.form.selectedProcessItem() || root.form.selectedProcessItem().networks.count === 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: 72
                    title: "No networks in the selected process"
                    emphasized: false
                }

                Repeater {
                    model: {
                        const revision = root.form.statsRevision
                        const item = root.form.selectedProcessItem()
                        return item ? item.networks : null
                    }
                    delegate: DataTableRow {
                        required property string network
                        required property string wildcard
                        required property string interface_name
                        required property int index
                        width: table.width
                        height: Theme.tableRowHeight
                        rowIndex: index
                        RowLayout {
                            anchors.fill: parent
                            spacing: Theme.spacing8
                            DataTableCell { Layout.fillWidth: true; text: root.form.processOptionLabel(root.form.selectedNetworkProcessIndex) }
                            DataTableCell { Layout.fillWidth: true; primary: true; monospaced: true; text: network }
                            DataTableCell { Layout.fillWidth: true; monospaced: true; text: wildcard }
                            DataTableCell { Layout.fillWidth: true; primary: true; text: interface_name }
                            RemoveIconButton { tooltip: "Remove network"; onClicked: root.form.removeNetworkFromSelectedProcess(index) }
                        }
                    }
                }
            }
        }
    }
}
