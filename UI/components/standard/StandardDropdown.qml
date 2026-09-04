pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: standardDropdown

    property var activeStatusFilters: []
    property var activeTypeFilters: []

    signal filtersChanged()

    visible: false
    width: 200
    color: Theme.panelSideBarSurface
    border.color: Theme.panelSideBarBorderColor
    border.width: Theme.borderWidth
    radius: 4

    // Tính height tự động theo nội dung
    height: filterColumn.implicitHeight + 16

    function toggle() { visible = !visible }

    Column {
        id: filterColumn
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 8
        spacing: 4

        // ── Lọc theo trạng thái ──
        Text {
            text: "STATUS"
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            font.weight: Font.Medium
            color: Theme.panelSideBarTextSecondary
            topPadding: 4
        }

        Repeater {
            model: [
                { label: "Connected",    value: "connected",    color: Theme.statusConnected    },
                { label: "Waiting",      value: "waiting",      color: Theme.statusWaiting      },
                { label: "Disconnected", value: "disconnected", color: Theme.statusDisconnected }
            ]

            delegate: Rectangle {
                required property var modelData

                width: parent.width
                height: 30
                radius: 4
                color: filterItemHover.hovered ? Theme.panelSideBarItemHover : "transparent"

                property bool isChecked: standardDropdown.activeStatusFilters.indexOf(modelData.value) !== -1

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    spacing: 8

                    // Checkbox
                    StandardCheckBox {
                        anchors.verticalCenter: parent.verticalCenter
                        checked: isChecked
                        checkedColor: Theme.panelSideBarAccentColor
                        uncheckedColor: Theme.panelSideBarSearchBackground2
                        focusBorderColor: Theme.panelSideBarAccentColor
                        idleBorderColor: Theme.panelSideBarInputBorderColor
                        textColor: Theme.panelSideBarTextPrimary
                        disabledTextColor: Theme.panelSideBarTextDisabled
                        // Không truyền text để giữ nguyên layout Row có sẵn chấm màu
                    }

                    // Status dot
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        anchors.verticalCenter: parent.verticalCenter
                        color: modelData.color
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.label
                        font.pixelSize: Theme.fontSizeNormal
                        font.family: Theme.fontFamily
                        color: Theme.panelSideBarTextPrimary
                    }
                }

                HoverHandler { id: filterItemHover }
                TapHandler {
                    onTapped: {
                        const filters = standardDropdown.activeStatusFilters.slice()
                        const idx = filters.indexOf(modelData.value)
                        if (idx === -1) filters.push(modelData.value)
                        else filters.splice(idx, 1)
                        standardDropdown.activeStatusFilters = filters
                        standardDropdown.filtersChanged()
                    }
                }
            }
        }

        // Divider
        Rectangle {
            width: parent.width
            height: Theme.borderWidth
            color: Theme.panelSideBarBorderColor
        }

        // ── Lọc theo loại thiết bị ──
        Text {
            text: "DEVICE TYPE"
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            font.weight: Font.Medium
            color: Theme.panelSideBarTextSecondary
            topPadding: 4
        }

        Repeater {
            model: [
                { label: "Router",       value: "Router"       },
                { label: "Switch",       value: "Switch"       },
                { label: "Access Point", value: "Access Point" },
                { label: "Firewall",     value: "Firewall"     },
                { label: "Server",       value: "Server"       }
            ]

            delegate: Rectangle {
                required property var modelData

                width: parent.width
                height: 30
                radius: 4
                color: typeItemHover.hovered ? Theme.panelSideBarItemHover : "transparent"

                property bool isChecked: standardDropdown.activeTypeFilters.indexOf(modelData.value) !== -1

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    spacing: 8

                    StandardCheckBox {
                        anchors.verticalCenter: parent.verticalCenter
                        checked: isChecked
                        checkedColor: Theme.panelSideBarAccentColor
                        uncheckedColor: Theme.panelSideBarSearchBackground2
                        focusBorderColor: Theme.panelSideBarAccentColor
                        idleBorderColor: Theme.panelSideBarInputBorderColor
                        textColor: Theme.panelSideBarTextPrimary
                        disabledTextColor: Theme.panelSideBarTextDisabled
                        // Không truyền text vì chữ modelData đã có riêng ở bên dưới
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.label
                        font.pixelSize: Theme.fontSizeNormal
                        font.family: Theme.fontFamily
                        color: Theme.panelSideBarTextPrimary
                    }
                }

                HoverHandler { id: typeItemHover }
                TapHandler {
                    onTapped: {
                        var filters = standardDropdown.activeTypeFilters.slice()
                        var idx = filters.indexOf(modelData.value)
                        if (idx === -1) filters.push(modelData.value)
                        else filters.splice(idx, 1)
                        standardDropdown.activeTypeFilters = filters
                        standardDropdown.filtersChanged()
                    }
                }
            }
        }
    }
}
