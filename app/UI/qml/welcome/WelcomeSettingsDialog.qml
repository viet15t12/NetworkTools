pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: root

    title: LanguageState.text("Global Settings")
    subtitle: LanguageState.text("Appearance is available before a project is opened")
    preferredWidth: 560
    implicitHeight: 490

    contentItem: ColumnLayout {
        spacing: Theme.spacing16

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

        Item { Layout.fillHeight: true }

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
