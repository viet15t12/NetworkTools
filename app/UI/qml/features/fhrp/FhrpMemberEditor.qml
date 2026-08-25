pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

// Per-host fields are isolated from FhrpView's group-level orchestration.
Rectangle {
    id: root

    required property int memberIndex
    required property string host
    required property var interfaceOptions
    required property int ifaceId
    required property string interfaceKind
    required property string priority
    required property bool preempt
    signal fieldChanged(int memberIndex, string field, var value)

    readonly property bool hasMatchingInterface: interfaceOptionCount() > 0

    Layout.fillWidth: true
    implicitHeight: layout.implicitHeight + Theme.spacing32
    radius: Theme.cardRadius
    color: root.hasMatchingInterface
           ? Theme.contentPanelSurface : Theme.alertWarningSubtle
    border.color: root.hasMatchingInterface
                  ? Theme.contentPanelBorder : Theme.alertWarning
    border.width: Theme.borderWidth

    function interfaceOptionCount() {
        if (!interfaceOptions)
            return 0
        if (typeof interfaceOptions.count === "number")
            return interfaceOptions.count
        return interfaceOptions.length || 0
    }

    function interfaceOptionAt(index) {
        return typeof interfaceOptions.get === "function"
               ? interfaceOptions.get(index) : interfaceOptions[index]
    }

    function interfaceLabels() {
        const labels = []
        for (let i = 0; i < interfaceOptionCount(); i++) {
            const item = interfaceOptionAt(i)
            labels.push(item.interface_name + " · " + item.ip_address
                        + " (" + item.network + ")")
        }
        return labels
    }

    function interfaceKeys() {
        const keys = []
        for (let i = 0; i < interfaceOptionCount(); i++)
            keys.push(String(interfaceOptionAt(i).interface_kind)
                      + ":" + String(interfaceOptionAt(i).iface_id))
        return keys
    }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: Theme.spacing16
        spacing: Theme.spacing12

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            Rectangle {
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30
                radius: 15
                color: Theme.accentEmphasis
                Text {
                    anchors.centerIn: parent
                    text: String(root.memberIndex + 1)
                    color: Theme.buttonTextSolid
                    font.family: Theme.fontFamily
                    font.bold: true
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing2
                Text {
                    Layout.fillWidth: true
                    text: root.host
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeNormal
                    font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: root.hasMatchingInterface
                          ? root.interfaceOptionCount() + " eligible interface(s)"
                          : "No interface reaches the virtual gateway"
                    color: root.hasMatchingInterface
                           ? Theme.textSecondary : Theme.alertWarning
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            StandardBadge {
                text: root.hasMatchingInterface ? "READY" : "NO MATCH"
                badgeColor: root.hasMatchingInterface
                            ? Theme.statusConnected : Theme.alertWarning
            }

            StandardCheckBox {
                text: "Preempt"
                checked: root.preempt
                onToggled: root.fieldChanged(
                               root.memberIndex, "preempt", checked)
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: Theme.borderWidth
            color: Theme.contentPanelBorder
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width < 760 ? 1 : 2
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            StandardComboBox {
                Layout.fillWidth: true
                labelText: "Gateway-facing interface"
                model: root.interfaceLabels()
                valueModel: root.interfaceKeys()
                emptyText: "No eligible interface"
                currentIndex: {
                    const values = root.interfaceKeys()
                    return Math.max(0, values.indexOf(
                                        root.interfaceKind + ":" + String(root.ifaceId)))
                }
                onActivated: root.fieldChanged(
                                 root.memberIndex, "interfaceKey", currentValue)
            }
            StandardTextField {
                Layout.fillWidth: true
                labelText: "Priority"
                text: root.priority
                inputMethodHints: Qt.ImhDigitsOnly
                onTextEdited: value => root.fieldChanged(
                                  root.memberIndex, "priority", value)
            }
        }

        Text {
            Layout.fillWidth: true
            text: "Higher priority becomes the active gateway. Preempt lets this router reclaim the role after recovery."
            color: Theme.textDisabled
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            wrapMode: Text.WordWrap
        }
    }
}
