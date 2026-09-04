pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// ─────────────────────────────────────────────────────────────────────────────
// StandardTextField
// Input field chuẩn của toàn bộ ứng dụng.
//
// Khi dùng standalone (không có label):
//   StandardTextField {
//       placeholderText: "e.g., 192.168.1.1"
//   }
//
// Khi dùng có label (đồng bộ với StandardComboBox / StandardSpinBox):
//   StandardTextField {
//       labelText: "Network"
//       placeholderText: "e.g., 10.0.0.0"
//   }
//
// Khi labelText rỗng (default), component hoạt động y hệt TextField thuần —
// không có thêm wrapper nào, không thay đổi implicitHeight.
// ─────────────────────────────────────────────────────────────────────────────

// Dùng ColumnLayout làm root khi có label, giống StandardComboBox/StandardSpinBox.
// Khi không có label, ColumnLayout chỉ có 1 child nên hành vi giống TextField thuần.

ColumnLayout {
    id: root
    spacing: Theme.spacing4
    Layout.minimumWidth: Theme.inputMinimumWidth

    // ── Public API ───────────────────────────────────────────────────────────
    property string labelText: ""
    property color labelColor: Theme.textSecondary
    property color textColor: Theme.textPrimary
    property color placeholderColor: Theme.placeholderTextColor
    property color backgroundColor: Theme.inputBackground
    property color borderColor: Theme.inputBorderColor
    property color focusBorderColor: Theme.inputBorderFocusColor

    // ── Alias toàn bộ TextField properties thường dùng ───────────────────────
    property alias text:                 inputField.text
    property alias placeholderText:      inputField.placeholderText
    property alias readOnly:             inputField.readOnly
    property alias validator:            inputField.validator
    property alias echoMode:             inputField.echoMode
    property alias inputMethodHints:     inputField.inputMethodHints
    property alias inputActiveFocus:     inputField.activeFocus
    property alias acceptableInput:      inputField.acceptableInput
    property alias selectedText:         inputField.selectedText
    property alias selectionStart:       inputField.selectionStart
    property alias selectionEnd:         inputField.selectionEnd
    property alias cursorPosition:       inputField.cursorPosition
    property alias displayText:          inputField.displayText
    property alias horizontalAlignment:  inputField.horizontalAlignment

    property alias background:           inputField.background
    property alias topPadding:           inputField.topPadding
    property alias bottomPadding:        inputField.bottomPadding
    property alias leftPadding:          inputField.leftPadding
    property alias rightPadding:         inputField.rightPadding

    // ── Signals ──────────────────────────────────────────────────────────────
    signal accepted()
    signal reverseAccepted()
    signal editingFinished()
    signal textEdited(string text)

    // ── Hàm tiện ích ─────────────────────────────────────────────────────────
    function forceActiveFocus() { inputField.forceActiveFocus() }
    function selectAll()        { inputField.selectAll() }
    function clear()            { inputField.clear() }

    // ── Label (optional) ─────────────────────────────────────────────────────
    Text {
        visible:        root.labelText !== ""
        text:           root.labelText
        color:          root.labelColor
        font.pixelSize: Theme.fontSizeSmall
        font.family:    Theme.fontFamily
    }

    // ── TextField chính ──────────────────────────────────────────────────────
    TextField {
        id: inputField
        Layout.fillWidth: true

        // Qt owns cursorVisible and may update it after activeFocusChanged.
        // A programmatic text replacement during focus-out (for example
        // normalizing /24) can otherwise leave a stale blinking caret behind.
        function hideCursorAfterFocusOut() {
            if (!activeFocus)
                cursorVisible = false
        }

        Accessible.role: Accessible.EditableText
        Accessible.name: root.labelText !== "" ? root.labelText : inputField.placeholderText

        color:                root.textColor
        font.pixelSize:       Theme.fontSizeNormal
        font.family:          Theme.fontFamily
        placeholderTextColor: root.placeholderColor
        selectionColor:       Theme.selectionBackground
        selectedTextColor:    Theme.selectionForeground

        opacity: (enabled && !readOnly) ? 1.0 : 0.6

        leftPadding:  Theme.spacing12
        rightPadding: Theme.spacing12

        background: Rectangle {
            // ── Dùng inputBackground thay vì searchBackground2 ──
            color:        root.backgroundColor
            border.color: inputField.activeFocus
                              ? root.focusBorderColor
                              : root.borderColor
            border.width: Theme.borderWidth
            radius:       Theme.radiusSmall

        }

        onEditingFinished: root.editingFinished()
        onAccepted:        root.accepted()
        onTextEdited:      root.textEdited(inputField.text)
        onActiveFocusChanged: {
            if (!activeFocus) {
                // Run after Qt's own focus/cursor bookkeeping so a late
                // cursorVisible=true cannot survive on an inactive field.
                Qt.callLater(inputField.hideCursorAfterFocusOut)
            }
        }

        Keys.onPressed: function(event) {
            if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                    && (event.modifiers & Qt.ShiftModifier)) {
                root.reverseAccepted()
                event.accepted = true
            }
        }
    }
}
