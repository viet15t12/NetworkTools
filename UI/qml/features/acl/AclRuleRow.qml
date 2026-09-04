pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ── AclRuleRow ───────────────────────────────────────────────────────────────
// Row hiển thị một rule trong bảng danh sách rules đang chờ lưu.
// Gồm 4 cột: Sequence | Action (badge màu) | Chi tiết rule | Nút Delete.
// Được dùng làm delegate trong ListView của AclForm.
// ─────────────────────────────────────────────────────────────────────────────
SavedListRow {
    id: ruleRow

    // ── Dữ liệu hiển thị được truyền từ delegate ngoài ──
    required property int    rowSequence
    required property string rowAction      // "Permit" hoặc "Deny"
    required property string rowDetail      // Chuỗi tóm tắt chi tiết rule
    required property string rowAclType     // Loại ACL để tô màu phân biệt nếu cần
    property bool allowDelete: true

    signal deleteClicked(int index)

    function displayAction(action) {
        return action === "Permit" ? "Permit" : "Deny"
    }

    Layout.fillWidth: true
    height: Theme.tableRowHeight

    RowLayout {
        anchors.fill:        parent
        spacing: Theme.spacing8

        // ── Cột 1: Sequence ──────────────────────────────────────────
        DataTableCell {
            Layout.preferredWidth: 44
            text:                  String(ruleRow.rowSequence)
            horizontalAlignment:   Text.AlignHCenter
        }

        // ── Cột 2: Action badge (Permit = xanh, Deny = đỏ) ──────────
        Rectangle {
            Layout.preferredWidth: 70
            Layout.preferredHeight: Theme.itemHeight - 8
            Layout.alignment:       Qt.AlignVCenter
            radius:                 Theme.borderRadius

            // ── Permit dùng statusConnected, Deny dùng alertError ──
            color: ruleRow.rowAction === "Permit"
                       ? Qt.rgba(
                             Qt.lighter(Theme.statusConnected, 1.0).r,
                             Qt.lighter(Theme.statusConnected, 1.0).g,
                             Qt.lighter(Theme.statusConnected, 1.0).b,
                             0.18
                         )
                       : Qt.rgba(
                             Theme.alertError.r,
                             Theme.alertError.g,
                             Theme.alertError.b,
                             0.18
                         )

            Text {
                anchors.centerIn: parent
                text:             ruleRow.displayAction(ruleRow.rowAction)
                color:            ruleRow.rowAction === "Permit"
                                      ? Theme.statusConnected
                                      : Theme.alertError
                font.pixelSize:   Theme.fontSizeSmall
                font.family:      Theme.fontFamily
                font.bold:        true
            }
        }

        // ── Cột 3: Chi tiết rule ─────────────────────────────────────
        DataTableCell {
            Layout.fillWidth:    true
            text:                ruleRow.rowDetail
            primary: true
        }

        // ── Cột 4: Nút Delete ────────────────────────────────────────
        IconButton {
            visible: ruleRow.allowDelete
            Layout.preferredWidth: 24
            Layout.preferredHeight: 24
            Layout.alignment: Qt.AlignVCenter
            buttonSize: 24
            glyph: "✕"
            danger: true
            tooltip: "Delete"
            onClicked: ruleRow.deleteClicked(ruleRow.rowIndex)
        }
    }

}
