pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

SavedListPanel {
    id: panel
    property var aclModel
    property int selectedAclId: 0
    signal viewRequested(int index)
    signal editRequested(int index)
    signal deleteRequested(int aclId)

    Layout.fillWidth: true
    Layout.preferredHeight: Math.max(210, parent ? parent.height * 0.38 : 210)
    title: "Saved ACLs"
    count: aclModel ? aclModel.count : 0
    countColor: Theme.accentColor
    emptyText: "No saved ACLs for this host and type."
    headerComponent: Component {
        SavedListHeader {
            width: parent ? parent.width : 0
            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacing8
                DataTableCell { Layout.preferredWidth: 34; header: true; text: "#" }
                DataTableCell { Layout.fillWidth: true; header: true; text: "ACL" }
                DataTableCell { Layout.preferredWidth: 68; header: true; text: "Rules" }
                DataTableCell { Layout.preferredWidth: 120; header: true; text: "Binding" }
                DataTableCell { Layout.preferredWidth: 192; header: true; text: "Actions" }
            }
        }
    }

    ListView {
        anchors.fill: parent
        model: panel.aclModel
        clip: true
        spacing: 0
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        delegate: SavedListRow {
            required property int index
            required property int aclIndex
            required property int aclId
            required property string aclName
            required property string description
            required property int ruleCount
            required property string bindingText
            rowIndex: index
            width: ListView.view ? ListView.view.width : 0
            height: description !== "" ? 48 : 38
            selected: panel.selectedAclId === aclId
            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacing8
                DataTableCell { Layout.preferredWidth: 34; text: index + 1 }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Text { Layout.fillWidth: true; text: aclName; color: Theme.textPrimary; elide: Text.ElideRight }
                    Text {
                        visible: description !== ""
                        Layout.fillWidth: true
                        text: description
                        color: Theme.textDisabled
                        font.pixelSize: Theme.fontSizeSmall
                        elide: Text.ElideRight
                    }
                }
                DataTableCell { Layout.preferredWidth: 68; text: ruleCount }
                DataTableCell {
                    Layout.preferredWidth: 120
                    text: bindingText
                }
                StandardButton {
                    Layout.preferredWidth: 56
                    text: "View"
                    type: "Secondary"
                    onClicked: panel.viewRequested(aclIndex)
                }
                StandardButton {
                    Layout.preferredWidth: 56
                    text: "Edit"
                    type: "Secondary"
                    onClicked: panel.editRequested(aclIndex)
                }
                StandardButton {
                    Layout.preferredWidth: 64
                    text: "Delete"
                    type: "Secondary"
                    onClicked: panel.deleteRequested(aclId)
                }
            }
        }
    }
}
