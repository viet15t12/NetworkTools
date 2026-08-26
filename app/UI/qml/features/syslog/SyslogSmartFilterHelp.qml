pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

StandardDialog {
    id: root
    preferredWidth: 680
    implicitHeight: 570
    title: "Smart Filter Help"
    subtitle: "Combine simple key:value filters in one line"
    closeTooltip: "Close smart filter help"

    contentItem: ColumnLayout {
        spacing: Theme.spacing12

        Text {
            Layout.fillWidth: true
            text: "Type plain words to search message, mnemonic, and facility. Add any of the keys below; smart keys override the matching dropdown or time field."
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            wrapMode: Text.WordWrap
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: Theme.spacing16
            rowSpacing: Theme.spacing8

            Repeater {
                model: [
                    { key: "host:<host>", detail: "Only one device host" },
                    { key: "from:<time>", detail: "Received at or after ISO time" },
                    { key: "to:<time>", detail: "Received at or before ISO time" },
                    { key: "since:<duration>", detail: "Recent window: 30m, 2h, 7d, 1w" },
                    { key: "last:<N>", detail: "Newest N logs for every host" },
                    { key: "severity:<level>", detail: "0–7 or error, warning, notice, info…" },
                    { key: "protocol:<name>", detail: "UDP or TCP" },
                    { key: "facility:<name>", detail: "Cisco facility contains value" },
                    { key: "mnemonic:<name>", detail: "Mnemonic contains value" },
                    { key: "text:<phrase>", detail: "Explicit message text; quote spaces" }
                ]

                delegate: RowLayout {
                    required property var modelData
                    Layout.columnSpan: 2
                    Layout.fillWidth: true
                    spacing: Theme.spacing12

                    Text {
                        Layout.preferredWidth: 170
                        text: modelData.key
                        color: Theme.accentColor
                        font.family: Theme.monoFontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        font.bold: true
                    }
                    Text {
                        Layout.fillWidth: true
                        text: modelData.detail
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: Theme.borderWidth
            color: Theme.contentPanelBorder
        }

        Text {
            Layout.fillWidth: true
            text: "Examples"
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            font.bold: true
        }
        Text {
            Layout.fillWidth: true
            text: "host:192.168.122.101 last:20\nfrom:2026-08-26T18:00 to:2026-08-26T19:00\nseverity:error protocol:udp\nfacility:LINK mnemonic:UPDOWN\nsince:30m \"Loopback99 changed state\""
            color: Theme.textSecondary
            font.family: Theme.monoFontFamily
            font.pixelSize: Theme.fontSizeSmall
            lineHeight: 1.35
        }

        Item { Layout.fillHeight: true }
    }

    footer: Item {
        implicitHeight: 58
        StandardButton {
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacing16
            anchors.verticalCenter: parent.verticalCenter
            text: "Close"
            type: "Primary"
            onClicked: root.close()
        }
    }
}
