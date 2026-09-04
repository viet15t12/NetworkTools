pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: settingsView
    color: Theme.contentBackground

    Component.onCompleted: {
        if (LanguageState.backend === null
                && typeof languageSettings !== "undefined")
            LanguageState.backend = languageSettings
    }

    property string activeSettingKey: "theme"
    property date statusBarPreviewDateTime: new Date()
    readonly property var menuBackend:
        typeof menuPresentation !== "undefined" ? menuPresentation : null
    readonly property bool isAppearanceSetting: activeSettingKey === "theme"
    readonly property bool isLanguageSetting: activeSettingKey === "language"
    readonly property bool isExternalToolsSetting: activeSettingKey === "external_tools"
                                                   || activeSettingKey === "tool_catalog"
    readonly property bool isSyslogSetting: activeSettingKey === "syslog_server"
    readonly property bool isSftpSetting: activeSettingKey === "sftp"
    readonly property bool isSoftwareUpdateSetting: activeSettingKey === "software_update"

    function statusBarPreviewDate() {
        const customFormat = (StatusBarState.customDateFormat || "").trim()
        if (StatusBarState.dateTimeFormatMode === 1 && customFormat !== "")
            return Qt.formatDate(statusBarPreviewDateTime, customFormat)
        return statusBarPreviewDateTime.toLocaleDateString(Qt.locale())
    }

    function statusBarPreviewTime() {
        const customFormat = (StatusBarState.customTimeFormat || "").trim()
        if (StatusBarState.dateTimeFormatMode === 1 && customFormat !== "")
            return Qt.formatTime(statusBarPreviewDateTime, customFormat)
        return statusBarPreviewDateTime.toLocaleTimeString(Qt.locale())
    }

    function resetStatusBarDefaults() {
        StatusBarState.resetDefaults()
    }

    function themeModeComboIndex(mode) {
        if (mode === ThemeState.light) return 0
        if (mode === ThemeState.dark) return 1
        return 2
    }

    function themeModeForComboIndex(index) {
        if (index === 0) return ThemeState.light
        if (index === 1) return ThemeState.dark
        return ThemeState.system
    }

    function menuStyleComboIndex(style) {
        if (style === "custom") return 1
        if (style === "global") return 2
        return 0
    }

    function menuStyleForComboIndex(index) {
        if (index === 1) return "custom"
        if (index === 2) return "global"
        return "auto"
    }

    Timer {
        interval: 1000
        running: settingsView.isAppearanceSetting
        repeat: true
        onTriggered: settingsView.statusBarPreviewDateTime = new Date()
    }

    Item {
        anchors.fill: parent
        visible: settingsView.isAppearanceSetting

        ScrollView {
            id: appearanceScroll
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            ColumnLayout {
                width: appearanceScroll.availableWidth
                spacing: 16

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 8
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    spacing: 12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: "Appearance"
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeLarge
                            font.family: Theme.fontFamily
                            font.weight: Font.Bold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "Customize the accent color, Status Bar, Activity Bar, and sidebar treatment."
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeSmall
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.preferredHeight: themeModeLayout.implicitHeight + 24
                    color: Theme.searchBackground2
                    radius: Theme.borderRadius
                    border.width: Theme.borderWidth
                    border.color: Theme.borderColor

                    ColumnLayout {
                        id: themeModeLayout
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
                                    text: "Theme Mode"
                                    color: Theme.textPrimary
                                    font.pixelSize: Theme.fontSizeNormal
                                    font.family: Theme.fontFamily
                                    font.weight: Font.Medium
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "Choose the base color scheme and sidebar treatment for the app."
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    wrapMode: Text.WordWrap
                                }
                            }

                            StandardComboBox {
                                Layout.preferredWidth: 230
                                model: [
                                    "Light",
                                    "Dark",
                                    "System"
                                ]
                                currentIndex: settingsView.themeModeComboIndex(ThemeState.themeMode)
                                onActivated: function(index) {
                                    ThemeState.themeMode = settingsView.themeModeForComboIndex(index)
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Theme.borderWidth
                            color: Theme.borderColor
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                Text {
                                    text: "Menu Style"
                                    color: Theme.textPrimary
                                    font.pixelSize: Theme.fontSizeNormal
                                    font.family: Theme.fontFamily
                                    font.weight: Font.Medium
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "Choose an in-window menu or publish menus to a supported system Global Menu service."
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    wrapMode: Text.WordWrap
                                }
                            }

                            StandardComboBox {
                                id: menuStyleCombo
                                objectName: "menuStyleCombo"
                                Layout.preferredWidth: 230
                                enabled: settingsView.menuBackend !== null
                                model: [
                                    "Auto (Recommended)",
                                    "In-Window Custom",
                                    "Native Global"
                                ]
                                currentIndex: settingsView.menuBackend !== null
                                              ? settingsView.menuStyleComboIndex(
                                                    settingsView.menuBackend.configuredStyle
                                                )
                                              : 0
                                onActivated: function(index) {
                                    if (settingsView.menuBackend !== null) {
                                        settingsView.menuBackend.configuredStyle =
                                            settingsView.menuStyleForComboIndex(index)
                                    }
                                }
                            }
                        }

                        InlineMessage {
                            Layout.fillWidth: true
                            message: settingsView.menuBackend !== null
                                     ? settingsView.menuBackend.fallbackMessage : ""
                            severity: "warning"
                        }

                        InlineMessage {
                            Layout.fillWidth: true
                            message: settingsView.menuBackend !== null
                                     && settingsView.menuBackend.restartRequired
                                     ? "Restart CAMS to apply the selected menu style."
                                     : ""
                            severity: "info"
                        }

                        StandardToggleButton {
                            Layout.fillWidth: true
                            text: "High Contrast"
                            description: "Increase foreground, border, and selection contrast for the active Light, Dark, or System theme."
                            checked: ThemeState.highContrast
                            onToggled: ThemeState.highContrast = checked
                        }

                        StandardToggleButton {
                            Layout.fillWidth: true
                            text: "Dark Side Bar"
                            description: "Use dark Activity Bar and Panel Side Bar with the current base theme."
                            checked: ThemeState.lightDarkSideBar
                            onToggled: ThemeState.lightDarkSideBar = checked
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.preferredHeight: accentLayout.implicitHeight + 24
                    color: Theme.searchBackground2
                    radius: Theme.borderRadius
                    border.width: Theme.borderWidth
                    border.color: Theme.borderColor

                    ColumnLayout {
                        id: accentLayout
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 14

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                Text {
                                    text: "Accent Color"
                                    color: Theme.textPrimary
                                    font.pixelSize: Theme.fontSizeNormal
                                    font.family: Theme.fontFamily
                                    font.weight: Font.Medium
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "Applies to the Activity Bar indicator, selected states, Status Bar, Panel split handle, and highlighted controls."
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    wrapMode: Text.WordWrap
                                }
                            }

                            Rectangle {
                                Layout.alignment: Qt.AlignVCenter
                                Layout.preferredWidth: 88
                                Layout.preferredHeight: 32
                                radius: Theme.radiusSmall
                                color: Theme.statusBarBackground

                                Text {
                                    anchors.centerIn: parent
                                    text: ThemeState.accentNameLabel(ThemeState.currentAccent.name)
                                    color: Theme.buttonTextSolid
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 58
                            radius: Theme.radiusSmall
                            color: Theme.contentSurface
                            border.width: Theme.borderWidth
                            border.color: Theme.borderColor

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 0

                                Rectangle {
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: 20
                                    color: Theme.activityBarBackground

                                    Rectangle {
                                        anchors.left: parent.left
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 3
                                        height: parent.height - 10
                                        color: Theme.accentColor
                                    }
                                }

                                Rectangle {
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: 80
                                    color: Theme.panelSideBarBackground

                                    Rectangle {
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.margins: 8
                                        height: 20
                                        radius: Theme.radiusSmall
                                        color: Theme.panelSideBarItemSelected
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    color: Theme.contentBackground
                                }

                                Rectangle {
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: 4
                                    color: Theme.statusBarBackground
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: systemAccentLayout.implicitHeight + 20
                            radius: Theme.radiusSmall
                            color: Theme.contentSurface
                            border.width: Theme.borderWidth
                            border.color: ThemeState.useSystemAccentColor
                                          ? Theme.accentColor : Theme.borderColor

                            RowLayout {
                                id: systemAccentLayout
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 12

                                StandardCheckBox {
                                    objectName: "systemAccentCheckBox"
                                    text: "Use system accent color"
                                    checked: ThemeState.useSystemAccentColor
                                    onToggled: {
                                        ThemeState.useSystemAccentColor = checked
                                        if (checked)
                                            ThemeState.useCustomAccentColor = false
                                    }
                                }

                                Rectangle {
                                    Layout.alignment: Qt.AlignVCenter
                                    Layout.preferredWidth: 32
                                    Layout.preferredHeight: 32
                                    radius: Theme.radiusSmall
                                    color: ThemeState.systemAccentColor
                                    border.width: Theme.borderWidth
                                    border.color: ThemeState.currentAccent.emphasis
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "Follows the desktop personalization palette on Windows and Linux and updates when Qt reports a palette change."
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: customAccentLayout.implicitHeight + 20
                            radius: Theme.radiusSmall
                            color: Theme.contentSurface
                            border.width: Theme.borderWidth
                            border.color: Theme.borderColor

                            ColumnLayout {
                                id: customAccentLayout
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                StandardCheckBox {
                                    text: "Use custom accent color"
                                    enabled: !ThemeState.useSystemAccentColor
                                    checked: ThemeState.useCustomAccentColor
                                    onToggled: {
                                        ThemeState.useCustomAccentColor = checked
                                        if (checked)
                                            ThemeState.useSystemAccentColor = false
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    Rectangle {
                                        Layout.alignment: Qt.AlignVCenter
                                        Layout.preferredWidth: 32
                                        Layout.preferredHeight: 32
                                        radius: Theme.radiusSmall
                                        color: ThemeState.normalizeHexColor(ThemeState.customAccentColor)
                                        border.width: Theme.borderWidth
                                        border.color: Theme.accentEmphasis
                                    }

                                    StandardTextField {
                                        Layout.preferredWidth: 180
                                        labelText: "Custom color"
                                        enabled: ThemeState.useCustomAccentColor
                                                 && !ThemeState.useSystemAccentColor
                                        text: ThemeState.customAccentColor
                                        placeholderText: "#356FD6"
                                        onTextEdited: function(value) {
                                            ThemeState.customAccentColor = value
                                        }
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: ThemeState.useSystemAccentColor
                                              ? "Disable System accent to select a custom or preset color."
                                              : ThemeState.useCustomAccentColor
                                              ? (ThemeState.isValidAccentColor(ThemeState.customAccentColor)
                                                 ? "Derived shades are generated automatically for light, dark, and contrast themes."
                                                 : "Use #RGB or #RRGGBB. Invalid input falls back to the default accent preview.")
                                              : "Select a preset below or enable custom input."
                                        color: ThemeState.useCustomAccentColor && !ThemeState.isValidAccentColor(ThemeState.customAccentColor)
                                               ? Theme.alertError
                                               : Theme.textSecondary
                                        font.pixelSize: Theme.fontSizeSmall
                                        font.family: Theme.fontFamily
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }

                        Flow {
                            id: accentGroupsFlow
                            Layout.fillWidth: true
                            Layout.preferredHeight: childrenRect.height
                            spacing: 14

                            Repeater {
                                model: ThemeState.accentGroups.length

                                delegate: Item {
                                    id: accentGroupDelegate
                                    required property int index
                                    property string groupName: ThemeState.accentGroups[index]
                                    property var groupOptions: ThemeState.accentOptionsForGroup(groupName)

                                    width: 132
                                    height: accentGroupColumn.implicitHeight

                                    Column {
                                        id: accentGroupColumn
                                        width: parent.width
                                        spacing: 8

                                        Text {
                                            width: parent.width
                                            text: ThemeState.accentGroupLabel(accentGroupDelegate.groupName)
                                            color: Theme.textSecondary
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.family: Theme.fontFamily
                                            font.capitalization: Font.AllUppercase
                                            font.weight: Font.Medium
                                            elide: Text.ElideRight
                                        }

                                        Row {
                                            spacing: 8

                                            Repeater {
                                                model: accentGroupDelegate.groupOptions.length

                                                delegate: Item {
                                                    required property int index
                                                    property var option: accentGroupDelegate.groupOptions[index]
                                                    readonly property bool selected: option !== undefined
                                                                             && !ThemeState.useSystemAccentColor
                                                                             && !ThemeState.useCustomAccentColor
                                                                             && ThemeState.accentColorIndex === option.index

                                                    width: 56
                                                    height: 56

                                                    Rectangle {
                                                        anchors.fill: parent
                                                        radius: Theme.radiusSmall
                                                        color: selected ? Theme.sideBarItemSelected
                                                                        : (swatchHover.hovered ? Theme.sideBarItemHover : "transparent")
                                                        border.width: selected ? Theme.borderWidth : 0
                                                        border.color: selected ? Theme.accentColor : "transparent"
                                                    }

                                                    Rectangle {
                                                        id: swatchSquare
                                                        anchors.top: parent.top
                                                        anchors.topMargin: 5
                                                        anchors.horizontalCenter: parent.horizontalCenter
                                                        width: 28
                                                        height: 28
                                                        radius: 5
                                                        color: option !== undefined ? option.color : "transparent"
                                                        border.width: Theme.borderWidth
                                                        border.color: option !== undefined ? option.emphasis : Theme.borderColor

                                                        Rectangle {
                                                            visible: selected
                                                            anchors.centerIn: parent
                                                            width: 8
                                                            height: 8
                                                            radius: 4
                                                            color: Theme.buttonTextSolid
                                                        }
                                                    }

                                                    Text {
                                                        anchors.top: swatchSquare.bottom
                                                        anchors.topMargin: 4
                                                        anchors.left: parent.left
                                                        anchors.right: parent.right
                                                        text: option !== undefined ? ThemeState.accentNameLabel(option.name) : ""
                                                        color: selected ? Theme.textPrimary : Theme.textSecondary
                                                        font.pixelSize: Theme.fontSizeCaption
                                                        font.family: Theme.fontFamily
                                                        horizontalAlignment: Text.AlignHCenter
                                                        elide: Text.ElideRight
                                                    }

                                                    HoverHandler {
                                                        id: swatchHover
                                                        cursorShape: Qt.PointingHandCursor
                                                    }

                                                    TapHandler {
                                                        enabled: option !== undefined
                                                        onTapped: {
                                                            ThemeState.useSystemAccentColor = false
                                                            ThemeState.useCustomAccentColor = false
                                                            ThemeState.accentColorIndex = option.index
                                                        }
                                                    }

                                                    ToolTip.visible: swatchHover.hovered
                                                    ToolTip.text: option !== undefined
                                                                  ? ThemeState.accentGroupLabel(option.group) + " - " + ThemeState.accentNameLabel(option.name)
                                                                  : ""
                                                    ToolTip.delay: 400
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    spacing: 12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: "Status Bar"
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeLarge
                            font.family: Theme.fontFamily
                            font.weight: Font.Bold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "Configure the bottom Status Bar and the indicators shown inside it."
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeSmall
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                        }
                    }

                    StandardButton {
                        visible: StatusBarState.hasCustomSettings
                        text: "Reset"
                        type: "Secondary"
                        onClicked: settingsView.resetStatusBarDefaults()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.preferredHeight: statusBarLayout.implicitHeight + 24
                    color: Theme.searchBackground2
                    radius: Theme.borderRadius
                    border.width: Theme.borderWidth
                    border.color: Theme.borderColor

                    ColumnLayout {
                        id: statusBarLayout
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12

                        StandardToggleButton {
                            Layout.fillWidth: true
                            text: "Show Status Bar"
                            description: "Hide or show the entire bottom Status Bar while keeping the indicator choices below."
                            checked: StatusBarState.showStatusBar
                            onToggled: StatusBarState.showStatusBar = checked
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: StatusBarState.showStatusBar && !StatusBarState.hasVisibleContent
                            text: "The Status Bar is hidden because no indicators are enabled."
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeSmall
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Theme.borderWidth
                            color: Theme.borderColor
                        }

                        StandardCheckBox {
                            text: "System Health"
                            checked: StatusBarState.showPythonStatus
                            onToggled: StatusBarState.showPythonStatus = checked
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Theme.borderWidth
                            color: Theme.borderColor
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 20

                                StandardCheckBox {
                                    Layout.preferredWidth: 160
                                    text: "Network"
                                    checked: StatusBarState.showNetwork
                                    onToggled: StatusBarState.showNetwork = checked
                                }

                                StandardCheckBox {
                                    Layout.preferredWidth: 180
                                    text: "Network Name"
                                    enabled: StatusBarState.showNetwork
                                    checked: StatusBarState.showNetworkName
                                    onToggled: StatusBarState.showNetworkName = checked
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: StatusBarState.showNetwork
                                text: "Virtual Lab is Active only when its API reports at least one running node. "
                                      + "An enabled VMnet adapter alone is not treated as a connection."
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeSmall
                                font.family: Theme.fontFamily
                                wrapMode: Text.WordWrap
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                visible: StatusBarState.showNetwork
                                columns: 3
                                columnSpacing: 12
                                rowSpacing: 8

                                StandardTextField {
                                    Layout.fillWidth: true
                                    labelText: "Preferred lab server (optional)"
                                    placeholderText: "e.g., https://192.168.56.128"
                                    text: StatusBarState.virtualLabServerUrl
                                    onEditingFinished: StatusBarState.virtualLabServerUrl = text.trim()
                                }

                                StandardTextField {
                                    Layout.fillWidth: true
                                    labelText: "API username"
                                    placeholderText: "Optional"
                                    text: StatusBarState.virtualLabUsername
                                    onEditingFinished: StatusBarState.virtualLabUsername = text.trim()
                                }

                                StandardPasswordField {
                                    Layout.fillWidth: true
                                    labelText: "API password"
                                    placeholderText: "Optional"
                                    text: StatusBarState.virtualLabPassword
                                    onEditingFinished: StatusBarState.virtualLabPassword = text
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: StatusBarState.showNetwork
                                text: "Other local or reachable lab servers are discovered automatically. "
                                      + "A preferred server URL enables API authentication for that server. "
                                      + "API credentials additionally enable lab-name and running-node detection. "
                                      + "The API password is kept only for this application session."
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeSmall
                                font.family: Theme.fontFamily
                                wrapMode: Text.WordWrap
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Theme.borderWidth
                            color: Theme.borderColor
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            StandardCheckBox {
                                text: "RAM"
                                checked: StatusBarState.showRam
                                onToggled: StatusBarState.showRam = checked
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                visible: StatusBarState.showRam
                                spacing: 10

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    columnSpacing: 20
                                    rowSpacing: 8

                                    StandardCheckBox {
                                        text: "Show usage bar"
                                        checked: StatusBarState.showRamBar
                                        onToggled: StatusBarState.showRamBar = checked
                                    }

                                    StandardCheckBox {
                                        text: "Show number"
                                        checked: StatusBarState.showRamText
                                        onToggled: StatusBarState.showRamText = checked
                                    }

                                    StandardCheckBox {
                                        text: "Turn red at threshold"
                                        checked: StatusBarState.ramWarningEnabled
                                        onToggled: StatusBarState.ramWarningEnabled = checked
                                    }

                                    StandardCheckBox {
                                        text: "Blink when high"
                                        enabled: StatusBarState.ramWarningEnabled
                                        checked: StatusBarState.ramBlinkOnHigh
                                        onToggled: StatusBarState.ramBlinkOnHigh = checked
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    StandardSpinBox {
                                        Layout.preferredWidth: 180
                                        labelText: "Warning threshold (%)"
                                        enabled: StatusBarState.ramWarningEnabled
                                        from: 1
                                        to: 100
                                        value: StatusBarState.ramWarningThreshold
                                        stepSize: 5
                                        onValueChanged: StatusBarState.ramWarningThreshold = value
                                    }

                                    Rectangle {
                                        Layout.alignment: Qt.AlignVCenter
                                        Layout.preferredWidth: 92
                                        Layout.preferredHeight: 8
                                        radius: height / 2
                                        color: Theme.statusBarSepColor
                                        clip: true

                                        Rectangle {
                                            anchors.left: parent.left
                                            anchors.top: parent.top
                                            anchors.bottom: parent.bottom
                                            width: parent.width * 0.58
                                            radius: height / 2
                                            color: Theme.buttonTextSolid
                                        }
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: "Normal RAM color matches Status Bar text; high usage still uses the warning color."
                                        color: Theme.textSecondary
                                        font.pixelSize: Theme.fontSizeSmall
                                        font.family: Theme.fontFamily
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Theme.borderWidth
                            color: Theme.borderColor
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 20

                                StandardCheckBox {
                                    Layout.preferredWidth: 160
                                    text: "Date"
                                    checked: StatusBarState.showDate
                                    onToggled: StatusBarState.showDate = checked
                                }

                                StandardCheckBox {
                                    Layout.preferredWidth: 160
                                    text: "Time"
                                    checked: StatusBarState.showTime
                                    onToggled: StatusBarState.showTime = checked
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                visible: StatusBarState.showDate || StatusBarState.showTime
                                spacing: 10

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    StandardComboBox {
                                        Layout.preferredWidth: 220
                                        labelText: "Format source"
                                        model: [
                                            "Regional format",
                                            "Custom format"
                                        ]
                                        currentIndex: StatusBarState.dateTimeFormatMode
                                        onCurrentIndexChanged: StatusBarState.dateTimeFormatMode = currentIndex
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: "Regional format follows the current system locale. Custom format uses Qt date/time patterns."
                                        color: Theme.textSecondary
                                        font.pixelSize: Theme.fontSizeSmall
                                        font.family: Theme.fontFamily
                                        wrapMode: Text.WordWrap
                                    }
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    columnSpacing: 12
                                    rowSpacing: 8
                                    visible: StatusBarState.dateTimeFormatMode === 1

                                    StandardTextField {
                                        Layout.fillWidth: true
                                        labelText: "Custom date format"
                                        enabled: StatusBarState.showDate
                                        text: StatusBarState.customDateFormat
                                        placeholderText: "dd/MM/yyyy"
                                        onTextEdited: function(value) {
                                            StatusBarState.customDateFormat = value
                                        }
                                    }

                                    StandardTextField {
                                        Layout.fillWidth: true
                                        labelText: "Custom time format"
                                        enabled: StatusBarState.showTime
                                        text: StatusBarState.customTimeFormat
                                        placeholderText: "HH:mm"
                                        onTextEdited: function(value) {
                                            StatusBarState.customTimeFormat = value
                                        }
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "Preview: "
                                          + (StatusBarState.showDate ? settingsView.statusBarPreviewDate() : "")
                                          + (StatusBarState.showDate && StatusBarState.showTime ? " " : "")
                                          + (StatusBarState.showTime ? settingsView.statusBarPreviewTime() : "")
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Theme.borderWidth
                            color: Theme.borderColor
                        }

                        StandardCheckBox {
                            text: "Notifications"
                            checked: StatusBarState.showNotifications
                            onToggled: StatusBarState.showNotifications = checked
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

    Item {
        anchors.fill: parent
        visible: settingsView.isLanguageSetting

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
                        text: LanguageState.text("Language")
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeLarge
                        font.family: Theme.fontFamily
                        font.weight: Font.Bold
                    }

                    Text {
                        Layout.fillWidth: true
                        text: LanguageState.text("Choose the language used by CAMS.")
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
                    Layout.preferredHeight: languageLayout.implicitHeight + 24
                    color: Theme.searchBackground2
                    radius: Theme.borderRadius
                    border.width: Theme.borderWidth
                    border.color: Theme.borderColor

                    ColumnLayout {
                        id: languageLayout
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12

                        StandardComboBox {
                            id: languageCombo
                            objectName: "applicationLanguageCombo"
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
                            message: LanguageState.text("The language choice is saved automatically and notification messages are translated first.")
                            severity: "info"
                        }

                        Text {
                            Layout.fillWidth: true
                            text: LanguageState.text("Technical terms such as host, SSH, Telnet, VLAN, OSPF, workspace, database, and CLI remain unchanged.")
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

    Item {
        anchors.fill: parent
        visible: settingsView.activeSettingKey !== ""
                 && !settingsView.isAppearanceSetting
                 && !settingsView.isLanguageSetting
                 && !settingsView.isExternalToolsSetting
                 && !settingsView.isSyslogSetting
                 && !settingsView.isSftpSetting
                 && !settingsView.isSoftwareUpdateSetting

        Text {
            anchors.centerIn: parent
            text: "Settings group '%1' is not implemented yet.".arg(settingsView.activeSettingKey)
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
        }
    }

    ExternalToolsSettings {
        anchors.fill: parent
        visible: settingsView.isExternalToolsSetting
    }

    SyslogServerSettings {
        anchors.fill: parent
        visible: settingsView.isSyslogSetting
    }

    SftpSettings {
        anchors.fill: parent
        visible: settingsView.isSftpSetting
    }

    SoftwareUpdateSettings {
        anchors.fill: parent
        visible: settingsView.isSoftwareUpdateSetting
    }

    Item {
        anchors.fill: parent
        visible: settingsView.activeSettingKey === ""

        Text {
            anchors.centerIn: parent
            text: "Select a settings group from the left panel."
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
        }
    }
}
