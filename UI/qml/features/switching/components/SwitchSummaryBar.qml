pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    property var metrics: []
    readonly property bool compact: width < 680 && metrics.length > 2

    function toneColor(tone) {
        switch (String(tone || "neutral")) {
        case "accent": return Theme.accentColor
        case "success": return Theme.alertSuccess
        case "warning": return Theme.alertWarning
        case "danger": return Theme.alertError
        default: return Theme.textPrimary
        }
    }

    implicitHeight: metrics.length === 0 ? 0 : (compact ? 124 : 76)
    color: Theme.contentPanelSurface
    border.color: Theme.contentPanelBorder
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall

    GridLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        columns: root.compact ? 2 : Math.max(1, root.metrics.length)
        columnSpacing: Theme.spacing8
        rowSpacing: Theme.spacing8

        Repeater {
            model: root.metrics

            delegate: Rectangle {
                required property int index
                required property var modelData

                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                Layout.minimumWidth: 0
                radius: Theme.radiusSmall
                color: Theme.tableRowAlternate
                border.color: Theme.contentPanelBorder
                border.width: Theme.borderWidth

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacing12
                    anchors.rightMargin: Theme.spacing12
                    spacing: Theme.spacing8

                    Rectangle {
                        Layout.preferredWidth: 3
                        Layout.preferredHeight: 30
                        radius: 2
                        color: root.toneColor(modelData.tone)
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        spacing: Theme.spacing2

                        Text {
                            Layout.fillWidth: true
                            text: String(modelData.label || "")
                            color: Theme.textSecondary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            text: String(modelData.value === undefined ? "—" : modelData.value)
                            color: root.toneColor(modelData.tone)
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeTitle
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }
}
