pragma ComponentBehavior: Bound

import QtQuick
import UI

// ─────────────────────────────────────────────────────────────────────────────
// DeviceFormInput
// Wrapper tương thích ngược với code cũ, kế thừa StandardTextField.
// ─────────────────────────────────────────────────────────────────────────────
StandardTextField {
    id: root

    // map "label" cũ sang "labelText" chuẩn
    property string label: ""
    labelText: root.label

    // map "placeholder" cũ sang "placeholderText" chuẩn
    property string placeholder: ""
    placeholderText: root.placeholder
}