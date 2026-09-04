pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ── FormLayout ───────────────────────────────────────────────────────────────
// Cấu trúc chuẩn cho toàn bộ các Form cấu hình (Routing, ACL, DHCP, v.v.)
// Tự động lo việc dàn trang Header, ScrollView (Body) và Footer.
// ─────────────────────────────────────────────────────────────────────────────
Rectangle {
    id: root
    color: Theme.contentBackground

    // ── Public API ──
    property string title: "Form Title"
    property string hostIp: ""
    property bool isDirty: false
    property string errorMessage: ""
    property bool showHeader: true

    // ── Slots để "thả" component từ bên ngoài vào ──
    default property alias content: scrollLayout.data
    property alias pinnedContent: pinnedLayout.data
    property alias footer: footerLayout.data

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── 1. HEADER (TOP BAR) ──────────────────────────────────────────────
        Rectangle {
            visible: root.showHeader
            Layout.fillWidth: true
            color: Theme.contentSurface
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Layout.topMargin: 12
            Layout.bottomMargin: 12
            radius: 6
            border.color: Theme.borderColor
            border.width: Theme.borderWidth
            implicitHeight: topBarLayout.implicitHeight + 16

            RowLayout {
                id: topBarLayout
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8

                Text {
                    text: root.title
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeLarge
                    font.family: Theme.fontFamily
                    font.bold: true
                }

                Rectangle {
                    radius: 10
                    color: Theme.sideBarItemHover
                    implicitHeight: hostText.implicitHeight + 6
                    implicitWidth: hostText.implicitWidth + 14
                    visible: root.hostIp !== ""

                    Text {
                        id: hostText
                        anchors.centerIn: parent
                        text: root.hostIp !== "" ? "Host: %1".arg(root.hostIp) : "Host: (none)"
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                    }
                }

                StandardBadge {
                    text: root.isDirty ? "Unsaved changes" : ""
                    badgeColor: Theme.badgeWarningBg
                    textColor: Theme.badgeWarningText
                }

                Item { Layout.fillWidth: true }

                Text {
                    visible: root.errorMessage !== ""
                    text: root.errorMessage
                    color: Theme.alertError
                    font.pixelSize: Theme.fontSizeSmall
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                    Layout.preferredWidth: 260
                }
            }
        }

        ColumnLayout {
            id: pinnedLayout
            Layout.fillWidth: true
            spacing: 12
            visible: children.length > 0
        }

        // ── 2. BODY (SCROLLABLE CONTENT) ─────────────────────────────────────
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            ColumnLayout {
                id: scrollLayout
                width: parent.width
                spacing: 12
                // Các Form Inputs sẽ tự động rớt vào đây
            }
        }

        // ── 3. PHÂN CÁCH FOOTER ──────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: Theme.borderWidth
            color: Theme.borderColor
        }

        // ── 4. FOOTER (ACTION BUTTONS) ───────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 56
            color: Theme.contentSurface

            RowLayout {
                id: footerLayout
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                anchors.topMargin: 10
                anchors.bottomMargin: 10
                spacing: 8
                // Các Nút bấm (Save, Cancel) sẽ rớt vào đây
            }
        }
    }
}
