pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

ColumnLayout {
    id: root
    spacing: Theme.spacing12

    required property var form

    component SectionTab: SegmentTab {
        minWidth: 92
        idleBorderColor: Theme.borderColor
    }

    GridLayout {
        visible: String(root.form.currentHostIp || "").trim() !== ""
        Layout.fillWidth: true
        Layout.leftMargin: 24
        Layout.rightMargin: 24
        Layout.topMargin: 6
        columns: width < 760 ? 2 : 4
        columnSpacing: Theme.spacing12
        rowSpacing: Theme.spacing12

        Repeater {
            model: [
                { label: "OSPF PROCESS", value: String(root.form.processCount), detail: "active cards", accent: false },
                { label: "NETWORKS", value: String(root.form.totalNetworkCount()), detail: "advertised entries", accent: true },
                { label: "HOST", value: root.form.currentHostIp, detail: "selected device", accent: false },
                { label: "STATE", value: root.form.hasPendingLocalChanges ? "DIRTY" : "SYNC", detail: root.form.hasPendingLocalChanges ? "pending save" : "database", state: true }
            ]

            delegate: Rectangle {
                required property var modelData

                Layout.fillWidth: true
                implicitHeight: 76
                radius: Theme.cardRadius
                color: modelData.state
                    ? (root.form.hasPendingLocalChanges ? Theme.alertWarningSubtle : Theme.alertSuccessSubtle)
                    : Theme.contentPanelSurface
                border.color: modelData.state
                    ? (root.form.hasPendingLocalChanges ? Theme.alertWarning : Theme.alertSuccess)
                    : Theme.contentPanelBorder
                border.width: Theme.borderWidth

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing2

                    Text {
                        text: modelData.label
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                        font.bold: true
                    }

                    Text {
                        Layout.fillWidth: true
                        text: modelData.value
                        color: modelData.state
                            ? (root.form.hasPendingLocalChanges ? Theme.alertWarning : Theme.alertSuccess)
                            : (modelData.accent ? Theme.accentColor : Theme.textPrimary)
                        font.pixelSize: Theme.fontSizeTitle
                        font.family: Theme.fontFamily
                        font.bold: true
                        elide: Text.ElideRight
                    }

                    Text {
                        text: modelData.detail
                        color: Theme.textDisabled
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                    }
                }
            }
        }
    }

    RowLayout {
        visible: String(root.form.currentHostIp || "").trim() !== ""
        Layout.fillWidth: true
        Layout.leftMargin: 24
        Layout.rightMargin: 24
        Layout.bottomMargin: Theme.spacing12
        spacing: Theme.spacing4

        SectionTab { label: "Process"; selected: root.form.activeRoutingSection === "Process"; onClicked: root.form.selectRoutingSection("Process") }
        SectionTab { label: "Networks"; selected: root.form.activeRoutingSection === "Networks"; onClicked: root.form.selectRoutingSection("Networks") }
        SectionTab { label: "Areas"; selected: root.form.activeRoutingSection === "Areas"; onClicked: root.form.selectRoutingSection("Areas") }
        SectionTab { label: "Distance"; selected: root.form.activeRoutingSection === "Distance"; onClicked: root.form.selectRoutingSection("Distance") }
        SectionTab { label: "Redistribute"; selected: root.form.activeRoutingSection === "Redistribute"; onClicked: root.form.selectRoutingSection("Redistribute") }
        SectionTab { label: "Interfaces"; selected: root.form.activeRoutingSection === "Interfaces"; onClicked: root.form.selectRoutingSection("Interfaces") }
        SectionTab { label: "Passive iface"; selected: root.form.activeRoutingSection === "Passive iface"; onClicked: root.form.selectRoutingSection("Passive iface") }
        SectionTab { label: "Tuning"; selected: root.form.activeRoutingSection === "Tuning"; onClicked: root.form.selectRoutingSection("Tuning") }
        Item { Layout.fillWidth: true }
        StandardButton {
            text: "Routing Group"
            type: "Primary"
            onClicked: root.form.routingGroupRequested("ospf")
        }
    }
}
