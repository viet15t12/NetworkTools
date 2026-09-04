pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

AclScrollablePane {
    id: pane

    property string currentHostIp: ""
    property string currentAclType: "Standard"
    property bool editing: false
    property bool viewing: false
    property string errorText: ""
    property alias aclNameText: aclName.text
    property alias descriptionText: description.text

    signal addRuleRequested()
    signal saveRequested()
    signal cancelRequested()
    signal clearRulesRequested()

    function clearRuleInputs() {
        sequence.text = ""
        standardInput.clearFields()
        extendedInput.clearFields()
        dynamicInput.clearFields()
        reflexiveInput.clearFields()
        macInput.clearFields()
    }

    function reset(host) {
        aclName.text = ""
        description.text = ""
        clearRuleInputs()
    }

    function loadFields(acl) {
        aclName.text = acl.acl_name || ""
        description.text = acl.description || ""
    }

    function buildRule(sequenceValue, actionValue) {
        let input = standardInput
        if (currentAclType === "Extended") input = extendedInput
        else if (currentAclType === "Dynamic") input = dynamicInput
        else if (currentAclType === "Reflexive") input = reflexiveInput
        else if (currentAclType === "MAC") input = macInput
        const data = input.buildRule()
        data.sequence = sequenceValue
        data.action = actionValue
        return { data: data, detail: input.buildDetail() }
    }

    function sequenceText() { return sequence.text.trim() }
    function actionText() { return action.currentIndex === 1 ? "deny" : "permit" }

    SplitView.preferredWidth: parent && parent.width >= 1080 ? 440 : 400
    SplitView.minimumWidth: 360

    RowLayout {
        Layout.fillWidth: true
        Text {
            Layout.fillWidth: true
            text: pane.editing ? "Edit ACL" : (pane.viewing ? "View ACL Rules" : "Create ACL")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLarge
            font.family: Theme.fontFamily
            font.bold: true
        }
        ParameterHelpButton {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            helpTitle: "ACL parameters"
            helpText: "ACL Name: unique IOS access-list name. Description is an optional operational note.\n\n" +
                      "Sequence: rule order; lower numbers are evaluated first. Action Permit allows matching traffic and Deny blocks it.\n\n" +
                      "Rule Builder fields depend on ACL type: Standard matches source IPv4, Extended adds protocol/source/destination/ports, MAC matches Layer-2 addresses, and Dynamic/Reflexive create state-related rules. ACL processing stops at the first match and ends with an implicit deny."
        }
        StandardButton {
            visible: pane.editing || pane.viewing
            text: pane.viewing ? "Close View" : "Cancel"
            type: "Text"
            onClicked: pane.cancelRequested()
        }
    }

    Rectangle { Layout.fillWidth: true; height: Theme.borderWidth; color: Theme.splitHandleColor }

    StandardTextField {
        id: aclName
        enabled: !pane.viewing
        Layout.fillWidth: true
        labelText: "ACL Name *"
        placeholderText: "e.g., ACL_INBOUND"
    }

    StandardTextField {
        id: description
        enabled: !pane.viewing
        Layout.fillWidth: true
        labelText: "Description"
        placeholderText: "e.g., Block untrusted inbound traffic"
    }

    Text {
        text: "Rule Builder"
        color: Theme.textPrimary
        font.pixelSize: Theme.fontSizeNormal
        font.family: Theme.fontFamily
        font.bold: true
    }

    RowLayout {
        Layout.fillWidth: true
        StandardTextField {
            id: sequence
            enabled: !pane.viewing
            Layout.fillWidth: true
            labelText: "Sequence"
            placeholderText: "e.g., 10"
        }
        StandardComboBox {
            id: action
            enabled: !pane.viewing
            Layout.preferredWidth: 120
            labelText: "Action"
            model: ["Permit", "Deny"]
            optionColors: [Theme.statusConnected, Theme.alertError]
            optionBackgroundColors: [Theme.alertSuccessSubtle, Theme.alertErrorSubtle]
            contentBold: true
        }
    }

    AclRuleInputStandard { id: standardInput; enabled: !pane.viewing; Layout.fillWidth: true; visible: pane.currentAclType === "Standard" }
    AclRuleInputExtended { id: extendedInput; enabled: !pane.viewing; Layout.fillWidth: true; visible: pane.currentAclType === "Extended" }
    AclRuleInputDynamic { id: dynamicInput; enabled: !pane.viewing; Layout.fillWidth: true; visible: pane.currentAclType === "Dynamic" }
    AclRuleInputReflexive { id: reflexiveInput; enabled: !pane.viewing; Layout.fillWidth: true; visible: pane.currentAclType === "Reflexive" }
    AclRuleInputMac { id: macInput; enabled: !pane.viewing; Layout.fillWidth: true; visible: pane.currentAclType === "MAC" }

    Text {
        visible: pane.errorText !== ""
        Layout.fillWidth: true
        text: pane.errorText
        color: Theme.alertError
        font.pixelSize: Theme.fontSizeSmall
        font.family: Theme.fontFamily
        wrapMode: Text.WordWrap
    }

    Item { Layout.fillHeight: true }

    RowLayout {
        Layout.fillWidth: true
        StandardButton {
            enabled: !pane.viewing && aclName.text.trim() !== "" && pane.currentHostIp !== ""
            Layout.fillWidth: true
            text: "+ Add Rule"
            type: "Secondary"
            onClicked: pane.addRuleRequested()
        }
        StandardButton {
            enabled: !pane.viewing
            text: "Clear Rules"
            type: "Secondary"
            onClicked: pane.clearRulesRequested()
        }
        StandardButton {
            enabled: !pane.viewing && aclName.text.trim() !== "" && pane.currentHostIp !== ""
            Layout.fillWidth: true
            text: pane.editing ? "Change ACL" : "Create ACL"
            icon.source: AppAssets.actionSave
            type: "Primary"
            onClicked: pane.saveRequested()
        }
    }
}
