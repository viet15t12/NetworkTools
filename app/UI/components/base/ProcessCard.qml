pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ProcessCard — card dùng chung cho OSPF và EIGRP (F4 — Process Workspace).
// Đây là component process-card duy nhất; alias BaseCard cũ đã được loại bỏ.
// Các protocol tùy chỉnh thông qua properties và slots bên dưới.
Item {
    id: processCard

    // ── Properties cơ bản ────────────────────────────────────────────
    property int    processIndex: 0
    property bool   showArea: true   // OSPF: true | EIGRP: false
    property bool   showAd: false
    property string processIdLabel: "Process ID"
    property string processIdPlaceholder: "e.g., 1"
    property string helpTitle: "Routing process parameters"
    property string helpText: ""
    property string activeSection: "Process"
    property bool showSectionTabs: true

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    // ── Slot để inject UI tùy chỉnh (checkboxes) ─────────────────────
    // Dùng default property để nhúng component con vào vùng checkbox
    default property alias extraControls: extraControlsContainer.data

    signal removeRequested()

    // ── Expose model và fields ra ngoài để subclass đọc nếu cần ──────
    property alias processId: processIdField.text
    property alias routerId:  routerIdField.text
    property alias ad:        adField.text
    property alias networks:  networkModel

    Layout.fillWidth: true
    implicitHeight:   cardInner.implicitHeight + 24

    ListModel { id: networkModel }

    Rectangle {
        anchors.fill:  parent
        radius:        Theme.cardRadius
        color:         Theme.contentPanelSurface
        border.color:  Theme.contentPanelBorder
        border.width:  Theme.borderWidth

        ColumnLayout {
            id:              cardInner
            anchors.left:    parent.left
            anchors.right:   parent.right
            anchors.top:     parent.top
            anchors.margins: 12
            spacing:         12

            // ── Header ──────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true

                Text {
                    text:           "Process " + processCard.processIndex
                    color:          Theme.textPrimary
                    font.pixelSize: Theme.fontSizeNormal
                    font.family:    Theme.fontFamily
                    font.bold:      true
                }

                ParameterHelpButton {
                    Layout.preferredWidth: 22
                    Layout.preferredHeight: 22
                    visible: processCard.helpText.trim() !== ""
                    helpTitle: processCard.helpTitle
                    helpText: processCard.helpText
                }

                Item { Layout.fillWidth: true }

                IconButton {
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                    buttonSize: 24
                    glyph: "✕"
                    danger: true
                    tooltip: "Remove this process"
                    onClicked: processCard.removeRequested()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height:           Theme.borderWidth
                color:            Theme.contentPanelBorder
                opacity:          0.6
            }

            // ── Segmented sections ───────────────────────────────────
            RowLayout {
                visible: processCard.showSectionTabs
                Layout.fillWidth: true
                spacing: Theme.spacing4

                SegmentTab {
                    label: "Process"
                    selected: processCard.activeSection === "Process"
                    minWidth: 96
                    idleBorderColor: Theme.contentPanelBorder
                    selectedTextColor: Theme.textPrimary
                    onClicked: processCard.activeSection = "Process"
                }

                SegmentTab {
                    label: "Networks"
                    selected: processCard.activeSection === "Networks"
                    minWidth: 100
                    idleBorderColor: Theme.contentPanelBorder
                    selectedTextColor: Theme.textPrimary
                    onClicked: processCard.activeSection = "Networks"
                }

                Item { Layout.fillWidth: true }
            }

            // ── Process ──────────────────────────────────────────────
            ColumnLayout {
                visible: processCard.activeSection === "Process"
                Layout.fillWidth: true
                spacing: Theme.spacing12

                GridLayout {
                    Layout.fillWidth: true
                    columns: width < 520 ? 1 : 2
                    columnSpacing: Theme.spacing12
                    rowSpacing: Theme.spacing8

                    StandardTextField {
                        id: processIdField
                        Layout.fillWidth: true
                        labelText: processCard.processIdLabel
                        placeholderText: processCard.processIdPlaceholder
                    }

                    StandardTextField {
                        id: routerIdField
                        Layout.fillWidth: true
                        labelText: "Router ID"
                        placeholderText: "e.g., 1.1.1.1"
                    }
                }

                // Vùng inject checkbox từ OspfProcessCard / EigrpProcessCard
                ColumnLayout {
                    id: extraControlsContainer
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                }

                ColumnLayout {
                    visible: processCard.showAd
                    Layout.preferredWidth: 120
                    spacing:               4

                    Text {
                        text:           "AD"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }

                    StandardTextField {
                        id:               adField
                        Layout.fillWidth: true
                        placeholderText:  "1-255"
                    }
                }
            }

            // ── Networks ─────────────────────────────────────────────
            ColumnLayout {
                visible: processCard.activeSection === "Networks"
                Layout.fillWidth: true
                spacing:          8

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        text:                "NETWORKS"
                        color:               Theme.textSecondary
                        font.pixelSize:      Theme.fontSizeSmall
                        font.family:         Theme.fontFamily
                        font.bold:           true
                        font.capitalization: Font.AllUppercase
                    }

                    Item { Layout.fillWidth: true }

                    StandardButton {
                        text: "+ Add Network"
                        type: "Primary"
                        onClicked: {
                            networkModel.append({ network: "", wildcard: "", area: "" })
                            processCard.notify("Added a network row to Process " + processCard.processIndex + ".", "info")
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: networkTableLayout.implicitHeight
                    radius: Theme.radiusSmall
                    color: "transparent"
                    border.color: Theme.contentPanelBorder
                    border.width: Theme.borderWidth

                    ColumnLayout {
                        id: networkTableLayout
                        width: parent.width
                        spacing: 0

                        Rectangle {
                            Layout.fillWidth: true
                            height: 34
                            color: "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacing12
                                anchors.rightMargin: Theme.spacing12
                                spacing: Theme.spacing8

                                Text {
                                    Layout.fillWidth: true
                                    text: "NETWORK"
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    font.bold: true
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "WILDCARD"
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    font.bold: true
                                }

                                Text {
                                    Layout.preferredWidth: 88
                                    visible: processCard.showArea
                                    text: "AREA"
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeSmall
                                    font.family: Theme.fontFamily
                                    font.bold: true
                                }

                                Text {
                                    Layout.preferredWidth: 34
                                    text: ""
                                }
                            }

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: Theme.borderWidth
                                color: Theme.contentPanelBorder
                            }
                        }

                        Text {
                            visible:             networkModel.count === 0
                            Layout.fillWidth: true
                            text:                "No network rows. Use Add Network to create one."
                            color:               Theme.textDisabled
                            font.pixelSize:      Theme.fontSizeNormal
                            font.family:         Theme.fontFamily
                            horizontalAlignment: Text.AlignHCenter
                            topPadding:          Theme.spacing16
                            bottomPadding:       Theme.spacing16
                        }

                        // ── Network rows ──────────────────────────────
                        Repeater {
                            model: networkModel

                            delegate: SavedListRow {
                                id: networkRow
                                width: networkTableLayout.width
                                height: 44
                                zebra: false

                                required property string network
                                required property string wildcard
                                required property string area
                                required property int index

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacing12
                                    anchors.rightMargin: Theme.spacing12
                                    spacing: Theme.spacing8

                                    StandardTextField {
                                        id: netField
                                        Layout.fillWidth: true
                                        placeholderText: "10.0.0.0"
                                        Component.onCompleted: text = networkRow.network

                                        onTextEdited: function(value) {
                                            if (networkRow.network !== value) {
                                                networkModel.setProperty(networkRow.index, "network", value)
                                            }
                                        }

                                        onEditingFinished: {
                                            if (networkRow.network !== text) {
                                                networkModel.setProperty(networkRow.index, "network", text)
                                            }
                                        }
                                    }

                                    StandardTextField {
                                        id: wildcardField
                                        Layout.fillWidth: true
                                        placeholderText: "0.0.0.255"

                                        Component.onCompleted: text = networkRow.wildcard
                                        onTextEdited: function(value) {
                                            if (networkRow.wildcard !== value) {
                                                networkModel.setProperty(networkRow.index, "wildcard", value)
                                            }
                                        }

                                        onEditingFinished: {
                                            if (networkRow.wildcard !== text) {
                                                networkModel.setProperty(networkRow.index, "wildcard", text)
                                            }
                                        }
                                    }

                                    StandardTextField {
                                        id: areaField
                                        Layout.preferredWidth: 88
                                        visible: processCard.showArea
                                        placeholderText: "0"

                                        Component.onCompleted: text = networkRow.area
                                        onTextEdited: function(value) {
                                            if (networkRow.area !== value) {
                                                networkModel.setProperty(networkRow.index, "area", value)
                                            }
                                        }

                                        onEditingFinished: {
                                            if (networkRow.area !== text) {
                                                networkModel.setProperty(networkRow.index, "area", text)
                                            }
                                        }
                                    }

                                    IconButton {
                                        Layout.preferredWidth: 28
                                        Layout.preferredHeight: 28
                                        buttonSize: 28
                                        iconSize: 12
                                        iconSource: AppAssets.actionClose
                                        danger: true
                                        tooltip: "Remove network"
                                        onClicked: {
                                            networkModel.remove(networkRow.index)
                                            processCard.notify("Removed a network row from Process " + processCard.processIndex + ".", "warning")
                                        }
                                    }
                                }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: Theme.borderWidth
                                    color: Theme.contentPanelBorder
                                    opacity: 0.6
                                }
                            }
                        }
                    }
                }
            }

            Item { height: 4 }
        }
    }
}
