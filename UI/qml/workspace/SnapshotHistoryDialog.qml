pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: root

    property var snapshots: []

    signal createRequested(string label)
    signal rollbackRequested(string snapshotId, string label)

    title: "Snapshot History"
    subtitle: "Whole-project recovery points"
    preferredWidth: 720
    implicitHeight: 590

    function openForCreate() {
        root.open()
        Qt.callLater(snapshotLabelField.forceActiveFocus)
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacing12

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            StandardTextField {
                id: snapshotLabelField
                objectName: "snapshotLabelField"
                Layout.fillWidth: true
                labelText: "New snapshot label"
                placeholderText: "Optional label"
                onAccepted: createSnapshotButton.clicked()
            }

            StandardButton {
                id: createSnapshotButton
                objectName: "createWorkspaceSnapshotButton"
                Layout.alignment: Qt.AlignBottom
                text: "Create Snapshot"
                type: "Primary"
                onClicked: {
                    root.createRequested(snapshotLabelField.text.trim())
                    snapshotLabelField.clear()
                }
            }
        }

        InlineMessage {
            Layout.fillWidth: true
            message: "Snapshots contain consistent database images and backup files. Automatic history is limited to 20 entries."
            severity: "info"
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.inputBackground
            border.color: Theme.borderColor
            border.width: Theme.borderWidth
            radius: Theme.radiusSmall

            Text {
                anchors.centerIn: parent
                visible: snapshotList.count === 0
                text: "No snapshots yet"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
            }

            ListView {
                id: snapshotList
                objectName: "workspaceSnapshotList"
                anchors.fill: parent
                anchors.margins: Theme.spacing8
                clip: true
                spacing: Theme.spacing4
                model: root.snapshots

                delegate: Rectangle {
                    id: row
                    required property var modelData
                    width: ListView.view.width
                    height: 74
                    color: rowMouse.containsMouse
                           ? Theme.hoverBackground
                           : "transparent"
                    radius: Theme.radiusSmall

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing12
                        anchors.rightMargin: Theme.spacing8
                        spacing: Theme.spacing12

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing4

                            Text {
                                Layout.fillWidth: true
                                text: String(row.modelData.label || "Snapshot")
                                      + (row.modelData.pinned ? "  •  Pinned" : "")
                                color: Theme.textPrimary
                                elide: Text.ElideRight
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeNormal
                                font.weight: Font.DemiBold
                            }

                            Text {
                                Layout.fillWidth: true
                                text: String(row.modelData.createdAt || "")
                                      + "  •  " + String(row.modelData.reason || "manual")
                                color: Theme.textSecondary
                                elide: Text.ElideRight
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeSmall
                            }
                        }

                        StandardButton {
                            text: "Roll Back"
                            type: "Secondary"
                            onClicked: root.rollbackRequested(
                                String(row.modelData.id || ""),
                                String(row.modelData.label || "Snapshot")
                            )
                        }
                    }

                    HoverHandler { id: rowMouse }
                }

                ScrollBar.vertical: ScrollBar {}
            }
        }
    }
}
