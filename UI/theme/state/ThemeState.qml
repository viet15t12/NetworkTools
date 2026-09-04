pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick

QtObject {
    id: root

    readonly property int system: 0
    readonly property int light: 1
    readonly property int dark: 2
    readonly property int lightHighContrast: 3
    readonly property int darkHighContrast: 4

    property bool _loadingSettings: true
    property var backend: null
    property int themeMode: system
    property bool highContrast: false
    property int accentColorIndex: 4
    property bool lightDarkSideBar: false
    property bool useSystemAccentColor: false
    property bool useCustomAccentColor: false
    property string customAccentColor: "#356FD6"
    property SystemPalette systemPalette: SystemPalette {
        colorGroup: SystemPalette.Active
    }
    readonly property color systemAccentColor: systemPalette.accent
    readonly property var systemAppearanceBackend:
        typeof systemAppearance !== "undefined" ? systemAppearance : null

    readonly property var accentGroups: [
        "Red",
        "Orange",
        "Blue",
        "Green",
        "Purple",
        "Black"
    ]

    readonly property var accentPalette: [
        { "index": 0, "group": "Red", "name": "Ruby", "color": "#C2413D", "emphasis": "#A9322F", "hover": "#D0524E", "statusBar": "#A9322F", "activeLight": "#FFE8E6", "activeDark": "#3A1717" },
        { "index": 1, "group": "Red", "name": "Crimson", "color": "#BE123C", "emphasis": "#9F1239", "hover": "#D11C4D", "statusBar": "#9F1239", "activeLight": "#FFE4EC", "activeDark": "#3B1020" },
        { "index": 2, "group": "Orange", "name": "Orange", "color": "#D97706", "emphasis": "#B45309", "hover": "#EA8A13", "statusBar": "#B45309", "activeLight": "#FFF0D9", "activeDark": "#3B2408" },
        { "index": 3, "group": "Orange", "name": "Amber", "color": "#B7791F", "emphasis": "#975A16", "hover": "#C98A2A", "statusBar": "#975A16", "activeLight": "#FFF3D6", "activeDark": "#372509" },
        { "index": 4, "group": "Blue", "name": "Azure", "color": "#356FD6", "emphasis": "#2F5DAA", "hover": "#4F86E5", "statusBar": "#2F5DAA", "activeLight": "#DDEBFF", "activeDark": "#0C2D6B" },
        { "index": 5, "group": "Blue", "name": "Sky", "color": "#0E7490", "emphasis": "#155E75", "hover": "#1592B3", "statusBar": "#155E75", "activeLight": "#D8F4FF", "activeDark": "#083545" },
        { "index": 6, "group": "Green", "name": "Emerald", "color": "#15803D", "emphasis": "#166534", "hover": "#1F9D50", "statusBar": "#166534", "activeLight": "#DCFCE7", "activeDark": "#0D321C" },
        { "index": 7, "group": "Green", "name": "Teal", "color": "#0F766E", "emphasis": "#115E59", "hover": "#14958C", "statusBar": "#115E59", "activeLight": "#CCFBF1", "activeDark": "#0A3834" },
        { "index": 8, "group": "Purple", "name": "Violet", "color": "#7C3AED", "emphasis": "#6D28D9", "hover": "#8B5CF6", "statusBar": "#5B21B6", "activeLight": "#EDE9FE", "activeDark": "#24105E" },
        { "index": 9, "group": "Purple", "name": "Indigo", "color": "#4F46E5", "emphasis": "#4338CA", "hover": "#6366F1", "statusBar": "#3730A3", "activeLight": "#E0E7FF", "activeDark": "#1E1B4B" },
        { "index": 10, "group": "Black", "name": "Graphite", "color": "#24292F", "emphasis": "#1F2328", "hover": "#3A414A", "statusBar": "#24292F", "activeLight": "#EAECEF", "activeDark": "#161B22" },
        { "index": 11, "group": "Black", "name": "Slate", "color": "#334155", "emphasis": "#1E293B", "hover": "#475569", "statusBar": "#1E293B", "activeLight": "#E2E8F0", "activeDark": "#182334" }
    ]

    readonly property bool systemPrefersDark:
        systemAppearanceBackend !== null
        ? systemAppearanceBackend.prefersDark
        : Qt.application.styleHints.colorScheme === Qt.ColorScheme.Dark

    readonly property int effectiveBaseThemeMode: {
        if (themeMode === light || themeMode === lightHighContrast)
            return light
        if (themeMode === dark || themeMode === darkHighContrast)
            return dark
        return systemPrefersDark ? dark : light
    }

    readonly property int effectiveThemeMode: {
        const contrastEnabled = highContrast
                             || themeMode === lightHighContrast
                             || themeMode === darkHighContrast
        if (!contrastEnabled)
            return effectiveBaseThemeMode
        return effectiveBaseThemeMode === dark ? darkHighContrast : lightHighContrast
    }

    readonly property bool isDarkMode: {
        return effectiveThemeMode === dark || effectiveThemeMode === darkHighContrast
    }

    readonly property bool isHighContrast: {
        return effectiveThemeMode === lightHighContrast || effectiveThemeMode === darkHighContrast
    }

    readonly property bool isLightHighContrast: effectiveThemeMode === lightHighContrast
    readonly property bool isDarkHighContrast: effectiveThemeMode === darkHighContrast
    readonly property bool isDarkSideBar: isDarkMode || lightDarkSideBar

    readonly property string themeName: {
        if (effectiveThemeMode === lightHighContrast) return "Light High Contrast"
        if (effectiveThemeMode === darkHighContrast) return "Dark High Contrast"
        if (effectiveThemeMode === dark) return "Dark"
        return "Light"
    }

    readonly property var currentAccent: useSystemAccentColor
                                         ? systemAccentOption(systemAccentColor)
                                         : (useCustomAccentColor
                                            ? customAccentOption(customAccentColor)
                                            : accentOption(accentColorIndex))

    function accentOption(index) {
        for (let i = 0; i < accentPalette.length; i++) {
            if (accentPalette[i].index === index)
                return accentPalette[i]
        }
        return accentPalette[4]
    }

    function accentOptionsForGroup(groupName) {
        let options = []
        for (let i = 0; i < accentPalette.length; i++) {
            if (accentPalette[i].group === groupName)
                options.push(accentPalette[i])
        }
        return options
    }

    function accentGroupLabel(groupName) {
        switch (groupName) {
        case "Red": return "Red"
        case "Orange": return "Orange"
        case "Blue": return "Blue"
        case "Green": return "Green"
        case "Purple": return "Purple"
        case "Black": return "Black"
        case "System": return "System"
        case "Custom": return "Custom"
        }
        return groupName
    }

    function accentNameLabel(name) {
        switch (name) {
        case "Ruby": return "Ruby"
        case "Crimson": return "Crimson"
        case "Orange": return "Orange"
        case "Amber": return "Amber"
        case "Azure": return "Azure"
        case "Sky": return "Sky"
        case "Emerald": return "Emerald"
        case "Teal": return "Teal"
        case "Violet": return "Violet"
        case "Indigo": return "Indigo"
        case "Graphite": return "Graphite"
        case "Slate": return "Slate"
        case "System": return "System"
        case "Custom": return "Custom"
        case "Custom*": return "Custom*"
        }
        return name
    }

    function normalizeThemeMode(value) {
        if (value === light || value === dark)
            return value
        return system
    }

    function normalizeAccentColorIndex(value) {
        for (let i = 0; i < accentPalette.length; i++) {
            if (accentPalette[i].index === value)
                return value
        }
        return 4
    }

    function isValidAccentColor(value) {
        const text = String(value || "").trim()
        return /^#?[0-9a-fA-F]{3}$/.test(text) || /^#?[0-9a-fA-F]{6}$/.test(text)
    }

    function normalizeHexColor(value) {
        let text = String(value || "").trim()
        if (text.length === 0)
            return "#356FD6"
        if (text.charAt(0) !== "#")
            text = "#" + text
        if (/^#[0-9a-fA-F]{3}$/.test(text)) {
            return ("#" + text.charAt(1) + text.charAt(1)
                        + text.charAt(2) + text.charAt(2)
                        + text.charAt(3) + text.charAt(3)).toUpperCase()
        }
        if (/^#[0-9a-fA-F]{6}$/.test(text))
            return text.toUpperCase()
        return "#356FD6"
    }

    function channelToHex(value) {
        const text = Math.max(0, Math.min(255, Math.round(value))).toString(16).toUpperCase()
        return text.length === 1 ? "0" + text : text
    }

    function hexChannel(hexColor, offset) {
        return parseInt(hexColor.substr(offset, 2), 16)
    }

    function mixHexColor(sourceColor, targetColor, amount) {
        const source = normalizeHexColor(sourceColor)
        const target = normalizeHexColor(targetColor)
        const ratio = Math.max(0, Math.min(1, amount))
        const red = hexChannel(source, 1) + (hexChannel(target, 1) - hexChannel(source, 1)) * ratio
        const green = hexChannel(source, 3) + (hexChannel(target, 3) - hexChannel(source, 3)) * ratio
        const blue = hexChannel(source, 5) + (hexChannel(target, 5) - hexChannel(source, 5)) * ratio
        return "#" + channelToHex(red) + channelToHex(green) + channelToHex(blue)
    }

    function colorLuminance(hexColor) {
        const color = normalizeHexColor(hexColor)
        const red = hexChannel(color, 1) / 255
        const green = hexChannel(color, 3) / 255
        const blue = hexChannel(color, 5) / 255
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue
    }

    function customAccentOption(value) {
        const base = normalizeHexColor(value)
        const lightBase = colorLuminance(base) > 0.55
        const emphasis = mixHexColor(base, "#000000", lightBase ? 0.36 : 0.18)
        return {
            "index": -1,
            "group": "Custom",
            "name": isValidAccentColor(value) ? "Custom" : "Custom*",
            "color": base,
            "emphasis": emphasis,
            "hover": mixHexColor(base, "#FFFFFF", lightBase ? 0.08 : 0.18),
            "statusBar": mixHexColor(base, "#000000", lightBase ? 0.52 : 0.22),
            "activeLight": mixHexColor(base, "#FFFFFF", 0.84),
            "activeDark": mixHexColor(base, "#000000", 0.68)
        }
    }

    function systemAccentOption(value) {
        const derived = customAccentOption(value)
        return {
            "index": -2,
            "group": "System",
            "name": "System",
            "color": derived.color,
            "emphasis": derived.emphasis,
            "hover": derived.hover,
            "statusBar": derived.statusBar,
            "activeLight": derived.activeLight,
            "activeDark": derived.activeDark
        }
    }

    function hasPersistentSettings() {
        return backend !== null
    }

    function loadPersistentSettings() {
        _loadingSettings = true
        if (hasPersistentSettings()) {
            const storedThemeMode = backend.themeMode
            const legacyHighContrast = storedThemeMode === lightHighContrast
                                     || storedThemeMode === darkHighContrast
            themeMode = storedThemeMode === lightHighContrast
                      ? light
                      : (storedThemeMode === darkHighContrast
                         ? dark
                         : normalizeThemeMode(storedThemeMode))
            highContrast = legacyHighContrast || backend.highContrast === true
            accentColorIndex = normalizeAccentColorIndex(backend.accentColorIndex)
            lightDarkSideBar = backend.lightDarkSideBar
            useSystemAccentColor = backend.useSystemAccentColor
            useCustomAccentColor = !useSystemAccentColor
                                   && backend.useCustomAccentColor
            customAccentColor = backend.customAccentColor
        }
        _loadingSettings = false
        savePersistentSettings()
    }

    function savePersistentSettings() {
        if (!hasPersistentSettings())
            return

        backend.themeMode = normalizeThemeMode(themeMode)
        backend.highContrast = highContrast
        backend.accentColorIndex = normalizeAccentColorIndex(accentColorIndex)
        backend.lightDarkSideBar = lightDarkSideBar
        backend.useSystemAccentColor = useSystemAccentColor
        backend.useCustomAccentColor = useCustomAccentColor
        backend.customAccentColor = customAccentColor
    }

    onBackendChanged: loadPersistentSettings()
    onThemeModeChanged: if (!_loadingSettings) savePersistentSettings()
    onHighContrastChanged: if (!_loadingSettings) savePersistentSettings()
    onAccentColorIndexChanged: if (!_loadingSettings) savePersistentSettings()
    onLightDarkSideBarChanged: if (!_loadingSettings) savePersistentSettings()
    onUseSystemAccentColorChanged: if (!_loadingSettings) savePersistentSettings()
    onUseCustomAccentColorChanged: if (!_loadingSettings) savePersistentSettings()
    onCustomAccentColorChanged: if (!_loadingSettings) savePersistentSettings()

    Component.onCompleted: loadPersistentSettings()
}
