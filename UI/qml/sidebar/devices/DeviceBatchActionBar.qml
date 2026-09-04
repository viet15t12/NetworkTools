pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    property int selectedCount: 0
    property int visibleCount: 0
    readonly property bool compact: width < 250

    signal selectAllRequested()
    signal clearRequested()

    implicitHeight: 42
    color: Theme.alertInfoSubtle
    border.color: Theme.panelSideBarAccentColor
    border.width: Theme.borderWidth

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing8
        anchors.rightMargin: Theme.spacing8
        spacing: Theme.spacing8

        StandardBadge {
            text: root.compact ? String(root.selectedCount)
                               : root.selectedCount + " selected"
            badgeColor: Theme.contentPanelSurface
            textColor: Theme.accentColor
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: !root.compact
            text: "Right-click for batch actions"
            color: Theme.panelSideBarTextSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            elide: Text.ElideRight
        }

        IconButton {
            Layout.preferredWidth: 28
            Layout.preferredHeight: 28
            buttonSize: 28
            iconSize: Theme.fontSizeNormal
            glyph: "✓"
            enabled: root.visibleCount > 0
            tooltip: "Select all visible hosts (Ctrl+A)"
            onClicked: root.selectAllRequested()
        }

        IconButton {
            Layout.preferredWidth: 28
            Layout.preferredHeight: 28
            buttonSize: 28
            iconSize: Theme.fontSizeNormal
            glyph: "×"
            tooltip: "Clear selection (Esc)"
            onClicked: root.clearRequested()
        }
    }
}
