pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

GridLayout {
    id: root

    property string title: ""
    property int totalCount: 0
    property int visibleCount: totalCount
    property string searchText: ""
    property string searchPlaceholder: "Filter rows..."
    property bool searchEnabled: true
    readonly property bool compact: width < 520

    signal searchEdited(string value)

    columns: compact ? 1 : 2
    columnSpacing: Theme.spacing12
    rowSpacing: Theme.spacing8

    RowLayout {
        Layout.fillWidth: true
        spacing: Theme.spacing8

        Text {
            Layout.fillWidth: true
            text: root.title
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeNormal
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }

        Rectangle {
            implicitWidth: countLabel.implicitWidth + Theme.spacing16
            implicitHeight: 24
            radius: Theme.radiusRound
            color: Theme.tableRowAlternate
            border.color: Theme.contentPanelBorder
            border.width: Theme.borderWidth

            Text {
                id: countLabel
                anchors.centerIn: parent
                text: root.visibleCount === root.totalCount
                      ? String(root.totalCount)
                      : "%1 / %2".arg(root.visibleCount).arg(root.totalCount)
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
        }
    }

    RowLayout {
        visible: root.searchEnabled
        Layout.fillWidth: true
        Layout.preferredWidth: root.compact ? root.width : 300
        Layout.alignment: Qt.AlignRight
        spacing: Theme.spacing4

        StandardTextField {
            Layout.fillWidth: true
            text: root.searchText
            placeholderText: root.searchPlaceholder
            onTextEdited: value => root.searchEdited(value)
        }

        StandardButton {
            visible: root.searchText !== ""
            type: "Icon"
            icon.source: AppAssets.actionClear
            tooltip: "Clear filter"
            onClicked: root.searchEdited("")
        }
    }
}
