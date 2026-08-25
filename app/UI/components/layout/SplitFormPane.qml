pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    default property alias content: paneLayout.data
    property alias spacing: paneLayout.spacing
    property int paneMargins: Theme.spacing24
    property int paneTopMargin: Theme.spacing16
    readonly property real scrollContentHeight: scrollContent.height
    readonly property real viewportHeight: paneScroll.availableHeight
    readonly property bool contentOverflow: scrollContentHeight > viewportHeight + 0.5

    color: Theme.contentBackground

    ScrollView {
        id: paneScroll
        objectName: "splitFormPaneScroll"
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: ScrollBar.AsNeeded

        Item {
            id: scrollContent
            width: paneScroll.availableWidth
            implicitHeight: paneLayout.implicitHeight
                            + root.paneTopMargin + root.paneMargins
            height: Math.max(paneScroll.height, implicitHeight)

            ColumnLayout {
                id: paneLayout
                x: root.paneMargins
                y: root.paneTopMargin
                width: Math.max(0, parent.width - root.paneMargins * 2)
                height: Math.max(
                    implicitHeight,
                    paneScroll.height
                    - root.paneTopMargin - root.paneMargins
                )
                spacing: 14
            }
        }
    }
}
