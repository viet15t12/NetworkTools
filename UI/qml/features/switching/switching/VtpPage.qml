pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "vtpPage"

    required property string host
    property var hostOptions: []
    property string errorText: ""
    property string hostFilterText: ""
    property int selectedGroupIndex: -1
    property int dataRevision: 0
    readonly property int maxHosts: 5
    readonly property bool isViewLoading: false
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    readonly property bool readyToSave: memberModel.count >= 2
                                            && domainField.text.trim() !== ""
    readonly property var filteredHostOptions: {
        const options = root.hostOptions || []
        const query = root.hostFilterText.trim().toLocaleLowerCase()
        if (query === "") return options
        const rows = []
        for (let i = 0; i < options.length; i++) {
            const item = options[i]
            const text = [item.device_name, item.host].join(" ").toLocaleLowerCase()
            if (text.indexOf(query) !== -1) rows.push(item)
        }
        return rows
    }
    readonly property var summaryMetrics: [
        { label: "Connected switches", value: root.hostOptions.length, tone: "success" },
        { label: "Selected", value: memberModel.count, tone: "accent" },
        { label: "Saved domains", value: groupModel.count, tone: "neutral" },
        { label: "Batch capacity", value: memberModel.count + " / " + root.maxHosts,
          tone: memberModel.count >= root.maxHosts ? "warning" : "neutral" }
    ]

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
        const result = dbManager.getVtpGroupOptions()
        hostOptions = result && result.hosts ? result.hosts : []
    }

    function loadGroups() {
        groupModel.clear()
        const result = dbManager.getVtpGroups()
        const rows = result && result.groups ? result.groups : []
        for (let i = 0; i < rows.length; i++)
            groupModel.append(normalizedGroup(rows[i]))
        if (selectedGroupIndex >= groupModel.count)
            selectedGroupIndex = -1
        dataRevision++
    }

    function normalizedGroup(group) {
        const source = group || ({})
        const sourceMembers = source.members || []
        const members = []
        for (let i = 0; i < sourceMembers.length; i++) {
            const member = sourceMembers[i] || ({})
            members.push({
                host: member.host === undefined || member.host === null
                      ? "" : String(member.host),
                mode: member.mode === undefined || member.mode === null
                      ? "client" : String(member.mode),
                pruning: Boolean(member.pruning),
                success: member.success === undefined || member.success === null
                         ? "pending_apply" : String(member.success)
            })
        }
        return {
            vtp_domain_id: Number(source.vtp_domain_id || 0),
            domain_name: source.domain_name === undefined || source.domain_name === null
                         ? "" : String(source.domain_name),
            version: Number(source.version || 2),
            description: source.description === undefined || source.description === null
                         ? "" : String(source.description),
            updated_at: source.updated_at === undefined || source.updated_at === null
                        ? "" : String(source.updated_at),
            members: members
        }
    }

    function listCount(value) {
        if (!value) return 0
        if (value.count !== undefined) return Number(value.count)
        return Number(value.length || 0)
    }

    function listItem(value, index) {
        return value && value.get ? value.get(index) : value[index]
    }

    function findMemberIndex(targetHost) {
        for (let i = 0; i < memberModel.count; i++) {
            if (memberModel.get(i).host === targetHost)
                return i
        }
        return -1
    }

    function toggleHost(targetHost, selected) {
        const index = findMemberIndex(targetHost)
        if (selected && index < 0) {
            if (memberModel.count >= maxHosts) {
                errorText = "VTP Group supports at most " + maxHosts + " switches."
                return
            }
            memberModel.append({
                host: targetHost,
                vtpMode: memberModel.count === 0 ? "server" : "client",
                pruning: false
            })
        } else if (!selected && index >= 0) {
            memberModel.remove(index)
        }
        errorText = ""
    }

    function memberPayload() {
        const members = []
        for (let i = 0; i < memberModel.count; i++) {
            const row = memberModel.get(i)
            members.push({
                host: row.host,
                mode: row.vtpMode,
                pruning: row.pruning
            })
        }
        return members
    }

    function resetDraft() {
        memberModel.clear()
        domainField.clear()
        descriptionField.clear()
        versionCombo.currentIndex = 1
        errorText = ""
        selectedGroupIndex = -1
    }

    function loadGroup(index) {
        if (index < 0 || index >= groupModel.count) return
        const group = groupModel.get(index)
        domainField.text = String(group.domain_name || "")
        descriptionField.text = String(group.description || "")
        versionCombo.currentIndex = Math.max(0, Math.min(2, Number(group.version || 2) - 1))
        memberModel.clear()
        const members = group.members || []
        for (let i = 0; i < listCount(members); i++) {
            const member = listItem(members, i)
            memberModel.append({
                host: String(member.host || ""),
                vtpMode: String(member.mode || "client"),
                pruning: Boolean(member.pruning)
            })
        }
        selectedGroupIndex = index
        errorText = ""
    }

    function saveGroup(pushAfterSave) {
        errorText = ""
        if (memberModel.count < 2) {
            errorText = "Select at least two connected switches."
            return
        }
        const result = dbManager.saveVtpGroup({
            domain_name: domainField.text.trim(),
            version: Number(versionCombo.currentValue),
            description: descriptionField.text.trim(),
            members: memberPayload()
        })
        const severity = result.ok ? "success" : (result.partial ? "warning" : "error")
        notify(String(result.message || ""), severity)
        if (!result.ok && !result.partial) {
            errorText = String(result.message || "Could not save VTP Group.")
            return
        }
        const savedDomain = domainField.text.trim()
        loadGroups()
        for (let i = 0; i < groupModel.count; i++) {
            if (groupModel.get(i).domain_name === savedDomain) {
                selectedGroupIndex = i
                break
            }
        }
        if (pushAfterSave)
            batchDialog.openPreview(result.successful || [], "vtp")
    }

    Component.onCompleted: reloadData("initial")

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing16
        spacing: Theme.spacing12

        WorkspaceHeader {
            Layout.fillWidth: true
            title: "VTP Group"
            subtitle: "Stage one VTP domain for two to five connected switches."

            StandardButton {
                text: "Add Group"
                icon.source: AppAssets.actionAdd
                type: "Secondary"
                onClicked: root.resetDraft()
            }

            StandardButton {
                text: "Reload UI"
                icon.source: AppAssets.actionDatabaseReload
                type: "Secondary"
                autoCompact: false
                Layout.minimumWidth: expandedImplicitWidth
                onClicked: root.reloadData("manual")
            }
        }

        InlineMessage {
            Layout.fillWidth: true
            visible: root.errorText !== ""
            message: root.errorText
            severity: "warning"
        }

        SwitchSummaryBar {
            Layout.fillWidth: true
            metrics: root.summaryMetrics
        }

        SplitView {
            id: workspaceSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.compactLayout ? Qt.Vertical : Qt.Horizontal
            handle: StandardSplitHandle { orientation: workspaceSplit.orientation }

            ScrollView {
                SplitView.fillWidth: !root.compactLayout
                SplitView.fillHeight: root.compactLayout
                SplitView.minimumWidth: root.compactLayout ? 0 : 520
                SplitView.minimumHeight: root.compactLayout ? 300 : 0
                clip: true

                ColumnLayout {
                    width: parent.width
                    spacing: Theme.spacing12

                    FormSection {
                        Layout.fillWidth: true
                        title: "Domain settings"
                        helpText: "Domain name groups switches that exchange VTP advertisements and is case-sensitive on some platforms. Version selects VTP 1, 2, or 3; all participating switches must be compatible. Review production domains carefully because VTP can modify VLAN databases."

                        Text {
                            Layout.fillWidth: true
                            text: "Authentication and VTPv3 primary/MST activation remain outside this non-interactive workflow."
                            color: Theme.textSecondary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                            wrapMode: Text.WordWrap
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: width < 660 ? 1 : 2
                            columnSpacing: Theme.spacing12
                            rowSpacing: Theme.spacing8

                            StandardTextField {
                                id: domainField
                                Layout.fillWidth: true
                                labelText: "Domain name"
                                placeholderText: "e.g. CAMPUS"
                            }
                            StandardComboBox {
                                id: versionCombo
                                Layout.fillWidth: true
                                labelText: "VTP version"
                                model: ["Version 1", "Version 2", "Version 3"]
                                valueModel: [1, 2, 3]
                                currentIndex: 1
                            }
                            StandardTextField {
                                id: descriptionField
                                Layout.fillWidth: true
                                Layout.columnSpan: width < 660 ? 1 : 2
                                labelText: "Description"
                                placeholderText: "Optional group description"
                            }
                        }
                    }

                    FormSection {
                        Layout.fillWidth: true
                        title: "Participating switches"
                        helpText: "Select 2-5 connected switches that should share the VTP domain configuration. Verify connectivity and current VLAN state before applying a common VTP policy."

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing12

                            Text {
                                Layout.fillWidth: true
                                text: memberModel.count + " selected · choose 2–5 connected switches"
                                color: memberModel.count >= 2 ? Theme.alertSuccess
                                                              : Theme.textSecondary
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeSmall
                                wrapMode: Text.WordWrap
                            }

                            StandardTextField {
                                Layout.preferredWidth: 240
                                text: root.hostFilterText
                                placeholderText: "Filter switches..."
                                onTextEdited: value => root.hostFilterText = value
                            }
                        }

                        EmptyState {
                            visible: root.filteredHostOptions.length === 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: 96
                            title: root.hostFilterText === ""
                                   ? "No connected switches"
                                   : "No switches match this filter"
                            description: root.hostFilterText === ""
                                         ? "Connect at least two switches before creating a VTP group."
                                         : "Clear the filter or try another device name or address."
                            emphasized: false
                        }

                        GridLayout {
                            objectName: "vtpHostPicker"
                            Layout.fillWidth: true
                            columns: width < 660 ? 1 : 2
                            columnSpacing: Theme.spacing8
                            rowSpacing: Theme.spacing8

                            Repeater {
                                model: root.filteredHostOptions
                                delegate: Rectangle {
                                    id: hostCard
                                    required property var modelData
                                    readonly property bool selected: root.findMemberIndex(
                                                                         modelData.host) >= 0
                                    Layout.fillWidth: true
                                    implicitHeight: 62
                                    radius: Theme.radiusSmall
                                    color: selected ? Theme.alertInfoSubtle
                                                    : Theme.contentBackground
                                    border.color: selected ? Theme.accentColor
                                                           : Theme.contentPanelBorder
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
                                                text: hostCard.modelData.device_name || "Switch"
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
                                }
                            }
                        }
                    }

                    FormSection {
                        Layout.fillWidth: true
                        title: "Member policy"
                        helpText: "VTP mode controls each switch's role: server can update the VLAN database, client learns it, transparent forwards advertisements while maintaining local VLANs, and off disables participation where supported. Pruning reduces unnecessary flooded traffic on trunks."

                        EmptyState {
                            visible: memberModel.count === 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: 96
                            title: "Select switches to configure their VTP mode"
                            emphasized: false
                        }

                        Repeater {
                            model: memberModel
                            delegate: Rectangle {
                                id: memberCard
                                required property int index
                                required property string host
                                required property string vtpMode
                                required property bool pruning
                                Layout.fillWidth: true
                                implicitHeight: 88
                                radius: Theme.radiusSmall
                                color: Theme.contentPanelSurface
                                border.color: Theme.contentPanelBorder
                                border.width: Theme.borderWidth

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: Theme.spacing12
                                    spacing: Theme.spacing12
                                    Text {
                                        Layout.fillWidth: true
                                        text: memberCard.host
                                        color: Theme.textPrimary
                                        font.family: Theme.fontFamily
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }
                                    StandardComboBox {
                                        Layout.preferredWidth: 180
                                        labelText: "VLAN database mode"
                                        model: ["server", "client", "transparent", "off"]
                                        currentIndex: Math.max(0, model.indexOf(memberCard.vtpMode))
                                        onActivated: index => memberModel.setProperty(
                                                         memberCard.index, "vtpMode", model[index])
                                    }
                                    StandardCheckBox {
                                        text: "Pruning"
                                        checked: memberCard.pruning
                                        onToggled: memberModel.setProperty(
                                                       memberCard.index, "pruning", checked)
                                    }
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: memberModel.count < 2
                                  ? "Select at least two switches"
                                  : "Ready to save " + memberModel.count + " members"
                            color: memberModel.count >= 2 ? Theme.statusConnected
                                                          : Theme.textSecondary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                        }
                        StandardButton {
                            objectName: "vtpFormCancelButton"
                            text: "Cancel"
                            icon.source: AppAssets.actionClear
                            type: "Text"
                            onClicked: root.resetDraft()
                        }
                        StandardButton {
                            text: "Save"
                            icon.source: AppAssets.actionSave
                            type: "Secondary"
                            enabled: root.readyToSave
                            onClicked: root.saveGroup(false)
                        }
                        StandardButton {
                            text: "Save & Push"
                            icon.source: AppAssets.actionSave
                            type: "Primary"
                            enabled: root.readyToSave
                            onClicked: root.saveGroup(true)
                        }
                    }
                }
            }

            Rectangle {
                SplitView.fillWidth: root.compactLayout
                SplitView.fillHeight: !root.compactLayout
                SplitView.preferredWidth: root.compactLayout
                                          ? workspaceSplit.width
                                          : workspaceSplit.width * 0.32
                SplitView.minimumWidth: root.compactLayout ? 0 : 320
                SplitView.minimumHeight: root.compactLayout ? 200 : 0
                color: Theme.contentSurface
                radius: Theme.radiusSmall
                border.color: Theme.contentPanelBorder
                border.width: Theme.borderWidth

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8
                    Text {
                        text: "Saved domains"
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeLarge
                        font.bold: true
                    }
                    Text {
                        text: groupModel.count + " domain(s)"
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: Theme.spacing8
                        model: groupModel
                        delegate: Rectangle {
                            id: groupCard
                            required property int index
                            required property string domain_name
                            required property int version
                            required property string description
                            required property var members
                            width: ListView.view.width
                            height: 88
                            radius: Theme.radiusSmall
                            color: root.selectedGroupIndex === groupCard.index
                                   ? Theme.tableRowSelected
                                   : groupHover.hovered ? Theme.tableRowHover
                                                        : Theme.contentPanelSurface
                            border.color: root.selectedGroupIndex === groupCard.index
                                          ? Theme.accentColor : Theme.contentPanelBorder
                            border.width: Theme.borderWidth
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing2
                                Text {
                                    Layout.fillWidth: true
                                    text: domain_name
                                    color: Theme.textPrimary
                                    font.family: Theme.fontFamily
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    visible: groupCard.description !== ""
                                    Layout.fillWidth: true
                                    text: groupCard.description
                                    color: Theme.textSecondary
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "Version " + version + " · "
                                          + root.listCount(members) + " switch(es)"
                                    color: Theme.textSecondary
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }
                            }
                            HoverHandler { id: groupHover }
                            TapHandler { onTapped: root.loadGroup(groupCard.index) }
                        }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                }
            }
        }
    }

    MultiHostViewPushDialog {
        id: batchDialog
        parent: Overlay.overlay
        controllerName: "switching"
        featureLabel: "VTP"
        ownerForm: root
    }
}
