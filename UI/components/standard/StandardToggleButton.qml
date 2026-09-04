pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Button {
    id: root

    property string description: ""
    property color textColor: Theme.textPrimary
    property color descriptionColor: Theme.textSecondary
    property color checkedTrackColor: Theme.accentEmphasis
    property color uncheckedTrackColor: Theme.inputBorderColor
    property color checkedKnobColor: Theme.buttonTextSolid
    property color uncheckedKnobColor: Theme.contentSurface

    checkable: true
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0

    implicitWidth: Math.max(180, toggleContent.implicitWidth)
    implicitHeight: Math.max(28, toggleContent.implicitHeight)

    HoverHandler {
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
    }

    background: Rectangle {
        color: "transparent"
        radius: Theme.radiusSmall
        border.width: root.visualFocus ? Theme.borderWidth : 0
        border.color: Theme.accentColor
    }

    contentItem: RowLayout {
        id: toggleContent
        spacing: Theme.spacing12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                visible: root.text !== ""
                Layout.fillWidth: true
                text: root.text
                color: root.enabled ? root.textColor : Theme.textDisabled
                font.pixelSize: Theme.fontSizeNormal
                font.family: Theme.fontFamily
                font.weight: Font.Medium
                elide: Text.ElideRight
            }

            Text {
                visible: root.description !== ""
                Layout.fillWidth: true
                text: root.description
                color: root.enabled ? root.descriptionColor : Theme.textDisabled
                font.pixelSize: Theme.fontSizeSmall
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            Layout.alignment: Qt.AlignVCenter
            Layout.preferredWidth: 42
            Layout.preferredHeight: 24
            radius: height / 2
            color: root.checked ? root.checkedTrackColor : root.uncheckedTrackColor
            opacity: root.enabled ? 1.0 : 0.55
            border.width: root.checked ? 0 : Theme.borderWidth
            border.color: Theme.borderColor

            Rectangle {
                width: 18
                height: 18
                radius: 9
                x: root.checked ? parent.width - width - 3 : 3
                anchors.verticalCenter: parent.verticalCenter
                color: root.checked ? root.checkedKnobColor : root.uncheckedKnobColor
                border.width: root.checked ? 0 : Theme.borderWidth
                border.color: Theme.borderColor

                Behavior on x {
                    NumberAnimation {
                        duration: Theme.animationDurationFast
                        easing.type: Easing.OutQuad
                    }
                }
            }
        }
    }
}
