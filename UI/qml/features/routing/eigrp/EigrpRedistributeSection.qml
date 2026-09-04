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
            text: "EIGRP REDISTRIBUTE"
            helpText: "Protocol: source routing protocol imported into EIGRP.\n\n" +
                      "Route Map: optional import policy.\n\n" +
                      "Metric BW, Delay, Reliability, Load, and MTU form the EIGRP seed metric. For protocols without a native compatible metric, provide all required values. Reliability and Load are 1-255; MTU is bytes."
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width < 760 ? 2 : 4
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8
            RoutingProcessComboBox { form: root.form; protocol: "EIGRP" }
            StandardComboBox { id: protocolCombo; Layout.fillWidth: true; labelText: "Protocol"; model: ["static", "connected", "ospf", "bgp", "rip", "isis"] }
            StandardTextField { id: routeMapField; Layout.fillWidth: true; labelText: "Route Map"; placeholderText: "optional" }
            StandardTextField { id: bwField; Layout.fillWidth: true; labelText: "Metric BW"; placeholderText: "optional" }
            StandardTextField { id: delayField; Layout.fillWidth: true; labelText: "Metric Delay"; placeholderText: "optional" }
            StandardTextField { id: reliabilityField; Layout.fillWidth: true; labelText: "Reliability"; placeholderText: "optional" }
            StandardTextField { id: loadField; Layout.fillWidth: true; labelText: "Load"; placeholderText: "optional" }
            StandardTextField { id: mtuField; Layout.fillWidth: true; labelText: "MTU"; placeholderText: "optional" }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardButton {
                text: "+ Add Redistribute"
                type: "Primary"
                onClicked: root.form.addRedistributeToSelectedProcess(protocolCombo.currentText, routeMapField.text, bwField.text, delayField.text, reliabilityField.text, loadField.text, mtuField.text)
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
                required property string route_map
                required property string metric_bw
                required property string metric_delay
                required property string metric_reliability
                required property string metric_load
                required property string metric_mtu
                required property int index
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: protocol; color: Theme.accentColor; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: route_map ? ("route-map " + route_map) : ""; color: Theme.textPrimary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: metric_bw ? ("metric " + metric_bw + " " + metric_delay + " " + metric_reliability + " " + metric_load + " " + metric_mtu) : ""; color: Theme.textSecondary; font.family: Theme.fontFamily; elide: Text.ElideRight }
                RemoveIconButton { tooltip: "Remove redistribution"; onClicked: root.form.removeRedistributeFromSelectedProcess(index) }
            }
        }
    }
}
