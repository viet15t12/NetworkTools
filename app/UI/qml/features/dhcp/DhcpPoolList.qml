pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

SavedListPanel {
    id: panel
    property var poolModel
    signal editRequested(int index, var row)
    signal deleteRequested(int index, var row)

    SplitView.fillWidth: true
    SplitView.minimumWidth: 0
    title: "Saved Pools"
    count: poolModel ? poolModel.count : 0
    countColor: Theme.accentColor
    emptyText: "No DHCP pools configured yet."
    headerComponent: Component {
        SavedListHeader {
            width: parent ? parent.width : 0
            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacing8
                DataTableCell { Layout.preferredWidth: 120; header: true; text: "Pool" }
                DataTableCell { Layout.preferredWidth: 130; header: true; text: "Network" }
                DataTableCell { Layout.preferredWidth: 140; header: true; text: "Subnet" }
                DataTableCell { Layout.preferredWidth: 130; header: true; text: "Gateway" }
                DataTableCell { Layout.fillWidth: true; header: true; text: "Lease" }
                DataTableCell { Layout.preferredWidth: 64; header: true; text: "Actions" }
            }
        }
    }
    ListView {
        anchors.fill: parent
        model: panel.poolModel
        clip: true
        spacing: 0
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        delegate: SavedListRow {
            required property int index
            required property var model
            rowIndex: index
            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacing8
                DataTableCell { Layout.preferredWidth: 120; primary: true; text: model.pool }
                DataTableCell { Layout.preferredWidth: 130; monospaced: true; text: model.network }
                DataTableCell { Layout.preferredWidth: 140; monospaced: true; text: model.subnetmask }
                DataTableCell { Layout.preferredWidth: 130; monospaced: true; text: model.defaut || "—" }
                DataTableCell { Layout.fillWidth: true; text: model.lease || "1" }
                Item {
                    Layout.preferredWidth: 64
                    Layout.fillHeight: true
                    Row {
                        anchors.centerIn: parent
                        spacing: 4
                        IconButton {
                            buttonSize: 24; glyph: "E"; tooltip: "Edit"
                            onClicked: panel.editRequested(index, model)
                        }
                        IconButton {
                            buttonSize: 24; glyph: "X"; danger: true; tooltip: "Delete"
                            onClicked: panel.deleteRequested(index, model)
                        }
                    }
                }
            }
        }
    }
}
