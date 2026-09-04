pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ── AclRuleInputStandard ─────────────────────────────────────────────────────
// Box nhập thông tin rule cho Standard ACL.
// Standard ACL chỉ lọc theo Source IP và Wildcard mask.
// Được nhúng vào AclForm khi ACL type = "Standard".
// ─────────────────────────────────────────────────────────────────────────────
Rectangle {
    id: root

    // ── Properties đọc từ bên ngoài để lấy giá trị hiện tại ──
    property alias sourceIp:       sourceIpField.text
    property alias sourceWildcard: sourceWildcardField.text

    // ── Signal thông báo dữ liệu thay đổi để AclForm theo dõi ──
    signal fieldChanged()

    // ── Hàm xóa sạch toàn bộ input sau khi Add Rule ──
    function clearFields() {
        sourceIpField.text       = ""
        sourceWildcardField.text = ""
    }

    // ── Hàm tạo chuỗi tóm tắt cho cột Detail trong bảng Rules ──
    function buildDetail() {
        const src  = sourceIpField.text.trim()
        const wild = sourceWildcardField.text.trim()

        if (src === "" && wild === "")
            return "(empty)"

        const wildcardPart = wild !== "" ? " / " + wild : ""
        return "src: " + src + wildcardPart
    }

    function buildRule() {
        return {
            source: sourceIpField.text.trim(),
            wildcard: sourceWildcardField.text.trim()
        }
    }

    implicitHeight: inputLayout.implicitHeight + 24
    radius:         Theme.cardRadius
    color:          Theme.contentSurface
    border.color:   Theme.borderColor
    border.width:   Theme.borderWidth

    ColumnLayout {
        id:              inputLayout
        anchors.fill:    parent
        anchors.margins: 12
        spacing:         12

        // ── Tiêu đề box ──────────────────────────────────────────────
        Text {
            text:           "Source"
            color:          Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family:    Theme.fontFamily
            font.bold:      true
            font.capitalization: Font.AllUppercase
        }

        Rectangle {
            Layout.fillWidth: true
            height:           Theme.borderWidth
            color:            Theme.borderColor
            opacity:          0.6
        }

        // ── Hàng nhập Source IP + Wildcard ───────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing:          12

            // Source IP
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Source IP"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardNetworkField {
                    id:               sourceIpField
                    inputKind:        "ipv4"
                    Layout.fillWidth: true
                    placeholderText:  "e.g., 192.168.1.0"
                    onTextChanged:    root.fieldChanged()
                }
            }

            // Wildcard Mask
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Wildcard"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardNetworkField {
                    id:               sourceWildcardField
                    inputKind:        "wildcard"
                    Layout.fillWidth: true
                    placeholderText:  "e.g., 0.0.0.255 or -/24"
                    onTextChanged:    root.fieldChanged()
                }
            }
        }
    }
}
