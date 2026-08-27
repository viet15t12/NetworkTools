pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 900
    height: 160
    visible: true

    readonly property int selectedMainFeature: featureBar.activeMain
    readonly property int selectedTextFeature: featureBar.activeText
    readonly property int contentMainFeature: tabs.currentFMain
    readonly property int contentTextFeature: tabs.currentFText
    readonly property string activeHost: tabs.activeUid

    function openFirstHost() {
        tabs.openTab("192.0.2.1", "R1", "router", "disconnected")
    }

    function selectNat() {
        return featureBar.selectTextFeature(5)
    }

    function openSecondHost() {
        tabs.openTab("192.0.2.2", "R2", "router", "disconnected")
    }

    function selectFirstHost() {
        tabs.openTabByUid("192.0.2.1")
    }

    Component.onCompleted: tabs.initializeTabs([])

    DeviceTabs {
        id: tabs
        objectName: "featureStateDeviceTabs"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
    }

    FeatureBar {
        id: featureBar
        objectName: "featureStateFeatureBar"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: tabs.bottom
        height: Theme.featureBarHeight
        activeMain: tabs.currentFMain
        activeText: tabs.currentFText
        deviceType: tabs.activeDeviceType
        onUserChangedFeature: function(mainIndex, textIndex) {
            tabs.setFeatureForActiveTab(mainIndex, textIndex)
        }
    }
}
