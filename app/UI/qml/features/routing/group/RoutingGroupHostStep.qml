pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

FormSection {
    id: root
    required property var targetModel
    required property var controller
    title: "Select participating hosts (2–5 devices)"
    helpText: "Select between 2 and 5 connected routers that will receive the shared routing configuration. Only checked hosts are changed. Review device reachability and interface synchronization before continuing."

    Repeater {
        model: root.targetModel
        delegate: RowLayout {
            required property int index
            required property string host
            required property string deviceName
            required property bool selected
            Layout.fillWidth: true
            StandardCheckBox {
                text: host
                checked: selected
                enabled: selected
                         || root.controller.selectedCount < root.controller.maxHosts
                onToggled: root.controller.updateSelected(index, checked)
            }
            Text {
                Layout.fillWidth: true
                text: deviceName
                color: Theme.textSecondary
                font.family: Theme.fontFamily
            }
        }
    }
}
