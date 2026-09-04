pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Button {
    id: root

    property url actionIcon
    property string titleText: ""
    property string descriptionText: ""

    Accessible.role: Accessible.Button
    Accessible.name: titleText
    Accessible.description: descriptionText
    focusPolicy: Qt.StrongFocus

    implicitWidth: 210
    implicitHeight: 92
    padding: Theme.spacing16

    HoverHandler {
        id: hoverHandler
        cursorShape: Qt.PointingHandCursor
    }

    background: Rectangle {
        radius: Theme.radiusMedium
        color: root.down
               ? Theme.sideBarItemSelected
               : (hoverHandler.hovered ? Theme.sideBarItemHover : Theme.contentPanelSurface)
        border.color: root.visualFocus || hoverHandler.hovered
                      ? Theme.accentColor : Theme.contentPanelBorder
        border.width: root.visualFocus ? 2 : Theme.borderWidth

        Behavior on color {
            ColorAnimation { duration: Theme.animationDurationFast }
        }
    }

    contentItem: RowLayout {
        spacing: Theme.spacing12

        Rectangle {
            Layout.preferredWidth: 40
            Layout.preferredHeight: 40
            Layout.alignment: Qt.AlignTop
            radius: Theme.radiusMedium
            color: Theme.selectionBackground

            ThemedIcon {
                anchors.centerIn: parent
                iconSource: root.actionIcon
                iconSize: Theme.iconSizeLarge
                iconColor: Theme.selectionForeground
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: Theme.spacing4

            Text {
                Layout.fillWidth: true
                text: root.titleText
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
                font.bold: true
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: root.descriptionText
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }
    }
}
