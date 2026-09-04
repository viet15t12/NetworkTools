pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Item {
    id: root

    required property string host
    required property string deviceRole
    property string feature: "interfaces"
    property string subFeature: "switchPorts"
    property var navigation: []

    // Each page is incubated on first visit and then kept alive.  This avoids
    // rebuilding tables and losing a user's selection/draft when switching
    // between the four switch features.
    property bool switchPortsLoaded: false
    property bool routedPortsLoaded: false
    property bool sviLoaded: false
    property bool vlanLoaded: false
    property bool etherChannelLoaded: false
    property bool stpLoaded: false
    property bool vtpLoaded: false
    property bool l2SecurityLoaded: false
    property bool portSecurityLoaded: false
    property bool portCountersLoaded: false
    property bool macTableLoaded: false
    property bool servicesLoaded: false
    property bool aclLoaded: false

    readonly property bool isSw3: String(deviceRole).toLowerCase() === "sw3"
    readonly property var currentSubFeatureTabs: subFeatureTabs()
    readonly property string pageKey: feature + ":" + subFeature
    readonly property bool pageSupported: activePageLoader() !== null
    readonly property bool isViewLoading: {
        const loader = activePageLoader()
        return loader !== null
                && (loader.status === Loader.Loading
                    || (loader.item !== null && loader.item.isViewLoading === true))
    }

    function reloadNavigation() {
        navigation = dbManager.getSwitchNavigation(deviceRole)
        normalizeSubFeature()
        ensureActivePageLoaded()
    }

    function subFeaturesForFeature() {
        for (let i = 0; i < navigation.length; i++) {
            if (navigation[i].id === feature)
                return navigation[i].subfeatures || []
        }
        return []
    }

    function label(value) {
        const labels = {
            switchPorts: "Switch Ports",
            routedPorts: "Routed Ports",
            svi: "SVI",
            vlan: "VLAN",
            etherChannel: "EtherChannel",
            stp: "STP",
            vtp: "VTP",
            l2Security: "L2 Security",
            portSecurity: "Port Security",
            acl: "ACL",
            portCounters: "Port Counters",
            macTable: "MAC Table",
            dhcpServer: "DHCP Server",
            dhcpRelay: "DHCP Relay"
        }
        return labels[value] || value
    }

    function subFeatureTabs() {
        const options = subFeaturesForFeature()
        const tabs = []
        for (let i = 0; i < options.length; i++)
            tabs.push(label(options[i]))
        return tabs
    }

    function subFeatureId(tabName) {
        const options = subFeaturesForFeature()
        for (let i = 0; i < options.length; i++) {
            if (label(options[i]) === tabName)
                return options[i]
        }
        return ""
    }

    function normalizeSubFeature() {
        const options = subFeaturesForFeature()
        if (options.length > 0 && options.indexOf(subFeature) === -1)
            subFeature = options[0]
    }

    function activePageLoader() {
        switch (pageKey) {
        case "interfaces:switchPorts": return switchPortsLoader
        case "interfaces:routedPorts": return routedPortsLoader
        case "interfaces:svi": return sviLoader
        case "switching:vlan": return vlanLoader
        case "switching:etherChannel": return etherChannelLoader
        case "switching:stp": return stpLoader
        case "switching:vtp": return vtpLoader
        case "security:l2Security": return l2SecurityLoader
        case "security:portSecurity": return portSecurityLoader
        case "security:acl": return aclLoader
        case "monitoring:portCounters": return portCountersLoader
        case "monitoring:macTable": return macTableLoader
        case "services:dhcpServer":
        case "services:dhcpRelay": return servicesLoader
        default: return null
        }
    }

    function hasUnsavedChanges(item) {
        if (!item)
            return false
        return item.hasPendingLocalChanges === true
                || item.hasPendingDeletes === true
                || item.dirty === true
                || item.saving === true
                || (item.formMode !== undefined && Number(item.formMode) !== 0)
                || (item.isEditing && item.isEditing())
    }

    function reloadData(reason) {
        const loader = activePageLoader()
        const item = loader ? loader.item : null
        if (!item || hasUnsavedChanges(item))
            return false
        if (item.reloadData)
            return item.reloadData(reason || "activation")
        if (item.load) {
            item.load()
            return true
        }
        return false
    }

    function activateSubFeature(value) {
        subFeature = value
        ensureActivePageLoaded()
        activationReloadTimer.restart()
    }

    function ensureActivePageLoaded() {
        // Read the writable properties directly. During a change handler the
        // derived pageKey binding can still contain the previous value.
        switch (feature + ":" + subFeature) {
        case "interfaces:switchPorts": switchPortsLoaded = true; break
        case "interfaces:routedPorts": routedPortsLoaded = true; break
        case "interfaces:svi": sviLoaded = true; break
        case "switching:vlan": vlanLoaded = true; break
        case "switching:etherChannel": etherChannelLoaded = true; break
        case "switching:stp": stpLoaded = true; break
        case "switching:vtp": vtpLoaded = true; break
        case "security:l2Security": l2SecurityLoaded = true; break
        case "security:portSecurity": portSecurityLoaded = true; break
        case "security:acl": aclLoaded = true; break
        case "monitoring:portCounters": portCountersLoaded = true; break
        case "monitoring:macTable": macTableLoaded = true; break
        case "services:dhcpServer":
        case "services:dhcpRelay": servicesLoaded = true; break
        }
    }

    onFeatureChanged: {
        normalizeSubFeature()
        ensureActivePageLoaded()
        activationReloadTimer.restart()
    }
    onSubFeatureChanged: {
        ensureActivePageLoaded()
        activationReloadTimer.restart()
    }
    onDeviceRoleChanged: reloadNavigation()
    Component.onCompleted: reloadNavigation()

    Timer {
        id: activationReloadTimer
        interval: 0
        repeat: false
        onTriggered: root.reloadData("subfeature-activated")
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        SubBar {
            objectName: "switchSubFeatureBar"
            Layout.fillWidth: true
            visible: root.currentSubFeatureTabs.length >= 2
            Layout.preferredHeight: visible ? Theme.subBarHeight : 0
            tabs: root.currentSubFeatureTabs
            activeTab: root.label(root.subFeature)
            onTabClicked: function(tabName) {
                const id = root.subFeatureId(tabName)
                if (id !== "")
                    root.activateSubFeature(id)
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Loader {
                id: switchPortsLoader
                objectName: "switchPortsLoader"
                anchors.fill: parent
                active: root.switchPortsLoaded
                asynchronous: true
                visible: root.pageKey === "interfaces:switchPorts"
                sourceComponent: Component {
                    SwitchPortsPage {
                        host: root.host
                        allowRouted: root.isSw3
                        routedOnly: false
                        viewMode: "interfaces"
                    }
                }
            }

            Loader {
                id: routedPortsLoader
                objectName: "switchRoutedPortsLoader"
                anchors.fill: parent
                active: root.routedPortsLoaded
                asynchronous: true
                visible: root.pageKey === "interfaces:routedPorts"
                sourceComponent: Component {
                    SwitchPortsPage {
                        host: root.host
                        allowRouted: root.isSw3
                        routedOnly: true
                        viewMode: "interfaces"
                    }
                }
            }

            Loader {
                id: sviLoader
                objectName: "switchSviLoader"
                anchors.fill: parent
                active: root.sviLoaded
                asynchronous: true
                visible: root.pageKey === "interfaces:svi"
                sourceComponent: Component { SviPage { host: root.host } }
            }

            Loader {
                id: vlanLoader
                objectName: "switchVlanLoader"
                anchors.fill: parent
                active: root.vlanLoaded
                asynchronous: true
                visible: root.pageKey === "switching:vlan"
                sourceComponent: Component { VlanPage { host: root.host } }
            }

            Loader {
                id: vtpLoader
                objectName: "switchVtpLoader"
                anchors.fill: parent
                active: root.vtpLoaded
                asynchronous: true
                visible: root.pageKey === "switching:vtp"
                sourceComponent: Component { VtpPage { host: root.host } }
            }

            Loader {
                id: stpLoader
                objectName: "switchStpLoader"
                anchors.fill: parent
                active: root.stpLoaded
                asynchronous: true
                visible: root.pageKey === "switching:stp"
                sourceComponent: Component { StpPage { host: root.host } }
            }

            Loader {
                id: etherChannelLoader
                objectName: "switchEtherChannelLoader"
                anchors.fill: parent
                active: root.etherChannelLoaded
                asynchronous: true
                visible: root.pageKey === "switching:etherChannel"
                sourceComponent: Component { EtherChannelPage { host: root.host } }
            }

            Loader {
                id: portSecurityLoader
                objectName: "switchPortSecurityLoader"
                anchors.fill: parent
                active: root.portSecurityLoaded
                asynchronous: true
                visible: root.pageKey === "security:portSecurity"
                sourceComponent: Component {
                    SwitchPortsPage {
                        host: root.host
                        allowRouted: root.isSw3
                        routedOnly: false
                        viewMode: "portSecurity"
                    }
                }
            }

            Loader {
                id: l2SecurityLoader
                objectName: "switchL2SecurityLoader"
                anchors.fill: parent
                active: root.l2SecurityLoaded
                asynchronous: true
                visible: root.pageKey === "security:l2Security"
                sourceComponent: Component { L2SecurityPage { host: root.host } }
            }

            Loader {
                id: portCountersLoader
                objectName: "switchPortCountersLoader"
                anchors.fill: parent
                active: root.portCountersLoaded
                asynchronous: true
                visible: root.pageKey === "monitoring:portCounters"
                sourceComponent: Component {
                    SwitchMonitoringPage { host: root.host; viewName: "portCounters" }
                }
            }

            Loader {
                id: macTableLoader
                objectName: "switchMacTableLoader"
                anchors.fill: parent
                active: root.macTableLoaded
                asynchronous: true
                visible: root.pageKey === "monitoring:macTable"
                sourceComponent: Component {
                    SwitchMonitoringPage { host: root.host; viewName: "macTable" }
                }
            }

            Loader {
                id: servicesLoader
                anchors.fill: parent
                active: root.servicesLoaded
                asynchronous: true
                visible: root.feature === "services"
                sourceComponent: Component {
                    DhcpView {
                        currentHostIp: root.host
                        currentTab: root.subFeature === "dhcpRelay" ? "Helper" : "Pool"
                    }
                }
            }

            Loader {
                id: aclLoader
                anchors.fill: parent
                active: root.aclLoaded
                asynchronous: true
                visible: root.pageKey === "security:acl"
                sourceComponent: Component { AclView { currentHostIp: root.host } }
            }

            EmptyState {
                anchors.fill: parent
                visible: !root.pageSupported
                title: "Feature unavailable"
                description: "This switch role does not expose a compatible page."
            }

            Rectangle {
                anchors.fill: parent
                visible: root.isViewLoading
                         && root.activePageLoader() !== null
                         && root.activePageLoader().item === null
                color: Theme.contentBackground
                z: 10

                Column {
                    anchors.centerIn: parent
                    spacing: Theme.spacing12

                    LoadingSpinner {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: Theme.iconSizeLarge
                        height: width
                        running: parent.parent.visible
                        spinnerColor: Theme.accentColor
                    }
                    Text {
                        text: "Loading " + root.label(root.subFeature) + "..."
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeNormal
                    }
                }
            }
        }
    }
}
