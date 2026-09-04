import QtQuick
import UI

Item {
    readonly property color selectionBackground: Theme.selectionBackground
    readonly property color selectionForeground: Theme.selectionForeground
    readonly property int effectiveThemeMode: ThemeState.effectiveThemeMode
    readonly property bool highContrastEnabled: ThemeState.isHighContrast
    readonly property color systemAccentColor: ThemeState.systemAccentColor
    readonly property color currentAccentColor: ThemeState.currentAccent.color
    readonly property string currentAccentName: ThemeState.currentAccent.name
    readonly property color statusBarBackground: Theme.statusBarBackground
    readonly property color statusBarWarningText: Theme.statusBarWarningText
    readonly property real statusBarWarningContrast:
        ColorTokens.contrastRatio(statusBarBackground, statusBarWarningText)

    function setSelectionContext(themeMode, customAccent) {
        ThemeState.themeMode = themeMode
        ThemeState.useSystemAccentColor = false
        ThemeState.useCustomAccentColor = true
        ThemeState.customAccentColor = customAccent
    }

    function setThemeContext(themeMode, highContrast) {
        ThemeState.themeMode = themeMode
        ThemeState.highContrast = highContrast
    }

    function setSystemAccentContext() {
        ThemeState.useCustomAccentColor = false
        ThemeState.useSystemAccentColor = true
    }

    function setPresetStatusContext(index) {
        ThemeState.themeMode = ThemeState.light
        ThemeState.highContrast = false
        ThemeState.useSystemAccentColor = false
        ThemeState.useCustomAccentColor = false
        ThemeState.accentColorIndex = index
    }

    function setCustomStatusContext(accent) {
        ThemeState.themeMode = ThemeState.light
        ThemeState.highContrast = false
        ThemeState.useSystemAccentColor = false
        ThemeState.useCustomAccentColor = true
        ThemeState.customAccentColor = accent
    }
}
