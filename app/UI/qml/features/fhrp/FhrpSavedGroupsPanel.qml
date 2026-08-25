pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

SavedListPanel {
    id: root
    required property var groupModel
    required property string protocolLabel
    signal removeRequested(int fhrpId)

    title: protocolLabel.toUpperCase() + " groups"
    count: groupModel.count
    emptyText: "No " + protocolLabel.toUpperCase()
               + " group includes this device yet."

    function memberCount(members) {
        if (!members)
            return 0
        if (typeof members.count === "number")
            return members.count
        return members.length || 0
    }

    function memberAt(members, index) {
        return typeof members.get === "function"
               ? members.get(index) : members[index]
    }

    function memberHosts(members) {
        const hosts = []
        for (let i = 0; i < memberCount(members); i++)
            hosts.push(memberAt(members, i).host)
        return hosts.join("  ·  ")
    }

    function pendingMembers(members) {
        let count = 0
        for (let i = 0; i < memberCount(members); i++) {
            if (String(memberAt(members, i).sync_status || "")
                    !== "synchronized")
                count++
        }
        return count
    }

    ListView {
        anchors.fill: parent
        spacing: Theme.spacing8
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        model: root.groupModel
        delegate: SavedListRow {
            id: groupRow
            required property int index
            required property var model
            rowIndex: index
            width: ListView.view.width
            height: 104

            Rectangle {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: 4
                height: 58
                radius: 2
                color: root.pendingMembers(groupRow.model.members) > 0
                       ? Theme.alertWarning : Theme.statusConnected
            }

            ColumnLayout {
                anchors.left: parent.left
                anchors.right: removeButton.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: Theme.spacing16
                anchors.rightMargin: Theme.spacing8
                spacing: Theme.spacing4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing4
                    Text {
                        Layout.fillWidth: true
                        text: groupRow.model.virtual_ip || ""
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeNormal
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    StandardBadge {
                        text: root.protocolLabel.toUpperCase()
                              + " " + String(groupRow.model.group_number || 0)
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: root.memberHosts(groupRow.model.members)
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    text: root.pendingMembers(groupRow.model.members) > 0
                          ? root.pendingMembers(groupRow.model.members)
                            + " member(s) waiting for push"
                          : "Synchronized on all members"
                    color: root.pendingMembers(groupRow.model.members) > 0
                           ? Theme.alertWarning : Theme.statusConnected
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            IconButton {
                id: removeButton
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing12
                anchors.verticalCenter: parent.verticalCenter
                buttonSize: 30
                iconSize: Theme.iconSizeNormal
                iconSource: AppAssets.actionDelete
                danger: true
                tooltip: "Remove group"
                onClicked: root.removeRequested(
                               Number(groupRow.model.fhrp_id || 0))
            }
        }
    }
}
