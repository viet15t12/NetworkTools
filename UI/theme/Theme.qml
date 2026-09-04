pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick
import UI

QtObject {
    readonly property int windowDefaultWidth: SizeTokens.windowDefaultWidth
    readonly property int windowDefaultHeight: SizeTokens.windowDefaultHeight
    readonly property int windowMinWidth: SizeTokens.windowMinWidth
    readonly property int windowMinHeight: SizeTokens.windowMinHeight

    readonly property int activityBarWidth: SizeTokens.activityBarWidth
    readonly property int sideBarWidth: SizeTokens.sideBarWidth
    readonly property int windowTitleHeight: SizeTokens.windowTitleHeight
    readonly property int featureBarHeight: SizeTokens.featureBarHeight
    readonly property int statusBarHeight: SizeTokens.statusBarHeight
    readonly property int tabBarHeight: SizeTokens.tabBarHeight
    readonly property int subBarHeight: SizeTokens.subBarHeight

    readonly property int listItemHeight: SizeTokens.listItemHeight
    readonly property int statusIconSize: SizeTokens.statusIconSize
    readonly property int sideBarFeatureIcon: SizeTokens.sideBarFeatureIcon
    readonly property int searchBarHeight: SizeTokens.searchBarHeight

    readonly property int sideBarMinWidth: SizeTokens.sideBarMinWidth
    readonly property int sideBarCollapseWidth: SizeTokens.sideBarCollapseWidth
    readonly property int itemHeight: SizeTokens.itemHeight
    readonly property int tableHeaderHeight: SizeTokens.tableHeaderHeight
    readonly property int tableRowHeight: SizeTokens.tableRowHeight
    readonly property int contextMenuWidth: SizeTokens.contextMenuWidth
    readonly property int checkboxSize: SizeTokens.checkboxSize
    readonly property int footerHeight: SizeTokens.footerHeight
    readonly property int inputMinimumWidth: SizeTokens.inputMinimumWidth

    readonly property int iconSizeSmall: SizeTokens.iconSizeSmall
    readonly property int iconSizeNormal: SizeTokens.iconSizeNormal
    readonly property int iconSizeLarge: SizeTokens.iconSizeLarge
    readonly property int iconSizeXLarge: SizeTokens.iconSizeXLarge

    readonly property int borderWidth: SizeTokens.borderWidth

    readonly property int radiusSmall: SizeTokens.radiusSmall
    readonly property int radiusMedium: SizeTokens.radiusMedium
    readonly property int radiusLarge: SizeTokens.radiusLarge
    readonly property int radiusRound: SizeTokens.radiusRound

    readonly property int borderRadius: SizeTokens.borderRadius
    readonly property int cardRadius: SizeTokens.cardRadius

    readonly property int spacing2: SizeTokens.spacing2
    readonly property int spacing4: SizeTokens.spacing4
    readonly property int spacing8: SizeTokens.spacing8
    readonly property int spacing12: SizeTokens.spacing12
    readonly property int spacing16: SizeTokens.spacing16
    readonly property int spacing24: SizeTokens.spacing24
    readonly property int spacing32: SizeTokens.spacing32

    readonly property int splitHandleWidth: SizeTokens.splitHandleWidth
    readonly property int splitHandleHitWidth: SizeTokens.splitHandleHitWidth
    readonly property int splitCollapseButtonSize: SizeTokens.splitCollapseButtonSize
    readonly property int minimumWorkspaceWidth: SizeTokens.minimumWorkspaceWidth
    readonly property int compactWorkspaceBreakpoint: SizeTokens.compactWorkspaceBreakpoint
    readonly property int largeWorkspaceBreakpoint: SizeTokens.largeWorkspaceBreakpoint
    readonly property int dataWorkspaceBreakpoint: SizeTokens.dataWorkspaceBreakpoint

    readonly property string fontFamily: TypographyTokens.fontFamily
    readonly property string monoFontFamily: TypographyTokens.monoFontFamily
    readonly property int fontSizeCaption: TypographyTokens.fontSizeCaption
    readonly property int fontSizeSmall: TypographyTokens.fontSizeSmall
    readonly property int fontSizeNormal: TypographyTokens.fontSizeNormal
    readonly property int fontSizeLarge: TypographyTokens.fontSizeLarge
    readonly property int fontSizeTitle: TypographyTokens.fontSizeTitle
    readonly property int fontSizeDisplay: TypographyTokens.fontSizeDisplay

    readonly property int animationDurationFast: MotionTokens.animationDurationFast
    readonly property int animationDurationMedium: MotionTokens.animationDurationMedium
    readonly property int animationDurationSlow: MotionTokens.animationDurationSlow
    readonly property int viewLoadDispatchDelay: MotionTokens.viewLoadDispatchDelay
    readonly property int loaderRotationDuration: MotionTokens.loaderRotationDuration

    readonly property int themeMode: ThemeState.themeMode
    readonly property int effectiveThemeMode: ThemeState.effectiveThemeMode
    readonly property bool isDarkMode: ThemeState.isDarkMode
    readonly property bool isHighContrast: ThemeState.isHighContrast
    readonly property bool isLightHighContrast: ThemeState.isLightHighContrast
    readonly property bool isDarkHighContrast: ThemeState.isDarkHighContrast
    readonly property bool isDarkSideBar: ThemeState.isDarkSideBar
    readonly property string themeName: ThemeState.themeName

    readonly property color windowTitleBackground: ColorTokens.windowTitleBackground
    readonly property color activityBarBackground: ColorTokens.activityBarBackground
    readonly property color sideBarBackground: ColorTokens.sideBarBackground
    readonly property color panelSideBarBackground: ColorTokens.panelSideBarBackground
    readonly property color panelSideBarSurface: ColorTokens.panelSideBarSurface
    readonly property color featureBarBackground: ColorTokens.featureBarBackground
    readonly property color contentBackground: ColorTokens.contentBackground
    readonly property color contentSurface: ColorTokens.contentSurface
    readonly property color contentPanelSurface: ColorTokens.contentPanelSurface
    readonly property color contentPanelBorder: ColorTokens.contentPanelBorder
    readonly property color statusBarBackground: ColorTokens.statusBarBackground
    readonly property color tabBarBackground: ColorTokens.tabBarBackground

    readonly property color activityBarTextPrimary: ColorTokens.activityBarTextPrimary
    readonly property color activityBarTextSecondary: ColorTokens.activityBarTextSecondary
    readonly property color activityBarBorderColor: ColorTokens.activityBarBorderColor
    readonly property color activityBarItemHover: ColorTokens.activityBarItemHover
    readonly property color activityBarItemActive: ColorTokens.activityBarItemActive

    readonly property color panelSideBarTextPrimary: ColorTokens.panelSideBarTextPrimary
    readonly property color panelSideBarTextSecondary: ColorTokens.panelSideBarTextSecondary
    readonly property color panelSideBarTextDisabled: ColorTokens.panelSideBarTextDisabled
    readonly property color panelSideBarPlaceholderTextColor: ColorTokens.panelSideBarPlaceholderTextColor
    readonly property color panelSideBarBorderColor: ColorTokens.panelSideBarBorderColor
    readonly property color panelSideBarInputBorderColor: ColorTokens.panelSideBarInputBorderColor
    readonly property color panelSideBarSearchBackground: ColorTokens.panelSideBarSearchBackground
    readonly property color panelSideBarSearchBackground2: ColorTokens.panelSideBarSearchBackground2
    readonly property color panelSideBarAccentColor: ColorTokens.panelSideBarAccentColor
    readonly property color panelSideBarItemHover: ColorTokens.panelSideBarItemHover
    readonly property color panelSideBarItemSelected: ColorTokens.panelSideBarItemSelected

    readonly property color sideBarItemHover: ColorTokens.sideBarItemHover
    readonly property color sideBarItemSelected: ColorTokens.sideBarItemSelected
    readonly property color tableRowAlternate: ColorTokens.tableRowAlternate
    readonly property color tableRowHover: ColorTokens.tableRowHover
    readonly property color tableRowSelected: ColorTokens.tableRowSelected
    readonly property color tableRowSelectionIndicator: ColorTokens.tableRowSelectionIndicator

    readonly property color tabActive: ColorTokens.tabActive
    readonly property color tabInactive: ColorTokens.tabInactive
    readonly property color tabHover: ColorTokens.tabHover

    readonly property color featureMainActive: ColorTokens.featureMainActive
    readonly property color featureMainHover: ColorTokens.featureMainHover

    readonly property color titleButtonHover: ColorTokens.titleButtonHover

    readonly property color textPrimary: ColorTokens.textPrimary
    readonly property color textSecondary: ColorTokens.textSecondary
    readonly property color textDisabled: ColorTokens.textDisabled
    readonly property color placeholderTextColor: ColorTokens.placeholderTextColor

    readonly property color borderColor: ColorTokens.borderColor
    readonly property color borderColor2: ColorTokens.borderColor2
    readonly property color accentColor: ColorTokens.accentColor
    readonly property color accentEmphasis: ColorTokens.accentEmphasis
    readonly property color selectionBackground: ColorTokens.selectionBackground
    readonly property color selectionForeground: ColorTokens.selectionForeground
    readonly property color logoBlue: ColorTokens.logoBlue
    readonly property color logoOrange: ColorTokens.logoOrange
    readonly property color brandOrange: ColorTokens.brandOrange
    readonly property color subBarAccentColor: ColorTokens.subBarAccentColor

    readonly property color inputBackground: ColorTokens.inputBackground
    readonly property color inputBorderColor: ColorTokens.inputBorderColor
    readonly property color inputBorderFocusColor: ColorTokens.inputBorderFocusColor

    readonly property color splitHandleColor: ColorTokens.splitHandleColor
    readonly property color splitHandleHoverColor: ColorTokens.splitHandleHoverColor

    readonly property color statusConnected: ColorTokens.statusConnected
    readonly property color statusWaiting: ColorTokens.statusWaiting
    readonly property color statusDisconnected: ColorTokens.statusDisconnected

    readonly property color alertError: ColorTokens.alertError
    readonly property color alertSuccess: ColorTokens.alertSuccess
    readonly property color alertWarning: ColorTokens.alertWarning
    readonly property color alertInfo: ColorTokens.alertInfo

    readonly property color alertErrorSubtle: ColorTokens.alertErrorSubtle
    readonly property color alertWarningSubtle: ColorTokens.alertWarningSubtle
    readonly property color alertSuccessSubtle: ColorTokens.alertSuccessSubtle
    readonly property color alertInfoSubtle: ColorTokens.alertInfoSubtle

    readonly property color notificationInfoAccent: ColorTokens.notificationInfoAccent
    readonly property color notificationSuccessAccent: ColorTokens.notificationSuccessAccent
    readonly property color notificationWarningAccent: ColorTokens.notificationWarningAccent
    readonly property color notificationErrorAccent: ColorTokens.notificationErrorAccent
    readonly property color notificationInfoBackground: ColorTokens.notificationInfoBackground
    readonly property color notificationSuccessBackground: ColorTokens.notificationSuccessBackground
    readonly property color notificationWarningBackground: ColorTokens.notificationWarningBackground
    readonly property color notificationErrorBackground: ColorTokens.notificationErrorBackground

    readonly property color syntaxIpAddress: ColorTokens.syntaxIpAddress
    readonly property color syntaxPrefix: ColorTokens.syntaxPrefix
    readonly property color syntaxMask: ColorTokens.syntaxMask
    readonly property color syntaxWildcard: ColorTokens.syntaxWildcard
    readonly property color syntaxInterface: ColorTokens.syntaxInterface
    readonly property color syntaxNumber: ColorTokens.syntaxNumber
    readonly property color syntaxBoolean: ColorTokens.syntaxBoolean
    readonly property color syntaxDateTime: ColorTokens.syntaxDateTime
    readonly property color syntaxPermit: ColorTokens.syntaxPermit
    readonly property color syntaxDeny: ColorTokens.syntaxDeny
    readonly property color syntaxInside: ColorTokens.syntaxInside
    readonly property color syntaxOutside: ColorTokens.syntaxOutside
    readonly property color syntaxComment: ColorTokens.syntaxComment

    readonly property color badgeWarningBg: ColorTokens.badgeWarningBg
    readonly property color badgeWarningText: ColorTokens.badgeWarningText
    readonly property color badgeErrorBg: ColorTokens.badgeErrorBg
    readonly property color badgeErrorText: ColorTokens.badgeErrorText
    readonly property color badgeSuccessBg: ColorTokens.badgeSuccessBg
    readonly property color badgeSuccessText: ColorTokens.badgeSuccessText

    readonly property color buttonTextSolid: ColorTokens.buttonTextSolid
    readonly property color buttonDisabled: ColorTokens.buttonDisabled

    readonly property color searchBackground: ColorTokens.searchBackground
    readonly property color searchBackground2: ColorTokens.searchBackground2

    readonly property color statusBarDimText: ColorTokens.statusBarDimText
    readonly property color statusBarSepColor: ColorTokens.statusBarSepColor
    readonly property color statusBarWarningText: ColorTokens.statusBarWarningText

    readonly property color shadowColor: ColorTokens.shadowColor
    readonly property color shadowColorLight: ColorTokens.shadowColorLight
    readonly property color dialogOverlay: ColorTokens.dialogOverlay
}
