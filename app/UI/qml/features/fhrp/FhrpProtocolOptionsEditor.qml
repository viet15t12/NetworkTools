pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

// Group-wide protocol knobs. Member-specific failover policy stays in
// FhrpMemberEditor because the SQL option rows are keyed by member_id.
FormSection {
    id: root

    required property string protocol
    required property int protocolVersion
    required property int helloMs
    required property int holdMs
    required property int advertisementMs
    required property string loadBalancing

    signal optionChanged(string field, var value)

    title: root.protocol.toUpperCase() + " protocol options"

    GridLayout {
        Layout.fillWidth: true
        columns: width < 700 ? 1 : 2
        columnSpacing: Theme.spacing12
        rowSpacing: Theme.spacing8

        StandardComboBox {
            Layout.fillWidth: true
            visible: root.protocol === "hsrp"
            labelText: "HSRP version"
            model: ["Version 1", "Version 2"]
            valueModel: ["1", "2"]
            currentIndex: Math.max(0, valueModel.indexOf(
                                       String(root.protocolVersion)))
            onActivated: root.optionChanged("version", Number(currentValue))
        }

        StandardTextField {
            Layout.fillWidth: true
            visible: root.protocol === "vrrp"
            labelText: "VRRP version"
            text: "Version 2 (Cisco IOS)"
            readOnly: true
        }

        StandardSpinBox {
            Layout.fillWidth: true
            visible: root.protocol === "hsrp" || root.protocol === "glbp"
            labelText: "Hello timer (ms)"
            from: 1
            to: 255000
            value: root.helloMs
            onValueChanged: {
                if (value !== root.helloMs)
                    root.optionChanged("hello_ms", value)
            }
        }

        StandardSpinBox {
            Layout.fillWidth: true
            visible: root.protocol === "hsrp" || root.protocol === "glbp"
            labelText: "Hold timer (ms)"
            from: 2
            to: 255000
            value: root.holdMs
            onValueChanged: {
                if (value !== root.holdMs)
                    root.optionChanged("hold_ms", value)
            }
        }

        StandardSpinBox {
            Layout.fillWidth: true
            visible: root.protocol === "vrrp"
            labelText: "Advertisement interval (ms)"
            from: 1
            to: 60000
            value: root.advertisementMs
            onValueChanged: {
                if (value !== root.advertisementMs)
                    root.optionChanged("advertisement_ms", value)
            }
        }

        StandardComboBox {
            Layout.fillWidth: true
            visible: root.protocol === "glbp"
            labelText: "Load balancing"
            model: ["Round robin", "Weighted", "Host dependent"]
            valueModel: ["round-robin", "weighted", "host-dependent"]
            currentIndex: Math.max(0, valueModel.indexOf(root.loadBalancing))
            onActivated: root.optionChanged("load_balancing", currentValue)
        }
    }

    Text {
        Layout.fillWidth: true
        text: root.protocol === "vrrp"
              ? "VRRPv3 and Accept Mode are unavailable because this Cisco IOS workflow uses classic VRRPv2 syntax."
              : "Timers and group-wide protocol behavior are applied identically to every member."
        color: Theme.textDisabled
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSmall
        wrapMode: Text.WordWrap
    }
}
