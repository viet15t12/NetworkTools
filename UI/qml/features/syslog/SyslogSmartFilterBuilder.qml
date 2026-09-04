pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

StandardDialog {
    id: dialog

    readonly property string previewExpression: buildExpression()

    signal applyRequested(string expression)

    preferredWidth: 780
    height: Math.min(parent ? parent.height - 48 : 700, 700)
    title: "Build Smart Filter"
    subtitle: "Fill only the conditions you need, then review the generated filter"

    function unquote(value) {
        const text = String(value || "")
        if (text.length >= 2
                && ((text[0] === '"' && text[text.length - 1] === '"')
                    || (text[0] === "'" && text[text.length - 1] === "'")))
            return text.slice(1, -1)
        return text
    }

    function quoteValue(value) {
        const text = String(value || "").trim()
        if (text === "") return ""
        if (!/\s/.test(text)) return text
        return '"' + text.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"'
    }

    function resetFields() {
        textField.clear()
        hostField.clear()
        severityField.clear()
        protocolBox.currentIndex = 0
        facilityField.clear()
        mnemonicField.clear()
        fromField.clear()
        toField.clear()
        sinceField.clear()
        lastField.value = 0
    }

    function openFor(expression) {
        loadExpression(expression)
        open()
    }

    function loadExpression(expression) {
        resetFields()
        const source = String(expression || "").trim()
        const tokens = source.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || []
        const textParts = []
        for (let i = 0; i < tokens.length; ++i) {
            const token = tokens[i]
            const separator = token.indexOf(":")
            if (separator <= 0) {
                textParts.push(unquote(token))
                continue
            }
            const key = token.slice(0, separator).toLocaleLowerCase()
            const value = unquote(token.slice(separator + 1))
            if (key === "host") hostField.text = value
            else if (key === "severity" || key === "sev") severityField.text = value
            else if (key === "protocol" || key === "proto") {
                const protocol = value.toLocaleLowerCase()
                protocolBox.currentIndex = protocol === "udp" ? 1
                                           : protocol === "tcp" ? 2
                                           : protocol === "udp,tcp" || protocol === "tcp,udp" ? 3 : 0
            } else if (key === "facility" || key === "fac") facilityField.text = value
            else if (key === "mnemonic" || key === "mn") mnemonicField.text = value
            else if (key === "from") fromField.text = value
            else if (key === "to") toField.text = value
            else if (key === "since") sinceField.text = value
            else if (key === "last" || key === "perhost") {
                const count = Number(value)
                lastField.value = isNaN(count) ? 0 : Math.max(0, Math.min(500, count))
            } else if (key === "text" || key === "message") textParts.push(value)
            else textParts.push(token)
        }
        textField.text = textParts.join(" ")
    }

    function buildExpression() {
        const parts = []
        const host = hostField.text.trim()
        const since = sinceField.text.trim()
        if (host !== "") parts.push("host:" + quoteValue(host))
        if (since === "") {
            if (fromField.text.trim() !== "")
                parts.push("from:" + quoteValue(fromField.text))
            if (toField.text.trim() !== "")
                parts.push("to:" + quoteValue(toField.text))
        } else {
            parts.push("since:" + quoteValue(since))
        }
        if (lastField.value > 0) parts.push("last:" + lastField.value)
        if (severityField.text.trim() !== "")
            parts.push("severity:" + quoteValue(severityField.text))
        if (protocolBox.currentIndex === 1) parts.push("protocol:udp")
        else if (protocolBox.currentIndex === 2) parts.push("protocol:tcp")
        else if (protocolBox.currentIndex === 3) parts.push("protocol:udp,tcp")
        if (facilityField.text.trim() !== "")
            parts.push("facility:" + quoteValue(facilityField.text))
        if (mnemonicField.text.trim() !== "")
            parts.push("mnemonic:" + quoteValue(mnemonicField.text))
        if (textField.text.trim() !== "")
            parts.push("text:" + quoteValue(textField.text))
        return parts.join(" ")
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacing12

        InlineMessage {
            Layout.fillWidth: true
            severity: "info"
            message: "Smart conditions override matching filters on the toolbar. Separate multiple hosts or severities with commas."
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: Theme.spacing12

                FormSection {
                    Layout.fillWidth: true
                    title: "Message and device"
                    helpText: "Message contains: Case-insensitive text searched in the Syslog message. Spaces are quoted automatically.\n\nHosts: Exact device host/IP values. Separate multiple hosts with commas. Leaving this blank keeps the Host checkboxes on the toolbar.\n\nCisco facility: Partial facility name such as LINK, LINEPROTO, SYS, or OSPF.\n\nMnemonic: Partial Cisco event mnemonic such as UPDOWN, CONFIG_I, or ADJCHG."

                    StandardTextField {
                        id: textField
                        Layout.fillWidth: true
                        labelText: "Message contains"
                        placeholderText: "interface changed state"
                    }
                    StandardTextField {
                        id: hostField
                        Layout.fillWidth: true
                        labelText: "Hosts (comma-separated)"
                        placeholderText: "192.0.2.10,192.0.2.11"
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        StandardTextField {
                            id: facilityField
                            Layout.fillWidth: true
                            labelText: "Cisco facility"
                            placeholderText: "LINK"
                        }
                        StandardTextField {
                            id: mnemonicField
                            Layout.fillWidth: true
                            labelText: "Mnemonic"
                            placeholderText: "UPDOWN"
                        }
                    }
                }

                FormSection {
                    Layout.fillWidth: true
                    title: "Severity and transport"
                    helpText: "Severities: Enter one or more RFC Syslog levels separated by commas. Accepted values are 0–7 or names: emergency, alert, critical, error, warning, notice, informational, and debug. Example: error,warning.\n\nProtocol: Transport used to receive the message. Any keeps the toolbar selection; UDP or TCP overrides it. UDP + TCP explicitly accepts both transports."

                    RowLayout {
                        Layout.fillWidth: true
                        StandardTextField {
                            id: severityField
                            Layout.fillWidth: true
                            labelText: "Severities (comma-separated)"
                            placeholderText: "error,warning or 3,4"
                        }
                        StandardComboBox {
                            id: protocolBox
                            Layout.fillWidth: true
                            labelText: "Protocol"
                            model: ["Any", "UDP", "TCP", "UDP + TCP"]
                        }
                    }
                }

                FormSection {
                    Layout.fillWidth: true
                    title: "Time window and result limit"
                    helpText: "From / To (UTC): Inclusive ISO timestamps, for example 2026-08-26T18:00. A date without time means start-of-day for From and end-of-day for To.\n\nRecent window: Relative duration such as 30m, 2h, 7d, or 1w. When present, it replaces From.\n\nLatest per host: Keep the newest N matching messages for every host after other filters. 0 means no per-host limit; maximum is 500."

                    RowLayout {
                        Layout.fillWidth: true
                        StandardTextField {
                            id: fromField
                            Layout.fillWidth: true
                            enabled: sinceField.text.trim() === ""
                            labelText: "From (UTC)"
                            placeholderText: "2026-08-26T18:00"
                        }
                        StandardTextField {
                            id: toField
                            Layout.fillWidth: true
                            enabled: sinceField.text.trim() === ""
                            labelText: "To (UTC)"
                            placeholderText: "2026-08-26T19:00"
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        StandardTextField {
                            id: sinceField
                            Layout.fillWidth: true
                            labelText: "Recent window"
                            placeholderText: "30m, 2h, 7d or 1w"
                        }
                        StandardSpinBox {
                            id: lastField
                            Layout.fillWidth: true
                            labelText: "Latest per host (0 = all)"
                            from: 0
                            to: 500
                            value: 0
                        }
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing4
            Text {
                text: "Generated Smart Filter"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.max(44, previewText.implicitHeight + Theme.spacing16)
                color: Theme.inputBackground
                border.color: Theme.inputBorderColor
                border.width: Theme.borderWidth
                radius: Theme.radiusSmall
                Text {
                    id: previewText
                    anchors.fill: parent
                    anchors.margins: Theme.spacing8
                    text: dialog.previewExpression || "No Smart Filter conditions"
                    color: dialog.previewExpression ? Theme.textPrimary : Theme.textDisabled
                    font.family: Theme.monoFontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    wrapMode: Text.WrapAnywhere
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardButton {
                text: "Clear"
                type: "Text"
                onClicked: dialog.resetFields()
            }
            Item { Layout.fillWidth: true }
            StandardButton {
                text: "Cancel"
                type: "Text"
                onClicked: dialog.close()
            }
            StandardButton {
                objectName: "syslogSmartFilterApplyButton"
                text: "Apply Filter"
                icon.source: AppAssets.actionFilter
                type: "Primary"
                onClicked: {
                    dialog.applyRequested(dialog.previewExpression)
                    dialog.close()
                }
            }
        }
    }
}
