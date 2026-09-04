pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    property var interfaceLabels: ["None"]
    property var interfaceIds: []
    property bool readOnly: false
    signal bindingDataChanged()

    function reset() {
        bindingModel.clear()
        iface.currentIndex = 0
        direction.currentIndex = 0
        bindingDataChanged()
    }

    function loadBindings(bindings) {
        reset()
        for (let i = 0; i < bindings.length; ++i) {
            const item = bindings[i]
            let name = item.interface_name || "Interface #" + item.iface_id
            bindingModel.append({
                ifaceId: Number(item.iface_id || 0),
                ifaceName: name,
                bindDirection: String(item.direction || "in").toLowerCase()
            })
        }
        bindingDataChanged()
    }

    function payload() {
        const result = []
        for (let i = 0; i < bindingModel.count; ++i) {
            const item = bindingModel.get(i)
            result.push({ iface_id: item.ifaceId, direction: item.bindDirection })
        }
        return result
    }

    function signature() { return JSON.stringify(payload()) }

    function addBinding() {
        if (iface.currentIndex <= 0) return
        const ifaceId = interfaceIds[iface.currentIndex - 1] || 0
        const bindDirection = direction.currentIndex === 1 ? "out" : "in"
        for (let i = 0; i < bindingModel.count; ++i) {
            const item = bindingModel.get(i)
            if (item.ifaceId === ifaceId && item.bindDirection === bindDirection)
                return
        }
        bindingModel.append({
            ifaceId: ifaceId,
            ifaceName: interfaceLabels[iface.currentIndex],
            bindDirection: bindDirection
        })
        bindingDataChanged()
    }

    function removeBinding(index) {
        if (index < 0 || index >= bindingModel.count) return
        bindingModel.remove(index)
        bindingDataChanged()
    }

    implicitHeight: content.implicitHeight + 20
    radius: Theme.cardRadius
    color: Theme.contentSurface
    border.color: Theme.borderColor
    border.width: Theme.borderWidth

    ListModel { id: bindingModel }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 10
        spacing: Theme.spacing8

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8
            Text {
                Layout.fillWidth: true
                text: "Interface Bindings"
                color: Theme.textPrimary
                font.bold: true
                font.family: Theme.fontFamily
            }
            ParameterHelpButton {
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
                helpTitle: "ACL interface binding parameters"
                helpText: "Interface selects where the ACL is applied. Direction In filters packets as they enter the interface; Out filters packets before they leave. Avoid applying the same policy in both directions unless that behavior is intentional."
            }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardComboBox {
                id: iface
                enabled: !root.readOnly
                Layout.fillWidth: true
                labelText: "Interface"
                model: root.interfaceLabels
            }
            StandardComboBox {
                id: direction
                enabled: !root.readOnly
                Layout.preferredWidth: 100
                labelText: "Direction"
                model: ["In", "Out"]
            }
            StandardButton {
                enabled: !root.readOnly && iface.currentIndex > 0
                Layout.alignment: Qt.AlignBottom
                text: "Add"
                type: "Secondary"
                onClicked: root.addBinding()
            }
        }

        Repeater {
            model: bindingModel
            delegate: RowLayout {
                required property int index
                required property int ifaceId
                required property string ifaceName
                required property string bindDirection
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: ifaceName
                    color: Theme.textSecondary
                    elide: Text.ElideRight
                }
                StandardBadge { text: bindDirection.toUpperCase() }
                StandardButton {
                    visible: !root.readOnly
                    text: "Remove"
                    type: "Secondary"
                    onClicked: root.removeBinding(index)
                }
            }
        }

        Text {
            visible: bindingModel.count === 0
            text: "No interface binding. This ACL can be saved and applied later."
            color: Theme.textDisabled
            font.pixelSize: Theme.fontSizeSmall
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
