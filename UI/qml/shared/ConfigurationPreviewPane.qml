pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

// Shared, scrollable, read-only command preview for View & Push dialogs.
Rectangle {
    id: root

    property string previewText: ""
    property string emptyText: "No configuration required for Push."
    property color previewColor: previewText === ""
                                 ? Theme.textDisabled : Theme.textPrimary

    color: Theme.contentBackground
    radius: Theme.radiusSmall
    border.color: Theme.borderColor
    border.width: Theme.borderWidth

    function scrollToStart() {
        if (!previewScroll.contentItem)
            return
        previewScroll.contentItem.contentX = 0
        previewScroll.contentItem.contentY = 0
    }

    onPreviewTextChanged: Qt.callLater(root.scrollToStart)

    ScrollView {
        id: previewScroll
        objectName: root.objectName + "ScrollView"
        anchors.fill: parent
        anchors.margins: Theme.spacing12
        clip: true

        ScrollBar.vertical: ScrollBar {
            objectName: root.objectName + "VerticalScrollBar"
            policy: ScrollBar.AsNeeded
        }
        ScrollBar.horizontal: ScrollBar {
            objectName: root.objectName + "HorizontalScrollBar"
            policy: ScrollBar.AsNeeded
        }

        TextArea {
            id: previewArea
            objectName: root.objectName + "TextArea"
            width: Math.max(previewScroll.availableWidth,
                            contentWidth + leftPadding + rightPadding)
            height: Math.max(previewScroll.availableHeight,
                             contentHeight + topPadding + bottomPadding)
            text: root.previewText === "" ? root.emptyText : root.previewText
            readOnly: true
            selectByMouse: true
            wrapMode: TextEdit.NoWrap
            color: root.previewColor
            selectedTextColor: Theme.selectionForeground
            selectionColor: Theme.selectionBackground
            font.family: Theme.monoFontFamily
            font.pixelSize: Theme.fontSizeSmall
            background: Rectangle { color: "transparent" }
        }
    }
}
