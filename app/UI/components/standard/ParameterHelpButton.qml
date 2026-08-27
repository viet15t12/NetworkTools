pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Button {
    id: root
    objectName: "parameterHelpIconButton"

    property string helpTitle: "Parameter help"
    property string helpText: ""
    property string tooltipText: "Explain these parameters"
    readonly property var entries: helpEntries()

    implicitWidth: 28
    implicitHeight: 28
    padding: 0
    enabled: helpText.trim() !== ""
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.role: Accessible.Button
    Accessible.name: tooltipText
    Accessible.description: helpTitle

    onClicked: helpDialog.open()

    function helpEntries() {
        const paragraphs = String(root.helpText || "").split(/\n\s*\n/)
        const entries = []
        for (let i = 0; i < paragraphs.length; ++i) {
            const paragraph = paragraphs[i].trim()
            if (paragraph === "")
                continue
            const separator = paragraph.indexOf(":")
            const hasShortLabel = separator > 0 && separator <= 64
            entries.push({
                "label": hasShortLabel ? paragraph.slice(0, separator).trim() : "Overview",
                "detail": hasShortLabel ? paragraph.slice(separator + 1).trim() : paragraph
            })
        }
        return entries
    }

    scale: root.down ? 0.94 : (root.hovered ? 1.06 : 1.0)

    Behavior on scale {
        NumberAnimation {
            duration: Theme.animationDurationFast
            easing.type: Easing.OutCubic
        }
    }

    background: Rectangle {
        radius: width / 2
        color: root.down || root.hovered
               ? Theme.alertInfoSubtle : Theme.contentPanelSurface
        border.color: root.enabled ? Theme.accentColor : Theme.textDisabled
        border.width: root.activeFocus ? 2 : Theme.borderWidth
    }

    contentItem: Text {
        text: "i"
        color: root.enabled ? Theme.accentColor : Theme.textDisabled
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeNormal
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    ToolTip {
        visible: root.hovered
        text: root.tooltipText
        delay: 350
    }

    StandardDialog {
        id: helpDialog
        objectName: "parameterHelpDialog"
        parent: Overlay.overlay
        readonly property bool compactLayout: width < 600
        preferredWidth: 720
        height: Math.max(0, Math.min(620, parent ? parent.height - Theme.spacing32 : 620))
        title: root.helpTitle
        subtitle: root.entries.length + (root.entries.length === 1
                                          ? " parameter guide" : " parameter guides")

        contentItem: ColumnLayout {
            spacing: Theme.spacing12

            Rectangle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                implicitHeight: guideRow.implicitHeight + Theme.spacing16
                radius: Theme.radiusMedium
                color: Theme.alertInfoSubtle
                border.color: Qt.rgba(Theme.accentColor.r,
                                      Theme.accentColor.g,
                                      Theme.accentColor.b, 0.35)
                border.width: Theme.borderWidth

                RowLayout {
                    id: guideRow
                    anchors.fill: parent
                    anchors.margins: Theme.spacing8
                    spacing: Theme.spacing12

                    Rectangle {
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        Layout.alignment: Qt.AlignTop
                        radius: Theme.radiusRound
                        color: Theme.accentColor

                        Text {
                            anchors.centerIn: parent
                            text: "i"
                            color: Theme.selectionForeground
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeNormal
                            font.bold: true
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: Theme.spacing2

                        Text {
                            Layout.fillWidth: true
                            text: "Quick parameter guide"
                            color: Theme.textPrimary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeNormal
                            font.bold: true
                            wrapMode: Text.Wrap
                        }

                        Text {
                            Layout.fillWidth: true
                            text: helpDialog.compactLayout
                                  ? "Review accepted values and examples below."
                                  : "Review each field, its accepted values, and practical examples before applying the configuration."
                            color: Theme.textSecondary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                            lineHeight: 1.2
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }

            ScrollView {
                id: helpScroll
                objectName: "parameterHelpScrollView"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                clip: true
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                ColumnLayout {
                    width: helpScroll.availableWidth
                    spacing: Theme.spacing8

                    Repeater {
                        model: root.entries

                        delegate: Rectangle {
                            id: helpEntry
                            objectName: "parameterHelpEntryCard"
                            required property int index
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            implicitHeight: entryLayout.implicitHeight + Theme.spacing16
                            radius: Theme.radiusMedium
                            color: index % 2 === 0
                                   ? Theme.contentPanelSurface : Theme.contentBackground
                            border.color: index === 0
                                          ? Qt.rgba(Theme.accentColor.r,
                                                    Theme.accentColor.g,
                                                    Theme.accentColor.b, 0.48)
                                          : Theme.contentPanelBorder
                            border.width: Theme.borderWidth

                            Rectangle {
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                width: 3
                                radius: Theme.radiusSmall
                                color: Theme.accentColor
                                opacity: helpEntry.index === 0 ? 1.0 : 0.45
                            }

                            GridLayout {
                                id: entryLayout
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                columns: helpDialog.compactLayout ? 1 : 2
                                columnSpacing: Theme.spacing16
                                rowSpacing: Theme.spacing8

                                RowLayout {
                                    Layout.preferredWidth: entryLayout.columns === 2 ? 190 : -1
                                    Layout.fillWidth: entryLayout.columns === 1
                                    Layout.minimumWidth: 0
                                    Layout.alignment: Qt.AlignTop
                                    spacing: Theme.spacing8

                                    Rectangle {
                                        Layout.preferredWidth: 24
                                        Layout.preferredHeight: 24
                                        Layout.alignment: Qt.AlignTop
                                        radius: Theme.radiusRound
                                        color: Theme.alertInfoSubtle
                                        border.color: Theme.accentColor
                                        border.width: Theme.borderWidth

                                        Text {
                                            anchors.centerIn: parent
                                            text: helpEntry.index + 1
                                            color: Theme.accentColor
                                            font.family: Theme.monoFontFamily
                                            font.pixelSize: Theme.fontSizeCaption
                                            font.bold: true
                                        }
                                    }

                                    Text {
                                        objectName: "parameterHelpEntryLabel"
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: helpEntry.modelData.label
                                        color: Theme.accentColor
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        font.bold: true
                                        lineHeight: 1.15
                                        wrapMode: Text.Wrap
                                    }
                                }

                                Text {
                                    objectName: "parameterHelpEntryDetail"
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.alignment: Qt.AlignTop
                                    text: helpEntry.modelData.detail
                                    color: Theme.textPrimary
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    lineHeight: 1.3
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    visible: !helpDialog.compactLayout
                    text: "Tip: optional fields can stay empty to preserve the device default."
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeCaption
                    elide: Text.ElideRight
                }

                Item { Layout.fillWidth: true }

                StandardButton {
                    text: "Close"
                    type: "Primary"
                    onClicked: helpDialog.close()
                }
            }
        }
    }
}
