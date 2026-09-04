pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import UI

Item {
    anchors.fill: parent

    readonly property int edgeSize: 6

    // ── Cạnh trên ──
    Item {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: edgeSize
        HoverHandler { cursorShape: Qt.SizeVerCursor }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.startSystemResize(Qt.TopEdge)
            cursorShape: Qt.SizeVerCursor
        }
    }

    // ── Cạnh dưới ──
    Item {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: edgeSize
        HoverHandler { cursorShape: Qt.SizeVerCursor }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.startSystemResize(Qt.BottomEdge)
            cursorShape: Qt.SizeVerCursor
        }
    }

    // ── Cạnh trái ──
    Item {
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: edgeSize
        HoverHandler { cursorShape: Qt.SizeHorCursor }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.startSystemResize(Qt.LeftEdge)
            cursorShape: Qt.SizeHorCursor
        }
    }

    // ── Cạnh phải ──
    Item {
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: edgeSize
        HoverHandler { cursorShape: Qt.SizeHorCursor }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.startSystemResize(Qt.RightEdge)
            cursorShape: Qt.SizeHorCursor
        }
    }

    // ── Góc trên trái ──
    Item {
        anchors.top: parent.top
        anchors.left: parent.left
        width: edgeSize * 2
        height: edgeSize * 2
        HoverHandler { cursorShape: Qt.SizeFDiagCursor }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.startSystemResize(Qt.TopEdge | Qt.LeftEdge)
            cursorShape: Qt.SizeFDiagCursor
        }
    }

    // ── Góc trên phải ──
    Item {
        anchors.top: parent.top
        anchors.right: parent.right
        width: edgeSize * 2
        height: edgeSize * 2
        HoverHandler { cursorShape: Qt.SizeBDiagCursor }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.startSystemResize(Qt.TopEdge | Qt.RightEdge)
            cursorShape: Qt.SizeBDiagCursor
        }
    }

    // ── Góc dưới trái ──
    Item {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: edgeSize * 2
        height: edgeSize * 2
        HoverHandler { cursorShape: Qt.SizeFDiagCursor }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.startSystemResize(Qt.BottomEdge | Qt.LeftEdge)
            cursorShape: Qt.SizeBDiagCursor
        }
    }

    // ── Góc dưới phải ──
    Item {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: edgeSize * 2
        height: edgeSize * 2
        HoverHandler { cursorShape: Qt.SizeFDiagCursor }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.startSystemResize(Qt.BottomEdge | Qt.RightEdge)
            cursorShape: Qt.SizeFDiagCursor
        }
    }
}
