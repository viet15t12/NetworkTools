pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "syslogFilterBar"

    property string selectedHost: ""
    readonly property bool wideLayout: width >= 1080
    readonly property bool twoColumnLayout: !wideLayout && width >= 480
    signal filtersChanged(var filters)
    signal resetHostRequested()

    implicitHeight: filterLayout.implicitHeight + Theme.spacing24
    color: Theme.contentPanelSurface
    border.color: Theme.contentPanelBorder
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall

    function currentFilters(hostOverride) {
        const severity = severityBox.currentIndex > 0
                       ? [severityBox.currentIndex - 1]
                       : []
        const protocols = protocolBox.currentIndex === 1 ? ["udp"]
                        : protocolBox.currentIndex === 2 ? ["tcp"] : []
        return {
            "host": hostOverride === undefined ? selectedHost : hostOverride,
            "search": search.text,
            "severities": severity,
            "protocols": protocols
        }
    }

    function emitFilters() {
        filtersChanged(currentFilters())
    }

    function resetFilters() {
        debounce.stop()
        search.clear()
        severityBox.currentIndex = 0
        protocolBox.currentIndex = 0
        if (selectedHost !== "")
            resetHostRequested()
        Qt.callLater(function() { root.filtersChanged(root.currentFilters("")) })
    }

    Timer {
        id: debounce
        interval: 280
        repeat: false
        onTriggered: root.emitFilters()
    }

    GridLayout {
        id: filterLayout
        objectName: "syslogFilterLayout"
        anchors.fill: parent
        anchors.margins: Theme.spacing12
        columns: root.wideLayout ? 5 : (root.twoColumnLayout ? 2 : 1)
        columnSpacing: Theme.spacing8
        rowSpacing: Theme.spacing8

        StandardTextField {
            id: search
            objectName: "syslogMessageSearch"
            Layout.row: 0
            Layout.column: 0
            Layout.fillWidth: true
            Layout.maximumWidth: root.wideLayout ? 360 : Number.POSITIVE_INFINITY
            placeholderText: "Search message or mnemonic..."
            onTextEdited: debounce.restart()
        }

        StandardComboBox {
            id: severityBox
            objectName: "syslogSeverityFilter"
            Layout.row: root.wideLayout || root.twoColumnLayout ? 0 : 1
            Layout.column: root.wideLayout || root.twoColumnLayout ? 1 : 0
            Layout.fillWidth: !root.wideLayout
            Layout.preferredWidth: root.wideLayout ? 190 : Theme.inputMinimumWidth
            model: [
                "All severities",
                "0 · Emergency",
                "1 · Alert",
                "2 · Critical",
                "3 · Error",
                "4 · Warning",
                "5 · Notice",
                "6 · Informational",
                "7 · Debug"
            ]
            onActivated: root.emitFilters()
        }

        StandardComboBox {
            id: protocolBox
            objectName: "syslogProtocolFilter"
            Layout.row: root.wideLayout ? 0 : (root.twoColumnLayout ? 1 : 2)
            Layout.column: root.wideLayout ? 2 : 0
            Layout.fillWidth: !root.wideLayout
            Layout.preferredWidth: root.wideLayout ? 150 : Theme.inputMinimumWidth
            model: ["All protocols", "UDP", "TCP"]
            onActivated: root.emitFilters()
        }

        Rectangle {
            objectName: "syslogHostFilterChip"
            Layout.row: root.wideLayout ? 0 : (root.twoColumnLayout ? 1 : 3)
            Layout.column: root.wideLayout ? 3 : (root.twoColumnLayout ? 1 : 0)
            Layout.preferredHeight: 28
            Layout.fillWidth: !root.wideLayout
            Layout.preferredWidth: root.wideLayout
                                   ? hostLabel.implicitWidth + Theme.spacing16
                                   : Theme.inputMinimumWidth
            radius: Theme.radiusRound
            color: Theme.alertInfoSubtle

            Text {
                id: hostLabel
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: Theme.spacing8
                anchors.rightMargin: Theme.spacing8
                anchors.verticalCenter: parent.verticalCenter
                text: root.selectedHost === "" ? "All connected hosts" : root.selectedHost
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
        }

        StandardButton {
            objectName: "syslogResetFiltersButton"
            Layout.row: root.wideLayout ? 0 : (root.twoColumnLayout ? 2 : 4)
            Layout.column: root.wideLayout ? 4 : 0
            Layout.columnSpan: root.twoColumnLayout ? 2 : 1
            Layout.fillWidth: !root.wideLayout
            text: "Reset Filters"
            type: "Secondary"
            enabled: search.text !== "" || severityBox.currentIndex > 0
                     || protocolBox.currentIndex > 0
                     || root.selectedHost !== ""
            onClicked: root.resetFilters()
        }
    }
}
