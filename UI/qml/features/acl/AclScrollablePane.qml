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

    color: Theme.contentBackground
    clip: true

    Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: Math.max(height, paneLayout.height + root.paneTopMargin + root.paneMargins)
        flickableDirection: Flickable.VerticalFlick
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height
        clip: true

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
        }

        ColumnLayout {
            id: paneLayout
            x: root.paneMargins
            y: root.paneTopMargin
            width: Math.max(0, flick.width - root.paneMargins * 2)
            height: Math.max(implicitHeight, flick.height - root.paneTopMargin - root.paneMargins)
            spacing: 14
        }
    }
}
