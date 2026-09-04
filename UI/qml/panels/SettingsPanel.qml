pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import UI

Item {
    id: settingsPanel

    signal settingSelected(string key)

    property int selectedIndex: 0
    property string selectedKey: filteredItems.length > 0 && selectedIndex >= 0 && selectedIndex < filteredItems.length
                                 ? filteredItems[selectedIndex].key
                                 : ""
    property var allItems: [
        { "key": "theme", "title": LanguageState.text("Theme"), "desc": LanguageState.text("Theme, accent, and Status Bar settings") },
        { "key": "language", "title": LanguageState.text("Language"), "desc": LanguageState.text("Language and notification translation") },
        { "key": "software_update", "title": LanguageState.text("Software Update"), "desc": LanguageState.text("Check for and install CAMS updates") },
        { "key": "external_tools", "title": LanguageState.text("External Tools"), "desc": LanguageState.text("Choose default, suggested, or custom applications") },
        { "key": "sftp", "title": "SFTP", "desc": LanguageState.text("Default local and remote connection directories") },
        { "key": "syslog_server", "title": LanguageState.text("System Logs"), "desc": LanguageState.text("Listener, device destination, and message retention") }
    ]

    property var filteredItems: []
    readonly property int renderedCardCount: settingsRepeater.count

    function cardAt(index) {
        return settingsRepeater.itemAt(index)
    }

    function selectSetting(key) {
        const normalizedKey = String(key || "")
        for (let i = 0; i < allItems.length; i++) {
            if (allItems[i].key === normalizedKey) {
                const previousKey = selectedKey
                searchDebounceTimer.stop()
                searchBar.text = ""
                filteredItems = allItems
                selectedIndex = i
                if (previousKey === normalizedKey)
                    settingSelected(normalizedKey)
                return true
            }
        }
        return false
    }

    function applyFilter() {
        const q = searchBar.text.toLowerCase().trim()
        if (q === "") {
            filteredItems = allItems
            return
        }
        filteredItems = allItems.filter(function(item) {
            return item.title.toLowerCase().indexOf(q) !== -1
                || item.desc.toLowerCase().indexOf(q) !== -1
        })
        if (filteredItems.length === 0) {
            selectedIndex = -1
            return
        }
        if (selectedIndex < 0 || selectedIndex >= filteredItems.length) {
            selectedIndex = 0
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.panelSideBarBackground
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            color: Theme.panelSideBarBackground

            Text {
                anchors.fill: parent
                anchors.leftMargin: 16
                verticalAlignment: Text.AlignVCenter
                text: LanguageState.text("SETTINGS")
                color: Theme.panelSideBarTextSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.capitalization: Font.AllUppercase
                font.weight: Font.Medium
            }

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: Theme.borderWidth
                color: Theme.panelSideBarBorderColor
            }
        }

        SideBarSearch {
            id: searchBar
            Layout.fillWidth: true
            Layout.margins: 8
            placeholderText: LanguageState.text("Search settings...")
            onTextChanged: searchDebounceTimer.restart()
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: width
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            ColumnLayout {
                width: parent.width
                spacing: 8

                Repeater {
                    id: settingsRepeater
                    model: settingsPanel.filteredItems

                    delegate: Rectangle {
                        id: settingsCard
                        required property int index
                        required property var modelData

                        objectName: "settingsCard" + index
                        readonly property real contentImplicitHeight:
                            settingsCardContent.implicitHeight
                        Layout.fillWidth: true
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                        implicitHeight: Math.max(72, contentImplicitHeight + 24)
                        radius: Theme.borderRadius
                        color: settingsPanel.selectedIndex === index
                               ? Theme.panelSideBarItemSelected
                               : (itemHover.hovered ? Theme.panelSideBarItemHover : Theme.panelSideBarSearchBackground2)
                        border.width: Theme.borderWidth
                        border.color: Theme.panelSideBarBorderColor

                        ColumnLayout {
                            id: settingsCardContent
                            objectName: "settingsCardContent" + settingsCard.index
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 4

                            Text {
                                text: modelData.title
                                color: Theme.panelSideBarTextPrimary
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeNormal
                                font.weight: Font.Medium
                            }

                            Text {
                                objectName: "settingsCardDescription" + settingsCard.index
                                text: modelData.desc
                                color: Theme.panelSideBarTextSecondary
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeSmall
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }

                        HoverHandler { id: itemHover }
                        TapHandler {
                            onTapped: settingsPanel.selectedIndex = index
                        }
                    }
                }

                Text {
                    visible: settingsPanel.filteredItems.length === 0
                    text: LanguageState.text("No matching settings group.")
                    color: Theme.panelSideBarTextSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    Layout.leftMargin: 12
                    Layout.rightMargin: 12
                }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 8
                }
            }
        }
    }

    Timer {
        id: searchDebounceTimer
        interval: 200
        repeat: false
        onTriggered: settingsPanel.applyFilter()
    }

    onSelectedKeyChanged: settingSelected(selectedKey)
    onAllItemsChanged: settingsPanel.applyFilter()

    Component.onCompleted: settingsPanel.applyFilter()
}
