pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    property var form
    property alias routeText: defaultRouteInput.text
    property bool canSaveDefault: root.form && root.form.canSaveDefaultOnly()

    Layout.fillWidth: true
    Layout.leftMargin: 24
    Layout.rightMargin: 24
    radius: 8
    color: Theme.contentPanelSurface
    border.color: Theme.contentPanelBorder
    border.width: Theme.borderWidth
    implicitHeight: defaultCardLayout.implicitHeight + 16

    function focusInput() {
        defaultRouteInput.forceActiveFocus()
    }

    ColumnLayout {
        id: defaultCardLayout
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8
            Text {
                Layout.fillWidth: true
                text: "Default Route"
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeNormal
                font.family: Theme.fontFamily
                font.bold: true
            }
            ParameterHelpButton {
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
                helpTitle: "Default route parameters"
                helpText: "Next hop is the reachable router IP or exit interface used when no more-specific route matches. Ensure recursive reachability to the next hop. Administrative distance optionally controls preference when multiple default routes exist; lower values are preferred."
            }
        }

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "ip route 0.0.0.0 0.0.0.0 <next-hop>"
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeSmall
                font.family: Theme.fontFamily
                Layout.fillWidth: true
            }

            // Nút Add
            StandardButton {
                visible: !root.form.defaultRouteEnabled
                text: "+ Add"
                type: "Primary"
                onClicked: {
                    root.form.defaultRouteEnabled = true
                    root.focusInput()
                    root.form.markDirty()
                }
            }
        }

        Text {
            visible: !root.form.defaultRouteEnabled
            text: "No default route configured. Click + Add to set a default route."
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
        }

        RowLayout {
            visible: root.form.defaultRouteEnabled
            Layout.fillWidth: true
            spacing: 8

            // Ô nhập liệu
            StandardTextField {
                id: defaultRouteInput
                Layout.fillWidth: true
                placeholderText: "e.g., 192.168.1.1"
                onTextChanged: root.form.markDirty()
                onAccepted: {
                    if (root.canSaveDefault)
                        root.form.saveDefaultOnly()
                }
            }

            // Nút Cancel
            StandardButton {
                text: "Cancel"
                type: "Text"
                enabled: root.form.hasDefaultChanges()
                onClicked: root.form.cancelDefaultChanges()
            }

            // Nút Clear
            StandardButton {
                text: "Clear"
                type: "Secondary"
                onClicked: {
                    root.routeText = ""
                    root.form.markDirty()
                }
            }

            // Nút Save
            StandardButton {
                text: root.form.isSaving ? "Saving..." : "Save Default"
                icon.source: AppAssets.actionSave
                type: "Primary"
                enabled: root.canSaveDefault
                onClicked: root.form.saveDefaultOnly()
            }
        }
    }
}
