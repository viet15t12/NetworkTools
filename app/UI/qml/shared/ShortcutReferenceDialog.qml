pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: root
    objectName: "shortcutReferenceDialog"

    title: "Keyboard Shortcuts"
    subtitle: "NetworkTools command reference"
    closeTooltip: "Close keyboard shortcuts"
    preferredWidth: 720
    implicitHeight: Math.min(660,
                             parent ? Math.max(420, parent.height - Theme.spacing32) : 660)

    readonly property int entryCount: shortcutModel.count

    ListModel {
        id: shortcutModel

        ListElement { sectionName: "Application"; shortcutText: "Alt+F4"; description: "Quit NetworkTools" }
        ListElement { sectionName: "Application"; shortcutText: "Ctrl+O"; description: "Open a project" }
        ListElement { sectionName: "Application"; shortcutText: "Ctrl+S"; description: "Save the current workspace" }
        ListElement { sectionName: "Application"; shortcutText: "Ctrl+K Ctrl+S"; description: "Open this keyboard shortcuts reference" }
        ListElement { sectionName: "Application"; shortcutText: "Alt+F / Alt+V / Alt+H"; description: "Open the File, View, or Help menu" }
        ListElement { sectionName: "General"; shortcutText: "Ctrl+B"; description: "Toggle the PanelSideBar" }
        ListElement { sectionName: "General"; shortcutText: "Ctrl+R"; description: "Reload the active UI" }
        ListElement { sectionName: "Activity Bar"; shortcutText: "Ctrl+Alt+D"; description: "Open Dashboard" }
        ListElement { sectionName: "Activity Bar"; shortcutText: "Ctrl+Alt+F"; description: "Open SFTP" }
        ListElement { sectionName: "Activity Bar"; shortcutText: "Ctrl+Alt+L"; description: "Open System Logs" }
        ListElement { sectionName: "Activity Bar"; shortcutText: "Ctrl+Alt+B"; description: "Open Database" }
        ListElement { sectionName: "Activity Bar"; shortcutText: "Ctrl+,"; description: "Open Settings" }

        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+N"; description: "Add a device" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Alt+N"; description: "Add multiple devices" }
        ListElement { sectionName: "Devices"; shortcutText: "F2"; description: "Edit the selected device" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Alt+P"; description: "Ping the selected device" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Alt+C"; description: "Connect to the selected device" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Alt+R"; description: "Reconnect the selected device" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Alt+Down"; description: "Mark the selected device down in Dev mode" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Alt+Up"; description: "Mark the selected device up in Dev mode" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Shift+C"; description: "Connect all selected devices" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Shift+R"; description: "Get running-config from all selected devices" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+Shift+D"; description: "Disconnect all selected devices" }
        ListElement { sectionName: "Devices"; shortcutText: "Ctrl+`"; description: "Open the active device in NetworkTools Terminal" }

        ListElement { sectionName: "Device tabs"; shortcutText: "Ctrl+T"; description: "Open a new device" }
        ListElement { sectionName: "Device tabs"; shortcutText: "Ctrl+W / Ctrl+F4"; description: "Close the active tab" }
        ListElement { sectionName: "Device tabs"; shortcutText: "Ctrl+Shift+T"; description: "Reopen the last closed tab" }
        ListElement { sectionName: "Device tabs"; shortcutText: "Ctrl+Tab"; description: "Select the next tab" }
        ListElement { sectionName: "Device tabs"; shortcutText: "Ctrl+Shift+Tab"; description: "Select the previous tab" }
        ListElement { sectionName: "Device tabs"; shortcutText: "Ctrl+1 … Ctrl+8"; description: "Select the corresponding numbered tab" }
        ListElement { sectionName: "Device tabs"; shortcutText: "Ctrl+9"; description: "Select the rightmost tab" }
        ListElement { sectionName: "Device tabs"; shortcutText: "Ctrl+K Ctrl+W"; description: "Close all tabs" }
        ListElement { sectionName: "Device tabs"; shortcutText: "Shift+F10"; description: "Open the active tab context menu" }

        ListElement { sectionName: "SFTP"; shortcutText: "Alt+Left"; description: "Go back in the active pane" }
        ListElement { sectionName: "SFTP"; shortcutText: "Alt+Right"; description: "Go forward in the active pane" }
        ListElement { sectionName: "SFTP"; shortcutText: "Alt+Up"; description: "Open the parent directory" }
        ListElement { sectionName: "SFTP"; shortcutText: "Backspace"; description: "Go back in the active pane" }
        ListElement { sectionName: "SFTP"; shortcutText: "F5 / Ctrl+R"; description: "Refresh the active pane" }
        ListElement { sectionName: "SFTP"; shortcutText: "Ctrl+Shift+N"; description: "Create a folder in the active pane" }
        ListElement { sectionName: "SFTP"; shortcutText: "F2"; description: "Rename the selected entry" }
        ListElement { sectionName: "SFTP"; shortcutText: "Del"; description: "Delete the selected entries" }
        ListElement { sectionName: "SFTP"; shortcutText: "Enter"; description: "Open or transfer the selected entry" }
        ListElement { sectionName: "SFTP"; shortcutText: "Ctrl+A"; description: "Select every entry in the active pane" }
        ListElement { sectionName: "SFTP"; shortcutText: "Esc"; description: "Clear the current selection" }
        ListElement { sectionName: "SFTP"; shortcutText: "Shift+F10"; description: "Open the file context menu" }

        ListElement { sectionName: "Interfaces"; shortcutText: "F2"; description: "Edit the selected saved interface" }
        ListElement { sectionName: "Interfaces"; shortcutText: "Del"; description: "Delete the selected saved interface" }
        ListElement { sectionName: "Interfaces"; shortcutText: "F5"; description: "Reload saved interfaces" }
        ListElement { sectionName: "Interfaces"; shortcutText: "Shift+F10"; description: "Open the selected interface context menu" }

        ListElement { sectionName: "Configuration viewer"; shortcutText: "Ctrl+F"; description: "Find text in the active configuration" }
        ListElement { sectionName: "Configuration viewer"; shortcutText: "Ctrl+C"; description: "Copy the selected configuration text" }
        ListElement { sectionName: "Configuration viewer"; shortcutText: "Ctrl+="; description: "Zoom in" }
        ListElement { sectionName: "Configuration viewer"; shortcutText: "Ctrl+-"; description: "Zoom out" }
        ListElement { sectionName: "Configuration viewer"; shortcutText: "Ctrl+0"; description: "Reset zoom to 100%" }

        ListElement { sectionName: "Dialogs"; shortcutText: "Enter / Return"; description: "Submit the active New Device form" }
        ListElement { sectionName: "Dialogs"; shortcutText: "Ctrl+Enter / Ctrl+Alt+N"; description: "Submit the Batch New Device form" }
        ListElement { sectionName: "Dialogs"; shortcutText: "Esc"; description: "Cancel or close the active dialog or selection" }
    }

    contentItem: ScrollView {
        id: shortcutScroll
        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: ScrollBar.AsNeeded

        ColumnLayout {
            width: shortcutScroll.availableWidth
            spacing: Theme.spacing4

            Repeater {
                model: shortcutModel

                delegate: ColumnLayout {
                    id: shortcutEntry
                    required property int index
                    required property string sectionName
                    required property string shortcutText
                    required property string description

                    Layout.fillWidth: true
                    spacing: Theme.spacing4

                    Text {
                        visible: shortcutEntry.index === 0
                                 || shortcutModel.get(shortcutEntry.index - 1).sectionName
                                    !== shortcutEntry.sectionName
                        Layout.fillWidth: true
                        Layout.topMargin: shortcutEntry.index === 0 ? 0 : Theme.spacing12
                        text: shortcutEntry.sectionName
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeNormal
                        font.weight: Font.DemiBold
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: Math.max(42, shortcutRow.implicitHeight + Theme.spacing16)
                        radius: Theme.radiusSmall
                        color: Theme.contentSurface
                        border.color: Theme.contentPanelBorder
                        border.width: Theme.borderWidth

                        RowLayout {
                            id: shortcutRow
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacing12
                            anchors.rightMargin: Theme.spacing12
                            anchors.topMargin: Theme.spacing8
                            anchors.bottomMargin: Theme.spacing8
                            spacing: Theme.spacing12

                            Rectangle {
                                Layout.preferredWidth: 168
                                Layout.minimumWidth: 132
                                implicitHeight: Math.max(26,
                                                         shortcutLabel.implicitHeight
                                                         + Theme.spacing8)
                                radius: Theme.radiusSmall
                                color: Theme.inputBackground
                                border.color: Theme.inputBorderColor
                                border.width: Theme.borderWidth

                                Text {
                                    id: shortcutLabel
                                    anchors.fill: parent
                                    anchors.margins: Theme.spacing4
                                    text: shortcutEntry.shortcutText
                                    color: Theme.textPrimary
                                    font.family: Theme.monoFontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    wrapMode: Text.WordWrap
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: shortcutEntry.description
                                color: Theme.textSecondary
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeNormal
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.spacing8
            }
        }
    }

    footer: Rectangle {
        implicitHeight: 64
        color: "transparent"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacing16
            anchors.rightMargin: Theme.spacing16
            spacing: Theme.spacing16

            Text {
                Layout.fillWidth: true
                text: "Contextual shortcuts pause while you are editing text."
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                wrapMode: Text.WordWrap
            }

            StandardButton {
                text: "Close"
                type: "Primary"
                onClicked: root.accept()
            }
        }
    }
}
