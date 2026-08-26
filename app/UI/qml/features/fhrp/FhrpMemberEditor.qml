pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

// Per-host fields are isolated from FhrpView's group-level orchestration.
Rectangle {
    id: root

    required property int memberIndex
    required property string protocol
    required property string host
    required property var interfaceOptions
    required property int ifaceId
    required property string interfaceKind
    required property string priority
    required property bool preempt
    required property int preemptDelayMinSec
    required property int preemptDelayReloadSec
    required property int weightingMax
    required property int weightingLower
    required property int weightingUpper
    required property bool forwarderPreempt
    required property int forwarderPreemptDelaySec
    required property var tracks
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

    function trackCount() {
        if (!tracks)
            return 0
        if (typeof tracks.count === "number")
            return tracks.count
        return tracks.length || 0
    }

    function trackAt(index) {
        return tracks && typeof tracks.get === "function"
                ? tracks.get(index) : tracks[index]
    }

    function trackPayload(changedIndex, field, value, removedIndex) {
        const result = []
        for (let i = 0; i < trackCount(); i++) {
            if (i === removedIndex)
                continue
            const row = trackAt(i)
            const item = {
                track_object: String(row.track_object || ""),
                decrement_value: Number(row.decrement_value || 10)
            }
            if (i === changedIndex)
                item[field] = value
            result.push(item)
        }
        return result
    }

    function updateTrack(index, field, value) {
        root.fieldChanged(root.memberIndex, "tracks",
                          trackPayload(index, field, value, -1))
    }

    function addTrack() {
        const result = trackPayload(-1, "", null, -1)
        result.push({track_object: "", decrement_value: 10})
        root.fieldChanged(root.memberIndex, "tracks", result)
    }

    function removeTrack(index) {
        root.fieldChanged(root.memberIndex, "tracks",
                          trackPayload(-1, "", null, index))
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

        GridLayout {
            Layout.fillWidth: true
            visible: root.protocol === "hsrp"
            columns: width < 760 ? 1 : 2
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            StandardSpinBox {
                Layout.fillWidth: true
                labelText: "Preempt minimum delay (sec)"
                from: 0
                to: 3600
                value: root.preemptDelayMinSec
                enabled: root.preempt
                onValueChanged: {
                    if (value !== root.preemptDelayMinSec)
                        root.fieldChanged(root.memberIndex,
                                          "preemptDelayMinSec", value)
                }
            }
            StandardSpinBox {
                Layout.fillWidth: true
                labelText: "Preempt reload delay (sec)"
                from: 0
                to: 3600
                value: root.preemptDelayReloadSec
                enabled: root.preempt
                onValueChanged: {
                    if (value !== root.preemptDelayReloadSec)
                        root.fieldChanged(root.memberIndex,
                                          "preemptDelayReloadSec", value)
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            visible: root.protocol === "glbp"
            columns: width < 760 ? 1 : 3
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing8

            StandardSpinBox {
                Layout.fillWidth: true
                labelText: "Maximum weighting"
                from: 1
                to: 254
                value: root.weightingMax
                onValueChanged: {
                    if (value !== root.weightingMax)
                        root.fieldChanged(root.memberIndex, "weightingMax", value)
                }
            }
            StandardSpinBox {
                Layout.fillWidth: true
                labelText: "Lower threshold (0 = unset)"
                from: 0
                to: 254
                value: root.weightingLower
                onValueChanged: {
                    if (value !== root.weightingLower)
                        root.fieldChanged(root.memberIndex, "weightingLower", value)
                }
            }
            StandardSpinBox {
                Layout.fillWidth: true
                labelText: "Upper threshold (0 = unset)"
                from: 0
                to: 254
                value: root.weightingUpper
                onValueChanged: {
                    if (value !== root.weightingUpper)
                        root.fieldChanged(root.memberIndex, "weightingUpper", value)
                }
            }
            StandardCheckBox {
                Layout.columnSpan: parent.columns === 1 ? 1 : 2
                text: "Forwarder preempt"
                checked: root.forwarderPreempt
                onToggled: root.fieldChanged(
                               root.memberIndex, "forwarderPreempt", checked)
            }
            StandardSpinBox {
                Layout.fillWidth: true
                labelText: "Forwarder preempt delay (sec)"
                from: 0
                to: 3600
                value: root.forwarderPreemptDelaySec
                enabled: root.forwarderPreempt
                onValueChanged: {
                    if (value !== root.forwarderPreemptDelaySec)
                        root.fieldChanged(root.memberIndex,
                                          "forwarderPreemptDelaySec", value)
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: Theme.borderWidth
            color: Theme.contentPanelBorder
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing2
                Text {
                    text: "Tracking objects"
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeNormal
                    font.bold: true
                }
                Text {
                    text: "Lower this member's election value when a tracked object fails."
                    color: Theme.textDisabled
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }
            StandardButton {
                objectName: "fhrpAddTrackButton"
                text: "Add tracking object"
                type: "Text"
                onClicked: root.addTrack()
            }
        }

        Repeater {
            model: root.tracks || []
            delegate: RowLayout {
                id: trackRow
                required property int index
                required property var modelData
                Layout.fillWidth: true
                spacing: Theme.spacing8

                StandardTextField {
                    Layout.fillWidth: true
                    labelText: "Track object"
                    placeholderText: "Interface or object ID"
                    text: String(trackRow.modelData.track_object || "")
                    onTextEdited: value => root.updateTrack(
                                      trackRow.index, "track_object", value)
                }
                StandardSpinBox {
                    Layout.preferredWidth: 180
                    labelText: "Decrement"
                    from: 1
                    to: 254
                    value: Number(trackRow.modelData.decrement_value || 10)
                    onValueChanged: {
                        if (value !== Number(trackRow.modelData.decrement_value || 10))
                            root.updateTrack(trackRow.index,
                                             "decrement_value", value)
                    }
                }
                RemoveIconButton {
                    Layout.alignment: Qt.AlignBottom
                    tooltip: "Remove tracking object"
                    onClicked: root.removeTrack(trackRow.index)
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.protocol === "glbp"
                  ? "Priority elects the AVG; weighting and tracking influence AVF forwarding eligibility."
                  : "Higher priority becomes the active gateway. Preempt lets this router reclaim the role after recovery."
            color: Theme.textDisabled
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            wrapMode: Text.WordWrap
        }
    }
}
