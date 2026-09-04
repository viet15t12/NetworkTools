pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

SavedListPanel {
    id: panel
    property var ruleModel
    property bool editing: false
    property bool viewing: false
    property bool allowDelete: true
    property string aclName: ""
    signal deleteRequested(int index)

    Layout.fillWidth: true
    Layout.fillHeight: true
    title: (editing || viewing) ? "Rules: " + aclName + (viewing && !editing ? " (View only)" : "") : "Pending Rules"
    count: ruleModel ? ruleModel.count : 0
    countColor: count > 0 ? Theme.accentColor : Theme.textDisabled
    emptyText: "No rules in the editor yet."
    headerComponent: Component {
        SavedListHeader {
            width: parent ? parent.width : 0
            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacing8
                DataTableCell { Layout.preferredWidth: 44; header: true; text: "Seq" }
                DataTableCell { Layout.preferredWidth: 70; header: true; text: "Action" }
                DataTableCell { Layout.fillWidth: true; header: true; text: "Detail" }
                DataTableCell { Layout.preferredWidth: 24; header: true; text: "" }
            }
        }
    }
    ListView {
        anchors.fill: parent
        model: panel.ruleModel
        clip: true
        spacing: 0
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        delegate: AclRuleRow {
            required property int index
            required property int ruleSequence
            required property string ruleAction
            required property string ruleDetail
            required property string ruleAclType
            width: ListView.view ? ListView.view.width : 0
            rowIndex: index
            rowSequence: ruleSequence
            rowAction: ruleAction
            rowDetail: ruleDetail
            rowAclType: ruleAclType
            allowDelete: panel.allowDelete
            onDeleteClicked: (idx) => panel.deleteRequested(idx)
        }
    }
}
