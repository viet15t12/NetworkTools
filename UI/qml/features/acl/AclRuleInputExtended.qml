pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ── AclRuleInputExtended ─────────────────────────────────────────────────────
// Box nhập thông tin rule cho Extended ACL.
// Extended ACL lọc theo Protocol, Source và Destination (IP, Wildcard, Port).
// Được nhúng vào AclForm khi ACL type = "Extended".
// Cũng được tái sử dụng bởi AclRuleInputDynamic và AclRuleInputReflexive
// thông qua property alias để lấy giá trị từ bên ngoài.
// ─────────────────────────────────────────────────────────────────────────────
Rectangle {
    id: root

    // ── Properties alias để đọc giá trị từ bên ngoài ──
    property alias protocol:          protocolCombo.currentText
    property alias sourceIp:          sourceIpField.text
    property alias sourceWildcard:    sourceWildcardField.text
    property alias sourcePort:        sourcePortField.text
    property alias destinationIp:     destinationIpField.text
    property alias destinationWildcard: destinationWildcardField.text
    property alias destinationPort:   destinationPortField.text

    // ── Signal thông báo dữ liệu thay đổi để form cha theo dõi ──
    signal fieldChanged()

    // ── Hàm xóa sạch toàn bộ input sau khi Add Rule ──
    function clearFields() {
        protocolCombo.currentIndex      = 0
        sourceIpField.text              = ""
        sourceWildcardField.text        = ""
        sourcePortField.text            = ""
        destinationIpField.text         = ""
        destinationWildcardField.text   = ""
        destinationPortField.text       = ""
    }

    // ── Hàm tạo chuỗi tóm tắt cho cột Detail trong bảng Rules ──
    function buildDetail() {
        const proto   = protocolCombo.currentText
        const srcIp   = sourceIpField.text.trim()
        const srcWild = sourceWildcardField.text.trim()
        const srcPort = sourcePortField.text.trim()
        const dstIp   = destinationIpField.text.trim()
        const dstWild = destinationWildcardField.text.trim()
        const dstPort = destinationPortField.text.trim()

        // ── Ghép phần source ──
        let srcPart = srcIp !== "" ? srcIp : "any"
        if (srcWild !== "")  srcPart += "/" + srcWild
        if (srcPort !== "")  srcPart += ":" + srcPort

        // ── Ghép phần destination ──
        let dstPart = dstIp !== "" ? dstIp : "any"
        if (dstWild !== "")  dstPart += "/" + dstWild
        if (dstPort !== "")  dstPart += ":" + dstPort

        return proto + "  " + srcPart + "  →  " + dstPart
    }

    function buildRule() {
        return {
            protocol: protocolCombo.currentText.toLowerCase(),
            source: sourceIpField.text.trim(),
            src_wildcard: sourceWildcardField.text.trim(),
            src_port: sourcePortField.text.trim(),
            destination: destinationIpField.text.trim(),
            dst_wildcard: destinationWildcardField.text.trim(),
            dst_port: destinationPortField.text.trim()
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

        // ── Hàng 1: Protocol ─────────────────────────────────────────
        StandardComboBox {
            id:               protocolCombo
            Layout.fillWidth: true
            labelText:        "Protocol"
            model:            ["IP", "TCP", "UDP", "ICMP"]

            onCurrentIndexChanged: root.fieldChanged()
        }

        Rectangle {
            Layout.fillWidth: true
            height:           Theme.borderWidth
            color:            Theme.borderColor
            opacity:          0.6
        }

        // ── Hàng 2: Source IP + Wildcard + Port ──────────────────────
        Text {
            text:           "Source"
            color:          Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family:    Theme.fontFamily
            font.bold:      true
            font.capitalization: Font.AllUppercase
        }

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
                    placeholderText:  "e.g., 10.0.0.0"
                    onTextChanged:    root.fieldChanged()
                }
            }

            // Source Wildcard
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Source Wildcard"
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

            // Source Port
            ColumnLayout {
                Layout.preferredWidth: 100
                spacing:               4

                Text {
                    text:           "Source Port"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardTextField {
                    id:               sourcePortField
                    Layout.fillWidth: true
                    placeholderText:  "e.g., 80"
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

        // ── Hàng 3: Destination IP + Wildcard + Port ─────────────────
        Text {
            text:           "Destination"
            color:          Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family:    Theme.fontFamily
            font.bold:      true
            font.capitalization: Font.AllUppercase
        }

        RowLayout {
            Layout.fillWidth: true
            spacing:          12

            // Destination IP
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Destination IP"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardNetworkField {
                    id:               destinationIpField
                    inputKind:        "ipv4"
                    Layout.fillWidth: true
                    placeholderText:  "e.g., 192.168.1.0"
                    onTextChanged:    root.fieldChanged()
                }
            }

            // Destination Wildcard
            ColumnLayout {
                Layout.fillWidth: true
                spacing:          4

                Text {
                    text:           "Destination Wildcard"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardNetworkField {
                    id:               destinationWildcardField
                    inputKind:        "wildcard"
                    Layout.fillWidth: true
                    placeholderText:  "e.g., 0.0.0.255 or -/24"
                    onTextChanged:    root.fieldChanged()
                }
            }

            // Destination Port
            ColumnLayout {
                Layout.preferredWidth: 100
                spacing:               4

                Text {
                    text:           "Destination Port"
                    color:          Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSmall
                    font.family:    Theme.fontFamily
                }

                StandardTextField {
                    id:               destinationPortField
                    Layout.fillWidth: true
                    placeholderText:  "e.g., 443"
                    onTextChanged:    root.fieldChanged()
                }
            }
        }
    }
}
