pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    required property var form

    visible: String(form.currentHostIp || "").trim() !== ""
        && form.activeRoutingSection === "Passive iface"
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
            text: "OSPF PASSIVE INTERFACES"
            helpText: "Interface: exact IOS interface name, for example GigabitEthernet0/0.\n\n" +
                      "Passive: stops OSPF hello packets and neighbor formation on the interface while still advertising its connected network. Clear it to override a passive-default policy."
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width < 760 ? 2 : 4
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            RoutingProcessComboBox { form: root.form; protocol: "OSPF" }
            StandardTextField { id: ifaceField; Layout.fillWidth: true; labelText: "Interface"; placeholderText: "GigabitEthernet0/0" }
            StandardCheckBox { id: passiveCheck; text: "Passive"; checked: true; Layout.alignment: Qt.AlignBottom }
            StandardButton {
                text: "+ Add"
                type: "Primary"
                Layout.alignment: Qt.AlignBottom
                onClicked: {
                    if (root.form.addPassiveInterfaceToSelectedProcess(ifaceField.text, passiveCheck.checked))
                        ifaceField.clear()
                }
            }
        }

        Repeater {
            model: {
                const revision = root.form.statsRevision
                const item = root.form.selectedProcessItem()
                return item ? item.passiveInterfaces : null
            }
            delegate: RowLayout {
                required property string interface_name
                required property bool passive
                required property int index
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: interface_name; color: Theme.accentColor; font.family: Theme.fontFamily }
                Text { Layout.fillWidth: true; text: passive ? "passive" : "no passive"; color: Theme.textPrimary; font.family: Theme.fontFamily }
                RemoveIconButton { tooltip: "Remove passive interface"; onClicked: root.form.removePassiveInterfaceFromSelectedProcess(index) }
            }
        }
    }
}
