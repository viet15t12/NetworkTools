pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    required property var backend
    property int maximumEntries: 500
    readonly property int entryCount: logModel.count

    color: Theme.contentPanelSurface
    border.color: Theme.contentPanelBorder
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall

    ListModel { id: logModel }

    Connections {
        target: root.backend
        function onLogMessage(message, level) {
            while (logModel.count >= root.maximumEntries)
                logModel.remove(0)
            logModel.append({
                "time": new Date().toLocaleTimeString(Qt.locale(), "HH:mm:ss"),
                "message": message,
                "level": level
            })
            logList.positionViewAtEnd()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing4

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "SESSION LOG"
                color: Theme.textPrimary
                font.bold: true
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
            }
            Text {
                Layout.fillWidth: true
                text: logModel.count + (logModel.count === 1 ? " event" : " events")
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
            StandardButton {
                text: "Clear log"
                type: "Ghost"
                icon.source: AppAssets.actionDelete
                enabled: logModel.count > 0
                onClicked: logModel.clear()
            }
        }

        ListView {
            id: logList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: logModel
            spacing: Theme.spacing2
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Text {
                required property string time
                required property string message
                required property string level
                width: logList.width
                text: "[" + time + "] " + message
                color: level === "error" ? Theme.alertError
                     : level === "success" ? Theme.alertSuccess
                     : level === "warning" ? Theme.alertWarning
                     : Theme.textSecondary
                elide: Text.ElideRight
                font.family: Theme.monoFontFamily
                font.pixelSize: Theme.fontSizeSmall
            }

            Text {
                anchors.centerIn: parent
                visible: logList.count === 0
                text: "Session events will appear here"
                color: Theme.textDisabled
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
        }
    }
}
