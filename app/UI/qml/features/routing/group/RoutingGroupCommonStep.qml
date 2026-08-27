pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

ColumnLayout {
    id: root
    required property string protocol

    function parameters() {
        if (protocol === "ospf") {
            return {
                reference_bandwidth: refBwField.text.trim(),
                passive_default: ospfPassiveCheck.checked,
                default_originate: defaultCheck.checked,
                default_originate_always: alwaysCheck.checked,
                authentication_cfg: authenticationCheck.checked
            }
        }
        return {
            bfd_all_interfaces: bfdCheck.checked,
            auto_summary: autoSummaryCheck.checked,
            passive_default: eigrpPassiveCheck.checked,
            metric_weights: metricWeightsField.text.trim(),
            variance: varianceField.text.trim(),
            maximum_paths: maximumPathsField.text.trim()
        }
    }

    FormSection {
        Layout.fillWidth: true
        visible: root.protocol === "ospf"
        title: "Common OSPF parameters"
        helpText: "Reference bandwidth: Mbps baseline used for OSPF cost; keep it identical across the domain.\n\n" +
                  "Passive default: disables neighbor formation on all interfaces unless overridden.\n\n" +
                  "Default originate advertises a default route; Originate always does so without requiring a local default.\n\n" +
                  "AuthenticationCFG enables area message-digest authentication; matching interface keys are required."
        StandardTextField {
            id: refBwField
            Layout.fillWidth: true
            labelText: "Reference bandwidth (Mbps)"
        }
        Flow {
            Layout.fillWidth: true
            spacing: Theme.spacing12
            StandardCheckBox { id: ospfPassiveCheck; text: "Passive default" }
            StandardCheckBox { id: defaultCheck; text: "Default originate" }
            StandardCheckBox {
                id: alwaysCheck
                text: "Originate always"
                enabled: defaultCheck.checked
            }
            StandardCheckBox {
                id: authenticationCheck
                text: "AuthenticationCFG"
            }
        }
    }

    FormSection {
        Layout.fillWidth: true
        visible: root.protocol === "eigrp"
        title: "Common EIGRP parameters"
        helpText: "Metric weights: K-value tuple, normally 0 1 0 1 0 0; neighbors must use compatible K-values.\n\n" +
                  "Variance: multiplier used for unequal-cost load balancing. Maximum paths limits installed parallel paths.\n\n" +
                  "BFD all interfaces enables fast failure detection. Auto summary enables classful summarization. Passive default prevents neighbor formation unless overridden."
        GridLayout {
            Layout.fillWidth: true
            columns: 3
            StandardTextField {
                id: metricWeightsField
                Layout.fillWidth: true
                labelText: "Metric weights"
                text: "0 1 0 1 0 0"
            }
            StandardTextField {
                id: varianceField
                Layout.fillWidth: true
                labelText: "Variance"
            }
            StandardTextField {
                id: maximumPathsField
                Layout.fillWidth: true
                labelText: "Maximum paths"
            }
        }
        Flow {
            Layout.fillWidth: true
            spacing: Theme.spacing12
            StandardCheckBox { id: bfdCheck; text: "BFD all interfaces" }
            StandardCheckBox { id: autoSummaryCheck; text: "Auto summary" }
            StandardCheckBox { id: eigrpPassiveCheck; text: "Passive default" }
        }
    }
}
