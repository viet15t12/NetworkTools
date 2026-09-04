pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: routingView


    color: Theme.contentBackground
    property string currentHostIp: ""

    // Info remains available internally for compatibility, but is no longer
    // exposed as a configuration tab.
    property string currentTab: "Static"
    property bool infoLoaded: false
    property bool staticLoaded: true
    property bool defaultLoaded: false
    property bool ospfLoaded: false
    property bool eigrpLoaded: false
    property string infoHostIp: ""
    property string staticHostIp: ""
    property string defaultHostIp: ""
    property string ospfHostIp: ""
    property string eigrpHostIp: ""
    readonly property bool isViewLoading: {
        switch (currentTab) {
        case "Info": return infoLoader.status === Loader.Loading
        case "Static": return staticLoader.status === Loader.Loading
        case "Default": return defaultLoader.status === Loader.Loading
        case "OSPF": return ospfLoader.status === Loader.Loading
        case "EIGRP": return eigrpLoader.status === Loader.Loading
        default: return false
        }
    }

    function activeLoader() {
        switch (currentTab) {
        case "Info": return infoLoader
        case "Static": return staticLoader
        case "Default": return defaultLoader
        case "OSPF": return ospfLoader
        case "EIGRP": return eigrpLoader
        default: return null
        }
    }

    function hasUnsavedChanges(item) {
        if (!item)
            return false
        return item.hasPendingLocalChanges === true
                || item.hasPendingStaticChanges === true
                || item.hasPendingDeletes === true
                || item.dirty === true
                || (item.formMode !== undefined && Number(item.formMode) !== 0)
                || (item.isEditing && item.isEditing())
    }

    function reloadData(reason) {
        const loader = activeLoader()
        const item = loader ? loader.item : null
        if (!item || hasUnsavedChanges(item) || item.isLoading === true || item.isSaving === true)
            return false
        if (item.reloadData)
            return item.reloadData(reason || "activation")
        if (item.loadFromDatabase) {
            item.loadFromDatabase()
            return true
        }
        return false
    }

    function activateTab(tabName) {
        currentTab = tabName
        syncHostToCurrentTab()
        ensureCurrentTabLoaded()
        activationReloadTimer.restart()
    }

    function ensureCurrentTabLoaded() {
        if (infoLoader.status === Loader.Loading && currentTab !== "Info")
            infoLoaded = false
        if (staticLoader.status === Loader.Loading && currentTab !== "Static")
            staticLoaded = false
        if (defaultLoader.status === Loader.Loading && currentTab !== "Default")
            defaultLoaded = false
        if (ospfLoader.status === Loader.Loading && currentTab !== "OSPF")
            ospfLoaded = false
        if (eigrpLoader.status === Loader.Loading && currentTab !== "EIGRP")
            eigrpLoaded = false

        switch (currentTab) {
        case "Info": infoLoaded = true; break
        case "Static": staticLoaded = true; break
        case "Default": defaultLoaded = true; break
        case "OSPF": ospfLoaded = true; break
        case "EIGRP": eigrpLoaded = true; break
        }
    }

    function syncHostToCurrentTab() {
        switch (currentTab) {
        case "Info": infoHostIp = currentHostIp; break
        case "Static": staticHostIp = currentHostIp; break
        case "Default": defaultHostIp = currentHostIp; break
        case "OSPF": ospfHostIp = currentHostIp; break
        case "EIGRP": eigrpHostIp = currentHostIp; break
        }
    }

    onCurrentTabChanged: {
        syncHostToCurrentTab()
        ensureCurrentTabLoaded()
        activationReloadTimer.restart()
    }
    onCurrentHostIpChanged: syncHostToCurrentTab()
    onInfoHostIpChanged: {
        if (infoLoader.item)
            infoLoader.item.currentHostIp = infoHostIp
    }
    Component.onCompleted: syncHostToCurrentTab()

    Timer {
        id: activationReloadTimer
        interval: 0
        repeat: false
        onTriggered: routingView.reloadData("subfeature-activated")
    }

    // ── Bố cục dọc: SubBar trên, Form dưới ──────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing:      0

        // 1. Thanh tab con
        RoutingSubBar {
            Layout.fillWidth: true
            activeTab:        routingView.currentTab
            onTabClicked:     (tabName) => routingView.activateTab(tabName)
        }

        // 2. Vùng nội dung — hoán đổi theo tab đang chọn
        Item {
            Layout.fillWidth:  true
            Layout.fillHeight: true

            // ── Info ──────────────────────────────────────────────
            Loader {
                id: infoLoader
                objectName: "routingInfoLoader"
                anchors.fill: parent
                visible:      routingView.currentTab === "Info"
                active:       routingView.infoLoaded
                asynchronous: true
                source:       "info_routing.qml"
                onLoaded:     item.currentHostIp = routingView.infoHostIp
            }

            // ── Default ───────────────────────────────────────────
            Loader {
                id: defaultLoader
                objectName: "routingDefaultLoader"
                anchors.fill: parent
                active: routingView.defaultLoaded
                asynchronous: true
                visible: routingView.currentTab === "Default"
                sourceComponent: Component {
                    DefaultRoutingForm { currentHostIp: routingView.defaultHostIp }
                }
            }

            // ── Static ────────────────────────────────────────────
            Loader {
                id: staticLoader
                objectName: "routingStaticLoader"
                anchors.fill: parent
                active: routingView.staticLoaded
                asynchronous: true
                visible: routingView.currentTab === "Static"
                sourceComponent: Component {
                    StaticRoutingForm { currentHostIp: routingView.staticHostIp }
                }
            }

            // ── OSPF ──────────────────────────────────────────────
            Loader {
                id: ospfLoader
                objectName: "routingOspfLoader"
                anchors.fill: parent
                active: routingView.ospfLoaded
                asynchronous: true
                visible: routingView.currentTab === "OSPF"
                sourceComponent: Component {
                    OspfRoutingForm {
                        id: loadedOspfForm
                        currentHostIp: routingView.ospfHostIp
                        onRoutingGroupRequested: function(protocol) {
                            routingGroupDialog.openFor(protocol, loadedOspfForm)
                        }
                    }
                }
            }

            // ── EIGRP ─────────────────────────────────────────────
            Loader {
                id: eigrpLoader
                objectName: "routingEigrpLoader"
                anchors.fill: parent
                active: routingView.eigrpLoaded
                asynchronous: true
                visible: routingView.currentTab === "EIGRP"
                sourceComponent: Component {
                    EigrpRoutingForm {
                        id: loadedEigrpForm
                        currentHostIp: routingView.eigrpHostIp
                        onRoutingGroupRequested: function(protocol) {
                            routingGroupDialog.openFor(protocol, loadedEigrpForm)
                        }
                    }
                }
            }

            // ── BGP ───────────────────────────────────────────────
            Item {
                anchors.fill: parent
                visible:      routingView.currentTab === "BGP"

                Text {
                    anchors.centerIn: parent
                    text:             "BGP — Not yet implemented"
                    color:            Theme.textDisabled
                    font.pixelSize:   Theme.fontSizeNormal
                    font.family:      Theme.fontFamily
                }
            }
        }
    }

    RoutingGroupDialog {
        id: routingGroupDialog
        parent: Overlay.overlay
    }

}
