pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

ColumnLayout {
    id: root
    spacing: 4
    Layout.minimumWidth: Theme.inputMinimumWidth

    // ── Các properties mở rộng để tái sử dụng ──
    property string labelText: ""
    property color  contentColor: Theme.textPrimary
    property bool   contentBold: false
    property var optionColors: []
    property var optionBackgroundColors: []
    property string emptyText: "No options available"
    property string emptyWarningText: ""

    readonly property bool hasOptions: combo.count > 0

    // ── Alias xuống ComboBox bên trong ──
    property alias model: combo.model
    property alias currentIndex: combo.currentIndex
    property alias currentText: combo.currentText
    property alias displayText: combo.displayText
    property var valueModel: []
    readonly property string currentValue: (currentIndex >= 0 && valueModel && valueModel.length > currentIndex)
                                           ? String(valueModel[currentIndex])
                                           : currentText

    signal activated(int index)

    function optionColor(index) {
        return optionColors && index >= 0 && optionColors.length > index
                ? optionColors[index]
                : contentColor
    }

    function optionBackgroundColor(index) {
        return optionBackgroundColors && index >= 0 && optionBackgroundColors.length > index
                ? optionBackgroundColors[index]
                : "transparent"
    }

    function notifyEmptyOptions() {
        const fieldName = root.labelText !== "" ? root.labelText : "This dropdown"
        const message = root.emptyWarningText !== ""
                      ? root.emptyWarningText
                      : "%1 has no options yet. Add or load the required data before selecting from this dropdown.".arg(fieldName)
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, "warning")
    }

    // ── Label hiển thị tên trường (nếu có) ──
    Text {
        visible: root.labelText !== ""
        text: root.labelText
        color: Theme.textSecondary
        font.pixelSize: Theme.fontSizeSmall
        font.family: Theme.fontFamily
    }

    // ── ComboBox chính ──
    ComboBox {
        id: combo
        Layout.fillWidth: true
        implicitHeight: Theme.itemHeight
        enabled: root.enabled
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily

        onActivated: (index) => root.activated(index)

        background: Rectangle {
            color: root.hasOptions ? Theme.inputBackground : Theme.buttonDisabled
            border.color: root.hasOptions && (combo.activeFocus || combo.popup.visible) ? Theme.inputBorderFocusColor : Theme.inputBorderColor
            border.width: Theme.borderWidth
            radius: Theme.radiusSmall

        }

        indicator: Item {
            x: combo.mirrored ? Theme.spacing8 : combo.width - width - Theme.spacing8
            y: (combo.height - height) / 2
            width: 14
            height: 14
            opacity: root.hasOptions && combo.enabled ? (combo.hovered || combo.activeFocus || combo.popup.visible ? 0.68 : 0.42) : 0.24

            ThemedIcon {
                anchors.centerIn: parent
                iconSource: AppAssets.navigationChevronDown
                iconSize: Theme.iconSizeSmall
                iconColor: Theme.textPrimary
            }
        }

        // Tùy chỉnh vùng hiển thị chữ đang được chọn
        contentItem: Text {
            text: root.hasOptions ? combo.displayText : root.emptyText
            color: root.optionColor(combo.currentIndex)
            font.pixelSize: Theme.fontSizeNormal
            font.family: Theme.fontFamily
            font.bold: root.contentBold // Áp dụng in đậm
            verticalAlignment: Text.AlignVCenter
            leftPadding: 10
            rightPadding: 32
            opacity: root.hasOptions ? 1.0 : 0.62
        }

        // Tùy chỉnh từng item trong danh sách thả xuống
        delegate: ItemDelegate {
            id: del
            width: combo.width
            required property int index
            required property string modelData

            hoverEnabled: true

            contentItem: Text {
                text: modelData
                color: root.optionColor(del.index)
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
                font.bold: root.contentBold
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                // Sáng lên khi chuột di qua HOẶC khi dùng phím mũi tên
                color: del.hovered || del.highlighted
                       ? Theme.sideBarItemHover
                       : root.optionBackgroundColor(del.index)
                radius: Theme.borderRadius
            }
        }

        // Tùy chỉnh khung popup chứa danh sách
        popup: Popup {
            y: combo.height + 4
            width: combo.width
            // Đặt padding nhỏ để danh sách gọn gàng
            padding: 4

            // Quan trọng: Giới hạn chiều cao popup để hiển thị tối đa 5 item.
            // Nếu model ít hơn 5, nó sẽ tự động thu nhỏ lại nhờ tính toán của QML.
            // Số 36 là chiều cao ước tính của một item (dựa trên font size và padding).
            // Số 8 là bù trừ cho padding trên/dưới của popup (4 + 4).
            height: Math.min(contentItem.implicitHeight + 8, (36 * 5) + 8)

            contentItem: ListView {
                id: listview
                clip: true
                implicitHeight: contentHeight
                model: combo.popup.visible ? combo.delegateModel : null
                currentIndex: combo.highlightedIndex

                // Tối ưu scrollbar
                ScrollIndicator.vertical: ScrollIndicator {
                    active: true
                }
            }

            background: Rectangle {
                color: Theme.inputBackground
                border.color: Theme.inputBorderColor
                border.width: Theme.borderWidth
                radius: Theme.radiusSmall
            }
        }

        MouseArea {
            anchors.fill: parent
            z: 10
            visible: root.enabled && !root.hasOptions
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.ArrowCursor
            onClicked: root.notifyEmptyOptions()
        }
    }
}
