pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    required property var form

    visible: String(form.currentHostIp || "").trim() !== ""
        && form.activeRoutingSection === "Interfaces"
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
            text: "OSPF INTERFACE SETTINGS"
            helpText: "Process: OSPF process to update.\n\n" +
                      "Interface: exact IOS interface name.\n\n" +
                      "Area: area assigned directly to this interface. Direct interface settings take precedence over broad network matching."
        }

        Text {
            Layout.fillWidth: true
            text: "Choose the process and interface first, then tune adjacency and authentication."
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            wrapMode: Text.WordWrap
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width < 720 ? 1 : 3
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            RoutingProcessComboBox { form: root.form; protocol: "OSPF" }
            StandardTextField { id: nameField; Layout.fillWidth: true; labelText: "Interface"; placeholderText: "GigabitEthernet0/0" }
            StandardTextField { id: areaField; Layout.fillWidth: true; labelText: "Area"; placeholderText: "0" }
        }

        SectionTitle {
            text: "PATH AND ADJACENCY"
            helpText: "Cost: OSPF interface metric; lower cost is preferred.\n\n" +
                      "Priority: DR/BDR election priority, 0-255; 0 makes the router ineligible.\n\n" +
                      "Hello/Dead: neighbor timers in seconds; values must match on the link.\n\n" +
                      "Network type: broadcast, non-broadcast, point-to-point, or point-to-multipoint.\n\n" +
                      "MTU ignore: allows adjacency despite an MTU mismatch. BFD: enables rapid neighbor failure detection."
        }
        GridLayout {
            Layout.fillWidth: true
            columns: width < 720 ? 2 : 4
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8
            StandardTextField { id: costField; Layout.fillWidth: true; labelText: "Cost"; placeholderText: "optional" }
            StandardTextField { id: priorityField; Layout.fillWidth: true; labelText: "Priority"; text: "1" }
            StandardTextField { id: helloField; Layout.fillWidth: true; labelText: "Hello"; placeholderText: "optional" }
            StandardTextField { id: deadField; Layout.fillWidth: true; labelText: "Dead"; placeholderText: "optional" }
            StandardComboBox { id: networkTypeCombo; Layout.fillWidth: true; labelText: "Network type"; model: ["", "broadcast", "non-broadcast", "point-to-point", "point-to-multipoint"] }
            StandardCheckBox { id: mtuCheck; text: "MTU ignore"; Layout.alignment: Qt.AlignBottom }
            StandardCheckBox { id: bfdCheck; text: "BFD"; Layout.alignment: Qt.AlignBottom }
        }

        SectionTitle {
            text: "AUTHENTICATION"
            helpText: "Auth: authentication method for OSPF packets on this interface. Both neighbors must use the same method.\n\n" +
                      "Authentication key: shared secret used by the selected method. Configure the identical key on the peer and protect it as sensitive data."
        }
        GridLayout {
            Layout.fillWidth: true
            columns: width < 720 ? 1 : 2
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8
            StandardComboBox {
                id: authTypeCombo
                Layout.fillWidth: true
                labelText: "Auth"
                model: ["None", "plain", "message-digest"]
                valueModel: ["", "plain", "message-digest"]
            }
            StandardPasswordField {
                id: authKeyField
                Layout.fillWidth: true
                enabled: authTypeCombo.currentValue !== ""
                labelText: "Authentication key"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardButton {
                text: "+ Add Interface Setting"
                type: "Primary"
                onClicked: root.form.addInterfaceSettingToSelectedProcess(
                               nameField.text, areaField.text, costField.text,
                               priorityField.text, helloField.text, deadField.text,
                               mtuCheck.checked, bfdCheck.checked,
                               networkTypeCombo.currentText,
                               authTypeCombo.currentValue, authKeyField.text)
            }
            Item { Layout.fillWidth: true }
        }

        Repeater {
            model: {
                const revision = root.form.statsRevision
                const item = root.form.selectedProcessItem()
                return item ? item.interfaceSettings : null
            }
            delegate: RowLayout {
                required property string interface_name
                required property string area
                required property string cost
                required property string priority
                required property string hello_interval
                required property string dead_interval
                required property string network_type
                required property string auth_type
                required property int index
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: interface_name; color: Theme.accentColor; font.family: Theme.fontFamily; elide: Text.ElideRight }
                Text { Layout.preferredWidth: 72; text: "area " + area; color: Theme.textPrimary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: (cost ? ("cost " + cost + " · ") : "") + "priority " + priority; color: Theme.textSecondary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: hello_interval || dead_interval ? ("hello/dead " + hello_interval + "/" + dead_interval) : ""; color: Theme.textSecondary; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: network_type || auth_type || "None"; color: Theme.textSecondary; font.family: Theme.fontFamily; elide: Text.ElideRight }
                RemoveIconButton { tooltip: "Remove interface setting"; onClicked: root.form.removeInterfaceSettingFromSelectedProcess(index) }
            }
        }
    }
}
