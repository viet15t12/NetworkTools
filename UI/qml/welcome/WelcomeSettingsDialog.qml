pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: root
    objectName: "welcomeGlobalSettingsDialog"

    readonly property var updateBackend:
        typeof updateManager !== "undefined" ? updateManager : null

    title: LanguageState.text("Global Settings")
    subtitle: LanguageState.text("Appearance is available before a project is opened")
    preferredWidth: 560
    implicitHeight: 540

    contentItem: ColumnLayout {
        spacing: Theme.spacing12

        Text {
            text: LanguageState.text("Color theme")
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            Repeater {
                model: [
                    { "label": LanguageState.text("System"), "value": ThemeState.system },
                    { "label": LanguageState.text("Light"), "value": ThemeState.light },
                    { "label": LanguageState.text("Dark"), "value": ThemeState.dark }
                ]

                delegate: StandardButton {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData.label
                    type: "Secondary"
                    checkable: true
                    checked: ThemeState.themeMode === modelData.value
                    onClicked: ThemeState.themeMode = modelData.value
                }
            }
        }

        StandardCheckBox {
            text: LanguageState.text("High contrast")
            checked: ThemeState.highContrast
            onToggled: ThemeState.highContrast = checked
        }

        StandardComboBox {
            objectName: "welcomeLanguageCombo"
            Layout.fillWidth: true
            labelText: LanguageState.text("Interface language")
            model: ["English", "Tiếng Việt"]
            valueModel: ["en", "vi"]
            currentIndex: LanguageState.isVietnamese ? 1 : 0
            onActivated: function(index) {
                LanguageState.setLanguage(index === 1 ? "vi" : "en")
            }
        }

        InlineMessage {
            Layout.fillWidth: true
            message: LanguageState.text("Additional global settings remain available from the workspace Settings view.")
            severity: "info"
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: welcomeUpdateLayout.implicitHeight + Theme.spacing16
            color: Theme.searchBackground2
            radius: Theme.borderRadius
            border.width: Theme.borderWidth
            border.color: Theme.borderColor

            ColumnLayout {
                id: welcomeUpdateLayout
                anchors.fill: parent
                anchors.margins: Theme.spacing8
                spacing: Theme.spacing8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        Text {
                            text: LanguageState.text("Software Update")
                            color: Theme.textPrimary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeNormal
                            font.bold: true
                        }

                        Text {
                            objectName: "welcomeInstalledVersionText"
                            text: root.updateBackend !== null
                                  ? LanguageState.text("Installed version") + ": "
                                    + root.updateBackend.currentVersion
                                  : LanguageState.text("The update service is unavailable.")
                            color: Theme.textSecondary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                        }
                    }

                    StandardButton {
                        objectName: "welcomeCheckAndUpdateButton"
                        text: LanguageState.text("Check and update")
                        type: "Primary"
                        enabled: root.updateBackend !== null
                                 && root.updateBackend.available
                                 && !root.updateBackend.busy
                                 && !root.updateBackend.restartRequired
                        onClicked: root.updateBackend.checkAndUpdate()
                    }
                }

                InlineMessage {
                    Layout.fillWidth: true
                    message: root.updateBackend !== null
                             ? LanguageState.text(root.updateBackend.statusMessage)
                             : LanguageState.text("The update service is unavailable.")
                    severity: root.updateBackend !== null
                              ? root.updateBackend.statusSeverity : "warning"
                    busy: root.updateBackend !== null && root.updateBackend.busy
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            StandardButton {
                text: LanguageState.text("Done")
                type: "Primary"
                onClicked: root.accept()
            }
        }
    }
}
