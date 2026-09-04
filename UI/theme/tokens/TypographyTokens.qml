pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick

QtObject {
    readonly property string fontFamily: "Segoe UI"
    readonly property string monoFontFamily: "Consolas"
    readonly property int fontSizeCaption: 10
    readonly property int fontSizeSmall: 11
    readonly property int fontSizeNormal: 13
    readonly property int fontSizeLarge: 15
    readonly property int fontSizeTitle: 18
    readonly property int fontSizeDisplay: 24
}
