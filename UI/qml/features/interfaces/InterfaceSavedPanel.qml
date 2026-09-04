pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

SavedListPanel {
    id: panel

    property var interfaceModel: null
    property int selectedIndex: -1
    property string interfaceCategory: "Physical"

    signal selected(int index, var row)
    signal editRequested(int index, var row)
    signal deleteRequested(int index, var row)
    signal contextRequested(int index, var row, real sceneX, real sceneY)

    title: interfaceCategory + " interfaces"
    count: interfaceModel ? interfaceModel.count : 0
    emptyText: "No " + interfaceCategory.toLowerCase() + " interfaces for this device."

    function itemAtIndex(index) {
        return interfaceList.itemAtIndex(index)
    }

    function referenceTables(row) {
        const refs = []
        if (Number(row.has_l3 || 0) === 1) refs.push("L3")
        if (Number(row.has_tunnel || 0) === 1) refs.push("Tunnel")
        if (Number(row.has_wan || 0) === 1) refs.push("WAN")
        if (String(row.interface_type || "") === "loopback") refs.push("Loopback")
        if (String(row.interface_type || "") === "subinterface") refs.push("802.1Q")
        return refs
    }

    ListView {
        id: interfaceList
        objectName: "interfaceSavedList"
        anchors.fill: parent
        model: panel.interfaceModel
        clip: true
        spacing: 0
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        delegate: SavedListRow {
            id: rowDelegate
            required property int index
            required property var model
            rowIndex: index
            height: 78
            selected: panel.selectedIndex === index

            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacing8

                Rectangle {
                    Layout.preferredWidth: 4
                    Layout.preferredHeight: 38
                    radius: 2
                    color: Number(rowDelegate.model.shutdown || 0) === 1
                           ? Theme.textDisabled : Theme.statusConnected
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing2
                    Text {
                        Layout.fillWidth: true
                        text: rowDelegate.model.interface_name || ""
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeNormal
                        font.family: Theme.fontFamily
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: rowDelegate.model.ip_address
                              ? rowDelegate.model.ip_address + "  " + (rowDelegate.model.subnet_mask || "")
                              : "No IPv4 address"
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4
                        Repeater {
                            model: panel.referenceTables(rowDelegate.model)
                            delegate: StandardBadge {
                                required property string modelData
                                text: modelData
                            }
                        }
                    }
                }

                IconButton {
                    buttonSize: 28
                    iconSize: Theme.iconSizeNormal
                    iconSource: AppAssets.actionEdit
                    tooltip: "Edit interface"
                    onClicked: panel.editRequested(rowDelegate.index, rowDelegate.model)
                }
                IconButton {
                    buttonSize: 28
                    iconSize: Theme.iconSizeNormal
                    iconSource: AppAssets.actionDelete
                    danger: true
                    visible: rowDelegate.model.can_delete === true
                    tooltip: "Delete interface"
                    onClicked: panel.deleteRequested(rowDelegate.index, rowDelegate.model)
                }
            }

            TapHandler {
                acceptedButtons: Qt.LeftButton
                onTapped: panel.selected(rowDelegate.index, rowDelegate.model)
            }
            TapHandler {
                acceptedButtons: Qt.RightButton
                onTapped: function(eventPoint, button) {
                    panel.contextRequested(
                        rowDelegate.index,
                        rowDelegate.model,
                        eventPoint.scenePosition.x,
                        eventPoint.scenePosition.y
                    )
                }
            }
        }
    }
}
