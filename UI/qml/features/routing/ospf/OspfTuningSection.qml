pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    required property var form

    visible: String(form.currentHostIp || "").trim() !== ""
        && form.activeRoutingSection === "Tuning"
        && form.processCount > 0
    Layout.fillWidth: true
    Layout.leftMargin: 24
    Layout.rightMargin: 24
    implicitHeight: layout.implicitHeight + Theme.spacing32
    radius: Theme.cardRadius
    color: Theme.contentPanelSurface
    border.color: Theme.contentPanelBorder
    border.width: Theme.borderWidth

    function displayValue(value) {
        return value === undefined || value === null ? "" : String(value)
    }

    function refreshFields() {
        const item = form.selectedProcessItem()
        const values = item && item.tuning ? item.tuning : ({})
        maxPathsField.text = displayValue(values.maximum_paths)
        maxLsaField.text = displayValue(values.max_lsa)
        spfDelayField.text = displayValue(values.spf_delay)
        spfMinField.text = displayValue(values.spf_min_delay)
        spfMaxField.text = displayValue(values.spf_max_delay)
        lsaDelayField.text = displayValue(values.lsa_delay)
        lsaMinField.text = displayValue(values.lsa_min_delay)
        lsaMaxField.text = displayValue(values.lsa_max_delay)
    }

    Component.onCompleted: Qt.callLater(refreshFields)

    Connections {
        target: root.form
        function onSelectedNetworkProcessIndexChanged() { root.refreshFields() }
        function onStatsRevisionChanged() {
            if (!maxPathsField.activeFocus && !maxLsaField.activeFocus
                    && !spfDelayField.activeFocus && !spfMinField.activeFocus
                    && !spfMaxField.activeFocus && !lsaDelayField.activeFocus
                    && !lsaMinField.activeFocus && !lsaMaxField.activeFocus)
                root.refreshFields()
        }
    }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: Theme.spacing16
        spacing: Theme.spacing12

        SectionTitle {
            text: "OSPF TUNING"
            helpText: "Max paths: maximum equal-cost OSPF paths installed in the routing table.\n\n" +
                      "Max LSA: safety limit for received LSAs.\n\n" +
                      "SPF delay/min/max: initial, minimum hold, and maximum hold timers for SPF calculations, in milliseconds.\n\n" +
                      "LSA delay/min/max: initial, minimum hold, and maximum hold timers for LSA generation, in milliseconds. Leave optional fields empty to keep the device default."
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width < 860 ? 2 : 5
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            RoutingProcessComboBox { form: root.form; protocol: "OSPF" }
            StandardTextField { id: maxPathsField; objectName: "ospfTuningMaxPathsField"; Layout.fillWidth: true; labelText: "Max paths"; placeholderText: "optional" }
            StandardTextField { id: maxLsaField; objectName: "ospfTuningMaxLsaField"; Layout.fillWidth: true; labelText: "Max LSA"; placeholderText: "optional" }
            StandardTextField { id: spfDelayField; objectName: "ospfTuningSpfDelayField"; Layout.fillWidth: true; labelText: "SPF delay"; placeholderText: "optional" }
            StandardTextField { id: spfMinField; objectName: "ospfTuningSpfMinField"; Layout.fillWidth: true; labelText: "SPF min"; placeholderText: "optional" }
            StandardTextField { id: spfMaxField; objectName: "ospfTuningSpfMaxField"; Layout.fillWidth: true; labelText: "SPF max"; placeholderText: "optional" }
            StandardTextField { id: lsaDelayField; objectName: "ospfTuningLsaDelayField"; Layout.fillWidth: true; labelText: "LSA delay"; placeholderText: "optional" }
            StandardTextField { id: lsaMinField; objectName: "ospfTuningLsaMinField"; Layout.fillWidth: true; labelText: "LSA min"; placeholderText: "optional" }
            StandardTextField { id: lsaMaxField; objectName: "ospfTuningLsaMaxField"; Layout.fillWidth: true; labelText: "LSA max"; placeholderText: "optional" }
            StandardButton {
                text: "Apply"
                type: "Primary"
                Layout.alignment: Qt.AlignBottom
                onClicked: root.form.setTuningForSelectedProcess(maxPathsField.text, maxLsaField.text, spfDelayField.text, spfMinField.text, spfMaxField.text, lsaDelayField.text, lsaMinField.text, lsaMaxField.text)
            }
        }
    }
}
