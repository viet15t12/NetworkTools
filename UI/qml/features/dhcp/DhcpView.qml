pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: dhcpView
    color: Theme.contentBackground

    property string currentHostIp: ""
    property string currentTab:    "Pool"
    property int viewPushRevision: 0
    property bool poolLoaded: true
    property bool excludedLoaded: false
    property bool helperLoaded: false
    property bool infoLoaded: false
    property string poolHostIp: ""
    property string excludedHostIp: ""
    property string helperHostIp: ""
    readonly property bool isViewLoading: {
        switch (currentTab) {
        case "Pool": return poolLoader.status === Loader.Loading
        case "Excluded": return excludedLoader.status === Loader.Loading
        case "Helper": return helperLoader.status === Loader.Loading
        case "Info": return infoLoader.status === Loader.Loading
        default: return false
        }
    }

    function activeLoader() {
        switch (currentTab) {
        case "Pool": return poolLoader
        case "Excluded": return excludedLoader
        case "Helper": return helperLoader
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

    function reloadData(reason) {
        const loader = activeLoader()
        const item = loader ? loader.item : null
        if (!item || hasUnsavedChanges(item))
            return false
        if (item.reloadData)
            return item.reloadData(reason || "activation")
        if (currentTab === "Pool" && item.reloadPools)
            item.reloadPools()
        else if (currentTab === "Excluded" && item.reloadExcluded)
            item.reloadExcluded()
        else if (currentTab === "Helper" && item.reloadAll)
            item.reloadAll()
        else
            return false
        refreshViewPush()
        return true
    }

    function activateTab(tabName) {
        currentTab = tabName
        syncHostToCurrentTab()
        ensureCurrentTabLoaded()
        activationReloadTimer.restart()
    }

    function ensureCurrentTabLoaded() {
        if (poolLoader.status === Loader.Loading && currentTab !== "Pool")
            poolLoaded = false
        if (excludedLoader.status === Loader.Loading && currentTab !== "Excluded")
            excludedLoaded = false
        if (helperLoader.status === Loader.Loading && currentTab !== "Helper")
            helperLoaded = false
        if (infoLoader.status === Loader.Loading && currentTab !== "Info")
            infoLoaded = false

        switch (currentTab) {
        case "Pool": poolLoaded = true; break
        case "Excluded": excludedLoaded = true; break
        case "Helper": helperLoaded = true; break
        case "Info": infoLoaded = true; break
        }
    }

    function syncHostToCurrentTab() {
        switch (currentTab) {
        case "Pool": poolHostIp = currentHostIp; break
        case "Excluded": excludedHostIp = currentHostIp; break
        case "Helper": helperHostIp = currentHostIp; break
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
        onTriggered: dhcpView.reloadData("subfeature-activated")
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function refreshViewPush() {
        viewPushRevision++
    }

    function reloadDhcpData() {
        if (poolLoader.item)
            poolLoader.item.reloadPools()
        if (excludedLoader.item)
            excludedLoader.item.reloadExcluded()
        if (helperLoader.item)
            helperLoader.item.reloadAll()
        refreshViewPush()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing:      0

        // 1. Thanh tab con
        DhcpSubBar {
            Layout.fillWidth: true
            activeTab:        dhcpView.currentTab
            onTabClicked:     (tabName) => dhcpView.activateTab(tabName)
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            color: Theme.contentSurface
            border.width: 0

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
                        text: "DHCP Information"
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeLarge
                        font.family: Theme.fontFamily
                        font.bold: true
                    }

                    Text {
                        text: String(dhcpView.currentHostIp || "").trim() === ""
                            ? "No device selected"
                            : dhcpView.currentHostIp
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSmall
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                ViewPushButton {
                    type: "Primary"
                    controllerName: "dhcp"
                    moduleName: "all"
                    hostIp: dhcpView.currentHostIp
                    ownerForm: dhcpView
                    refreshKey: dhcpView.viewPushRevision
                    onPushCompleted: function(ok, message) {
                        if (ok)
                            dhcpView.reloadDhcpData()
                    }
                }
            }
        }

        // 2. Vùng nội dung
        Item {
            Layout.fillWidth:  true
            Layout.fillHeight: true

            // ── Info ──────────────────────────────────────────────
            // Phase D: converted from static Text to Loader (consistent with other tabs).
            // When DhcpInfoView is implemented, replace the placeholder component.
            Loader {
                id: infoLoader
                objectName: "dhcpInfoLoader"
                anchors.fill: parent
                active: dhcpView.infoLoaded
                asynchronous: true
                visible:      dhcpView.currentTab === "Info"
                sourceComponent: Component {
                    Item {
                        Text {
                            anchors.centerIn: parent
                            text:             "DHCP Info — Not yet implemented"
                            color:            Theme.textDisabled
                            font.pixelSize:   Theme.fontSizeNormal
                            font.family:      Theme.fontFamily
                        }
                    }
                }
            }

            // ── Pool ──────────────────────────────────────────────
            Loader {
                id: poolLoader
                objectName: "dhcpPoolLoader"
                anchors.fill:  parent
                active: dhcpView.poolLoaded
                asynchronous: true
                visible: dhcpView.currentTab === "Pool"
                sourceComponent: Component {
                    DhcpPoolForm {
                        currentHostIp: dhcpView.poolHostIp
                        onDataChanged: dhcpView.refreshViewPush()
                    }
                }
            }

            // ── Excluded Address ──────────────────────────────────
            Loader {
                id: excludedLoader
                objectName: "dhcpExcludedLoader"
                anchors.fill:  parent
                active: dhcpView.excludedLoaded
                asynchronous: true
                visible: dhcpView.currentTab === "Excluded"
                sourceComponent: Component {
                    DhcpExcludedForm {
                        currentHostIp: dhcpView.excludedHostIp
                        onDataChanged: dhcpView.refreshViewPush()
                    }
                }
            }

            // -- Helper Address --------------------------------------------
            Loader {
                id: helperLoader
                objectName: "dhcpHelperLoader"
                anchors.fill: parent
                active: dhcpView.helperLoaded
                asynchronous: true
                visible: dhcpView.currentTab === "Helper"
                sourceComponent: Component {
                    DhcpHelperForm {
                        currentHostIp: dhcpView.helperHostIp
                        onDataChanged: dhcpView.refreshViewPush()
                    }
                }
            }
        }
    }

    onCurrentHostIpChanged: {
        syncHostToCurrentTab()
        refreshViewPush()
    }
}
