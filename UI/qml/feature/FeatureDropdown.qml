pragma ComponentBehavior: Bound

import QtQuick
import UI

Rectangle {
    id: featureDropdown

    property var hiddenFeatures: []
    property int activeIndex: -1

    signal featureSelected(int globalIndex)

    visible: false
    width: 160
    height: Math.min(hiddenFeatures.length * 36, 300)
    color: Theme.contentSurface
    border.color: Theme.borderColor
    border.width: Theme.borderWidth
    radius: 4

    // Đóng khi click ra ngoài
    function show(x, y) {
        parent.x = x
        parent.y = y
        visible = true
    }

    function hide() {
        visible = false
    }

    ListView {
        anchors.fill: parent
        anchors.margins: 4
        clip: true
        model: featureDropdown.hiddenFeatures

        delegate: Rectangle {
            id: dropdownRow
            required property int index
            required property var modelData

            width: parent.width
            height: 36
            color: dropItemHover.hovered && dropdownRow.modelData.implemented
                   ? Theme.sideBarItemHover : "transparent"
            radius: 4

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 12
                text: dropdownRow.modelData.label
                font.pixelSize: Theme.fontSizeNormal
                font.family: Theme.fontFamily
                color: dropdownRow.modelData.implemented
                       ? Theme.textPrimary : Theme.textDisabled
                opacity: dropdownRow.modelData.implemented ? 1.0 : 0.55
            }

            HoverHandler {
                id: dropItemHover
                cursorShape: dropdownRow.modelData.implemented
                             ? Qt.PointingHandCursor : Qt.ArrowCursor
            }
            TapHandler {
                enabled: dropdownRow.modelData.implemented
                onTapped: {
                    featureDropdown.featureSelected(dropdownRow.modelData.globalIndex)
                    featureDropdown.hide()
                }
            }
        }
    }
}
