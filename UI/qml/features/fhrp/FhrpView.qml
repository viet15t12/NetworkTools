pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

// FHRP workspace orchestration only. Each protocol page owns its own form,
// selected hosts and unsaved draft so switching tabs does not mix protocols.
Rectangle {
    id: root

    property string currentHostIp: ""
    property string currentTab: "HSRP"
    property bool hsrpLoaded: true
    property bool vrrpLoaded: false
    property bool glbpLoaded: false
    property string hsrpHostIp: ""
    property string vrrpHostIp: ""
    property string glbpHostIp: ""

    readonly property bool isViewLoading: {
        const loader = activeLoader()
        return loader ? loader.status === Loader.Loading : false
    }

    color: Theme.contentBackground

    function activeLoader() {
        switch (currentTab) {
        case "HSRP": return hsrpLoader
        case "VRRP": return vrrpLoader
        case "GLBP": return glbpLoader
        default: return null
        }
    }

    function activateTab(tabName) {
        currentTab = tabName
        syncHostToCurrentTab()
        if (tabName === "HSRP")
            hsrpLoaded = true
        else if (tabName === "VRRP")
            vrrpLoaded = true
        else if (tabName === "GLBP")
            glbpLoaded = true
    }

    function syncHostToCurrentTab() {
        if (currentTab === "HSRP")
            hsrpHostIp = currentHostIp
        else if (currentTab === "VRRP")
            vrrpHostIp = currentHostIp
        else if (currentTab === "GLBP")
            glbpHostIp = currentHostIp
    }

    function reloadData(reason) {
        const loader = activeLoader()
        if (!loader || !loader.item || !loader.item.reloadData)
            return false
        return loader.item.reloadData(reason || "activation")
    }

    onCurrentHostIpChanged: syncHostToCurrentTab()
    Component.onCompleted: syncHostToCurrentTab()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        FhrpSubBar {
            Layout.fillWidth: true
            activeTab: root.currentTab
            onTabClicked: tabName => root.activateTab(tabName)
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Loader {
                id: hsrpLoader
                objectName: "fhrpHsrpLoader"
                anchors.fill: parent
                active: root.hsrpLoaded
                asynchronous: true
                visible: root.currentTab === "HSRP"
                sourceComponent: Component {
                    FhrpProtocolPage {
                        protocol: "hsrp"
                        currentHostIp: root.hsrpHostIp
                    }
                }
            }

            Loader {
                id: vrrpLoader
                objectName: "fhrpVrrpLoader"
                anchors.fill: parent
                active: root.vrrpLoaded
                asynchronous: true
                visible: root.currentTab === "VRRP"
                sourceComponent: Component {
                    FhrpProtocolPage {
                        protocol: "vrrp"
                        currentHostIp: root.vrrpHostIp
                    }
                }
            }

            Loader {
                id: glbpLoader
                objectName: "fhrpGlbpLoader"
                anchors.fill: parent
                active: root.glbpLoaded
                asynchronous: true
                visible: root.currentTab === "GLBP"
                sourceComponent: Component {
                    FhrpProtocolPage {
                        protocol: "glbp"
                        currentHostIp: root.glbpHostIp
                    }
                }
            }
        }
    }
}
