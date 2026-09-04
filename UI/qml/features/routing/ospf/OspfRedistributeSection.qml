pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    required property var form

    visible: String(form.currentHostIp || "").trim() !== ""
        && form.activeRoutingSection === "Redistribute"
        && form.processCount > 0
    Layout.fillWidth: true
    Layout.leftMargin: 24
    Layout.rightMargin: 24
    implicitHeight: layout.implicitHeight + Theme.spacing32
    radius: Theme.cardRadius
    color: Theme.contentPanelSurface
    border.color: Theme.contentPanelBorder
    border.width: Theme.borderWidth

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: Theme.spacing16
        spacing: Theme.spacing12

        SectionTitle {
            text: "OSPF REDISTRIBUTE"
            helpText: "Protocol: source routing protocol imported into OSPF.\n\n" +
                      "Process ID: source process/AS when the selected protocol requires one.\n\n" +
                      "Metric: seed OSPF cost for redistributed routes.\n\n" +
                      "Metric type: E1 adds internal path cost; E2 keeps the external metric dominant.\n\n" +
                      "Route map: optional policy controlling which routes and attributes are imported.\n\n" +
                      "Subnets: includes subnetted routes, not only classful networks."
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width < 760 ? 2 : 6
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            RoutingProcessComboBox { form: root.form; protocol: "OSPF" }
            StandardComboBox { id: protocolCombo; Layout.fillWidth: true; labelText: "Protocol"; model: ["static", "connected", "eigrp", "bgp", "rip", "isis"] }
            StandardTextField { id: pidField; Layout.fillWidth: true; labelText: "Process ID"; placeholderText: "optional" }
            StandardTextField { id: metricField; Layout.fillWidth: true; labelText: "Metric"; placeholderText: "optional" }
            StandardComboBox { id: metricTypeCombo; Layout.fillWidth: true; labelText: "Metric type"; model: ["", "1", "2"] }
            StandardTextField { id: routeMapField; Layout.fillWidth: true; labelText: "Route map"; placeholderText: "optional" }
            StandardCheckBox { id: subnetsCheck; text: "Subnets"; checked: true }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardButton {
                text: "+ Add Redistribute"
                type: "Primary"
                onClicked: root.form.addRedistributeToSelectedProcess(protocolCombo.currentText, pidField.text, subnetsCheck.checked, metricField.text, metricTypeCombo.currentText, routeMapField.text)
            }
            Item { Layout.fillWidth: true }
        }

        Repeater {
            model: {
                const revision = root.form.statsRevision
                const item = root.form.selectedProcessItem()
                return item ? item.redistribute : null
            }
            delegate: RowLayout {
                required property string protocol
                required property string process_id
                required property bool subnets
                required property string metric
                required property string metric_type
                required property string route_map
                required property int index
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: protocol + (process_id ? " " + process_id : ""); color: Theme.accentColor; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: subnets ? "subnets" : ""; color: Theme.textPrimary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: metric ? ("metric " + metric) : ""; color: Theme.textSecondary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: metric_type ? ("type " + metric_type) : ""; color: Theme.textSecondary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: route_map ? ("route-map " + route_map) : ""; color: Theme.textSecondary; font.family: Theme.fontFamily }
                RemoveIconButton { tooltip: "Remove redistribution"; onClicked: root.form.removeRedistributeFromSelectedProcess(index) }
            }
        }
    }
}
