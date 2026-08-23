pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Item {
    id: root
    objectName: "syslogDevicesPanel"

    property var devices: []
    property var filteredDevices: []
    property string selectedHost: ""
    property bool busy: false
    readonly property var backend: typeof syslogManager !== "undefined" && syslogManager !== null
                                   ? syslogManager : null

    signal hostSelected(string host)
    signal operationFinished(bool ok, string message)

    function applyFilter() {
        const value = search.text.toLowerCase().trim()
        filteredDevices = devices.filter(function(row) {
            return value === ""
                || String(row.host || "").toLowerCase().indexOf(value) >= 0
                || String(row.device_name || "").toLowerCase().indexOf(value) >= 0
        })
    }

    function reloadDevices() {
        if (backend !== null)
            backend.loadConnectedDevices()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 36

            Text {
                objectName: "syslogPanelHeaderTitle"
                anchors.left: parent.left
                anchors.leftMargin: Theme.spacing16
                anchors.right: hostCountBadge.left
                anchors.rightMargin: Theme.spacing8
                anchors.verticalCenter: parent.verticalCenter
                text: "HOSTS"
                elide: Text.ElideRight
                color: Theme.panelSideBarTextSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.capitalization: Font.AllUppercase
                font.weight: Font.Medium
            }

            StandardBadge {
                id: hostCountBadge
                objectName: "syslogPanelHostCountBadge"
                anchors.right: reloadButton.left
                anchors.rightMargin: Theme.spacing8
                anchors.verticalCenter: parent.verticalCenter
                text: String(root.devices.length)
                badgeColor: Theme.accentEmphasis
            }

            IconButton {
                id: reloadButton
                objectName: "syslogPanelReloadButton"
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing8
                anchors.verticalCenter: parent.verticalCenter
                buttonSize: Theme.sideBarFeatureIcon
                iconSource: AppAssets.actionRefresh
                idleColor: Theme.panelSideBarTextSecondary
                activeColor: Theme.panelSideBarTextPrimary
                selectedBackground: Theme.panelSideBarItemSelected
                hoverBackground: Theme.panelSideBarItemHover
                tooltip: root.busy ? "Refreshing Connected Hosts..." : "Refresh Connected Hosts"
                enabled: root.backend !== null && !root.busy
                onClicked: root.reloadDevices()
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.borderWidth
                color: Theme.panelSideBarBorderColor
            }
        }

        SideBarSearch {
            id: search
            Layout.fillWidth: true
            Layout.margins: Theme.spacing8
            placeholderText: "Search connected hosts..."
            onTextChanged: debounce.restart()
        }

        ListView {
            id: deviceList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.filteredDevices
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: SyslogDeviceItem {
                required property var modelData
                width: ListView.view.width
                deviceData: modelData
                selected: root.selectedHost === String(modelData.host || "")
                onClicked: function(host) {
                    root.selectedHost = host
                    root.hostSelected(host)
                }
            }

            Text {
                anchors.centerIn: parent
                width: Math.max(0, parent.width - Theme.spacing32)
                visible: root.filteredDevices.length === 0
                text: root.backend === null
                      ? "System Logs backend is unavailable."
                      : root.devices.length === 0
                        ? "No connected devices.\nConnect a device from Dashboard first."
                        : "No hosts match the current search."
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: Theme.panelSideBarTextSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
        }

    }

    Timer {
        id: debounce
        interval: 250
        repeat: false
        onTriggered: root.applyFilter()
    }

    Timer {
        interval: 5000
        repeat: true
        running: root.visible && root.backend !== null
        onTriggered: root.reloadDevices()
    }

    Connections {
        target: root.backend

        function onConnectedDevicesChanged(rows) {
            root.devices = rows || []
            root.applyFilter()
        }

    }

    onVisibleChanged: {
        if (visible)
            reloadDevices()
    }
}
