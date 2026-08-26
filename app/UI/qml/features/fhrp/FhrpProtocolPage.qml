pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "fhrpProtocolPage"

    component SummaryTile: Rectangle {
        required property string label
        required property string value
        required property string detail
        property color valueColor: Theme.textPrimary

        Layout.fillWidth: true
        implicitHeight: 78
        radius: Theme.radiusSmall
        color: Theme.contentPanelSurface
        border.color: Theme.contentPanelBorder
        border.width: Theme.borderWidth

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.spacing12
            spacing: Theme.spacing2
            Text {
                text: label
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                font.capitalization: Font.AllUppercase
            }
            Text {
                text: value
                color: valueColor
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeLarge
                font.bold: true
            }
            Text {
                Layout.fillWidth: true
                text: detail
                color: Theme.textDisabled
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                elide: Text.ElideRight
            }
        }
    }

    required property string protocol
    property string currentHostIp: ""
    property var hostOptions: []
    property var matchingInterfaces: []
    property var pendingPushHosts: []
    property string errorText: ""
    property bool operationBusy: false
    property string groupAuthType: "none"
    property string groupAuthSecret: ""
    property int protocolVersion: 2
    property int helloMs: 3000
    property int holdMs: 10000
    property int advertisementMs: 1000
    property string loadBalancing: "round-robin"
    property alias savedGroupModel: groupModel
    readonly property int maxHosts: 5
    readonly property bool isViewLoading: false
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property string protocolTitle: protocol === "hsrp"
                                                   ? "Hot Standby Router Protocol"
                                                   : protocol === "vrrp"
                                                     ? "Virtual Router Redundancy Protocol"
                                                     : "Gateway Load Balancing Protocol"
    readonly property string protocolSummary: protocol === "glbp"
                                             ? "Share gateway traffic while preserving failover."
                                             : "Build a resilient virtual gateway across multiple routers."
    readonly property string groupRange: protocol === "vrrp" ? "1–255"
                                         : protocol === "glbp" ? "0–1023"
                                         : protocolVersion === 1 ? "0–255" : "0–4095"
    readonly property bool readyToSave: memberModel.count >= 2
                                        && matchedHostCount() === memberModel.count
                                        && groupField.text.trim() !== ""
                                        && gatewayField.text.trim() !== ""

    color: Theme.contentBackground

    ListModel { id: memberModel }
    ListModel { id: groupModel }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function reloadData(reason) {
        loadOptions()
        loadGroups()
        return true
    }

    function loadOptions() {
        const result = dbManager.getFhrpOptions()
        hostOptions = result && result.hosts ? result.hosts : []
    }

    function loadGroups() {
        groupModel.clear()
        const result = dbManager.getFhrpGroups(currentHostIp)
        const rows = result && result.groups ? result.groups : []
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            if (String(row.protocol || "").toLowerCase() === root.protocol) {
                groupModel.append({
                    fhrp_id: Number(row.fhrp_id || 0),
                    protocol: String(row.protocol || ""),
                    group_number: Number(row.group_number || 0),
                    virtual_ip: String(row.virtual_ip || ""),
                    address_family: String(row.address_family || "ipv4"),
                    description: row.description === undefined
                                 || row.description === null
                                 ? "" : String(row.description),
                    updated_at: String(row.updated_at || ""),
                    members: row.members || []
                })
            }
        }
        refreshPendingPushHosts()
    }

    function collectionCount(collection) {
        if (!collection)
            return 0
        if (typeof collection.count === "number")
            return collection.count
        return collection.length || 0
    }

    function collectionItem(collection, index) {
        return collection && typeof collection.get === "function"
                ? collection.get(index) : collection[index]
    }

    function refreshPendingPushHosts() {
        const hosts = []
        const seen = ({})
        for (let groupIndex = 0; groupIndex < groupModel.count; groupIndex++) {
            const members = groupModel.get(groupIndex).members
            for (let memberIndex = 0;
                    memberIndex < collectionCount(members); memberIndex++) {
                const member = collectionItem(members, memberIndex)
                const status = String(member.sync_status || "")
                const host = String(member.host || "").trim()
                if ((status === "pending_apply" || status === "pending_delete")
                        && host !== "" && !seen[host]) {
                    seen[host] = true
                    hosts.push(host)
                }
            }
        }
        pendingPushHosts = hosts
    }

    function openViewPush() {
        if (pendingPushHosts.length === 0 || operationBusy)
            return
        operationBusy = true
        batchDialog.openPreview(pendingPushHosts, protocol)
    }

    function findMemberIndex(host) {
        for (let i = 0; i < memberModel.count; i++) {
            if (memberModel.get(i).host === host)
                return i
        }
        return -1
    }

    function toggleHost(host, selected) {
        const index = findMemberIndex(host)
        if (selected && index < 0) {
            if (memberModel.count >= maxHosts) {
                errorText = "FHRP supports at most " + maxHosts + " hosts."
                return
            }
            memberModel.append({
                host: host,
                ifaceId: 0,
                interfaceKind: "router",
                priority: "100",
                preempt: true,
                preemptDelayMinSec: 0,
                preemptDelayReloadSec: 0,
                weightingMax: 100,
                weightingLower: 0,
                weightingUpper: 0,
                forwarderPreempt: true,
                forwarderPreemptDelaySec: 30,
                tracksJson: "[]"
            })
        } else if (!selected && index >= 0) {
            memberModel.remove(index)
        }
        errorText = ""
        refreshMatchingInterfaces()
    }

    function selectedHosts() {
        const hosts = []
        for (let i = 0; i < memberModel.count; i++)
            hosts.push(memberModel.get(i).host)
        return hosts
    }

    function matchedHostCount() {
        let count = 0
        for (let i = 0; i < memberModel.count; i++) {
            if (interfaceOptionsForHost(memberModel.get(i).host).length > 0)
                count++
        }
        return count
    }

    function interfaceOptionsForHost(host) {
        return (matchingInterfaces || []).filter(
                    item => item.host === host)
    }

    function clearMemberMatches() {
        for (let i = 0; i < memberModel.count; i++) {
            memberModel.setProperty(i, "ifaceId", 0)
            memberModel.setProperty(i, "interfaceKind", "router")
        }
    }

    function resetDraft() {
        memberModel.clear()
        matchingInterfaces = []
        groupField.clear()
        gatewayField.clear()
        descriptionField.clear()
        groupAuthType = "none"
        groupAuthSecret = ""
        protocolVersion = 2
        helloMs = 3000
        holdMs = 10000
        advertisementMs = 1000
        loadBalancing = "round-robin"
        errorText = ""
    }

    function updateProtocolOption(field, value) {
        if (field === "version") {
            protocolVersion = Number(value)
            if (protocol === "hsrp" && protocolVersion === 1
                    && groupAuthType.indexOf("md5-") === 0) {
                groupAuthType = "none"
                groupAuthSecret = ""
            }
        } else if (field === "hello_ms")
            helloMs = Number(value)
        else if (field === "hold_ms")
            holdMs = Number(value)
        else if (field === "advertisement_ms")
            advertisementMs = Number(value)
        else if (field === "load_balancing")
            loadBalancing = String(value)
    }

    function refreshMatchingInterfaces() {
        const gateway = gatewayField.text.trim()
        if (gateway === "" || memberModel.count === 0) {
            matchingInterfaces = []
            clearMemberMatches()
            return
        }
        const result = dbManager.getFhrpMatchingInterfaces(
            selectedHosts(), gateway)
        if (!result.ok) {
            errorText = String(result.message || "")
            matchingInterfaces = []
            clearMemberMatches()
            return
        }
        errorText = ""
        matchingInterfaces = result.interfaces || []
        for (let i = 0; i < memberModel.count; i++) {
            const host = memberModel.get(i).host
            const options = interfaceOptionsForHost(host)
            const current = Number(memberModel.get(i).ifaceId || 0)
            const currentKind = String(memberModel.get(i).interfaceKind || "router")
            if (!options.some(item => Number(item.iface_id) === current
                              && String(item.interface_kind) === currentKind)) {
                memberModel.setProperty(i, "ifaceId",
                                        options.length > 0 ? Number(options[0].iface_id) : 0)
                memberModel.setProperty(i, "interfaceKind",
                                        options.length > 0
                                        ? String(options[0].interface_kind) : "router")
            }
        }
    }

    function updateMember(index, field, value) {
        if (field === "interfaceKey") {
            const parts = String(value || "").split(":")
            memberModel.setProperty(index, "interfaceKind", parts[0] || "router")
            memberModel.setProperty(index, "ifaceId", Number(parts[1] || 0))
            return
        }
        if (field === "tracks") {
            memberModel.setProperty(index, "tracksJson", JSON.stringify(value || []))
            return
        }
        memberModel.setProperty(index, field, value)
    }

    function parseTracks(value) {
        try {
            const parsed = JSON.parse(String(value || "[]"))
            return Array.isArray(parsed) ? parsed : []
        } catch (error) {
            return []
        }
    }

    function memberPayload() {
        const members = []
        for (let i = 0; i < memberModel.count; i++) {
            const row = memberModel.get(i)
            members.push({
                host: row.host,
                iface_id: Number(row.ifaceId),
                interface_kind: String(row.interfaceKind || "router"),
                priority: Number(row.priority),
                preempt: row.preempt,
                shutdown: false,
                auth_type: root.groupAuthType,
                auth_secret: root.groupAuthSecret,
                version: root.protocolVersion,
                hello_ms: root.helloMs,
                hold_ms: root.holdMs,
                advertisement_ms: root.advertisementMs,
                load_balancing: root.loadBalancing,
                preempt_delay_min_sec: Number(row.preemptDelayMinSec || 0),
                preempt_delay_reload_sec: Number(row.preemptDelayReloadSec || 0),
                weighting_max: Number(row.weightingMax || 100),
                weighting_lower: Number(row.weightingLower || 0) > 0
                                 ? Number(row.weightingLower) : null,
                weighting_upper: Number(row.weightingUpper || 0) > 0
                                 ? Number(row.weightingUpper) : null,
                forwarder_preempt: Boolean(row.forwarderPreempt),
                forwarder_preempt_delay_sec:
                    Number(row.forwarderPreemptDelaySec || 0),
                tracks: parseTracks(row.tracksJson)
            })
        }
        return members
    }

    function saveGroup() {
        errorText = ""
        if (groupField.text.trim() === "") {
            errorText = root.protocol === "vrrp"
                        ? "Enter a VRID." : "Enter a group number."
            return
        }
        if (gatewayField.text.trim() === "") {
            errorText = "Enter a Default Gateway IP."
            return
        }
        if (memberModel.count < 2) {
            errorText = "Select at least two hosts."
            return
        }
        for (let i = 0; i < memberModel.count; i++) {
            if (Number(memberModel.get(i).ifaceId || 0) <= 0) {
                errorText = "No matching interface for " + memberModel.get(i).host + "."
                return
            }
        }
        const result = dbManager.saveFhrpGroup({
            protocol: root.protocol,
            group_number: groupField.text.trim(),
            default_gateway: gatewayField.text.trim(),
            description: descriptionField.text.trim(),
            members: memberPayload()
        })
        if (!result.ok) {
            errorText = String(result.message || "Could not save FHRP group.")
            notify(errorText, "error")
            return
        }
        notify(String(result.message || ""), "success")
        loadGroups()
    }

    function deleteGroup(fhrpId) {
        const result = dbManager.deleteFhrpGroup(Number(fhrpId))
        notify(String(result.message || ""), result.ok ? "success" : "error")
        if (result.ok)
            loadGroups()
    }

    function cancelGroupDelete(fhrpId) {
        const result = dbManager.cancelFhrpGroupDelete(Number(fhrpId))
        notify(String(result.message || ""), result.ok ? "success" : "error")
        if (result.ok)
            loadGroups()
    }

    onCurrentHostIpChanged: loadGroups()
    Component.onCompleted: {
        loadOptions()
        loadGroups()
    }

    Connections {
        target: typeof dbManager !== "undefined" ? dbManager : null

        function onRunningConfigUpdated(updatedHost) {
            const host = String(updatedHost || "").trim()
            if (host !== "" && root.visible)
                root.reloadData("backgroundSync")
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            color: Theme.contentSurface

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.borderWidth
                color: Theme.borderColor
            }

            WorkspaceHeader {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacing24
                anchors.rightMargin: Theme.spacing24
                title: root.protocolTitle
                subtitle: root.protocol.toUpperCase() + " · " + root.protocolSummary

                StandardButton {
                    objectName: "fhrpReloadButton"
                    text: "Reload UI"
                    icon.source: AppAssets.actionDatabaseReload
                    type: "Secondary"
                    autoCompact: false
                    width: Math.ceil(expandedImplicitWidth)
                    Layout.minimumWidth: expandedImplicitWidth
                    onClicked: {
                        root.reloadData("manual")
                        root.notify("Reloaded FHRP options and saved groups.", "info")
                    }
                }

                StandardButton {
                    objectName: "fhrpViewPushButton"
                    text: "View & Push"
                    icon.source: AppAssets.actionPush
                    type: "Primary"
                    enabled: root.pendingPushHosts.length > 0
                             && !root.operationBusy
                    tooltip: enabled ? ""
                                     : "No FHRP configuration is waiting for Push."
                    onClicked: root.openViewPush()
                }
            }
        }

        SplitView {
            id: workspaceSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { orientation: workspaceSplit.orientation }

            SplitFormPane {
                id: fhrpFormPane
                objectName: "fhrpFormPane"
                width: 560
                height: 420
                SplitView.fillWidth: !root.compactLayout
                SplitView.fillHeight: root.compactLayout
                SplitView.preferredWidth: root.compactLayout
                                          ? workspaceSplit.width
                                          : workspaceSplit.width * 0.68
                SplitView.minimumWidth: root.compactLayout ? 0 : 560
                SplitView.minimumHeight: root.compactLayout ? 420 : 0

                Binding on width {
                    when: root.compactLayout
                    value: workspaceSplit.width
                }
                Binding on height {
                    when: !root.compactLayout
                    value: workspaceSplit.height
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: protocolHero.implicitHeight + Theme.spacing24
                    radius: Theme.cardRadius
                    color: Theme.alertInfoSubtle
                    border.color: Theme.accentColor
                    border.width: Theme.borderWidth

                    RowLayout {
                        id: protocolHero
                        anchors.fill: parent
                        anchors.margins: Theme.spacing12
                        spacing: Theme.spacing12

                        Rectangle {
                            Layout.preferredWidth: 42
                            Layout.preferredHeight: 42
                            radius: Theme.radiusSmall
                            color: Theme.accentEmphasis
                            Text {
                                anchors.centerIn: parent
                                text: root.protocol.toUpperCase().slice(0, 2)
                                color: Theme.buttonTextSolid
                                font.family: Theme.fontFamily
                                font.bold: true
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing2
                            Text {
                                Layout.fillWidth: true
                                text: "Create a resilient gateway"
                                color: Theme.textPrimary
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeNormal
                                font.bold: true
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "Choose the virtual IP first; eligible interfaces are matched automatically by subnet."
                                color: Theme.textSecondary
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeSmall
                                wrapMode: Text.WordWrap
                            }
                        }

                        StandardBadge {
                            text: "GROUP " + root.groupRange
                            badgeColor: Theme.accentEmphasis
                        }
                    }
                }

                GridLayout {
                    objectName: "fhrpSummaryGrid"
                    Layout.fillWidth: true
                    columns: width < 700 ? 1 : 3
                    columnSpacing: Theme.spacing8
                    rowSpacing: Theme.spacing8

                    SummaryTile {
                        label: "Selected routers"
                        value: String(memberModel.count)
                        detail: memberModel.count >= 2 ? "Minimum reached" : "Choose at least two"
                        valueColor: memberModel.count >= 2
                                    ? Theme.statusConnected : Theme.alertWarning
                    }
                    SummaryTile {
                        label: "Gateway matches"
                        value: root.matchedHostCount() + " / " + memberModel.count
                        detail: gatewayField.text.trim() === ""
                                ? "Enter a virtual IP" : "Matched by connected subnet"
                        valueColor: memberModel.count > 0
                                    && root.matchedHostCount() === memberModel.count
                                    ? Theme.statusConnected : Theme.textPrimary
                    }
                    SummaryTile {
                        label: "Saved groups"
                        value: String(groupModel.count)
                        detail: root.currentHostIp || "All connected devices"
                        valueColor: Theme.accentColor
                    }
                }

                InlineMessage {
                    Layout.fillWidth: true
                    visible: root.errorText !== ""
                    severity: "warning"
                    message: root.errorText
                }

                FormSection {
                    Layout.fillWidth: true
                    title: "Gateway identity"
                    GridLayout {
                        Layout.fillWidth: true
                        columns: width < 700 ? 1 : 2
                        columnSpacing: Theme.spacing12
                        rowSpacing: Theme.spacing8
                        StandardTextField {
                            id: groupField
                            Layout.fillWidth: true
                            labelText: root.protocol === "vrrp" ? "VRID" : "Group number"
                            placeholderText: root.groupRange
                            inputMethodHints: Qt.ImhDigitsOnly
                        }
                        StandardNetworkField {
                            id: gatewayField
                            Layout.fillWidth: true
                            inputKind: "ipv4"
                            labelText: "Default Gateway IP"
                            placeholderText: "192.168.10.1"
                            onTextEdited: matchingTimer.restart()
                        }
                        StandardTextField {
                            id: descriptionField
                            Layout.fillWidth: true
                            Layout.columnSpan: width < 700 ? 1 : 2
                            labelText: "Description"
                            placeholderText: "e.g. Campus users default gateway"
                        }
                    }
                }

                FormSection {
                    Layout.fillWidth: true
                    title: "Participating routers"

                    Text {
                        Layout.fillWidth: true
                        text: "Select two or more connected routers or Layer 3 switches."
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        wrapMode: Text.WordWrap
                    }

                    GridLayout {
                        objectName: "fhrpHostPicker"
                        Layout.fillWidth: true
                        columns: width < 700 ? 1 : 2
                        columnSpacing: Theme.spacing8
                        rowSpacing: Theme.spacing8

                        Repeater {
                            model: root.hostOptions
                            delegate: Rectangle {
                                id: hostCard
                                required property var modelData
                                readonly property bool selected: root.findMemberIndex(
                                                                     modelData.host) >= 0
                                Layout.fillWidth: true
                                implicitHeight: 62
                                radius: Theme.radiusSmall
                                color: selected
                                       ? Theme.alertInfoSubtle : Theme.contentBackground
                                border.color: selected
                                              ? Theme.accentColor : Theme.contentPanelBorder
                                border.width: Theme.borderWidth

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: Theme.spacing8
                                    spacing: Theme.spacing8
                                    StandardCheckBox {
                                        checked: hostCard.selected
                                        onToggled: root.toggleHost(
                                                       hostCard.modelData.host, checked)
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: Theme.spacing2
                                        Text {
                                            Layout.fillWidth: true
                                            text: hostCard.modelData.device_name || "Router"
                                            color: Theme.textPrimary
                                            font.family: Theme.fontFamily
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: hostCard.modelData.host
                                            color: Theme.textSecondary
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fontSizeSmall
                                            elide: Text.ElideRight
                                        }
                                    }
                                    Rectangle {
                                        Layout.preferredWidth: 8
                                        Layout.preferredHeight: 8
                                        radius: 4
                                        color: Theme.statusConnected
                                    }
                                }

                                TapHandler {
                                    onTapped: root.toggleHost(
                                                  hostCard.modelData.host,
                                                  !hostCard.selected)
                                }
                            }
                        }
                    }
                }

                FormSection {
                    Layout.fillWidth: true
                    title: "Group authentication"

                    GridLayout {
                        Layout.fillWidth: true
                        columns: width < 700 ? 1 : 2
                        columnSpacing: Theme.spacing12
                        rowSpacing: Theme.spacing8

                        StandardComboBox {
                            Layout.fillWidth: true
                            labelText: "Authentication"
                            model: root.protocol === "vrrp"
                                   || (root.protocol === "hsrp"
                                       && root.protocolVersion === 1)
                                   ? ["None", "Plain"]
                                   : ["None", "Plain", "MD5 key", "MD5 key-chain"]
                            valueModel: root.protocol === "vrrp"
                                        || (root.protocol === "hsrp"
                                            && root.protocolVersion === 1)
                                        ? ["none", "plain"]
                                        : ["none", "plain", "md5-key", "md5-keychain"]
                            currentIndex: Math.max(
                                              0, valueModel.indexOf(root.groupAuthType))
                            onActivated: {
                                root.groupAuthType = currentValue
                                if (currentValue === "none")
                                    root.groupAuthSecret = ""
                            }
                        }
                        StandardPasswordField {
                            Layout.fillWidth: true
                            visible: root.groupAuthType !== "none"
                            labelText: root.groupAuthType === "md5-keychain"
                                       ? "Key-chain name" : "Authentication secret"
                            text: root.groupAuthSecret
                            onTextChanged: root.groupAuthSecret = text
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Authentication is applied identically to every member so peers can form one FHRP group."
                        color: Theme.textDisabled
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        wrapMode: Text.WordWrap
                    }
                }

                FhrpProtocolOptionsEditor {
                    objectName: "fhrpProtocolOptionsEditor"
                    Layout.fillWidth: true
                    protocol: root.protocol
                    protocolVersion: root.protocolVersion
                    helloMs: root.helloMs
                    holdMs: root.holdMs
                    advertisementMs: root.advertisementMs
                    loadBalancing: root.loadBalancing
                    onOptionChanged: function(field, value) {
                        root.updateProtocolOption(field, value)
                    }
                }

                FormSection {
                    Layout.fillWidth: true
                    title: "Member policy"

                    EmptyState {
                        visible: memberModel.count === 0
                        Layout.fillWidth: true
                        Layout.preferredHeight: 96
                        title: "Select routers to configure member policy"
                        emphasized: false
                    }

                    Repeater {
                        model: memberModel
                        delegate: FhrpMemberEditor {
                            id: memberEditor
                            required property int index
                            required property var model

                            memberIndex: memberEditor.index
                            protocol: root.protocol
                            host: memberEditor.model.host
                            interfaceOptions: root.interfaceOptionsForHost(
                                                  memberEditor.model.host)
                            ifaceId: memberEditor.model.ifaceId
                            interfaceKind: memberEditor.model.interfaceKind
                            priority: memberEditor.model.priority
                            preempt: memberEditor.model.preempt
                            preemptDelayMinSec:
                                Number(memberEditor.model.preemptDelayMinSec || 0)
                            preemptDelayReloadSec:
                                Number(memberEditor.model.preemptDelayReloadSec || 0)
                            weightingMax: Number(memberEditor.model.weightingMax || 100)
                            weightingLower: Number(memberEditor.model.weightingLower || 0)
                            weightingUpper: Number(memberEditor.model.weightingUpper || 0)
                            forwarderPreempt:
                                Boolean(memberEditor.model.forwarderPreempt)
                            forwarderPreemptDelaySec:
                                Number(memberEditor.model.forwarderPreemptDelaySec || 0)
                            tracks: root.parseTracks(memberEditor.model.tracksJson)
                            onFieldChanged: function(memberIndex, field, value) {
                                root.updateMember(memberIndex, field, value)
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8
                    Text {
                        Layout.fillWidth: true
                        text: memberModel.count < 2
                              ? "Select at least two routers to continue"
                              : root.matchedHostCount() < memberModel.count
                                ? "Some routers have no matching interface"
                                : "Ready to save " + memberModel.count + " members"
                        color: memberModel.count >= 2
                               && root.matchedHostCount() === memberModel.count
                               ? Theme.statusConnected : Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                    Item { Layout.fillWidth: true }
                    StandardButton {
                        text: "Reset"
                        type: "Text"
                        enabled: memberModel.count > 0
                                 || groupField.text.trim() !== ""
                                 || gatewayField.text.trim() !== ""
                        onClicked: root.resetDraft()
                    }
                    StandardButton {
                        objectName: "fhrpSaveButton"
                        text: "Save"
                        icon.source: AppAssets.actionSave
                        type: "Secondary"
                        enabled: !root.operationBusy
                        onClicked: root.saveGroup()
                    }
                }
            }

            FhrpSavedGroupsPanel {
                id: savedGroupsPanel
                objectName: "fhrpSavedGroupsPanel"
                width: 340
                height: 220
                SplitView.fillWidth: root.compactLayout
                SplitView.fillHeight: !root.compactLayout
                SplitView.preferredWidth: root.compactLayout
                                          ? workspaceSplit.width
                                          : workspaceSplit.width * 0.32
                SplitView.minimumWidth: root.compactLayout ? 0 : 340
                SplitView.preferredHeight: root.compactLayout
                                           ? Math.min(320, workspaceSplit.height * 0.38)
                                           : workspaceSplit.height
                SplitView.minimumHeight: root.compactLayout ? 220 : 0

                Binding on width {
                    when: root.compactLayout
                    value: workspaceSplit.width
                }
                Binding on height {
                    when: !root.compactLayout
                    value: workspaceSplit.height
                }
                groupModel: root.savedGroupModel
                protocolLabel: root.protocol
                onRemoveRequested: function(fhrpId) {
                    root.deleteGroup(fhrpId)
                }
                onCancelRemoveRequested: function(fhrpId) {
                    root.cancelGroupDelete(fhrpId)
                }
            }
        }
    }

    Timer {
        id: matchingTimer
        interval: 250
        repeat: false
        onTriggered: root.refreshMatchingInterfaces()
    }

    MultiHostViewPushDialog {
        id: batchDialog
        parent: Overlay.overlay
        controllerName: "fhrp"
        featureLabel: "FHRP"
        ownerForm: root
        onClosed: root.operationBusy = false
    }
}
