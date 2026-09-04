pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Item {
    id: root

    readonly property var backend:
        typeof updateManager !== "undefined" ? updateManager : null

    ScrollView {
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: ScrollBar.AsNeeded

        ColumnLayout {
            width: parent.width
            spacing: 16

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 8
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: 4

                Text {
                    text: LanguageState.text("Software Update")
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeLarge
                    font.family: Theme.fontFamily
                    font.weight: Font.Bold
                }

                Text {
                    Layout.fillWidth: true
                    text: LanguageState.text("Check the CAMS repository and install the latest version.")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.preferredHeight: updateLayout.implicitHeight + 24
                color: Theme.searchBackground2
                radius: Theme.borderRadius
                border.width: Theme.borderWidth
                border.color: Theme.borderColor

                ColumnLayout {
                    id: updateLayout
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            Text {
                                text: LanguageState.text("Installed version")
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fontSizeNormal
                                font.family: Theme.fontFamily
                                font.weight: Font.Medium
                            }

                            Text {
                                objectName: "installedVersionText"
                                text: root.backend !== null
                                      ? root.backend.currentVersion
                                      : LanguageState.text("Unavailable")
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeSmall
                                font.family: Theme.fontFamily
                            }
                        }

                        StandardButton {
                            objectName: "checkAndUpdateButton"
                            text: LanguageState.text("Check and update")
                            type: "Primary"
                            enabled: root.backend !== null
                                     && root.backend.available
                                     && !root.backend.busy
                                     && !root.backend.restartRequired
                            onClicked: root.backend.checkAndUpdate()
                        }
                    }

                    InlineMessage {
                        Layout.fillWidth: true
                        message: root.backend !== null
                                 ? LanguageState.text(root.backend.statusMessage)
                                 : LanguageState.text("The update service is unavailable.")
                        severity: root.backend !== null ? root.backend.statusSeverity : "warning"
                        busy: root.backend !== null && root.backend.busy
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.backend === null || !root.backend.available
                        text: LanguageState.text("Automatic updates are supported by Linux installations. You can still update a development checkout with Git.")
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 8
            }
        }
    }
}
