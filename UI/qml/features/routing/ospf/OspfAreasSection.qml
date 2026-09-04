pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    required property var form

    visible: String(form.currentHostIp || "").trim() !== ""
        && form.activeRoutingSection === "Areas"
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
            text: "OSPF AREAS"
            helpText: "Area ID: decimal or dotted OSPF area identifier.\n\n" +
                      "Type: normal, stub, or NSSA. All routers in an area must use compatible area types.\n\n" +
                      "Auth: area authentication mode; interface keys must match between neighbors.\n\n" +
                      "No summary: blocks inter-area summaries into stub/NSSA areas.\n\n" +
                      "Area for Range: area whose routes are summarized. Range IP/Mask define the summary; Cost optionally fixes its metric; Advertise controls whether the summary is announced."
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width < 760 ? 2 : 5
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            RoutingProcessComboBox { form: root.form; protocol: "OSPF" }
            StandardTextField { id: areaIdField; Layout.fillWidth: true; labelText: "Area ID"; placeholderText: "0" }
            StandardComboBox { id: areaTypeCombo; Layout.fillWidth: true; labelText: "Type"; model: ["normal", "stub", "nssa"] }
            StandardComboBox {
                id: areaAuthCombo
                Layout.fillWidth: true
                labelText: "Auth"
                model: ["None", "plain", "message-digest"]
                valueModel: ["", "plain", "message-digest"]
            }
            StandardCheckBox { id: areaNoSummaryCheck; text: "No summary"; Layout.alignment: Qt.AlignBottom }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardButton {
                text: "+ Add Area"
                type: "Primary"
                onClicked: {
                    if (root.form.addAreaToSelectedProcess(areaIdField.text, areaTypeCombo.currentText, areaNoSummaryCheck.checked, areaAuthCombo.currentValue))
                        areaIdField.clear()
                }
            }
            Item { Layout.fillWidth: true }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width < 760 ? 2 : 5
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            StandardComboBox {
                Layout.fillWidth: true
                labelText: "Area for Range"
                model: root.form.areaOptionsForSelectedProcess()
                currentIndex: root.form.selectedAreaIndex
                enabled: root.form.areaOptionsForSelectedProcess().length > 0
                onCurrentIndexChanged: if (currentIndex >= 0) root.form.selectedAreaIndex = currentIndex
            }
            StandardTextField { id: rangeIpField; Layout.fillWidth: true; labelText: "Range IP"; placeholderText: "10.0.0.0" }
            StandardTextField { id: rangeMaskField; Layout.fillWidth: true; labelText: "Range mask"; placeholderText: "255.255.255.0" }
            StandardTextField { id: rangeCostField; Layout.fillWidth: true; labelText: "Cost"; placeholderText: "optional" }
            StandardCheckBox { id: rangeAdvertiseCheck; text: "Advertise"; checked: true; Layout.alignment: Qt.AlignBottom }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardButton {
                text: "+ Add Range"
                type: "Secondary"
                enabled: root.form.areaOptionsForSelectedProcess().length > 0
                onClicked: {
                    if (root.form.addAreaRangeToSelectedArea(rangeIpField.text, rangeMaskField.text, rangeAdvertiseCheck.checked, rangeCostField.text)) {
                        rangeIpField.clear()
                        rangeMaskField.clear()
                        rangeCostField.clear()
                    }
                }
            }
            Item { Layout.fillWidth: true }
        }

        Repeater {
            model: {
                const revision = root.form.statsRevision
                const item = root.form.selectedProcessItem()
                return item ? item.areas : null
            }
            delegate: RowLayout {
                required property string area_id
                required property string area_type
                required property bool no_summary
                required property string authentication
                required property int index
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: "Area " + area_id; color: Theme.accentColor; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: area_type; color: Theme.textPrimary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: authentication || "None"; color: Theme.textSecondary; font.family: Theme.fontFamily }
                Text { Layout.preferredWidth: 110; text: no_summary ? "no-summary" : ""; color: Theme.textSecondary; font.family: Theme.fontFamily }
                RemoveIconButton { tooltip: "Remove area"; onClicked: root.form.removeAreaFromSelectedProcess(index) }
            }
        }

        Text {
            visible: root.form.areaOptionsForSelectedProcess().length > 0
            Layout.fillWidth: true
            text: "Ranges for " + (root.form.areaOptionsForSelectedProcess()[root.form.selectedAreaIndex] || "selected area")
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            font.bold: true
        }

        Repeater {
            model: root.form.selectedAreaRanges()
            delegate: RowLayout {
                required property string ip
                required property string mask
                required property var cost
                required property bool advertise
                required property int index
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: ip; color: Theme.accentColor; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: mask; color: Theme.textPrimary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: advertise ? "advertise" : "not-advertise"; color: Theme.textSecondary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: cost ? ("cost " + cost) : ""; color: Theme.textSecondary; font.family: Theme.fontFamily }
                RemoveIconButton { tooltip: "Remove range"; onClicked: root.form.removeAreaRangeFromSelectedArea(index) }
            }
        }
    }
}
