pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick
import UI

QtObject {
    readonly property int mode: ThemeState.effectiveThemeMode

    function pick(lightColor, darkColor, lightHighContrastColor, darkHighContrastColor) {
        if (mode === ThemeState.lightHighContrast)
            return lightHighContrastColor
        if (mode === ThemeState.darkHighContrast)
            return darkHighContrastColor
        if (mode === ThemeState.dark)
            return darkColor
        return lightColor
    }

    function pickSideBar(lightColor, darkColor, lightHighContrastColor, darkHighContrastColor) {
        if (ThemeState.lightDarkSideBar) {
            if (mode === ThemeState.lightHighContrast || mode === ThemeState.darkHighContrast)
                return darkHighContrastColor
            return darkColor
        }
        return pick(lightColor, darkColor, lightHighContrastColor, darkHighContrastColor)
    }

    readonly property var accent: ThemeState.currentAccent

    property color windowTitleBackground: pick("#F6F8FA", "#010409", "#FFFFFF", "#000000")
    property color activityBarBackground: pickSideBar("#FFFFFF", "#0D1117", "#FFFFFF", "#000000")
    property color sideBarBackground: pick("#F6F8FA", "#010409", "#F6F8FA", "#000000")
    property color panelSideBarBackground: pickSideBar("#F6F8FA", "#010409", "#F6F8FA", "#000000")
    property color panelSideBarSurface: pickSideBar("#FFFFFF", "#161B22", "#FFFFFF", "#0D1117")
    property color panelSideBarTextPrimary: pickSideBar("#1F2328", "#E6EDF3", "#0E1116", "#FFFFFF")
    property color panelSideBarTextSecondary: pickSideBar("#59636E", "#B1BAC4", "#24292F", "#D0D7DE")
    property color panelSideBarTextDisabled: pickSideBar("#818B98", "#6E7681", "#57606A", "#8B949E")
    property color panelSideBarPlaceholderTextColor: pickSideBar("#6E7781", "#8B949E", "#57606A", "#B1BAC4")
    property color panelSideBarBorderColor: pickSideBar("#D1D9E0", "#30363D", "#57606A", "#8B949E")
    property color panelSideBarInputBorderColor: pickSideBar("#D1D9E0", "#484F58", "#57606A", "#8B949E")
    property color panelSideBarSearchBackground: pickSideBar("#FFFFFF", "#0D1117", "#FFFFFF", "#000000")
    property color panelSideBarSearchBackground2: pickSideBar("#F6F8FA", "#161B22", "#F6F8FA", "#0D1117")
    property color featureBarBackground: pick("#FFFFFF", "#0D1117", "#FFFFFF", "#000000")
    property color contentBackground: pick("#FFFFFF", "#0D1117", "#FFFFFF", "#000000")
    property color contentSurface: pick("#FFFFFF", "#161B22", "#FFFFFF", "#0D1117")
    property color contentPanelSurface: pick("#FFFFFF", "#161B22", "#FFFFFF", "#0D1117")
    property color contentPanelBorder: pick("#D1D9E0", "#30363D", "#57606A", "#8B949E")
    property color statusBarBackground: accent.statusBar
    property color tabBarBackground: pick("#F6F8FA", "#010409", "#FFFFFF", "#000000")

    property color activityBarTextPrimary: pickSideBar("#1F2328", "#E6EDF3", "#0E1116", "#FFFFFF")
    property color activityBarTextSecondary: pickSideBar("#59636E", "#B1BAC4", "#24292F", "#D0D7DE")
    property color activityBarBorderColor: pickSideBar("#D1D9E0", "#30363D", "#57606A", "#8B949E")
    property color activityBarItemHover: pickSideBar("#EAEEF2", "#21262D", accent.activeLight, accent.activeDark)
    property color activityBarItemActive: pickSideBar(accent.activeLight, accent.activeDark, accent.activeLight, accent.activeDark)

    property color sideBarItemHover: pick("#EAEEF2", "#21262D", accent.activeLight, accent.activeDark)
    property color sideBarItemSelected: pick(accent.activeLight, accent.activeDark, accent.activeLight, accent.activeDark)
    readonly property color tableRowAlternate: pick("#FBFCFD", "#10151C", "#FFFFFF", "#0D1117")
    readonly property color tableRowHover: pick("#F3F6F9", "#1B222C", "#EAEFF5", "#161B22")
    readonly property color tableRowSelected: pick("#EDF3FA", "#1A2635", "#E1EAF5", "#172438")
    readonly property color tableRowSelectionIndicator: accentColor
    property color panelSideBarItemHover: pickSideBar("#EAEEF2", "#21262D", accent.activeLight, accent.activeDark)
    property color panelSideBarItemSelected: pickSideBar(accent.activeLight, accent.activeDark, accent.activeLight, accent.activeDark)

    property color tabActive: pick("#FFFFFF", "#0D1117", "#FFFFFF", "#000000")
    property color tabInactive: pick("#F6F8FA", "#010409", "#F6F8FA", "#000000")
    property color tabHover: pick("#EAEEF2", "#21262D", accent.activeLight, accent.activeDark)

    property color featureMainActive: sideBarItemSelected
    property color featureMainHover: sideBarItemHover

    property color titleButtonHover: pick("#EAEEF2", "#21262D", accent.activeLight, accent.activeDark)

    property color textPrimary: pick("#1F2328", "#E6EDF3", "#0E1116", "#FFFFFF")
    property color textSecondary: pick("#59636E", "#B1BAC4", "#24292F", "#D0D7DE")
    property color textDisabled: pick("#818B98", "#6E7681", "#57606A", "#8B949E")
    property color placeholderTextColor: pick("#6E7781", "#8B949E", "#57606A", "#B1BAC4")

    property color borderColor: pick("#D1D9E0", "#30363D", "#57606A", "#8B949E")
    readonly property color logoBlue: "#6597F8"
    readonly property color logoOrange: "#EF8641"
    property color borderColor2: accentColor
    property color accentColor: pick(accent.color, accent.hover, accent.emphasis, accent.hover)
    property color accentEmphasis: pick(accent.emphasis, accent.color, accent.emphasis, accent.hover)
    readonly property string selectionBackgroundValue: {
        if (mode === ThemeState.lightHighContrast)
            return "#000000"
        if (mode === ThemeState.darkHighContrast)
            return "#FFFFFF"
        if (mode === ThemeState.dark)
            return accent.color
        return accent.emphasis
    }
    readonly property color selectionBackground: selectionBackgroundValue
    readonly property color selectionForeground: selectionForegroundFor(selectionBackgroundValue)
    readonly property color brandOrange: pick("#D9762E", "#EF8641", "#C65F1A", "#F09A5B")
    property color subBarAccentColor: accentColor
    property color panelSideBarAccentColor: accentColor

    property color inputBackground: pick("#FFFFFF", "#0D1117", "#FFFFFF", "#000000")
    property color inputBorderColor: pick("#D1D9E0", "#484F58", "#57606A", "#8B949E")
    property color inputBorderFocusColor: accentColor

    function linearColorChannel(channel) {
        return channel <= 0.04045
                ? channel / 12.92
                : Math.pow((channel + 0.055) / 1.055, 2.4)
    }

    function relativeLuminance(hexColor) {
        const color = ThemeState.normalizeHexColor(hexColor)
        const red = linearColorChannel(ThemeState.hexChannel(color, 1) / 255)
        const green = linearColorChannel(ThemeState.hexChannel(color, 3) / 255)
        const blue = linearColorChannel(ThemeState.hexChannel(color, 5) / 255)
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue
    }

    function contrastRatio(firstColor, secondColor) {
        const first = relativeLuminance(firstColor)
        const second = relativeLuminance(secondColor)
        return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
    }

    function selectionForegroundFor(backgroundColor) {
        return contrastRatio(backgroundColor, "#FFFFFF") >= contrastRatio(backgroundColor, "#000000")
                ? "#FFFFFF"
                : "#000000"
    }

    property color splitHandleColor: pick("#D1D9E0", "#30363D", "#57606A", "#8B949E")
    property color splitHandleHoverColor: statusBarBackground

    readonly property color statusConnected: pick("#1A7F37", "#3FB950", "#116329", "#56D364")
    readonly property color statusWaiting: pick("#9A6700", "#F2CC60", "#7D4E00", "#F8E3A1")
    readonly property color statusDisconnected: pick("#CF222E", "#DA3633", "#A40E26", "#DA3633")

    property color alertError: statusDisconnected
    property color alertSuccess: pick("#1A7F37", "#56D364", "#116329", "#7EE787")
    property color alertWarning: pick("#9A6700", "#F2CC60", "#7D4E00", "#F8E3A1")
    property color alertInfo: accentColor

    readonly property color alertErrorSubtle: {
        if (ThemeState.isDarkHighContrast) return Qt.rgba(1.0, 0.635, 0.596, 0.22)
        if (ThemeState.isDarkMode) return Qt.rgba(1.0, 0.482, 0.447, 0.16)
        if (ThemeState.isLightHighContrast) return "#FFD8D3"
        return "#FFEBE9"
    }
    readonly property color alertWarningSubtle: {
        if (ThemeState.isDarkHighContrast) return Qt.rgba(0.973, 0.890, 0.631, 0.22)
        if (ThemeState.isDarkMode) return Qt.rgba(0.949, 0.800, 0.376, 0.16)
        if (ThemeState.isLightHighContrast) return "#FAE17D"
        return "#FFF8C5"
    }
    readonly property color alertSuccessSubtle: {
        if (ThemeState.isDarkHighContrast) return Qt.rgba(0.494, 0.906, 0.529, 0.22)
        if (ThemeState.isDarkMode) return Qt.rgba(0.337, 0.827, 0.392, 0.16)
        if (ThemeState.isLightHighContrast) return "#B4F1B4"
        return "#DAFBE1"
    }
    readonly property color alertInfoSubtle: {
        if (ThemeState.isDarkHighContrast) return accent.activeDark
        if (ThemeState.isDarkMode) return Qt.rgba(0.345, 0.651, 1.0, 0.16)
        if (ThemeState.isLightHighContrast) return accent.activeLight
        return "#DDF4FF"
    }

    // Notification severity colors are deliberately independent from the
    // user-selected accent. An information toast must stay blue even when the
    // application accent/status bar is red, orange, or custom.
    readonly property color notificationInfoAccent: pick("#0969DA", "#58A6FF", "#0349B4", "#79C0FF")
    readonly property color notificationSuccessAccent: pick("#1A7F37", "#56D364", "#116329", "#7EE787")
    readonly property color notificationWarningAccent: pick("#9A6700", "#F2CC60", "#7D4E00", "#F8E3A1")
    readonly property color notificationErrorAccent: pick("#CF222E", "#FF7B72", "#A40E26", "#FFA198")

    readonly property color notificationInfoBackground: pick("#DDF4FF", "#162D4D", "#B6E3FF", "#0C2D6B")
    readonly property color notificationSuccessBackground: pick("#DAFBE1", "#163B24", "#B4F1B4", "#0B4F1D")
    readonly property color notificationWarningBackground: pick("#FFF8C5", "#3D2E00", "#FAE17D", "#4D3800")
    readonly property color notificationErrorBackground: pick("#FFEBE9", "#3D1515", "#FFD8D3", "#4B1113")

    // ConfigTextViewer syntax palette. Each semantic token family has a
    // distinct color in every theme so addresses, masks and policy keywords
    // are distinguishable without relying on the user-selected accent.
    readonly property color syntaxIpAddress: pick("#0969DA", "#79C0FF", "#0349B4", "#B6E3FF")
    readonly property color syntaxPrefix: pick("#8250DF", "#D2A8FF", "#6639BA", "#E2C5FF")
    readonly property color syntaxMask: pick("#1A7F37", "#56D364", "#116329", "#7EE787")
    readonly property color syntaxWildcard: pick("#9A6700", "#E3B341", "#7D4E00", "#F8E3A1")
    readonly property color syntaxInterface: pick("#CF222E", "#FF7B72", "#A40E26", "#FFA198")
    readonly property color syntaxNumber: pick("#953800", "#FFA657", "#702C00", "#FFC680")
    readonly property color syntaxBoolean: pick("#0550AE", "#A5D6FF", "#033D8B", "#CAE8FF")
    readonly property color syntaxDateTime: pick("#57606A", "#B1BAC4", "#24292F", "#D0D7DE")
    readonly property color syntaxPermit: pick("#0E7C66", "#4AC26B", "#075B4B", "#72E6A1")
    readonly property color syntaxDeny: pick("#B42318", "#FF938A", "#821B12", "#FFB4AD")
    readonly property color syntaxInside: pick("#0E7490", "#39C5CF", "#07566B", "#73E1E8")
    readonly property color syntaxOutside: pick("#7C3AED", "#BC8CFF", "#5B21B6", "#D8B4FE")
    readonly property color syntaxComment: pick("#6E7781", "#8B949E", "#57606A", "#B1BAC4")

    readonly property color badgeWarningBg: pick("#FFF8C5", "#3D2E00", "#FAE17D", "#4D3800")
    readonly property color badgeWarningText: pick("#7D4E00", "#F2CC60", "#3F2200", "#F8E3A1")
    readonly property color badgeErrorBg: pick("#FFEBE9", "#3D1515", "#FFD8D3", "#4B1113")
    readonly property color badgeErrorText: pick("#A40E26", "#FF7B72", "#6E0711", "#FFA198")
    readonly property color badgeSuccessBg: pick("#DAFBE1", "#0F3A1D", "#B4F1B4", "#0B4F1D")
    readonly property color badgeSuccessText: pick("#116329", "#7EE787", "#0A4A1F", "#AFF5B4")

    property color buttonTextSolid: "#FFFFFF"
    property color buttonDisabled: pick("#EFF2F5", "#30363D", "#D1D9E0", "#484F58")

    property color searchBackground: pick("#FFFFFF", "#0D1117", "#FFFFFF", "#000000")
    property color searchBackground2: pick("#F6F8FA", "#161B22", "#F6F8FA", "#0D1117")

    readonly property color statusBarDimText: Qt.rgba(1, 1, 1, ThemeState.isHighContrast ? 0.88 : 0.72)
    readonly property color statusBarWarningText:
        contrastRatio(statusBarBackground, "#FFF3BF") >= 4.5
        ? "#FFF3BF"
        : selectionForegroundFor(statusBarBackground)
    readonly property color statusBarSepColor: Qt.rgba(1, 1, 1, ThemeState.isHighContrast ? 0.42 : 0.24)

    readonly property color shadowColor: ThemeState.isDarkMode ? Qt.rgba(0, 0, 0, 0.45) : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.20)
    readonly property color shadowColorLight: ThemeState.isDarkMode ? Qt.rgba(0, 0, 0, 0.30) : Qt.rgba(31 / 255, 35 / 255, 40 / 255, 0.12)
    readonly property color dialogOverlay: ThemeState.isHighContrast ? "#B0000000" : "#80000000"
}
