pragma ComponentBehavior: Bound

import QtQuick
import UI

Text {
    id: root

    property bool header: false
    property bool primary: false
    property bool monospaced: false

    color: header || primary ? Theme.textPrimary : Theme.textSecondary
    font.family: monospaced ? Theme.monoFontFamily : Theme.fontFamily
    font.pixelSize: Theme.fontSizeSmall
    font.bold: header
    verticalAlignment: Text.AlignVCenter
    elide: Text.ElideRight
}
