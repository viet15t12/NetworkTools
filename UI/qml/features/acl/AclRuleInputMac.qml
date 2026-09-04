pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ── AclRuleInputMac ──────────────────────────────────────────────────────────
// Box nhập thông tin rule cho MAC ACL.
// MAC ACL lọc theo địa chỉ MAC nguồn, đích, mask và Ethertype.
// Khác với các loại ACL khác, MAC ACL hoạt động ở Layer 2 (Data Link).
// Được nhúng vào AclForm khi ACL type = "MAC".
// ─────────────────────────────────────────────────────────────────────────────
Rectangle {
    id: root

    // ── Properties alias để đọc giá trị từ bên ngoài ──
    property alias sourceMac:        sourceMacField.text
    property alias sourceMask:       sourceMaskField.text
    property alias destinationMac:   destinationMacField.text
    property alias destinationMask:  destinationMaskField.text
    property alias ethertype:        ethertypeField.text

    // ── Signal thông báo dữ liệu thay đổi để AclForm theo dõi ──
    signal fieldChanged()

    // ── Hàm xóa sạch toàn bộ input sau khi Add Rule ──
    function clearFields() {
        sourceMacField.text       = ""
        sourceMaskField.text      = ""
        destinationMacField.text  = ""
        destinationMaskField.text = ""
        ethertypeField.text       = ""
    }

    // ── Hàm tạo chuỗi tóm tắt cho cột Detail trong bảng Rules ──
    function buildDetail() {
        const srcMac  = sourceMacField.text.trim()
        const srcMask = sourceMaskField.text.trim()
        const dstMac  = destinationMacField.text.trim()
        const dstMask = destinationMaskField.text.trim()
        const ethType = ethertypeField.text.trim()

        // ── Ghép phần source ──
        let srcPart = srcMac !== "" ? srcMac : "any"
        if (srcMask !== "") srcPart += "/" + srcMask

        // ── Ghép phần destination ──
        let dstPart = dstMac !== "" ? dstMac : "any"
        if (dstMask !== "") dstPart += "/" + dstMask

        // ── Ghép phần ethertype ──
        const ethPart = ethType !== "" ? "  ethertype: " + ethType : ""

        return "MAC  " + srcPart + "  →  " + dstPart + ethPart
    }

    function buildRule() {
        return {
            src_mac: sourceMacField.text.trim(),
            src_mask: sourceMaskField.text.trim(),
            dst_mac: destinationMacField.text.trim(),
            dst_mask: destinationMaskField.text.trim(),
            ethertype: ethertypeField.text.trim()
        }
    }

    implicitHeight: macLayout.implicitHeight + 24
    radius:         Theme.cardRadius
    color:          Theme.contentSurface
    border.color:   Theme.borderColor
    border.width:   Theme.borderWidth

    ColumnLayout {
        id:              macLayout
        anchors.fill:    parent
        anchors.margins: 12
        spacing:         12

        // ── Tiêu đề Source ───────────────────────────────────────────
        Text {
            text:                "Source"
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

        // ── Hàng 1: Source MAC + Source Mask ─────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing:          12

            // Source MAC
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Source MAC"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardTextField {
                    id:               sourceMacField
                    Layout.fillWidth: true
                    placeholderText:  "e.g., 00:1A:2B:3C:4D:5E"
                    onTextChanged:    root.fieldChanged()
                }
            }

            // Source Mask
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Source Mask"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardTextField {
                    id:               sourceMaskField
                    Layout.fillWidth: true
                    placeholderText:  "e.g., FF:FF:FF:00:00:00"
                    onTextChanged:    root.fieldChanged()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height:           Theme.borderWidth
            color:            Theme.borderColor
            opacity:          0.6
        }

        // ── Tiêu đề Destination ──────────────────────────────────────
        Text {
            text:                "Destination"
            color:               Theme.textSecondary
            font.pixelSize:      Theme.fontSizeSmall
            font.family:         Theme.fontFamily
            font.bold:           true
            font.capitalization: Font.AllUppercase
        }

        // ── Hàng 2: Destination MAC + Destination Mask ───────────────
        RowLayout {
            Layout.fillWidth: true
            spacing:          12

            // Destination MAC
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Destination MAC"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardTextField {
                    id:               destinationMacField
                    Layout.fillWidth: true
                    placeholderText:  "e.g., FF:FF:FF:FF:FF:FF"
                    onTextChanged:    root.fieldChanged()
                }
            }

            // Destination Mask
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Destination Mask"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardTextField {
                    id:               destinationMaskField
                    Layout.fillWidth: true
                    placeholderText:  "e.g., FF:FF:FF:00:00:00"
                    onTextChanged:    root.fieldChanged()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height:           Theme.borderWidth
            color:            Theme.borderColor
            opacity:          0.6
        }

        // ── Hàng 3: Ethertype ────────────────────────────────────────
        ColumnLayout {
            Layout.preferredWidth: parent.width / 2 - 6
            spacing:               4

            Text {
                text:           "Ethertype"
                color:          Theme.textSecondary
                font.pixelSize: Theme.fontSizeSmall
                font.family:    Theme.fontFamily
            }

            StandardTextField {
                id:               ethertypeField
                Layout.fillWidth: true
                // ── Ethertype thường ở dạng hex, ví dụ 0x0800 = IPv4 ──
                placeholderText:  "e.g., 0x0800"
                onTextChanged:    root.fieldChanged()
            }
        }
    }
}
