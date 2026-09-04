pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: form
    readonly property bool compactLayout: width < Theme.dataWorkspaceBreakpoint
    color: Theme.contentBackground

    property string currentHostIp: ""
    property string currentAclType: "Standard"
    property string lastError: ""
    property var savedAcls: []
    property int selectedAclId: 0
    property int viewedAclId: 0
    property string viewedAclName: ""
    property string loadedDescription: ""
    property string loadedRulesSignature: ""
    property var pendingDeleteIds: []
    property bool hasPendingDeletes: pendingDeleteIds.length > 0
    readonly property bool hasPendingLocalChanges: hasPendingDeletes
                                                    || (selectedAclId > 0
                                                        && (loadedDescription !== editor.descriptionText.trim()
                                                            || loadedRulesSignature !== rulesSignature()))
                                                    || (selectedAclId === 0
                                                        && viewedAclId === 0
                                                        && (editor.aclNameText.trim() !== ""
                                                            || editor.descriptionText.trim() !== ""
                                                            || ruleModel.count > 0))

    ListModel { id: ruleModel }
    ListModel { id: savedAclModel }

    function isEditing() { return selectedAclId > 0 }
    function titleAction(value) { return String(value || "permit").toLowerCase() === "deny" ? "Deny" : "Permit" }

    function notify(message, type) {
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(message, type)
    }

    function bindingLabel(acl) {
        const bindings = acl.bindings || []
        if (bindings.length === 0) return "Not applied"
        const binding = bindings[0]
        const first = (binding.interface_name || "Interface #" + binding.iface_id) +
                      " / " + String(binding.direction || "in").toUpperCase()
        return bindings.length > 1 ? first + " (+" + (bindings.length - 1) + ")" : first
    }

    function isPendingDelete(aclId) {
        for (let i = 0; i < pendingDeleteIds.length; ++i) {
            if (Number(pendingDeleteIds[i]) === Number(aclId)) return true
        }
        return false
    }

    function refreshSavedAcls() {
        savedAclModel.clear()
        savedAcls = []
        if (currentHostIp === "" || typeof dbManager === "undefined") return
        savedAcls = dbManager.getAcls(currentHostIp, currentAclType)
        for (let i = 0; i < savedAcls.length; ++i) {
            const acl = savedAcls[i]
            if (isPendingDelete(acl.Acl_id || 0)) continue
            savedAclModel.append({
                aclIndex: i,
                aclId: acl.Acl_id || 0,
                aclName: acl.acl_name || "",
                description: acl.description || "",
                ruleCount: acl.rules ? acl.rules.length : 0,
                bindingText: bindingLabel(acl)
            })
        }
    }

    function ruleDetail(rule) {
        const type = currentAclType.toLowerCase()
        if (type === "standard")
            return "src: " + (rule.source || "any") + (rule.wildcard ? " / " + rule.wildcard : "")
        if (type === "mac")
            return "MAC " + (rule.src_mac || "any") + " -> " + (rule.dst_mac || "any")
        let src = rule.source || "any"
        let dst = rule.destination || "any"
        if (rule.src_wildcard) src += "/" + rule.src_wildcard
        if (rule.src_port) src += " " + rule.src_port
        if (rule.dst_wildcard) dst += "/" + rule.dst_wildcard
        if (rule.dst_port) dst += " " + rule.dst_port
        return String(rule.protocol || "ip").toUpperCase() + " " + src + " -> " + dst
    }

    function clearEditor() {
        selectedAclId = 0
        viewedAclId = 0
        viewedAclName = ""
        loadedDescription = ""
        loadedRulesSignature = ""
        ruleModel.clear()
        editor.reset(currentHostIp)
        lastError = ""
    }

    function populateRules(acl) {
        ruleModel.clear()
        const rules = acl.rules || []
        for (let i = 0; i < rules.length; ++i) {
            const rule = rules[i]
            ruleModel.append({
                ruleSequence: rule.sequence || ((i + 1) * 10),
                ruleAction: titleAction(rule.action),
                ruleDetail: ruleDetail(rule),
                ruleAclType: currentAclType,
                ruleData: rule
            })
        }
    }

    function viewAcl(index) {
        if (index < 0 || index >= savedAcls.length) return
        const acl = savedAcls[index]
        selectedAclId = 0
        viewedAclId = acl.Acl_id || 0
        viewedAclName = acl.acl_name || ""
        editor.reset(currentHostIp)
        populateRules(acl)
        lastError = ""
    }

    function loadAcl(index) {
        if (index < 0 || index >= savedAcls.length) return
        const acl = savedAcls[index]
        selectedAclId = acl.Acl_id || 0
        viewedAclId = selectedAclId
        viewedAclName = acl.acl_name || ""
        editor.loadFields(acl)
        populateRules(acl)
        loadedDescription = editor.descriptionText
        loadedRulesSignature = rulesSignature()
        lastError = ""
    }

    function rulesSignature() {
        const values = []
        for (let i = 0; i < ruleModel.count; ++i) {
            const row = ruleModel.get(i)
            values.push([row.ruleSequence, row.ruleAction, row.ruleDetail])
        }
        return JSON.stringify(values)
    }

    function validateSequence(text) {
        if (text === "") return 0
        const value = Number(text)
        if (!Number.isInteger(value) || value < 1 || value > 65535) {
            lastError = "Sequence must be an integer between 1 and 65535."
            return -1
        }
        for (let i = 0; i < ruleModel.count; ++i) {
            if (ruleModel.get(i).ruleSequence === value) {
                lastError = "Sequence " + value + " already exists."
                return -1
            }
        }
        return value
    }

    function addRule() {
        const requested = validateSequence(editor.sequenceText())
        if (requested < 0) return
        const sequence = requested || ((ruleModel.count + 1) * 10)
        const built = editor.buildRule(sequence, editor.actionText())
        ruleModel.append({
            ruleSequence: sequence,
            ruleAction: titleAction(built.data.action),
            ruleDetail: built.detail,
            ruleAclType: currentAclType,
            ruleData: built.data
        })
        editor.clearRuleInputs()
        lastError = ""
    }

    function saveAcl() {
        if (ruleModel.count === 0) {
            lastError = "Add at least one rule before saving."
            return
        }
        const rules = []
        for (let i = 0; i < ruleModel.count; ++i) {
            const row = ruleModel.get(i)
            const data = row.ruleData || {}
            data.sequence = row.ruleSequence
            data.action = String(row.ruleAction).toLowerCase()
            rules.push(data)
        }
        const currentRulesSignature = rulesSignature()
        const descriptionChanged = loadedDescription !== editor.descriptionText.trim()
        const rulesChanged = loadedRulesSignature !== currentRulesSignature
        if (selectedAclId > 0 && !descriptionChanged && !rulesChanged) {
            notify("No ACL changes to save.", "info")
            return
        }
        const payload = {
            acl_id: selectedAclId,
            host: currentHostIp,
            acl_name: editor.aclNameText.trim(),
            acl_type: currentAclType,
            description: editor.descriptionText.trim(),
            description_only: selectedAclId > 0 && descriptionChanged && !rulesChanged,
            rules_changed: selectedAclId === 0 || rulesChanged,
            rules: rules
        }
        if (typeof dbManager === "undefined" || !dbManager.saveAcl(payload)) {
            lastError = isEditing()
                        ? "Change ACL failed. Check Cisco address, wildcard and port syntax."
                        : "Create ACL failed. Check for a duplicate name or invalid Cisco syntax."
            return
        }
        const savedName = editor.aclNameText.trim()
        refreshSavedAcls()
        for (let i = 0; i < savedAcls.length; ++i) {
            if (savedAcls[i].acl_name === savedName) {
                loadAcl(i)
                break
            }
        }
        notify("ACL " + savedName + " saved to database.", "success")
    }

    function stageDeleteAcl(aclId) {
        if (aclId <= 0 || isPendingDelete(aclId)) return
        pendingDeleteIds = pendingDeleteIds.concat([aclId])
        if (selectedAclId === aclId || viewedAclId === aclId) clearEditor()
        refreshSavedAcls()
        notify("ACL hidden locally. Press Save to mark it for removal.", "info")
    }

    function savePendingDeletes() {
        if (!hasPendingDeletes || typeof dbManager === "undefined") return
        if (!dbManager.deleteAcls(pendingDeleteIds)) {
            lastError = "Save ACL deletes failed."
            return
        }
        pendingDeleteIds = []
        refreshSavedAcls()
        notify("ACL deletes saved as pending_delete.", "success")
    }

    function cancelPendingDeletes() {
        pendingDeleteIds = []
        refreshSavedAcls()
        notify("Pending ACL deletes cancelled.", "info")
    }

    function resetContext() {
        pendingDeleteIds = []
        clearEditor()
        refreshSavedAcls()
    }

    onCurrentHostIpChanged: resetContext()
    onCurrentAclTypeChanged: { clearEditor(); refreshSavedAcls() }
    Component.onCompleted: refreshSavedAcls()

    SplitView {
        id: aclSplit
        objectName: "aclResponsiveSplit"
        anchors.fill: parent
        orientation: form.compactLayout ? Qt.Vertical : Qt.Horizontal
        handle: StandardSplitHandle { enabled: false }

        AclEditorPane {
            id: editor
            SplitView.fillWidth: false
            SplitView.fillHeight: false
            SplitView.preferredWidth: form.compactLayout ? aclSplit.width : aclSplit.width * 0.4
            SplitView.minimumWidth: form.compactLayout ? 0 : aclSplit.width * 0.4
            SplitView.maximumWidth: form.compactLayout ? Number.POSITIVE_INFINITY : aclSplit.width * 0.4
            SplitView.preferredHeight: form.compactLayout ? aclSplit.height * 0.4 : aclSplit.height
            SplitView.minimumHeight: form.compactLayout ? aclSplit.height * 0.4 : 0
            SplitView.maximumHeight: form.compactLayout ? aclSplit.height * 0.4 : Number.POSITIVE_INFINITY
            currentHostIp: form.currentHostIp
            currentAclType: form.currentAclType
            editing: form.isEditing()
            viewing: form.viewedAclId > 0 && !form.isEditing()
            errorText: form.lastError
            onAddRuleRequested: form.addRule()
            onSaveRequested: form.saveAcl()
            onCancelRequested: form.clearEditor()
            onClearRulesRequested: { ruleModel.clear(); editor.clearRuleInputs() }
        }

        Item {
            SplitView.fillWidth: true
            SplitView.fillHeight: true
            SplitView.minimumWidth: form.compactLayout ? 0 : 480
            SplitView.minimumHeight: form.compactLayout ? 260 : 0
            ColumnLayout {
                anchors.fill: parent
                spacing: 0
                AclSavedPanel {
                    aclModel: savedAclModel
                    selectedAclId: form.viewedAclId
                    onViewRequested: (index) => form.viewAcl(index)
                    onEditRequested: (index) => form.loadAcl(index)
                    onDeleteRequested: (aclId) => form.stageDeleteAcl(aclId)
                }
                AclRulesPanel {
                    ruleModel: ruleModel
                    editing: form.isEditing()
                    viewing: form.viewedAclId > 0
                    aclName: form.viewedAclName
                    allowDelete: form.viewedAclId === 0 || form.isEditing()
                    onDeleteRequested: (index) => {
                        if (index >= 0 && index < ruleModel.count) ruleModel.remove(index)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.margins: 10
                    Text {
                        Layout.fillWidth: true
                        text: form.hasPendingDeletes
                              ? form.pendingDeleteIds.length + " ACL delete(s) waiting for Save"
                              : "Delete only hides a row until Save"
                        color: form.hasPendingDeletes ? Theme.alertWarning : Theme.textSecondary
                    }
                    StandardButton {
                        text: "Cancel Deletes"
                        type: "Text"
                        enabled: form.hasPendingDeletes
                        onClicked: form.cancelPendingDeletes()
                    }
                    StandardButton {
                        text: "Save"
                        icon.source: AppAssets.actionSave
                        type: "Primary"
                        enabled: form.hasPendingDeletes
                        onClicked: form.savePendingDeletes()
                    }
                }
            }
        }
    }
}
