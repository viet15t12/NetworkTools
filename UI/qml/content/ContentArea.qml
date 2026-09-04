pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: contentArea
    color: Theme.contentBackground

    property int    tabCount:          0
    property string currentHostIp:     ""
    property int    activeMainFeature: -1
    property int    activeTextFeature: -1
    property string appMode:           "devices"
    property string activeSettingKey:  "theme"
    property string activeDatabaseTable: ""
    property string deviceRole: ""

    property bool   hostConfigEnabled: true

    // UI-P1-01: Load each expensive screen on first visit, then keep it alive.
    // Caching preserves unsaved form state while avoiding eager startup work.
    property bool routingViewLoaded: false
    property bool dhcpViewLoaded: false
    property bool aclViewLoaded: false
    property bool natViewLoaded: false
    property bool fhrpViewLoaded: false
    property bool interfaceViewLoaded: false
    property bool informationViewLoaded: false
    property bool switchWorkspaceLoaded: false
    property bool syslogConfigLoaded: false
    property bool settingsViewLoaded: false
    property bool databaseViewLoaded: false
    property string effectiveHostIp: ""
    property string pendingHostIp: ""
    property bool activeViewLoadPending: false
    property bool hostApplyPending: false
    property string routingHostIp: ""
    property string dhcpHostIp: ""
    property string aclHostIp: ""
    property string natHostIp: ""
    property string fhrpHostIp: ""
    property string interfaceHostIp: ""
    property string informationHostIp: ""
    property string switchHostIp: ""
    property string syslogConfigHostIp: ""

    readonly property bool isSwitchDevice: {
        const role = String(contentArea.deviceRole || "").trim().toLowerCase()
        return role === "sw2" || role === "sw3"
    }
    readonly property bool switchWorkspaceActive: contentArea.isSwitchDevice
                                                   && ((contentArea.activeFeatureName === ""
                                                        && contentArea.activeMainFeatureName === "Interface")
                                                       || ["Switching", "Services", "Security", "Monitoring"].indexOf(contentArea.activeFeatureName) !== -1)

    readonly property bool activeViewLoading: {
        if (contentArea.appMode !== "devices" || contentArea.tabCount <= 0)
            return false
        if (contentArea.activeViewLoadPending || contentArea.hostApplyPending)
            return true

        switch (contentArea.activeFeatureName) {
        case "Routing": return loaderIsBusy(routingLoader)
        case "DHCP": return loaderIsBusy(dhcpLoader)
        case "ACL": return loaderIsBusy(aclLoader)
        case "NAT": return loaderIsBusy(natLoader)
        case "FHRP": return loaderIsBusy(fhrpLoader)
        case "Syslog Server": return loaderIsBusy(syslogConfigLoader)
        case "Switching":
        case "Services":
        case "Security":
        case "Monitoring":
            return contentArea.isSwitchDevice ? loaderIsBusy(switchWorkspaceLoader) : false
        }

        if (contentArea.activeFeatureName === "") {
            if (contentArea.activeMainFeatureName === "Interface")
                return contentArea.isSwitchDevice
                     ? loaderIsBusy(switchWorkspaceLoader)
                     : loaderIsBusy(interfaceLoader)
            if (contentArea.activeMainFeatureName === "Information")
                return loaderIsBusy(informationLoader)
        }
        return false
    }

    // Index phải khớp với FeatureBar.allTextFeatures[i].globalIndex
    // 0=Routing,1=VLAN,2=DHCP,3=ACL,4=BGP,5=NAT,6=STP,7=SNMP,
    // 8=NTP,9=AAA,10=MPLS,11=VPN,12=Firewall,13=Monitor,
    // 14=Switching,15=Services,16=Security,17=Monitoring,18=FHRP,19=Syslog Server
    readonly property var textFeatureNames: [
        "Routing", "VLAN", "DHCP", "ACL", "BGP", "NAT",
        "STP", "SNMP", "NTP", "AAA", "MPLS",
        "VPN", "Firewall", "Monitor", "Switching", "Services",
        "Security", "Monitoring", "FHRP", "Syslog Server"
    ]
    readonly property var mainFeatureNames: ["Information", "CLI", "Interface"]

    property string activeFeatureName: activeTextFeature >= 0
                                       ? textFeatureNames[activeTextFeature]
                                       : ""
    property string activeMainFeatureName: activeMainFeature >= 0
                                           ? mainFeatureNames[activeMainFeature]
                                           : ""

    function loaderIsBusy(loader) {
        return loader.status === Loader.Loading
                || (loader.item !== null && loader.item.isViewLoading === true)
    }

    function cancelInactivePendingLoads() {
        if (routingLoader.status === Loader.Loading && activeFeatureName !== "Routing")
            routingViewLoaded = false
        if (dhcpLoader.status === Loader.Loading && activeFeatureName !== "DHCP")
            dhcpViewLoaded = false
        if (aclLoader.status === Loader.Loading && activeFeatureName !== "ACL")
            aclViewLoaded = false
        if (natLoader.status === Loader.Loading && activeFeatureName !== "NAT")
            natViewLoaded = false
        if (fhrpLoader.status === Loader.Loading && activeFeatureName !== "FHRP")
            fhrpViewLoaded = false
        if (syslogConfigLoader.status === Loader.Loading && activeFeatureName !== "Syslog Server")
            syslogConfigLoaded = false
        if (interfaceLoader.status === Loader.Loading
                && !(activeFeatureName === "" && activeMainFeatureName === "Interface"))
            interfaceViewLoaded = false
        if (informationLoader.status === Loader.Loading
                && !(activeFeatureName === "" && activeMainFeatureName === "Information"))
            informationViewLoaded = false
        if (switchWorkspaceLoader.status === Loader.Loading && !switchWorkspaceActive)
            switchWorkspaceLoaded = false
        if (settingsLoader.status === Loader.Loading && appMode !== "settings")
            settingsViewLoaded = false
        if (databaseLoader.status === Loader.Loading && appMode !== "database")
            databaseViewLoaded = false
    }

    function ensureActiveViewLoaded() {
        cancelInactivePendingLoads()
        syncHostToActiveView()
        switch (activeFeatureName) {
        case "Routing": routingViewLoaded = true; break
        case "DHCP": dhcpViewLoaded = true; break
        case "ACL": aclViewLoaded = true; break
        case "NAT": natViewLoaded = true; break
        case "FHRP": fhrpViewLoaded = true; break
        case "Syslog Server": syslogConfigLoaded = true; break
        }

        if (switchWorkspaceActive)
            switchWorkspaceLoaded = true
        else if (activeMainFeatureName === "Interface")
            interfaceViewLoaded = true
        else if (activeMainFeatureName === "Information")
            informationViewLoaded = true

        if (appMode === "settings")
            settingsViewLoaded = true
        else if (appMode === "database")
            databaseViewLoaded = true
    }

    function syncHostToActiveView() {
        switch (activeFeatureName) {
        case "Routing": routingHostIp = effectiveHostIp; return
        case "DHCP": dhcpHostIp = effectiveHostIp; return
        case "ACL": aclHostIp = effectiveHostIp; return
        case "NAT": natHostIp = effectiveHostIp; return
        case "FHRP": fhrpHostIp = effectiveHostIp; return
        case "Syslog Server": syslogConfigHostIp = effectiveHostIp; return
        case "Switching":
        case "Services":
        case "Security":
        case "Monitoring":
            if (isSwitchDevice) {
                switchHostIp = effectiveHostIp
                return
            }
        }

        if (activeFeatureName === "") {
            if (activeMainFeatureName === "Interface") {
                if (isSwitchDevice)
                    switchHostIp = effectiveHostIp
                else
                    interfaceHostIp = effectiveHostIp
            }
            else if (activeMainFeatureName === "Information")
                informationHostIp = effectiveHostIp
        }
    }

    function scheduleActiveViewLoad() {
        activeViewLoadPending = true
        activeViewLoadTimer.restart()
    }

    function isInformationActive() {
        return appMode === "devices"
                && tabCount > 0
                && activeFeatureName === ""
                && activeMainFeatureName === "Information"
    }

    readonly property bool reloadCommandEnabled: isInformationActive()
                                                  && informationLoader.item !== null
                                                  && String(informationHostIp || "").trim() !== ""
                                                  && !informationLoader.item.isLoadingLive

    function triggerReloadCommand() {
        if (!reloadCommandEnabled || !informationLoader.item.reloadData)
            return false
        return informationLoader.item.reloadData("shortcut", true)
    }

    property string pendingActivationReason: "activation"

    function activeFeatureLoader() {
        switch (activeFeatureName) {
        case "Routing": return routingLoader
        case "DHCP": return dhcpLoader
        case "ACL": return aclLoader
        case "NAT": return natLoader
        case "FHRP": return fhrpLoader
        case "Syslog Server": return syslogConfigLoader
        case "Switching":
        case "Services":
        case "Security":
        case "Monitoring":
            return isSwitchDevice ? switchWorkspaceLoader : null
        }

        if (activeFeatureName === "" && activeMainFeatureName === "Interface")
            return isSwitchDevice ? switchWorkspaceLoader : interfaceLoader
        return null
    }

    function reloadActiveView(reason) {
        const loader = activeFeatureLoader()
        if (loader === null || loader.item === null || !loader.item.reloadData)
            return false
        return loader.item.reloadData(reason || "activation")
    }

    function requestActivationReload(reason) {
        pendingActivationReason = reason || "activation"
        featureActivationTimer.restart()
    }

    function scheduleInformationActivationReload() {
        if (isInformationActive())
            informationActivationTimer.restart()
        else
            informationActivationTimer.stop()
    }

    onActiveFeatureNameChanged: {
        scheduleActiveViewLoad()
        scheduleInformationActivationReload()
        requestActivationReload("feature-activated")
    }
    onActiveMainFeatureNameChanged: {
        scheduleActiveViewLoad()
        scheduleInformationActivationReload()
        requestActivationReload("main-feature-activated")
    }
    onDeviceRoleChanged: scheduleActiveViewLoad()
    onAppModeChanged: {
        scheduleActiveViewLoad()
        scheduleInformationActivationReload()
    }
    onCurrentHostIpChanged: {
        pendingHostIp = String(currentHostIp || "")
        hostApplyPending = true
        hostApplyTimer.restart()
        informationActivationTimer.stop()
    }
    onTabCountChanged: scheduleInformationActivationReload()
    Component.onCompleted: {
        pendingHostIp = String(currentHostIp || "")
        hostApplyPending = true
        scheduleActiveViewLoad()
        hostApplyTimer.restart()
        scheduleInformationActivationReload()
    }

    Timer {
        id: activeViewLoadTimer
        interval: 0
        repeat: false
        onTriggered: {
            contentArea.ensureActiveViewLoaded()
            contentArea.activeViewLoadPending = false
        }
    }

    Timer {
        id: hostApplyTimer
        interval: Theme.viewLoadDispatchDelay
        repeat: false
        onTriggered: {
            contentArea.effectiveHostIp = contentArea.pendingHostIp
            contentArea.syncHostToActiveView()
            contentArea.hostApplyPending = false
            contentArea.scheduleInformationActivationReload()
        }
    }

    Timer {
        id: informationActivationTimer
        interval: 0
        repeat: false
        onTriggered: {
            if (contentArea.isInformationActive()
                    && informationLoader.item
                    && informationLoader.item.reloadData)
                informationLoader.item.reloadData("activation")
        }
    }

    Timer {
        id: featureActivationTimer
        interval: 0
        repeat: false
        onTriggered: contentArea.reloadActiveView(contentArea.pendingActivationReason)
    }

    function displayFeatureName(name) {
        switch (name) {
        case "Routing": return "Routing"
        case "VLAN": return "VLAN"
        case "DHCP": return "DHCP"
        case "ACL": return "ACL"
        case "NAT": return "NAT"
        case "FHRP": return "FHRP"
        case "Syslog Server": return "Syslog Server"
        case "STP": return "STP"
        case "SNMP": return "SNMP"
        case "NTP": return "NTP"
        case "AAA": return "AAA"
        case "MPLS": return "MPLS"
        case "VPN": return "VPN"
        case "Firewall": return "Firewall"
        case "Monitor": return "Monitor"
        case "Switching": return "Switching"
        case "Services": return "Services"
        case "Security": return "Security"
        case "Monitoring": return "Monitoring"
        default: return name
        }
    }

    function displayMainFeatureName(name) {
        switch (name) {
        case "Information": return "Information"
        case "CLI": return "CLI"
        case "Interface": return "Interface"
        default: return name
        }
    }

    // ── Áp dụng StackLayout để quản lý các màn hình chuyên nghiệp hơn ──
    StackLayout {
        anchors.fill: parent
        currentIndex: {
            if (contentArea.appMode === "settings") return 1
            if (contentArea.appMode === "database") return 2
            return 0
        }

        // ── INDEX 0: WORKSPACE (Quản lý thiết bị) ──
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Màn hình chào mừng
            WelcomeScreen {
                anchors.fill: parent
                visible: contentArea.tabCount === 0
            }

            // Khu vực làm việc
            Item {
                anchors.fill: parent
                visible: contentArea.tabCount > 0
                enabled: contentArea.hostConfigEnabled
                opacity: contentArea.hostConfigEnabled ? 1.0 : 0.4

                Behavior on opacity {
                    NumberAnimation { duration: Theme.animationDurationMedium }
                }

                // ── Routing ──────────────────────────────────────────────
                Loader {
                    id: routingLoader
                    objectName: "routingLoader"
                    anchors.fill: parent
                    active: contentArea.routingViewLoaded
                    asynchronous: true
                    visible: contentArea.activeFeatureName === "Routing"
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        RoutingView {
                            objectName: "loadedRoutingView"
                            currentHostIp: contentArea.routingHostIp
                        }
                    }
                }

                // ── DHCP ─────────────────────────────────────────────────
                Loader {
                    id: dhcpLoader
                    objectName: "dhcpLoader"
                    anchors.fill: parent
                    active: contentArea.dhcpViewLoaded
                    asynchronous: true
                    visible: contentArea.activeFeatureName === "DHCP"
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        DhcpView {
                            objectName: "loadedDhcpView"
                            currentHostIp: contentArea.dhcpHostIp
                        }
                    }
                }

                // ── ACL ──────────────────────────────────────────────────
                Loader {
                    id: aclLoader
                    objectName: "aclLoader"
                    anchors.fill: parent
                    active: contentArea.aclViewLoaded
                    asynchronous: true
                    visible: contentArea.activeFeatureName === "ACL"
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        AclView {
                            objectName: "loadedAclView"
                            currentHostIp: contentArea.aclHostIp
                        }
                    }
                }

                // ── NAT ──────────────────────────────────────────────────
                Loader {
                    id: natLoader
                    objectName: "natLoader"
                    anchors.fill: parent
                    active: contentArea.natViewLoaded
                    asynchronous: true
                    visible: contentArea.activeFeatureName === "NAT"
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        NatView {
                            objectName: "loadedNatView"
                            currentHostIp: contentArea.natHostIp
                        }
                    }
                }

                // ── FHRP ─────────────────────────────────────────────────
                Loader {
                    id: fhrpLoader
                    objectName: "fhrpLoader"
                    anchors.fill: parent
                    active: contentArea.fhrpViewLoaded
                    asynchronous: true
                    visible: contentArea.activeFeatureName === "FHRP"
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        FhrpView {
                            objectName: "loadedFhrpView"
                            currentHostIp: contentArea.fhrpHostIp
                        }
                    }
                }

                // ── Per-device Syslog destinations ─────────────────────
                Loader {
                    id: syslogConfigLoader
                    objectName: "syslogConfigLoader"
                    anchors.fill: parent
                    active: contentArea.syslogConfigLoaded
                    asynchronous: true
                    visible: contentArea.activeFeatureName === "Syslog Server"
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        SyslogDeviceConfigPage {
                            objectName: "loadedSyslogDeviceConfigPage"
                            host: contentArea.syslogConfigHostIp
                        }
                    }
                }

                Loader {
                    id: interfaceLoader
                    objectName: "interfaceLoader"
                    anchors.fill: parent
                    active: contentArea.interfaceViewLoaded && !contentArea.isSwitchDevice
                    asynchronous: true
                    visible: !contentArea.isSwitchDevice
                             && contentArea.activeFeatureName === ""
                             && contentArea.activeMainFeatureName === "Interface"
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        InterfaceView {
                            objectName: "loadedInterfaceView"
                            currentHostIp: contentArea.interfaceHostIp
                        }
                    }
                }

                Loader {
                    id: switchWorkspaceLoader
                    objectName: "switchWorkspaceLoader"
                    anchors.fill: parent
                    active: contentArea.switchWorkspaceLoaded
                    asynchronous: true
                    visible: contentArea.switchWorkspaceActive
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        SwitchWorkspace {
                            objectName: "loadedSwitchWorkspace"
                            host: contentArea.switchHostIp
                            deviceRole: contentArea.deviceRole
                            feature: contentArea.activeFeatureName === ""
                                     ? "interfaces"
                                     : contentArea.activeFeatureName.toLowerCase()
                        }
                    }
                }

                Loader {
                    id: informationLoader
                    objectName: "informationLoader"
                    anchors.fill: parent
                    active: contentArea.informationViewLoaded
                    asynchronous: true
                    visible: contentArea.activeFeatureName === ""
                             && contentArea.activeMainFeatureName === "Information"
                             && !contentArea.activeViewLoadPending
                             && !contentArea.hostApplyPending
                    sourceComponent: Component {
                        InformationView {
                            objectName: "loadedInformationView"
                            currentHostIp: contentArea.informationHostIp
                        }
                    }
                    onLoaded: contentArea.scheduleInformationActivationReload()
                }

                // ── Các feature chưa implement ───────────────────────────
                Text {
                    anchors.centerIn: parent
                    visible: contentArea.activeFeatureName !== ""
                             && !contentArea.switchWorkspaceActive
                             && contentArea.activeFeatureName !== "Routing"
                             && contentArea.activeFeatureName !== "DHCP"
                             && contentArea.activeFeatureName !== "ACL"
                             && contentArea.activeFeatureName !== "NAT"
                             && contentArea.activeFeatureName !== "FHRP"
                             && contentArea.activeFeatureName !== "Syslog Server"
                    text: "%1 — Not yet implemented".arg(contentArea.displayFeatureName(contentArea.activeFeatureName))
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeNormal
                }

                Text {
                    anchors.centerIn: parent
                    visible: contentArea.activeFeatureName === ""
                             && contentArea.activeMainFeatureName !== ""
                             && contentArea.activeMainFeatureName !== "Information"
                             && contentArea.activeMainFeatureName !== "Interface"
                    text: "%1 - Not yet implemented".arg(contentArea.displayMainFeatureName(contentArea.activeMainFeatureName))
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeNormal
                }

                Text {
                    anchors.centerIn: parent
                    visible: contentArea.activeFeatureName === ""
                             && contentArea.activeMainFeatureName === ""
                    text: "Choose a feature from the feature bar to get started"
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeNormal
                }
            }

            // Lớp phủ thông báo khi thiết bị đang ở trạng thái Waiting
            Rectangle {
                anchors.fill: parent
                visible: contentArea.tabCount > 0 && !contentArea.hostConfigEnabled
                color: "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "Device is waiting. Configuration is disabled until it connects."
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeNormal
                }
            }
        }

        // ── INDEX 1: SETTINGS ──
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Loader {
                id: settingsLoader
                objectName: "settingsLoader"
                anchors.fill: parent
                active: contentArea.settingsViewLoaded
                asynchronous: true
                sourceComponent: Component {
                    SettingsView {
                        objectName: "loadedSettingsView"
                        activeSettingKey: contentArea.activeSettingKey
                    }
                }
            }
        }

        // ── INDEX 2: DATABASE BROWSER ──
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Loader {
                id: databaseLoader
                objectName: "databaseLoader"
                anchors.fill: parent
                active: contentArea.databaseViewLoaded
                asynchronous: true
                sourceComponent: Component {
                    DatabaseBrowserView {
                        objectName: "loadedDatabaseView"
                        activeTable: contentArea.activeDatabaseTable
                    }
                }
            }
        }
    }
}
