pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    property string title: ""
    property int count: 0
    property string emptyText: ""
    property color countColor: Theme.accentColor
    property Component headerComponent: null
    default property alias content: contentHost.data

    color: Theme.contentBackground
    clip: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing24
        anchors.topMargin: Theme.spacing16
        spacing: Theme.spacing12

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: root.title
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLarge
                font.family: Theme.fontFamily
                font.bold: true
            }

            StandardBadge {
                text: String(root.count)
                badgeColor: root.countColor
                textColor: Theme.buttonTextSolid
                Layout.alignment: Qt.AlignVCenter
                Layout.leftMargin: Theme.spacing8
            }

            Item { Layout.fillWidth: true }
        }

        Rectangle {
            Layout.fillWidth: true
            height: Theme.borderWidth
            color: Theme.splitHandleColor
        }

        Loader {
            Layout.fillWidth: true
            Layout.preferredHeight: active ? Theme.tableHeaderHeight : 0
            active: root.headerComponent !== null
            visible: active
            sourceComponent: root.headerComponent
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            EmptyState {
                anchors.fill: parent
                visible: root.count === 0
                title: root.emptyText
                emphasized: false
            }

            Item {
                id: contentHost
                anchors.fill: parent
                visible: root.count > 0
            }
        }
    }
}
