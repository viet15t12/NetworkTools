pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

ItemDelegate {
    id: root

    property string projectName: ""
    property string projectPath: ""
    property string projectUrl: ""
    property string openedAt: ""

    signal removeClicked()

    Accessible.role: Accessible.ListItem
    Accessible.name: projectName
    Accessible.description: projectUrl + ", opened " + openedAt
    focusPolicy: Qt.StrongFocus

    implicitHeight: 82
    padding: Theme.spacing12

    HoverHandler {
        id: hoverHandler
        cursorShape: Qt.PointingHandCursor
    }

    background: Rectangle {
        radius: Theme.radiusSmall
        color: root.down
               ? Theme.sideBarItemSelected
               : (hoverHandler.hovered ? Theme.sideBarItemHover : "transparent")
        border.color: root.visualFocus ? Theme.accentColor : "transparent"
        border.width: root.visualFocus ? 2 : 0
    }

    contentItem: RowLayout {
        spacing: Theme.spacing12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing2

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing8

                Text {
                    Layout.fillWidth: true
                    text: root.projectName
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeNormal
                    font.bold: true
                    elide: Text.ElideRight
                }

                Text {
                    text: "Opened: " + root.openedAt
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeCaption
                }
            }

            Text {
                Layout.fillWidth: true
                text: "URL: " + root.projectUrl
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                elide: Text.ElideMiddle
            }
        }

        ThemedIcon {
            id: removeBtn
            visible: hoverHandler.hovered
            Layout.preferredWidth: Theme.iconSizeSmall
            Layout.preferredHeight: Theme.iconSizeSmall
            iconSource: AppAssets.actionClose
            iconSize: Theme.iconSizeSmall
            iconColor: removeHover.hovered ? Theme.notificationErrorAccent : Theme.textSecondary

            HoverHandler {
                id: removeHover
                cursorShape: Qt.PointingHandCursor
            }

            TapHandler {
                onTapped: root.removeClicked()
            }
        }

        ThemedIcon {
            visible: !removeBtn.visible
            Layout.preferredWidth: Theme.iconSizeSmall
            Layout.preferredHeight: Theme.iconSizeSmall
            iconSource: AppAssets.navigationChevronRight
            iconSize: Theme.iconSizeSmall
            iconColor: hoverHandler.hovered ? Theme.textPrimary : Theme.textSecondary
        }
    }
}
