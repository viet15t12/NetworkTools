pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Item {
    id: delegateRoot
    width: Math.max(140, tabLayout.implicitWidth + 40)
    height: Theme.tabBarHeight

    required property var model
    required property int index

    property string tabTitle: model.title
    property string deviceType: model.deviceType || "unknown"
    property string deviceStatus: model.status || "disconnected"
    property bool isActive: model.isActive
    property int tabIndex: index
    readonly property string normalizedDeviceType: String(deviceType || "").toLowerCase()
    readonly property string normalizedStatus: String(deviceStatus || "").toLowerCase()
    readonly property int deviceMarkerSize: Theme.iconSizeLarge
    readonly property bool hasDeviceIcon: iconSource !== ""
    readonly property bool isLoading: model.contentLoading === true
                                      || String(model.sessionState || "") === "opening"
    readonly property bool hasDeviceMarker: hasDeviceIcon || isLoading
    readonly property color deviceMarkerColor: {
        if (normalizedStatus === "connected") return Theme.statusConnected
        if (normalizedStatus === "waiting") return Theme.statusWaiting
        return Theme.statusDisconnected
    }

    readonly property string iconSource: {
        if (normalizedDeviceType === "router")
            return AppAssets.deviceRouter
        if (normalizedDeviceType === "sw2" || normalizedDeviceType === "sw3")
            return AppAssets.deviceSwitch
        return ""
    }

    // ── 1. KHAI BÁO CÁC TÍN HIỆU (SIGNALS) ĐỂ BÁO CHO FILE CHA ──
    signal moveRequested(int fromIdx, int toIdx)
    signal selectRequested(int idx)
    signal closeRequested(int idx)
    signal contextMenuRequested(int idx, real sceneX, real sceneY)

    DropArea {
        anchors.fill: parent
        keys: ["tabDrag"]
        onEntered: (drag) => {
            const fromIdx = drag.source && drag.source.tabIndex !== undefined ? drag.source.tabIndex : -1
            const toIdx = delegateRoot.tabIndex
            if (fromIdx !== -1 && fromIdx !== toIdx) {
                // PHÁT TÍN HIỆU YÊU CẦU ĐỔI CHỖ
                delegateRoot.moveRequested(fromIdx, toIdx)
            }
        }
    }

    Rectangle {
        id: visualItem
        width: delegateRoot.width
        height: delegateRoot.height

        color: delegateRoot.isActive ? Theme.tabActive : (tabHover.hovered ? Theme.tabHover : Theme.tabInactive)

        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.borderColor }
        Rectangle { anchors.top: parent.top; width: parent.width; height: 2; color: Theme.accentColor; visible: delegateRoot.isActive }

        RowLayout {
            id: tabLayout
            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 6; spacing: 6

            Item {
                visible: delegateRoot.hasDeviceMarker
                Layout.preferredWidth: visible ? delegateRoot.deviceMarkerSize : 0
                Layout.preferredHeight: delegateRoot.deviceMarkerSize
                Layout.alignment: Qt.AlignVCenter

                ThemedIcon {
                    objectName: "deviceTabDeviceIcon"
                    visible: delegateRoot.hasDeviceIcon && !delegateRoot.isLoading
                    anchors.centerIn: parent
                    iconSource: delegateRoot.iconSource
                    iconSize: delegateRoot.deviceMarkerSize
                    iconColor: delegateRoot.deviceMarkerColor
                }

                LoadingSpinner {
                    objectName: "deviceTabLoadingSpinner"
                    anchors.centerIn: parent
                    width: delegateRoot.deviceMarkerSize
                    height: delegateRoot.deviceMarkerSize
                    running: delegateRoot.isLoading
                    spinnerColor: Theme.accentColor
                }
            }

            Text {
                text: delegateRoot.tabTitle
                color: delegateRoot.isActive ? Theme.textPrimary : Theme.textSecondary
                font.pixelSize: Theme.fontSizeNormal; font.family: Theme.fontFamily
                Layout.fillWidth: true;
                elide: Text.ElideRight
            }

            Item {
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24

                CloseButton {
                    visible: delegateRoot.isActive || tabHover.hovered
                    anchors.centerIn: parent
                    variant: "tab"
                    tooltip: "Close"
                    onClicked: delegateRoot.closeRequested(delegateRoot.tabIndex)
                }
            }
        }

        HoverHandler { id: tabHover }
        TapHandler {
            // PHÁT TÍN HIỆU YÊU CẦU CHỌN TAB
            onTapped: delegateRoot.selectRequested(delegateRoot.tabIndex)
        }
        TapHandler {
            acceptedButtons: Qt.RightButton
            onTapped: function(eventPoint, button) {
                delegateRoot.contextMenuRequested(
                    delegateRoot.tabIndex,
                    eventPoint.scenePosition.x,
                    eventPoint.scenePosition.y
                )
            }
        }

        DragHandler {
            id: dragHandler
            xAxis.enabled: true; yAxis.enabled: false
            target: visualItem
        }

        Drag.active: dragHandler.active
        Drag.source: delegateRoot
        Drag.keys: ["tabDrag"]

        states: [
            State {
                when: dragHandler.active
                // Fix lỗi Parent: Gọi trực tiếp ListView thông qua thuộc tính đính kèm (attached property)
                ParentChange { target: visualItem; parent: delegateRoot.ListView.view }
                PropertyChanges { target: visualItem; opacity: 0.7; z: 100 }
            }
        ]
    }
}
