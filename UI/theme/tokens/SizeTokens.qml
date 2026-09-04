pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick

QtObject {
    readonly property int windowDefaultWidth: 1440
    readonly property int windowDefaultHeight: 1024
    readonly property int windowMinWidth: 1024
    readonly property int windowMinHeight: 700

    readonly property int activityBarWidth: 48
    readonly property int sideBarWidth: 300
    readonly property int windowTitleHeight: 35
    readonly property int featureBarHeight: 35
    readonly property int statusBarHeight: 22
    readonly property int tabBarHeight: 35
    readonly property int subBarHeight: 36

    readonly property int listItemHeight: 28
    readonly property int statusIconSize: 28
    readonly property int sideBarFeatureIcon: 28
    readonly property int searchBarHeight: 28

    readonly property int sideBarMinWidth: 180
    readonly property int sideBarCollapseWidth: 60

    readonly property int itemHeight: 32
    readonly property int tableHeaderHeight: 36
    readonly property int tableRowHeight: 40
    readonly property int contextMenuWidth: 160
    readonly property int checkboxSize: 16
    readonly property int footerHeight: 56
    readonly property int inputMinimumWidth: 120

    readonly property int iconSizeSmall: 14
    readonly property int iconSizeNormal: 16
    readonly property int iconSizeLarge: 20
    readonly property int iconSizeXLarge: 24

    readonly property int borderWidth: 1

    readonly property int radiusSmall: 4
    readonly property int radiusMedium: 6
    readonly property int radiusLarge: 8
    readonly property int radiusRound: 999

    readonly property int borderRadius: 4
    readonly property int cardRadius: 6

    readonly property int spacing2: 2
    readonly property int spacing4: 4
    readonly property int spacing8: 8
    readonly property int spacing12: 12
    readonly property int spacing16: 16
    readonly property int spacing24: 24
    readonly property int spacing32: 32

    readonly property int splitHandleWidth: 1
    readonly property int splitHandleHitWidth: 5
    readonly property int splitCollapseButtonSize: 16
    readonly property int minimumWorkspaceWidth: 640
    readonly property int compactWorkspaceBreakpoint: 640
    readonly property int largeWorkspaceBreakpoint: 1008
    readonly property int dataWorkspaceBreakpoint: 920
}
