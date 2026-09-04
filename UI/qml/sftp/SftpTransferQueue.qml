pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    required property var backend
    readonly property bool backendAvailable: backend !== null && backend !== undefined
    color: Theme.contentPanelSurface
    border.color: Theme.contentPanelBorder
    radius: Theme.radiusSmall

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing4

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "FILE TRANSFER QUEUE"
                color: Theme.textPrimary
                font.bold: true
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
            }
            Item { Layout.fillWidth: true }
            StandardButton {
                text: "Clear finished"
                type: "Ghost"
                icon.source: AppAssets.actionDelete
                enabled: root.backendAvailable
                onClicked: {
                    if (root.backendAvailable)
                        root.backend.transferModel.clearFinished()
                }
            }
        }
        ListView {
            id: transferList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.backendAvailable ? root.backend.transferModel : null
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: row
                required property int index
                required property string taskId
                required property string name
                required property string direction
                required property string status
                required property real progress
                required property string detail
                width: transferList.width
                height: 44
                color: index % 2 ? Theme.sideBarBackground : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacing8
                    anchors.rightMargin: Theme.spacing8
                    spacing: Theme.spacing8
                    ThemedIcon {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: Theme.iconSizeNormal
                        iconSource: row.direction === "upload"
                                    ? AppAssets.fileTransferUpload
                                    : AppAssets.fileTransferDownload
                        iconColor: row.direction === "upload"
                            ? Theme.alertSuccess : Theme.alertInfo
                        iconSize: Theme.iconSizeNormal
                    }
                    Text {
                        Layout.preferredWidth: parent.width * 0.28
                        text: row.name
                        elide: Text.ElideRight
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                    }
                    ProgressBar {
                        Layout.fillWidth: true
                        value: row.progress
                    }
                    Text {
                        Layout.preferredWidth: parent.width * 0.28
                        text: row.status + "  " + row.detail
                        elide: Text.ElideRight
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                    }
                    StandardButton {
                        text: "Cancel"
                        type: "Text"
                        enabled: row.status === "Waiting"
                                 || row.status === "Transferring"
                        onClicked: {
                            if (root.backendAvailable)
                                root.backend.cancelTransfer(row.taskId)
                        }
                    }
                }
            }
            Text {
                anchors.centerIn: parent
                visible: transferList.count === 0
                text: "No file transfers yet"
                color: Theme.textDisabled
                font.family: Theme.fontFamily
            }
        }
    }
}
