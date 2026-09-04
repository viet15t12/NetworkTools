pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ── AclRuleInputDynamic ──────────────────────────────────────────────────────
// Box nhập thông tin rule cho Dynamic ACL.
// Gồm 2 phần:
//   1. Phần Extended (Protocol, Source, Destination) — tái sử dụng AclRuleInputExtended
//   2. Phần Dynamic-specific (Dynamic Name + Timeout)
// Được nhúng vào AclForm khi ACL type = "Dynamic".
// ─────────────────────────────────────────────────────────────────────────────
ColumnLayout {
    id: root

    // ── Properties alias trỏ vào Extended box bên trong ──
    property alias protocol:            extendedBox.protocol
    property alias sourceIp:            extendedBox.sourceIp
    property alias sourceWildcard:      extendedBox.sourceWildcard
    property alias sourcePort:          extendedBox.sourcePort
    property alias destinationIp:       extendedBox.destinationIp
    property alias destinationWildcard: extendedBox.destinationWildcard
    property alias destinationPort:     extendedBox.destinationPort

    // Cisco dynamic ACL syntax expresses the absolute timeout in minutes.
    // Persistence keeps the shared timeout_seconds column used by ACL rules.
    property alias dynamicName: dynamicNameField.text
    readonly property int timeout: timeoutSpinBox.value * 60

    // ── Signal thông báo dữ liệu thay đổi để AclForm theo dõi ──
    signal fieldChanged()

    // ── Hàm xóa sạch toàn bộ input sau khi Add Rule ──
    function clearFields() {
        extendedBox.clearFields()
        dynamicNameField.text = ""
        timeoutSpinBox.value  = 5
    }

    // ── Hàm tạo chuỗi tóm tắt cho cột Detail trong bảng Rules ──
    function buildDetail() {
        const extDetail = extendedBox.buildDetail()
        const dynName   = dynamicNameField.text.trim()
        const tout      = timeoutSpinBox.value

        let dynPart = dynName !== "" ? "  |  dynamic: " + dynName : ""
        dynPart += "  timeout: " + tout + "m"

        return extDetail + dynPart
    }

    function buildRule() {
        const rule = extendedBox.buildRule()
        rule.dynamic_name = dynamicNameField.text.trim()
        rule.timeout_seconds = timeoutSpinBox.value * 60
        return rule
    }

    spacing: 12

    // ── Phần 1: Extended box (tái sử dụng hoàn toàn) ─────────────────
    AclRuleInputExtended {
        id:               extendedBox
        Layout.fillWidth: true
        onFieldChanged:   root.fieldChanged()
    }

    // ── Phần 2: Dynamic-specific box ─────────────────────────────────
    Rectangle {
        Layout.fillWidth: true
        implicitHeight:   dynamicLayout.implicitHeight + 24
        radius:           Theme.cardRadius
        color:            Theme.contentSurface
        border.color:     Theme.borderColor
        border.width:     Theme.borderWidth

        ColumnLayout {
            id:              dynamicLayout
            anchors.fill:    parent
            anchors.margins: 12
            spacing:         12

            // ── Tiêu đề box ──────────────────────────────────────────
            Text {
                text:                "Dynamic Options"
                color:               Theme.textSecondary
                font.pixelSize:      Theme.fontSizeSmall
                font.family:         Theme.fontFamily
                font.bold:           true
                font.capitalization: Font.AllUppercase
            }

            Rectangle {
                Layout.fillWidth: true
                height:           Theme.borderWidth
                color:            Theme.borderColor
                opacity:          0.6
            }

            RowLayout {
                Layout.fillWidth: true
                spacing:          12

                // Dynamic Name
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing:          4

                    Text {
                        text:           "Dynamic Name"
                        color:          Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family:    Theme.fontFamily
                    }

                    StandardTextField {
                        id:               dynamicNameField
                        Layout.fillWidth: true
                        placeholderText:  "e.g., DYNAMIC_ACL"
                        onTextChanged:    root.fieldChanged()
                    }
                }

                StandardSpinBox {
                    id: timeoutSpinBox
                    Layout.preferredWidth: 180
                    labelText: "Timeout (Minutes)"
                    from: 1
                    to: 9999
                    value: 5
                    stepSize: 1
                    onValueChanged: root.fieldChanged()
                }
            }
        }
    }
}
