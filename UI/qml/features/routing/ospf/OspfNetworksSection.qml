pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
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
            implicitHeight: ospfNetworksLayout.implicitHeight + Theme.spacing32
            ColumnLayout {
                id: ospfNetworksLayout
                anchors.fill: parent
                anchors.margins: Theme.spacing16
                spacing: Theme.spacing12

                SectionTitle {
                    text: "OSPF NETWORKS"
                    helpText: "Process: OSPF process that receives this network statement.\n\n" +
                              "Network: IPv4 network or interface address to match.\n\n" +
                              "Wildcard: inverse subnet mask, for example 0.0.0.255; CIDR shorthand such as -/24 is also accepted.\n\n" +
                              "Area: OSPF area ID, either decimal (0) or dotted format (0.0.0.0). Interfaces matching the statement join this area."
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: width < 760 ? 2 : 4
                    columnSpacing: Theme.spacing12
                    rowSpacing: Theme.spacing8

                    RoutingProcessComboBox { form: root.form; protocol: "OSPF" }

                    StandardNetworkField {
                        id: ospfNetworkField
                        inputKind: "ipv4"
                        Layout.fillWidth: true
                        labelText: "Network"
                        placeholderText: "10.0.0.0"
                        enabled: root.form.processCount > 0
                    }

                    StandardNetworkField {
                        id: ospfWildcardField
                        inputKind: "wildcard"
                        Layout.fillWidth: true
                        labelText: "Wildcard"
                        placeholderText: "0.0.0.255 or -/24"
                        enabled: root.form.processCount > 0
                    }

                    StandardTextField {
                        id: ospfAreaField
                        Layout.fillWidth: true
                        labelText: "Area"
                        placeholderText: "0"
                        text: "0"
                        enabled: root.form.processCount > 0
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    StandardButton {
                        text: "+ Add Network"
                        type: "Primary"
                        enabled: root.form.processCount > 0
                        onClicked: {
                            if (root.form.addNetworkToSelectedProcess(ospfNetworkField.text, ospfWildcardField.text, ospfAreaField.text)) {
                                ospfNetworkField.clear()
                                ospfWildcardField.clear()
                                ospfAreaField.text = "0"
                            }
                        }
                    }

                    StandardButton {
                        text: "Clear"
                        type: "Secondary"
                        onClicked: {
                            ospfNetworkField.clear()
                            ospfWildcardField.clear()
                            ospfAreaField.text = "0"
                        }
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            implicitHeight: ospfNetworkTableLayout.implicitHeight
            radius: Theme.cardRadius
            color: Theme.contentPanelSurface
            border.color: Theme.contentPanelBorder
            border.width: Theme.borderWidth

            ColumnLayout {
                id: ospfNetworkTableLayout
                width: parent.width
                spacing: 0
                readonly property real tableInnerWidth: Math.max(0, width - Theme.spacing16 * 2)
                readonly property real fixedColumnWidth: 96 + 34 + Theme.spacing8 * 4
                readonly property real flexibleColumnWidth: Math.max(0, (tableInnerWidth - fixedColumnWidth) / 3)

                DataTableHeader {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Theme.tableHeaderHeight

                    RowLayout {
                        anchors.fill: parent
                        spacing: Theme.spacing8

                        DataTableCell { Layout.preferredWidth: ospfNetworkTableLayout.flexibleColumnWidth; header: true; text: "Process" }
                        DataTableCell { Layout.preferredWidth: ospfNetworkTableLayout.flexibleColumnWidth; header: true; text: "Network" }
                        DataTableCell { Layout.preferredWidth: ospfNetworkTableLayout.flexibleColumnWidth; header: true; text: "Wildcard" }
                        DataTableCell { Layout.preferredWidth: 96; header: true; text: "Area" }
                        DataTableCell { Layout.preferredWidth: 34; header: true; text: "" }
                    }
                }

                EmptyState {
                    visible: !root.form.selectedNetworkProcessItem()
                        || root.form.selectedNetworkProcessItem().networks.count === 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: 72
                    title: "No networks in the selected process"
                    emphasized: false
                }

                Repeater {
                    model: {
                        const revision = root.form.statsRevision
                        const item = root.form.selectedNetworkProcessItem()
                        return item ? item.networks : null
                    }

                    delegate: DataTableRow {
                        id: ospfNetworkRow
                        required property string network
                        required property string wildcard
                        required property var area
                        required property int index

                        width: ospfNetworkTableLayout.width
                        height: Theme.tableRowHeight
                        rowIndex: index

                        RowLayout {
                            anchors.fill: parent
                            spacing: Theme.spacing8

                            DataTableCell { Layout.preferredWidth: ospfNetworkTableLayout.flexibleColumnWidth; text: root.form.processOptionLabel(root.form.selectedNetworkProcessIndex) }
                            DataTableCell { Layout.preferredWidth: ospfNetworkTableLayout.flexibleColumnWidth; primary: true; monospaced: true; text: ospfNetworkRow.network }
                            DataTableCell { Layout.preferredWidth: ospfNetworkTableLayout.flexibleColumnWidth; monospaced: true; text: ospfNetworkRow.wildcard }
                            DataTableCell { Layout.preferredWidth: 96; primary: true; text: ospfNetworkRow.area === undefined || ospfNetworkRow.area === null ? "" : String(ospfNetworkRow.area) }
                            RemoveIconButton {
                                tooltip: "Remove network"
                                onClicked: root.form.removeNetworkFromSelectedProcess(ospfNetworkRow.index)
                            }
                        }
                    }
                }
            }
        }
    }
}
