pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

ColumnLayout {
    id: root
    spacing: 4
    Layout.minimumWidth: Theme.inputMinimumWidth

    // ── Public API ──
    property string labelText: ""
    property bool showIndicators: true
    // ── Alias xuống SpinBox bên trong ──
    property alias from: spinBox.from
    property alias to: spinBox.to
    property alias value: spinBox.value
    property alias stepSize: spinBox.stepSize
    property alias editable: spinBox.editable
    property alias inputActiveFocus: spinBox.activeFocus

    // ── Label hiển thị tên trường (nếu có) ──
    Text {
        visible: root.labelText !== ""
        text: root.labelText
        color: Theme.textSecondary
        font.pixelSize: Theme.fontSizeSmall
        font.family: Theme.fontFamily
    }

    // ── SpinBox chính ──
    SpinBox {
        id: spinBox
        objectName: "standardSpinBoxControl"
        Layout.fillWidth: true
        implicitHeight: Theme.itemHeight
        editable: true // Mặc định cho phép gõ phím
        // Qt's base SpinBox reserves indicator padding on both sides. The
        // indicators in this component both live on the right, so keep the
        // control padding neutral and let the TextInput own its exact inset.
        leftPadding: 0
        rightPadding: 0

        background: Rectangle {
            color: Theme.inputBackground
            border.color: spinBox.activeFocus ? Theme.inputBorderFocusColor : Theme.inputBorderColor
            border.width: Theme.borderWidth
            radius: Theme.radiusSmall
        }

        contentItem: TextInput {
            objectName: "standardSpinBoxInput"
            text: spinBox.textFromValue(spinBox.value, spinBox.locale)
            font.pixelSize: Theme.fontSizeNormal
            font.family: Theme.fontFamily
            color: Theme.textPrimary
            selectionColor: Theme.selectionBackground
            selectedTextColor: Theme.selectionForeground
            horizontalAlignment: Qt.AlignLeft
            verticalAlignment: Qt.AlignVCenter
            leftPadding: Theme.spacing12
            rightPadding: root.showIndicators
                          ? spinBox.up.indicator.width + Theme.spacing8
                          : Theme.spacing12
            readOnly: !spinBox.editable
            validator: spinBox.validator
            inputMethodHints: Qt.ImhFormattedNumbersOnly
            opacity: spinBox.enabled ? 1.0 : 0.5
        }

        up.indicator: Rectangle {
            objectName: "standardSpinBoxUpIndicator"
            visible: root.showIndicators
            z: 2
            x: spinBox.mirrored ? 1 : parent.width - width - 1
            y: 1
            width: 28
            height: (parent.height - 2) / 2
            color: upMouseArea.pressed
                   ? Theme.sideBarItemSelected
                   : (upMouseArea.containsMouse ? Theme.sideBarItemHover : "transparent")
            opacity: upMouseArea.enabled ? 1.0 : 0.45
            radius: Theme.radiusSmall

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Theme.borderWidth
                color: Theme.inputBorderColor
            }

            ThemedIcon {
                anchors.centerIn: parent
                iconSource: AppAssets.navigationChevronUp
                iconSize: Theme.iconSizeSmall
                iconColor: Theme.textSecondary
                opacity: 0.7
            }

            MouseArea {
                id: upMouseArea
                anchors.fill: parent
                enabled: spinBox.enabled && root.showIndicators && spinBox.value < spinBox.to
                hoverEnabled: true
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: spinBox.increase()
            }
        }

        down.indicator: Rectangle {
            objectName: "standardSpinBoxDownIndicator"
            visible: root.showIndicators
            z: 2
            x: spinBox.mirrored ? 1 : parent.width - width - 1
            y: parent.height / 2
            width: 28
            height: (parent.height - 2) / 2
            color: downMouseArea.pressed
                   ? Theme.sideBarItemSelected
                   : (downMouseArea.containsMouse ? Theme.sideBarItemHover : "transparent")
            opacity: downMouseArea.enabled ? 1.0 : 0.45
            radius: Theme.radiusSmall

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Theme.borderWidth
                color: Theme.inputBorderColor
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: Theme.borderWidth
                color: Theme.inputBorderColor
            }

            ThemedIcon {
                anchors.centerIn: parent
                iconSource: AppAssets.navigationChevronDown
                iconSize: Theme.iconSizeSmall
                iconColor: Theme.textSecondary
                opacity: 0.7
            }

            MouseArea {
                id: downMouseArea
                anchors.fill: parent
                enabled: spinBox.enabled && root.showIndicators && spinBox.value > spinBox.from
                hoverEnabled: true
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: spinBox.decrease()
            }
        }
    }
}
