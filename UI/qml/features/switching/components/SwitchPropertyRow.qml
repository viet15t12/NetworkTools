pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

RowLayout {
    id: root

    property string label: ""
    property string value: "—"
    property color valueColor: Theme.textPrimary
    property bool monospaced: false
    property bool emphasize: false

    implicitHeight: 24
    spacing: Theme.spacing12

    Text {
        Layout.preferredWidth: Math.min(126, Math.max(96, root.width * 0.36))
        text: root.label
        color: Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSmall
        elide: Text.ElideRight
    }

    Text {
        Layout.fillWidth: true
        text: root.value === "" ? "—" : root.value
        color: root.valueColor
        font.family: root.monospaced ? Theme.monoFontFamily : Theme.fontFamily
        font.pixelSize: Theme.fontSizeNormal
        font.weight: root.emphasize ? Font.DemiBold : Font.Normal
        horizontalAlignment: Text.AlignRight
        elide: Text.ElideRight
    }
}
