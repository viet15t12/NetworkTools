pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

StandardDialog {
    id: dialog

    property string hostIp: ""
    property var interfaceNames: []
    property string feedback: ""
    property string feedbackSeverity: "info"

    signal setupSaved()

    preferredWidth: 620
    title: "Quick PAT Setup"
    subtitle: "Create the common Internet-sharing NAT policy"

    function openForHost(host) {
        hostIp = String(host || "").trim()
        feedback = ""
        aclNameField.text = "NAT_INSIDE"
        sourceNetworkField.text = ""
        wildcardField.text = ""
        const rows = hostIp === "" ? [] : dbManager.getRouterInterfaces(hostIp)
        const names = []
        for (let i = 0; i < rows.length; ++i) {
            const name = String(rows[i].interface_name || "")
            if (name !== "" && names.indexOf(name) < 0)
                names.push(name)
        }
        interfaceNames = names
        insideInterface.currentIndex = names.length > 0 ? 0 : -1
        outsideInterface.currentIndex = names.length > 1 ? 1 : (names.length > 0 ? 0 : -1)
        open()
    }

    function applySetup() {
        const result = dbManager.applyNatPatQuickSetup(hostIp, {
            inside_interface: insideInterface.currentValue,
            outside_interface: outsideInterface.currentValue,
            source_network: sourceNetworkField.text.trim(),
            wildcard: wildcardField.text.trim(),
            acl_name: aclNameField.text.trim()
        })
        feedback = String(result && result.message ? result.message : "Quick PAT setup failed.")
        feedbackSeverity = result && result.ok ? "success" : "error"
        if (result && result.ok) {
            setupSaved()
            Qt.callLater(close)
        }
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacing16

        InlineMessage {
            Layout.fillWidth: true
            message: dialog.interfaceNames.length < 2
                     ? "Add or synchronize at least two routed interfaces before using Quick PAT setup."
                     : "Creates inside/outside roles, a LAN ACL, and an overload rule."
            severity: dialog.interfaceNames.length < 2 ? "warning" : "info"
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing12

            StandardComboBox {
                id: insideInterface
                Layout.fillWidth: true
                labelText: "Inside interface"
                model: dialog.interfaceNames
                valueModel: dialog.interfaceNames
                emptyText: "No interfaces"
            }

            StandardComboBox {
                id: outsideInterface
                Layout.fillWidth: true
                labelText: "Outside interface"
                model: dialog.interfaceNames
                valueModel: dialog.interfaceNames
                emptyText: "No interfaces"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing4
                Text {
                    text: "LAN network"
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
                StandardNetworkField {
                    id: sourceNetworkField
                    Layout.fillWidth: true
                    inputKind: "ipv4"
                    placeholderText: "e.g., 192.168.10.0"
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing4
                Text {
                    text: "Wildcard"
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
                StandardNetworkField {
                    id: wildcardField
                    Layout.fillWidth: true
                    inputKind: "ipv4"
                    placeholderText: "e.g., 0.0.0.255"
                }
            }
        }

        StandardTextField {
            id: aclNameField
            Layout.fillWidth: true
            labelText: "ACL name"
            text: "NAT_INSIDE"
            placeholderText: "NAT_INSIDE"
        }

        InlineMessage {
            Layout.fillWidth: true
            message: dialog.feedback
            severity: dialog.feedbackSeverity
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            StandardButton {
                text: "Cancel"
                type: "Text"
                onClicked: dialog.reject()
            }
            StandardButton {
                objectName: "natQuickSetupApplyButton"
                text: "Create PAT policy"
                type: "Primary"
                enabled: dialog.hostIp !== "" && dialog.interfaceNames.length >= 2
                onClicked: dialog.applySetup()
            }
        }
    }
}
