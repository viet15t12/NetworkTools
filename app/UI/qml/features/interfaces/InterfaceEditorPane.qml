pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

SplitFormPane {
    id: editor

    property string currentHostIp: ""
    property string selectedKind: "L3"
    property string selectedType: "physical"
    property string activeInterfaceType: "physical"
    property var physicalInterfaceNames: []
    property int selectedIfaceId: -1
    property int viewPushRevision: 0
    property var ownerForm: null

    signal saveRequested(var payload, string interfaceName)
    signal virtualNameRequested(string interfaceType, var payload)

    spacing: Theme.spacing16

    function typeLabel(interfaceType) {
        if (interfaceType === "subinterface")
            return "802.1Q Subinterface"
        if (interfaceType === "loopback")
            return "Loopback"
        if (interfaceType === "tunnel")
            return "Tunnel"
        return "Physical"
    }

    function clearForm() {
        selectedIfaceId = -1
        selectedType = activeInterfaceType
        selectedKind = activeInterfaceType === "tunnel" ? "Tunnel"
                     : activeInterfaceType === "subinterface" ? "Subinterface" : "L3"
        ifaceField.text = ""
        virtualNumberField.text = activeInterfaceType === "subinterface" ? "1" : "0"
        virtualParentCombo.currentIndex = physicalInterfaceNames.length > 0 ? 0 : -1
        ipField.text = ""
        maskField.text = ""
        descriptionField.text = ""
        shutdownCheck.checked = false
        secondaryIpField.text = ""
        secondaryMaskField.text = ""
        mtuField.text = "1500"
        bandwidthField.text = ""
        delayField.text = ""
        speedCombo.currentIndex = 0
        duplexCombo.currentIndex = 0
        negotiationCheck.checked = true
        proxyArpCheck.checked = true
        unreachablesCheck.checked = true
        directedBroadcastCheck.checked = false
        tunnelModeCombo.currentIndex = 0
        tunnelSrcField.text = ""
        tunnelDstField.text = ""
        tunnelKeyField.text = ""
        keepaliveSecField.text = ""
        keepaliveRetryField.text = ""
        ipsecProfileField.text = ""
        encapCombo.currentIndex = 0
        pppoePoolField.text = ""
        pppAuthCombo.currentIndex = 0
        pppUsernameField.text = ""
        pppPasswordField.text = ""
        clockRateField.text = ""
        lmiCombo.currentIndex = 0
        parentInterfaceField.text = ""
        subinterfaceNumberField.text = ""
        subinterfaceVlanField.text = ""
        subinterfaceNativeCheck.checked = false
    }

    function applyRow(row) {
        clearForm()
        selectedIfaceId = Number(row.iface_id || -1)
        ifaceField.text = row.interface_name || ""
        ipField.text = row.ip_address || ""
        maskField.text = row.subnet_mask || ""
        descriptionField.text = row.description || ""
        shutdownCheck.checked = Number(row.shutdown || 0) === 1
        selectedKind = row.interface_kind || "L3"
        selectedType = row.interface_type || "physical"
        if (selectedType === "loopback" || selectedType === "tunnel") {
            const numberMatch = String(row.interface_name || "").match(/(\d+)$/)
            virtualNumberField.text = numberMatch ? numberMatch[1] : "0"
        }
        secondaryIpField.text = row.secondary_ip || ""
        secondaryMaskField.text = row.secondary_mask || ""
        mtuField.text = row.mtu ? String(row.mtu) : "1500"
        bandwidthField.text = row.bandwidth ? String(row.bandwidth) : ""
        delayField.text = row.delay ? String(row.delay) : ""
        speedCombo.currentIndex = Math.max(0, ["auto", "10", "100", "1000", "10000"].indexOf(row.speed || "auto"))
        duplexCombo.currentIndex = Math.max(0, ["auto", "full", "half"].indexOf(row.duplex || "auto"))
        negotiationCheck.checked = Number(row.negotiation === undefined ? 1 : row.negotiation) === 1
        proxyArpCheck.checked = Number(row.proxy_arp === undefined ? 1 : row.proxy_arp) === 1
        unreachablesCheck.checked = Number(row.unreachables === undefined ? 1 : row.unreachables) === 1
        directedBroadcastCheck.checked = Number(row.directed_broadcast || 0) === 1
        tunnelModeCombo.currentIndex = Math.max(0, ["gre", "ipip", "ipsec", "gre-ipsec"].indexOf(row.tunnel_mode || "gre"))
        tunnelSrcField.text = row.tunnel_src || ""
        tunnelDstField.text = row.tunnel_dst || ""
        tunnelKeyField.text = row.tunnel_key ? String(row.tunnel_key) : ""
        keepaliveSecField.text = row.keepalive_sec ? String(row.keepalive_sec) : ""
        keepaliveRetryField.text = row.keepalive_retry ? String(row.keepalive_retry) : ""
        ipsecProfileField.text = row.ipsec_profile || ""
        encapCombo.currentIndex = Math.max(0, ["none", "pppoe", "hdlc", "ppp", "frame-relay"].indexOf(row.encap_type || "none"))
        pppoePoolField.text = row.pppoe_dialer_pool ? String(row.pppoe_dialer_pool) : ""
        pppAuthCombo.currentIndex = Math.max(0, ["", "pap", "chap"].indexOf(row.ppp_auth || ""))
        pppUsernameField.text = row.ppp_username || ""
        pppPasswordField.text = row.ppp_password || ""
        clockRateField.text = row.clock_rate ? String(row.clock_rate) : ""
        lmiCombo.currentIndex = Math.max(0, ["", "cisco", "ansi", "q933a"].indexOf(row.lmi_type || ""))
        parentInterfaceField.text = row.parent_interface || ""
        subinterfaceNumberField.text = row.interface_type === "subinterface"
                                     ? String(row.interface_name || "").split(".").pop() : ""
        subinterfaceVlanField.text = row.subif_vlan_id ? String(row.subif_vlan_id) : ""
        subinterfaceNativeCheck.checked = Number(row.subif_native || 0) === 1
    }

    function beginInterface(name) {
        clearForm()
        ifaceField.text = name
        if (String(name).startsWith("Tunnel")) {
            selectedType = "tunnel"
            selectedKind = "Tunnel"
        } else if (String(name).startsWith("Loopback")) {
            selectedType = "loopback"
            selectedKind = "L3"
        } else if (String(name).indexOf(".") >= 0) {
            selectedType = "subinterface"
            selectedKind = "Subinterface"
            parentInterfaceField.text = String(name).split(".")[0]
            subinterfaceNumberField.text = String(name).split(".").pop()
        }
    }

    function beginVirtualInterface(interfaceType, interfaceName, parentName, number) {
        // The create controls always start a distinct draft.  Reusing the
        // selected pending iface_id here made a second subinterface rename
        // the first one instead of inserting another database row.
        clearForm()
        selectedType = interfaceType
        virtualNumberField.text = String(number)
        ifaceField.text = interfaceName
        if (interfaceType === "tunnel") {
            selectedKind = "Tunnel"
        } else if (interfaceType === "subinterface") {
            selectedKind = "Subinterface"
            parentInterfaceField.text = parentName || ""
            subinterfaceNumberField.text = String(number || "")
            subinterfaceVlanField.text = String(number || "")
        } else {
            selectedKind = "L3"
        }
    }

    onActiveInterfaceTypeChanged: clearForm()

    function payload() {
        return {
            "iface_id": selectedIfaceId,
            "host": currentHostIp,
            "interface_name": ifaceField.text.trim(),
            "interface_kind": selectedKind,
            "interface_type": selectedType,
            "ip_address": ipField.text.trim(),
            "subnet_mask": maskField.text.trim(),
            "description": descriptionField.text.trim(),
            "shutdown": shutdownCheck.checked,
            "secondary_ip": secondaryIpField.text.trim(),
            "secondary_mask": secondaryMaskField.text.trim(),
            "mtu": mtuField.text.trim(),
            "bandwidth": bandwidthField.text.trim(),
            "delay": delayField.text.trim(),
            "speed": speedCombo.currentValue,
            "duplex": duplexCombo.currentValue,
            "negotiation": negotiationCheck.checked,
            "proxy_arp": proxyArpCheck.checked,
            "unreachables": unreachablesCheck.checked,
            "directed_broadcast": directedBroadcastCheck.checked,
            "tunnel_mode": tunnelModeCombo.currentText,
            "tunnel_src": tunnelSrcField.text.trim(),
            "tunnel_dst": tunnelDstField.text.trim(),
            "tunnel_key": tunnelKeyField.text.trim(),
            "keepalive_sec": keepaliveSecField.text.trim(),
            "keepalive_retry": keepaliveRetryField.text.trim(),
            "ipsec_profile": ipsecProfileField.text.trim(),
            "encap_type": encapCombo.currentText,
            "pppoe_dialer_pool": pppoePoolField.text.trim(),
            "ppp_auth": pppAuthCombo.currentText,
            "ppp_username": pppUsernameField.text.trim(),
            "ppp_password": pppPasswordField.text.trim(),
            "clock_rate": clockRateField.text.trim(),
            "lmi_type": lmiCombo.currentText,
            "parent_interface": parentInterfaceField.text.trim(),
            "vlan_id": subinterfaceVlanField.text.trim(),
            "encapsulation": "dot1q",
            "native": subinterfaceNativeCheck.checked
        }
    }

    FormSection {
        Layout.fillWidth: true
        visible: editor.activeInterfaceType !== "physical"
        title: "Create " + editor.typeLabel(editor.activeInterfaceType)
        helpText: "Number: numeric suffix used to create a Loopback or Tunnel name. For a subinterface it is the suffix after the parent name, for example 10 in GigabitEthernet0/0.10.\n\n" +
                  "Parent interface: synchronized physical interface on which a subinterface is created. Create the generated name before entering the remaining settings."

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing12

            StandardTextField {
                id: virtualNumberField
                Layout.fillWidth: true
                labelText: editor.activeInterfaceType === "subinterface"
                           ? "Subinterface ID" : "Number"
                text: "0"
            }
            StandardComboBox {
                id: virtualParentCombo
                Layout.fillWidth: true
                visible: editor.activeInterfaceType === "subinterface"
                labelText: "Parent interface"
                model: editor.physicalInterfaceNames
                emptyText: "No synchronized physical interfaces"
            }
            StandardButton {
                Layout.alignment: Qt.AlignBottom
                text: editor.activeInterfaceType === "loopback" ? "Create Loopback"
                      : editor.activeInterfaceType === "tunnel" ? "Create Tunnel"
                      : "Create Subinterface"
                type: "Secondary"
                enabled: virtualNumberField.text.trim() !== ""
                         && (editor.activeInterfaceType !== "subinterface"
                             || virtualParentCombo.hasOptions)
                onClicked: editor.virtualNameRequested(
                    editor.activeInterfaceType,
                    {
                        "number": virtualNumberField.text.trim(),
                        "parent_interface": virtualParentCombo.currentText
                    }
                )
            }
        }
    }

    SectionTitle {
        Layout.fillWidth: true
        text: editor.selectedIfaceId > 0 ? "Edit router interface"
              : editor.activeInterfaceType === "physical"
                ? "Select a physical interface" : "New router interface"
    }

    Text {
        Layout.fillWidth: true
        text: editor.activeInterfaceType === "physical"
              ? "Physical interface names come from synchronized device data. Select an interface from the database list to edit it."
              : "Prepare a backend-generated interface name, then configure the fields for this interface type."
        color: Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSmall
        wrapMode: Text.WordWrap
    }

    FormSection {
        Layout.fillWidth: true
        title: "Identity and addressing"
        helpText: "Interface name: IOS interface identifier; physical names come from synchronized device data and virtual names are generated by the application.\n\n" +
                  "Profile: L3 for routed Ethernet settings or WAN for serial/PPP-style encapsulation.\n\n" +
                  "IPv4 address and Subnet mask: primary interface address; masks accept dotted decimal or CIDR such as /24.\n\n" +
                  "Description: optional operational note. Administratively down emits shutdown and disables forwarding."
        enabled: editor.activeInterfaceType !== "physical" || editor.selectedIfaceId > 0

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing12
            StandardTextField {
                id: ifaceField
                Layout.fillWidth: true
                labelText: "Interface name"
                placeholderText: editor.activeInterfaceType === "physical"
                                 ? "Select from synchronized interfaces"
                                 : "Generated by backend"
                readOnly: true
            }
            StandardComboBox {
                Layout.preferredWidth: 132
                labelText: "Profile"
                model: editor.selectedType === "physical"
                       ? ["L3", "WAN"] : [editor.selectedKind]
                valueModel: editor.selectedType === "physical"
                            ? ["L3", "WAN"] : [editor.selectedKind]
                currentIndex: editor.selectedType === "physical"
                              ? Math.max(0, ["L3", "WAN"].indexOf(editor.selectedKind))
                              : 0
                enabled: editor.selectedType === "physical"
                onActivated: editor.selectedKind = currentValue
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing12
            StandardNetworkField { id: ipField; Layout.fillWidth: true; inputKind: "ipv4"; labelText: "IPv4 address"; placeholderText: "192.168.1.1" }
            StandardNetworkField { id: maskField; Layout.fillWidth: true; inputKind: "subnet"; labelText: "Subnet mask"; placeholderText: "255.255.255.0 or /24" }
            StandardTextField { id: descriptionField; Layout.fillWidth: true; Layout.columnSpan: 2; labelText: "Description"; placeholderText: "Link purpose or peer" }
        }

        Flow {
            Layout.fillWidth: true
            spacing: Theme.spacing12
            StandardCheckBox { id: shutdownCheck; text: "Administratively down" }
        }
    }

    FormSection {
        Layout.fillWidth: true
        visible: editor.selectedKind === "L3" && editor.selectedType === "physical"
        enabled: editor.selectedIfaceId > 0
        title: "Layer 3 options"
        helpText: "Secondary IP/Mask: additional IPv4 subnet on the same interface.\n\n" +
                  "MTU: maximum Layer-3 packet size in bytes; 1500 is the common Ethernet default.\n\n" +
                  "Bandwidth: IOS informational bandwidth in Kbps used by routing metrics; it does not directly set link speed. Delay is the IOS interface delay value.\n\n" +
                  "Speed/Duplex/Negotiation: physical link settings; both ends must be compatible.\n\n" +
                  "Proxy ARP answers ARP for remote destinations. Unreachables permits ICMP unreachable messages. Directed broadcast is normally disabled for security."

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing12
            StandardNetworkField { id: secondaryIpField; Layout.fillWidth: true; inputKind: "ipv4"; labelText: "Secondary IP" }
            StandardNetworkField { id: secondaryMaskField; Layout.fillWidth: true; inputKind: "subnet"; labelText: "Secondary mask" }
            StandardTextField { id: mtuField; Layout.fillWidth: true; labelText: "MTU"; text: "1500" }
            StandardTextField { id: bandwidthField; Layout.fillWidth: true; labelText: "Bandwidth" }
            StandardTextField { id: delayField; Layout.fillWidth: true; labelText: "Delay" }
            StandardComboBox { id: speedCombo; Layout.fillWidth: true; labelText: "Speed"; model: ["Auto", "10", "100", "1000", "10000"]; valueModel: ["auto", "10", "100", "1000", "10000"] }
            StandardComboBox { id: duplexCombo; Layout.fillWidth: true; labelText: "Duplex"; model: ["Auto", "Full", "Half"]; valueModel: ["auto", "full", "half"] }
        }

        Flow {
            Layout.fillWidth: true
            spacing: Theme.spacing12
            StandardCheckBox { id: negotiationCheck; text: "Negotiation"; checked: true }
            StandardCheckBox { id: proxyArpCheck; text: "Proxy ARP"; checked: true }
            StandardCheckBox { id: unreachablesCheck; text: "Unreachables"; checked: true }
            StandardCheckBox { id: directedBroadcastCheck; text: "Directed broadcast" }
        }
    }

    FormSection {
        Layout.fillWidth: true
        visible: editor.selectedKind === "Tunnel"
        title: "Tunnel"
        helpText: "Mode: GRE, IP-in-IP, IPsec, or GRE protected by IPsec.\n\n" +
                  "Source: local IP or interface used as tunnel source. Destination: reachable peer IP.\n\n" +
                  "Key: optional tunnel identifier; both peers must match where the mode uses it.\n\n" +
                  "Keepalive sec / Retries: probe interval and missed-probe threshold.\n\n" +
                  "IPsec profile: existing IOS profile applied to IPsec-capable tunnel modes."

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing12
            StandardComboBox { id: tunnelModeCombo; Layout.fillWidth: true; labelText: "Mode"; model: ["gre", "ipip", "ipsec", "gre-ipsec"] }
            StandardTextField { id: tunnelSrcField; Layout.fillWidth: true; labelText: "Source" }
            StandardTextField { id: tunnelDstField; Layout.fillWidth: true; labelText: "Destination" }
            StandardTextField { id: tunnelKeyField; Layout.fillWidth: true; labelText: "Key" }
            StandardTextField { id: keepaliveSecField; Layout.fillWidth: true; labelText: "Keepalive sec" }
            StandardTextField { id: keepaliveRetryField; Layout.fillWidth: true; labelText: "Retries" }
            StandardTextField { id: ipsecProfileField; Layout.fillWidth: true; Layout.columnSpan: 3; labelText: "IPsec profile" }
        }
    }

    FormSection {
        Layout.fillWidth: true
        visible: editor.selectedKind === "Subinterface"
        title: "802.1Q subinterface"
        helpText: "Parent: physical interface carrying the 802.1Q trunk.\n\n" +
                  "Subinterface ID: numeric suffix of the generated interface name; it is locally significant.\n\n" +
                  "VLAN ID: 802.1Q VLAN tag, normally 1-4094.\n\n" +
                  "Native VLAN: sends this VLAN untagged. Only one native VLAN should be configured consistently across both ends of the trunk."

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing12
            StandardTextField { id: parentInterfaceField; Layout.fillWidth: true; labelText: "Parent"; readOnly: true }
            StandardTextField { id: subinterfaceNumberField; Layout.fillWidth: true; labelText: "Subinterface ID"; readOnly: true }
            StandardTextField { id: subinterfaceVlanField; Layout.fillWidth: true; labelText: "VLAN ID" }
            StandardCheckBox { id: subinterfaceNativeCheck; text: "Native VLAN" }
        }
    }

    FormSection {
        Layout.fillWidth: true
        visible: editor.selectedKind === "WAN"
        enabled: editor.selectedIfaceId > 0
        title: "WAN encapsulation"
        helpText: "Encapsulation: WAN framing or access method used on the interface. The peer must use a compatible mode.\n\n" +
                  "PPPoE pool: dialer-pool number associated with PPPoE.\n\n" +
                  "PPP auth: PAP or CHAP; Username/Password are the peer credentials.\n\n" +
                  "Clock rate: DCE serial clock value; configure only on the DCE side.\n\n" +
                  "LMI: Frame Relay management type (Cisco, ANSI, or Q933a), which must match the provider."

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: Theme.spacing12
            rowSpacing: Theme.spacing12
            StandardComboBox { id: encapCombo; Layout.fillWidth: true; labelText: "Encapsulation"; model: ["none", "pppoe", "hdlc", "ppp", "frame-relay"] }
            StandardTextField { id: pppoePoolField; Layout.fillWidth: true; labelText: "PPPoE pool" }
            StandardComboBox { id: pppAuthCombo; Layout.fillWidth: true; labelText: "PPP auth"; model: ["", "pap", "chap"] }
            StandardTextField { id: pppUsernameField; Layout.fillWidth: true; labelText: "PPP username" }
            StandardPasswordField { id: pppPasswordField; Layout.fillWidth: true; labelText: "PPP password" }
            StandardTextField { id: clockRateField; Layout.fillWidth: true; labelText: "Clock rate" }
            StandardComboBox { id: lmiCombo; Layout.fillWidth: true; labelText: "LMI"; model: ["", "cisco", "ansi", "q933a"] }
        }
    }

    Item { Layout.fillHeight: true }

    RowLayout {
        Layout.fillWidth: true
        spacing: Theme.spacing12
        StandardButton {
            Layout.fillWidth: true
            text: editor.selectedIfaceId > 0 ? "Update Interface" : "Save Interface"
            icon.source: AppAssets.actionSave
            type: "Primary"
            enabled: editor.currentHostIp !== "" && ifaceField.text.trim() !== ""
                     && (editor.selectedKind !== "Tunnel"
                         || (tunnelSrcField.text.trim() !== "" && tunnelDstField.text.trim() !== ""))
            onClicked: editor.saveRequested(editor.payload(), ifaceField.text.trim())
        }
        ViewPushButton {
            Layout.preferredWidth: 150
            visible: editor.selectedType === "loopback"
                     || editor.selectedType === "tunnel"
            controllerName: "interface"
            moduleName: "all"
            hostIp: editor.currentHostIp
            ownerForm: editor.ownerForm
            refreshKey: editor.viewPushRevision
        }
        StandardButton {
            Layout.preferredWidth: 110
            text: "Clear"
            type: "Secondary"
            onClicked: editor.clearForm()
        }
    }
}
