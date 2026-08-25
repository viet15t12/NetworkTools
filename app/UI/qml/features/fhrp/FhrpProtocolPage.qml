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
    property string errorText: ""
    property int viewPushRevision: 0
    property bool operationBusy: false
    property string groupAuthType: "none"
    property string groupAuthSecret: ""
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
                                         : protocol === "glbp" ? "0–1023" : "0–4095"
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
        viewPushRevision++
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
                preempt: true
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
        errorText = ""
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
        memberModel.setProperty(index, field, value)
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
                version: 2
            })
        }
        return members
    }

    function saveGroup(pushAfterSave) {
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
        if (pushAfterSave) {
            operationBusy = true
            batchDialog.openPreview(result.hosts || [], root.protocol)
        }
    }

    function deleteGroup(fhrpId) {
        const result = dbManager.deleteFhrpGroup(Number(fhrpId))
        notify(String(result.message || ""), result.ok ? "success" : "error")
        if (result.ok) {
            loadGroups()
            operationBusy = true
            batchDialog.openPreview(result.hosts || [], root.protocol)
        }
    }

    onCurrentHostIpChanged: loadGroups()
    Component.onCompleted: {
        loadOptions()
        loadGroups()
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
                    text: "Reload"
                    icon.source: AppAssets.actionDatabaseReload
                    type: "Secondary"
                    onClicked: {
                        root.reloadData("manual")
                        root.notify("Reloaded FHRP options and saved groups.", "info")
                    }
                }

                ViewPushButton {
                    type: "Primary"
                    controllerName: "fhrp"
                    moduleName: root.protocol
                    hostIp: root.currentHostIp
                    ownerForm: root
                    refreshKey: root.viewPushRevision
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
                                   ? ["None", "Plain"]
                                   : ["None", "Plain", "MD5 key", "MD5 key-chain"]
                            valueModel: root.protocol === "vrrp"
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
                            host: memberEditor.model.host
                            interfaceOptions: root.interfaceOptionsForHost(
                                                  memberEditor.model.host)
                            ifaceId: memberEditor.model.ifaceId
                            interfaceKind: memberEditor.model.interfaceKind
                            priority: memberEditor.model.priority
                            preempt: memberEditor.model.preempt
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
                        onClicked: root.saveGroup(false)
                    }
                    StandardButton {
                        objectName: "fhrpSavePushButton"
                        text: "Save & Push"
                        icon.source: AppAssets.actionSave
                        type: "Primary"
                        enabled: !root.operationBusy
                        onClicked: root.saveGroup(true)
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
