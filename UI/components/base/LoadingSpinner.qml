pragma ComponentBehavior: Bound

import QtQuick
import UI

Item {
    id: root

    property bool running: false
    property color spinnerColor: Theme.accentColor
    property real strokeWidth: Math.max(2, Math.round(width / 8))

    implicitWidth: Theme.iconSizeLarge
    implicitHeight: Theme.iconSizeLarge
    visible: running

    Canvas {
        id: arcCanvas
        anchors.fill: parent

        onPaint: {
            const context = getContext("2d")
            const inset = root.strokeWidth / 2 + 1
            const radius = Math.max(0, Math.min(width, height) / 2 - inset)
            context.clearRect(0, 0, width, height)
            context.beginPath()
            context.arc(width / 2, height / 2, radius,
                        -Math.PI / 2, -Math.PI / 2 + Math.PI * 1.5, false)
            context.lineWidth = root.strokeWidth
            context.lineCap = "round"
            context.strokeStyle = root.spinnerColor
            context.stroke()
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    Connections {
        target: root
        function onSpinnerColorChanged() { arcCanvas.requestPaint() }
        function onStrokeWidthChanged() { arcCanvas.requestPaint() }
    }

    RotationAnimator on rotation {
        from: 0
        to: 360
        duration: Theme.loaderRotationDuration
        loops: Animation.Infinite
        running: root.running && root.visible
    }

    onRunningChanged: {
        if (!running)
            rotation = 0
    }
}
