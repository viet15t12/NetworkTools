pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import UI

Dialog {
    id: root

    property real preferredWidth: 480
    property string subtitle: ""
    property string closeTooltip: "Close dialog"
    property bool closeEnabled: true
    property bool lockApplication: true
    property bool _ownsWindowLock: false

    parent: Overlay.overlay
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    width: Math.min(root.preferredWidth,
                    parent ? parent.width - Theme.spacing16 * 2 : root.preferredWidth)
    modal: true
    dim: true
    focus: true
    padding: Theme.spacing24
    closePolicy: root.closeEnabled ? Popup.CloseOnEscape : Popup.NoAutoClose

    Overlay.modal: Rectangle {
        color: Theme.dialogOverlay

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.animationDurationFast
                easing.type: Easing.OutCubic
            }
        }
    }

    background: Rectangle {
        color: Theme.contentPanelSurface
        border.color: Theme.contentPanelBorder
        border.width: Theme.borderWidth
        radius: Theme.radiusLarge

        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.shadowColor
            shadowBlur: 0.75
            shadowVerticalOffset: 4
        }
    }

    header: Item {
        implicitHeight: standardDialogTitleBar.implicitHeight + Theme.spacing24 * 2

        DialogTitleBar {
            id: standardDialogTitleBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: Theme.spacing24
            anchors.rightMargin: Theme.spacing24
            title: root.title
            subtitle: root.subtitle
            closeTooltip: root.closeTooltip
            closeEnabled: root.closeEnabled
            onCloseRequested: root.reject()
        }
    }

    onAboutToShow: {
        if (root.lockApplication) {
            root._ownsWindowLock = !UiState.windowLock
            UiState.windowLock = true
        }
    }

    onClosed: {
        if (root._ownsWindowLock)
            UiState.windowLock = false
        root._ownsWindowLock = false
    }
}
