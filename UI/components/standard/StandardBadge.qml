pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: root

    property string text: ""
    property color badgeColor: Theme.accentEmphasis
    property color textColor: Theme.buttonTextSolid

    // Tự động ẩn nếu không có nội dung hoặc bằng 0
    visible: text !== "" && text !== "0"

    // Tự động co giãn theo nội dung, chiều rộng tối thiểu là 20 để tạo hình tròn đẹp
    implicitWidth: Math.max(20, badgeText.implicitWidth + 12)
    implicitHeight: 20
    radius: 10
    color: badgeColor

    Text {
        id: badgeText
        anchors.centerIn: parent
        text: root.text
        color: root.textColor
        font.pixelSize: Theme.fontSizeSmall
        font.family: Theme.fontFamily
        font.bold: true
    }
}
