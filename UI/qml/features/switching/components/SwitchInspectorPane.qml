pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

DataTableFrame {
    id: root

    property string title: "Details"
    property string subtitle: ""
    property bool hasContent: false
    property bool editing: false
    property string emptyTitle: "Nothing selected"
    property string emptyDescription: "Select a table row to inspect it."
    default property alias content: inspectorContent.data

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            color: Theme.inputBackground

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacing16
                anchors.rightMargin: Theme.spacing12
                spacing: Theme.spacing8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing2

                    Text {
                        Layout.fillWidth: true
                        text: root.title
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeNormal
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }

                    Text {
                        visible: root.subtitle !== ""
                        Layout.fillWidth: true
                        text: root.subtitle
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        elide: Text.ElideRight
                    }
                }

                Rectangle {
                    visible: root.hasContent
                    implicitWidth: modeLabel.implicitWidth + Theme.spacing16
                    implicitHeight: 22
                    radius: Theme.radiusRound
                    color: root.editing ? Theme.alertInfoSubtle : Theme.tableRowAlternate
                    border.color: root.editing ? Theme.alertInfo : Theme.contentPanelBorder
                    border.width: Theme.borderWidth

                    Text {
                        id: modeLabel
                        anchors.centerIn: parent
                        text: root.editing ? "Editing" : "Read only"
                        color: root.editing ? Theme.alertInfo : Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 3
                color: root.editing ? Theme.accentColor : Theme.contentPanelBorder
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.borderWidth
                color: Theme.contentPanelBorder
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            EmptyState {
                anchors.fill: parent
                visible: !root.hasContent
                title: root.emptyTitle
                description: root.emptyDescription
            }

            ScrollView {
                id: inspectorScroll
                anchors.fill: parent
                visible: root.hasContent
                clip: true
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                Item {
                    width: inspectorScroll.availableWidth
                    implicitHeight: inspectorContent.implicitHeight + Theme.spacing32

                    ColumnLayout {
                        id: inspectorContent
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Theme.spacing16
                        spacing: Theme.spacing12
                    }
                }
            }
        }
    }
}
