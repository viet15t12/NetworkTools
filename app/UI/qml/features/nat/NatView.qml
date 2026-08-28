pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: natView
    color: Theme.contentBackground

    property string currentHostIp: ""
    property string currentTab:    "Interfaces"
    property int viewPushRevision: 0
    property bool staticLoaded: false
    property bool dynamicLoaded: false
    property bool patLoaded: false
    property bool interfacesLoaded: true
    property bool aclLoaded: false
    property bool routeMapLoaded: false
    property bool infoLoaded: false
    property string staticHostIp: ""
    property string dynamicHostIp: ""
    property string patHostIp: ""
    property string interfacesHostIp: ""
    property string aclHostIp: ""
    property string routeMapHostIp: ""
    readonly property bool isViewLoading: {
        switch (currentTab) {
        case "Static": return staticLoader.status === Loader.Loading
        case "Dynamic": return dynamicLoader.status === Loader.Loading
        case "PAT": return patLoader.status === Loader.Loading
        case "Interfaces": return interfacesLoader.status === Loader.Loading
        case "ACL": return aclLoader.status === Loader.Loading
        case "Route Map": return routeMapLoader.status === Loader.Loading
        case "Info": return infoLoader.status === Loader.Loading
        default: return false
        }
    }

    function activeLoader() {
        switch (currentTab) {
        case "Static": return staticLoader
        case "Dynamic": return dynamicLoader
        case "PAT": return patLoader
        case "Interfaces": return interfacesLoader
        case "ACL": return aclLoader
        case "Route Map": return routeMapLoader
        case "Info": return infoLoader
        default: return null
        }
    }

    function hasUnsavedChanges(item) {
        if (!item)
            return false
        return item.hasPendingLocalChanges === true
                || item.hasPendingDeletes === true
                || item.dirty === true
                || (item.formMode !== undefined && Number(item.formMode) !== 0)
                || (item.isEditing && item.isEditing())
    }

    function ensureCurrentTabLoaded() {
        if (staticLoader.status === Loader.Loading && currentTab !== "Static")
            staticLoaded = false
        if (dynamicLoader.status === Loader.Loading && currentTab !== "Dynamic")
            dynamicLoaded = false
        if (patLoader.status === Loader.Loading && currentTab !== "PAT")
            patLoaded = false
        if (interfacesLoader.status === Loader.Loading && currentTab !== "Interfaces")
            interfacesLoaded = false
        if (aclLoader.status === Loader.Loading && currentTab !== "ACL")
            aclLoaded = false
        if (routeMapLoader.status === Loader.Loading && currentTab !== "Route Map")
            routeMapLoaded = false
        if (infoLoader.status === Loader.Loading && currentTab !== "Info")
            infoLoaded = false

        switch (currentTab) {
        case "Static": staticLoaded = true; break
        case "Dynamic": dynamicLoaded = true; break
        case "PAT": patLoaded = true; break
        case "Interfaces": interfacesLoaded = true; break
        case "ACL": aclLoaded = true; break
        case "Route Map": routeMapLoaded = true; break
        case "Info": infoLoaded = true; break
        }
    }

    function reloadSelectedNatTab() {
        return reloadData("subfeature-activated")
    }

    function reloadData(reason) {
        const loader = activeLoader()
        const item = loader ? loader.item : null
        if (!item || hasUnsavedChanges(item))
            return false

        if (item.reloadData)
            return item.reloadData(reason || "activation")

        if (currentTab === "Static" && item.reloadEntries) {
            item.reloadEntries()
        } else if (currentTab === "Dynamic" && item.reloadAclNames && item.reloadPools) {
            item.reloadAclNames()
            item.reloadPools()
        } else if (currentTab === "PAT" && item.reloadAclNames && item.reloadRules) {
            item.reloadAclNames()
            item.reloadRules()
        } else if (currentTab === "Interfaces" && item.reloadInterfaceNames && item.reloadInterfaces) {
            item.reloadInterfaceNames()
            item.reloadInterfaces()
        } else if (currentTab === "ACL" && item.reloadAclNames && item.reloadAcls) {
            item.reloadAclNames()
            item.reloadAcls()
        } else if (currentTab === "Route Map" && item.reloadAclNames && item.reloadRouteMapNames && item.reloadEntries) {
            item.reloadAclNames()
            item.reloadRouteMapNames()
            item.reloadEntries()
        } else {
            return false
        }
        refreshViewPush()
        return true
    }

    function activateTab(tabName) {
        currentTab = tabName
        syncHostToCurrentTab()
        ensureCurrentTabLoaded()
        activationReloadTimer.restart()
    }

    function syncHostToCurrentTab() {
        switch (currentTab) {
        case "Static": staticHostIp = currentHostIp; break
        case "Dynamic": dynamicHostIp = currentHostIp; break
        case "PAT": patHostIp = currentHostIp; break
        case "Interfaces": interfacesHostIp = currentHostIp; break
        case "ACL": aclHostIp = currentHostIp; break
        case "Route Map": routeMapHostIp = currentHostIp; break
        }
    }

    onCurrentTabChanged: {
        syncHostToCurrentTab()
        ensureCurrentTabLoaded()
        activationReloadTimer.restart()
    }
    Component.onCompleted: syncHostToCurrentTab()

    Timer {
        id: activationReloadTimer
        interval: 0
        repeat: false
        onTriggered: natView.reloadSelectedNatTab()
    }

    function refreshViewPush() {
        viewPushRevision++
    }

    function reloadNatData() {
        if (staticLoader.item) staticLoader.item.reloadEntries()
        if (dynamicLoader.item) {
            dynamicLoader.item.reloadAclNames()
            dynamicLoader.item.reloadPools()
        }
        if (patLoader.item) {
            patLoader.item.reloadAclNames()
            patLoader.item.reloadRules()
        }
        if (interfacesLoader.item) {
            interfacesLoader.item.reloadInterfaceNames()
            interfacesLoader.item.reloadInterfaces()
        }
        if (aclLoader.item) {
            aclLoader.item.reloadAclNames()
            aclLoader.item.reloadAcls()
        }
        if (routeMapLoader.item) {
            routeMapLoader.item.reloadAclNames()
            routeMapLoader.item.reloadRouteMapNames()
            routeMapLoader.item.reloadEntries()
        }
        refreshViewPush()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing:      0

        NatSubBar {
            Layout.fillWidth: true
            activeTab:        natView.currentTab
            onTabClicked:     (tabName) => natView.activateTab(tabName)
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            color: Theme.contentSurface

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.borderWidth
                color: Theme.borderColor
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                spacing: Theme.spacing12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: "NAT Configuration"
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeLarge
                        font.family: Theme.fontFamily
                        font.bold: true
                    }
                    Text {
                        Layout.fillWidth: true
                        text: String(natView.currentHostIp || "").trim() === "" ? "No device selected" : natView.currentHostIp
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                    }
                }

                StandardButton {
                    objectName: "natQuickSetupButton"
                    text: "Quick setup"
                    type: "Secondary"
                    enabled: String(natView.currentHostIp || "").trim() !== ""
                    tooltip: "Create a standard interface PAT policy"
                    onClicked: quickSetupDialog.openForHost(natView.currentHostIp)
                }

                ViewPushButton {
                    type: "Primary"
                    controllerName: "nat"
                    moduleName: "all"
                    hostIp: natView.currentHostIp
                    ownerForm: natView
                    refreshKey: natView.viewPushRevision
                    onPushCompleted: function(ok, message) {
                        if (ok) natView.reloadNatData()
                    }
                }
            }
        }

        Item {
            Layout.fillWidth:  true
            Layout.fillHeight: true

            // Phase D: converted from static Text to Loader (consistent with other tabs).
            // When NatInfoView is implemented, replace the placeholder component.
            Loader {
                id: infoLoader
                objectName: "natInfoLoader"
                anchors.fill: parent
                active: natView.infoLoaded
                asynchronous: true
                visible: natView.currentTab === "Info"
                sourceComponent: Component {
                    Item {
                        Text {
                            anchors.centerIn: parent
                            text:             "NAT Info — Not yet implemented"
                            color:            Theme.textDisabled
                            font.pixelSize:   Theme.fontSizeNormal
                            font.family:      Theme.fontFamily
                        }
                    }
                }
            }

            Loader {
                id: staticLoader
                objectName: "natStaticLoader"
                anchors.fill:  parent
                active: natView.staticLoaded
                asynchronous: true
                visible: natView.currentTab === "Static"
                sourceComponent: Component {
                    NatStaticForm {
                        currentHostIp: natView.staticHostIp
                        onDataChanged: natView.refreshViewPush()
                    }
                }
            }

            Loader {
                id: dynamicLoader
                objectName: "natDynamicLoader"
                anchors.fill:  parent
                active: natView.dynamicLoaded
                asynchronous: true
                visible: natView.currentTab === "Dynamic"
                sourceComponent: Component {
                    NatDynamicForm {
                        currentHostIp: natView.dynamicHostIp
                        onDataChanged: natView.refreshViewPush()
                    }
                }
            }

            Loader {
                id: patLoader
                objectName: "natPatLoader"
                anchors.fill:  parent
                active: natView.patLoaded
                asynchronous: true
                visible: natView.currentTab === "PAT"
                sourceComponent: Component {
                    NatPatForm {
                        currentHostIp: natView.patHostIp
                        onDataChanged: natView.refreshViewPush()
                    }
                }
            }

            Loader {
                id: interfacesLoader
                objectName: "natInterfacesLoader"
                anchors.fill:  parent
                active: natView.interfacesLoaded
                asynchronous: true
                visible: natView.currentTab === "Interfaces"
                sourceComponent: Component {
                    NatInterfaceForm {
                        currentHostIp: natView.interfacesHostIp
                        onDataChanged: natView.refreshViewPush()
                    }
                }
            }

            Loader {
                id: aclLoader
                objectName: "natAclLoader"
                anchors.fill:  parent
                active: natView.aclLoaded
                asynchronous: true
                visible: natView.currentTab === "ACL"
                sourceComponent: Component {
                    NatAclForm {
                        currentHostIp: natView.aclHostIp
                        onDataChanged: natView.refreshViewPush()
                    }
                }
            }

            Loader {
                id: routeMapLoader
                objectName: "natRouteMapLoader"
                anchors.fill:  parent
                active: natView.routeMapLoaded
                asynchronous: true
                visible: natView.currentTab === "Route Map"
                sourceComponent: Component {
                    NatRouteMapForm {
                        currentHostIp: natView.routeMapHostIp
                        onDataChanged: natView.refreshViewPush()
                    }
                }
            }
        }
    }

    onCurrentHostIpChanged: {
        syncHostToCurrentTab()
        refreshViewPush()
    }

    NatQuickSetupDialog {
        id: quickSetupDialog
        onSetupSaved: {
            natView.reloadNatData()
            natView.activateTab("PAT")
        }
    }
}
