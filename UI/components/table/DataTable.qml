pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

DataTableFrame {
    id: root

    property int count: 0
    property string emptyTitle: "No data"
    property string emptyDescription: ""
    property Component headerComponent: null
    property int bodyMargins: Theme.spacing8
    default property alias content: contentHost.data

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Loader {
            Layout.fillWidth: true
            Layout.preferredHeight: active ? Theme.tableHeaderHeight : 0
            visible: active
            active: root.headerComponent !== null
            sourceComponent: root.headerComponent
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Item {
                id: contentHost
                anchors.fill: parent
                anchors.margins: root.bodyMargins
                visible: root.count > 0
            }

            EmptyState {
                anchors.fill: parent
                visible: root.count === 0
                title: root.emptyTitle
                description: root.emptyDescription
            }
        }
    }
}
