pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Item {
    id: root

    property var options: []
    property var selectedValues: []
    property string allText: "All"
    property string pluralText: "items"
    property string accessibleName: allText
    readonly property string summaryText: {
        if (!selectedValues || selectedValues.length === 0)
            return allText
        if (selectedValues.length === 1)
            return labelFor(selectedValues[0])
        return selectedValues.length + " " + pluralText + " selected"
    }

    signal selectionChanged(var values)

    implicitHeight: Theme.itemHeight
    Layout.minimumWidth: Theme.inputMinimumWidth

    function sameValue(left, right) {
        return String(left) === String(right)
    }

    function containsValue(value) {
        for (let i = 0; i < selectedValues.length; ++i) {
            if (sameValue(selectedValues[i], value)) return true
        }
        return false
    }

    function labelFor(value) {
        for (let i = 0; i < options.length; ++i) {
            if (sameValue(options[i].value, value)) return String(options[i].label)
        }
        return String(value)
    }

    function toggleValue(value) {
        const next = selectedValues ? selectedValues.slice() : []
        let found = -1
        for (let i = 0; i < next.length; ++i) {
            if (sameValue(next[i], value)) {
                found = i
                break
            }
        }
        if (found >= 0) next.splice(found, 1)
        else next.push(value)
        selectionChanged(next)
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.inputBackground
        border.color: menu.opened ? Theme.inputBorderFocusColor : Theme.inputBorderColor
        border.width: Theme.borderWidth
        radius: Theme.radiusSmall

        Text {
            anchors.left: parent.left
            anchors.right: indicator.left
            anchors.leftMargin: Theme.spacing12
            anchors.rightMargin: Theme.spacing8
            anchors.verticalCenter: parent.verticalCenter
            text: root.summaryText
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            elide: Text.ElideRight
        }

        ThemedIcon {
            id: indicator
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacing8
            anchors.verticalCenter: parent.verticalCenter
            iconSource: AppAssets.navigationChevronDown
            iconSize: Theme.iconSizeSmall
            iconColor: Theme.textSecondary
            rotation: menu.opened ? 180 : 0
        }
    }

    Accessible.role: Accessible.ComboBox
    Accessible.name: accessibleName
    Accessible.description: summaryText

    TapHandler {
        onTapped: menu.opened ? menu.close() : menu.open()
    }

    Popup {
        id: menu
        objectName: "syslogMultiSelectPopup"
        y: root.height + Theme.spacing4
        width: Math.max(root.width, 250)
        height: Math.min(54 + root.options.length * 36, 310)
        padding: Theme.spacing8
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: Theme.contentPanelSurface
            border.color: Theme.contentPanelBorder
            border.width: Theme.borderWidth
            radius: Theme.radiusSmall
        }

        contentItem: ColumnLayout {
            spacing: Theme.spacing4

            StandardCheckBox {
                Layout.fillWidth: true
                text: root.allText
                checked: root.selectedValues.length === 0
                onClicked: {
                    if (root.selectedValues.length > 0)
                        root.selectionChanged([])
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Theme.borderWidth
                color: Theme.contentPanelBorder
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                Column {
                    width: parent.width
                    Repeater {
                        model: root.options
                        delegate: StandardCheckBox {
                            required property var modelData
                            width: parent.width
                            text: String(modelData.label)
                            checked: root.containsValue(modelData.value)
                            onClicked: root.toggleValue(modelData.value)
                        }
                    }
                }
            }
        }
    }
}
