pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ─────────────────────────────────────────────────────────────────────────────
// StandardButton
// Button chuẩn của ứng dụng.
// Hỗ trợ 7 types:
// - "Primary": Nút chính (màu xanh accent).
// - "Secondary": Nút phụ (nền xám/outline).
// - "Danger": Nút cảnh báo (màu đỏ).
// - "Ghost": Nút trong suốt, chỉ hiện nền khi hover.
// - "Icon": Nút vuông, chỉ hiển thị icon (MỚI THÊM).
// - "Text": Nút chữ không nền/khung; dùng cho action phụ như Cancel Changes.
// - "TextIcon": Nút chữ kèm semantic icon; dùng cho disclosure/link action.
// ─────────────────────────────────────────────────────────────────────────────
Button {
    id: root

    // ── Public API ───────────────────────────────────────────────────────────
    property string type:       "Secondary" // Primary | Secondary | Danger | Ghost | Icon | Text | TextIcon
    property string tooltip:    ""
    property bool autoCompact:  true

    readonly property bool hasIcon: icon.source.toString() !== ""
    readonly property real expandedContentWidth:
        (hasIcon ? Theme.iconSizeNormal : 0)
        + (hasIcon && text !== "" ? Theme.spacing8 : 0)
        + (text !== "" ? buttonTextMetrics.advanceWidth : 0)
    readonly property real expandedImplicitWidth: type === "Icon"
        ? implicitHeight
        : Math.ceil(Math.max(80, expandedContentWidth + leftPadding + rightPadding))
    readonly property bool compactContent: autoCompact
        && type !== "Icon" && hasIcon && text !== ""
        && width > 0 && width + 0.5 < expandedImplicitWidth
    readonly property real minimumUsableWidth:
        type === "Icon" || (autoCompact && hasIcon) ? implicitHeight : 80

    // UI-P2-01: Standard controls are the lowest-cost place to establish an
    // accessibility contract for every feature that consumes them.
    Accessible.role: Accessible.Button
    Accessible.name: text !== "" ? text : tooltip
    Accessible.description: tooltip !== "" ? tooltip : text
    focusPolicy: Qt.StrongFocus
    Layout.minimumWidth: minimumUsableWidth

    // Lưu ý: Icon truyền qua property `icon.source` mặc định của Button.
    // Text truyền qua property `text` mặc định của Button.

    // ── Kích thước ───────────────────────────────────────────────────────────
    implicitHeight: 34

    // Xử lý kích thước đặc biệt cho type "Icon" (ép thành hình vuông)
    implicitWidth: type === "Icon"
        ? implicitHeight
        : expandedImplicitWidth

    TextMetrics {
        id: buttonTextMetrics
        text: root.text
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily
        font.bold: root.type === "Primary" || root.type === "Danger"
    }

    leftPadding:  type === "Icon" ? 0 : ((type === "Text" || type === "TextIcon") ? Theme.spacing8 : Theme.spacing16)
    rightPadding: type === "Icon" ? 0 : ((type === "Text" || type === "TextIcon") ? Theme.spacing8 : Theme.spacing16)

    // ── Interaction ──────────────────────────────────────────────────────────
    HoverHandler {
        id: hoverHandler
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    // ── Styling Helper ───────────────────────────────────────────────────────
    readonly property bool _selected: root.checkable && root.checked

    property color _textColor: {
        if (!root.enabled) return Theme.textDisabled
        if (root.type === "Primary" || root.type === "Danger") return Theme.buttonTextSolid
        if (root.type === "Text") return Theme.textPrimary
        if (root.type === "TextIcon") {
            return hoverHandler.hovered || root.visualFocus ? Theme.textPrimary : Theme.textSecondary
        }
        if (root._selected) return Theme.textPrimary
        if (root.type === "Secondary" || root.type === "Ghost" || root.type === "Icon") {
            return hoverHandler.hovered ? Theme.textPrimary : Theme.textSecondary
        }
        return Theme.textPrimary
    }

    icon.color: _textColor

    // ── Background ───────────────────────────────────────────────────────────
    background: Rectangle {
        objectName: root.objectName !== "" ? root.objectName + "Background" : ""
        radius: Theme.radiusSmall

        color: {
            if (root.type === "Text" || root.type === "TextIcon") return "transparent"
            if (!root.enabled) return Theme.sideBarBackground
            if (root._selected) return Theme.sideBarItemSelected

            if (root.type === "Primary") {
                return hoverHandler.hovered ? Qt.lighter(Theme.accentEmphasis, 1.15) : Theme.accentEmphasis
            }
            if (root.type === "Danger") {
                return hoverHandler.hovered ? Qt.lighter(Theme.alertError, 1.15) : Theme.alertError
            }
            if (root.type === "Ghost" || root.type === "Icon") {
                return hoverHandler.hovered ? Theme.sideBarItemHover : "transparent"
            }
            // Secondary
            return hoverHandler.hovered ? Theme.sideBarItemHover : "transparent"
        }

        border.color: {
            if (root.visualFocus) return Theme.accentColor
            if (root.type === "Text" || root.type === "TextIcon") return "transparent"
            if (!root.enabled) return Theme.inputBorderColor
            if (root._selected) return Theme.accentColor
            if (root.type === "Secondary") {
                return hoverHandler.hovered ? Theme.textSecondary : Theme.borderColor
            }
            return "transparent"
        }
        border.width: (root.visualFocus || !root.enabled || root.type === "Secondary" || root._selected)
                         ? Theme.borderWidth
                         : 0

        // ── Focus Ring ────────────────────────────────────────────────────────
        Rectangle {
            anchors.fill: parent
            anchors.margins: -4
            radius: parent.radius + 2
            color: "transparent"
            border.color: Theme.accentColor
            border.width: 2
            visible: opacity > 0
            opacity: root.visualFocus ? 0.8 : 0.0
            scale: root.visualFocus ? 1.0 : 0.8

            Behavior on opacity {
                NumberAnimation { duration: 150 }
            }

            SequentialAnimation on scale {
                running: root.visualFocus
                loops: Animation.Infinite
                NumberAnimation { to: 1.05; duration: 800; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.98; duration: 800; easing.type: Easing.InOutSine }
            }
        }

    }

    // ── Content ──────────────────────────────────────────────────────────────
    contentItem: Item {
        implicitWidth: root.type === "Icon" ? Theme.iconSizeNormal : standardContent.implicitWidth
        implicitHeight: Math.max(Theme.iconSizeNormal, standardContent.implicitHeight)

        // Icon-only buttons need an anchored item. A RowLayout packs its only
        // child at the leading edge, which made toolbar icons look off-center.
        ThemedIcon {
            id: iconOnlyContent
            objectName: root.objectName !== "" ? root.objectName + "Icon" : ""
            visible: root.type === "Icon" && root.icon.source.toString() !== ""
            anchors.centerIn: parent
            iconSource: root.icon.source
            iconSize: Theme.iconSizeNormal
            iconColor: root._textColor
        }

        RowLayout {
            id: standardContent
            visible: root.type !== "Icon"
            anchors.centerIn: parent
            width: Math.min(implicitWidth, parent.width)
            implicitWidth: root.compactContent
                           ? Theme.iconSizeNormal
                           : root.expandedContentWidth
            spacing: Theme.spacing8

            ThemedIcon {
                visible: root.hasIcon
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredWidth: Theme.iconSizeNormal
                Layout.preferredHeight: Theme.iconSizeNormal
                iconSource: root.icon.source
                iconSize: Theme.iconSizeNormal
                iconColor: root._textColor
            }

            Text {
                id: standardLabel
                objectName: root.objectName !== "" ? root.objectName + "Label" : ""
                visible: root.text !== "" && !root.compactContent
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.text
                color: root._textColor
                font.pixelSize: Theme.fontSizeNormal
                font.family: Theme.fontFamily
                font.bold: root.type === "Primary" || root.type === "Danger"
                font.underline: root.type === "Text" && (hoverHandler.hovered || root.visualFocus)
                Layout.alignment: Qt.AlignVCenter
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
        }
    }

    // ── Tooltip ──────────────────────────────────────────────────────────────
    ToolTip {
        visible: (root.tooltip !== "" || root.compactContent) && hoverHandler.hovered
        text: root.tooltip !== "" ? root.tooltip : root.text
        delay: 400
    }
}
