pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: featureBar
    color: Theme.featureBarBackground

    property var mainFeatures: [
        { id: "information", icon: AppAssets.navigationInformation,      tooltip: "Information" },
        { id: "cli",         icon: AppAssets.navigationTerminal,  tooltip: "Open NetworkTools Terminal" },
        { id: "interface",   icon: AppAssets.navigationInterface, tooltip: "Interface"   }
    ]

    property string deviceType: ""
    property string terminalState: "closed"

    function mainFeatureTooltip(feature) {
        if (feature.id !== "cli")
            return feature.tooltip
        switch (terminalState) {
        case "open": return "Focus NetworkTools Terminal (Open)"
        case "starting": return "NetworkTools Terminal is starting"
        case "disconnected": return "Restart NetworkTools Terminal (SSH ended)"
        case "error": return "Restart NetworkTools Terminal (Error)"
        default: return "Open NetworkTools Terminal"
        }
    }

    readonly property var allTextFeatures: [
        { id: "routing", label: "Routing", globalIndex: 0, implemented: true },
        { id: "vlan", label: "VLAN", globalIndex: 1, implemented: false },
        { id: "dhcp", label: "DHCP", globalIndex: 2, implemented: true },
        { id: "acl", label: "ACL", globalIndex: 3, implemented: true },
        { id: "bgp", label: "BGP", globalIndex: 4, implemented: false },
        { id: "nat", label: "NAT", globalIndex: 5, implemented: true },
        { id: "stp", label: "STP", globalIndex: 6, implemented: false },
        { id: "snmp", label: "SNMP", globalIndex: 7, implemented: false },
        { id: "ntp", label: "NTP", globalIndex: 8, implemented: false },
        { id: "aaa", label: "AAA", globalIndex: 9, implemented: false },
        { id: "mpls", label: "MPLS", globalIndex: 10, implemented: false },
        { id: "vpn", label: "VPN", globalIndex: 11, implemented: false },
        { id: "firewall", label: "Firewall", globalIndex: 12, implemented: false },
        { id: "monitor", label: "Monitor", globalIndex: 13, implemented: false },
        { id: "switching", label: "Switching", globalIndex: 14, implemented: true },
        { id: "services", label: "Services", globalIndex: 15, implemented: true },
        { id: "security", label: "Security", globalIndex: 16, implemented: true },
        { id: "monitoring", label: "Monitoring", globalIndex: 17, implemented: true },
        { id: "fhrp", label: "FHRP", globalIndex: 18, implemented: true },
        { id: "syslog", label: "Syslog Server", globalIndex: 19, implemented: true }
    ]

    property var textFeatures: featuresForDeviceType(deviceType)
    property int activeMain: 0
    property int activeText: -1

    signal userChangedFeature(int mIdx, int tIdx)
    signal cliOpenRequested()

    function normalizedDeviceType(value) {
        const text = String(value || "").trim().toLowerCase()
        if (text === "router" || text.indexOf("router") !== -1)
            return "router"
        if (text === "sw2" || text === "sw3")
            return text
        if (text.indexOf("switch") !== -1)
            return "sw2"
        return "unknown"
    }

    function featuresForDeviceType(value) {
        const type = normalizedDeviceType(value)
        let allowed = []
        if (type === "router")
            allowed = ["routing", "fhrp", "dhcp", "acl", "nat", "syslog"]
        else if (type === "sw2")
            allowed = ["switching", "security", "monitoring", "syslog"]
        else if (type === "sw3")
            allowed = ["switching", "routing", "fhrp", "services", "security", "monitoring", "syslog"]
        else
            return allTextFeatures
        const result = []

        for (let i = 0; i < allTextFeatures.length; i++) {
            if (allowed.indexOf(allTextFeatures[i].id) !== -1)
                result.push(allTextFeatures[i])
        }
        return result
    }

    function isTextFeatureAllowed(globalIndex) {
        for (let i = 0; i < textFeatures.length; i++) {
            if (textFeatures[i].globalIndex === globalIndex)
                return true
        }
        return false
    }

    onTextFeaturesChanged: {
        if (activeText >= 0 && !isTextFeatureAllowed(activeText)) {
            activeMain = 0
            activeText = -1
            userChangedFeature(0, -1)
        }
    }

    Row {
        anchors.fill: parent

        Row {
            id: mainFeaturesRow
            height: parent.height

            Repeater {
                model: featureBar.mainFeatures
                delegate: MainFeatureItem {
                    id: mainItemDelegate
                    required property int index
                    required property var modelData
                    iconSource: modelData.icon
                    tooltipText: featureBar.mainFeatureTooltip(modelData)
                    isActive: featureBar.activeMain === index

                    onClicked: {
                        if (modelData.id === "cli") {
                            mainItemDelegate.triggerFlash()
                            featureBar.cliOpenRequested()
                        } else {
                            featureBar.activeMain = index
                            featureBar.activeText = -1
                            featureBar.userChangedFeature(index, -1)
                        }
                    }
                }
            }
        }

        Rectangle {
            width: Theme.borderWidth; height: parent.height - 12
            anchors.verticalCenter: parent.verticalCenter; color: Theme.borderColor
        }

        Item {
            id: textFeaturesArea
            width: parent.width - mainFeaturesRow.width - 1 - moreBtn.width
            height: parent.height

            ListView {
                id: textFeatureList
                anchors.fill: parent; orientation: ListView.Horizontal; clip: true
                model: featureBar.textFeatures

                Behavior on contentX { NumberAnimation { duration: Theme.animationDurationMedium; easing.type: Easing.OutQuad } }

                delegate: TextFeatureItem {
                    required property int index
                    required property var modelData
                    height: textFeatureList.height; label: modelData.label
                    selectable: modelData.implemented
                    isActive: featureBar.activeText === modelData.globalIndex
                    onClicked: {
                        featureBar.activeText = modelData.globalIndex
                        featureBar.activeMain = -1
                        featureBar.userChangedFeature(-1, modelData.globalIndex)
                    }
                }
                ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AlwaysOff }
            }
        }

        Rectangle {
            id: moreBtn
            visible: featureBar.textFeatures.length > 0
            width: visible ? 28 : 0
            height: parent.height
            color: moreBtnHover.hovered ? Theme.sideBarItemHover : "transparent"
            ThemedIcon {
                anchors.centerIn: parent
                iconSource: AppAssets.navigationChevronRight
                iconSize: Theme.iconSizeSmall
                iconColor: Theme.textSecondary
            }
            HoverHandler { id: moreBtnHover }
            TapHandler {
                onTapped: {
                    if (dropdown.visible) {
                        dropdown.hide()
                    } else {
                        const hidden = []
                        for (let i = 0; i < featureBar.textFeatures.length; i++) {
                            const itemX = textFeatureList.contentItem.children[i]
                            if (itemX && (itemX.x < textFeatureList.contentX ||
                                itemX.x + itemX.width > textFeatureList.contentX + textFeatureList.width)) {
                                hidden.push(featureBar.textFeatures[i])
                            }
                        }
                        dropdown.hiddenFeatures = hidden.length > 0 ? hidden : featureBar.textFeatures
                        dropdown.visible = true
                    }
                }
            }
        }
    }

    FeatureDropdown {
        id: dropdown
        anchors.right: parent.right; anchors.top: parent.bottom

        onFeatureSelected: function(globalIndex) {
            featureBar.activeText = globalIndex
            featureBar.activeMain = -1
            featureBar.userChangedFeature(-1, globalIndex)
        }
    }

    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Theme.borderWidth; color: Theme.borderColor }
}
