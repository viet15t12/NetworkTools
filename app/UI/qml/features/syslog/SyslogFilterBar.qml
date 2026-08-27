pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "syslogFilterBar"

    property string selectedHost: ""
    property string chosenHost: ""
    property var selectedHosts: []
    property var selectedSeverities: []
    property var hostOptions: []
    property int displayedCount: 0
    property string validationMessage: ""
    property bool resetting: false
    readonly property var backend: typeof syslogManager !== "undefined"
                                   && syslogManager !== null ? syslogManager : null
    readonly property bool wideLayout: width >= 1180
    readonly property bool twoColumnLayout: !wideLayout && width >= 560
    readonly property var hostValues: {
        const values = []
        const seen = ({})
        const selected = String(root.selectedHost || "").trim()
        if (selected !== "") {
            values.push(selected)
            seen[selected.toLocaleLowerCase()] = true
        }
        for (let i = 0; i < root.hostOptions.length; ++i) {
            const host = String(root.hostOptions[i] || "").trim()
            const key = host.toLocaleLowerCase()
            if (host !== "" && !seen[key]) {
                values.push(host)
                seen[key] = true
            }
        }
        return values
    }
    readonly property var hostFilterOptions: {
        const options = []
        for (let i = 0; i < root.hostValues.length; ++i)
            options.push({label: root.hostValues[i], value: root.hostValues[i]})
        return options
    }
    readonly property var severityFilterOptions: [
        {label: "0 · Emergency", value: 0},
        {label: "1 · Alert", value: 1},
        {label: "2 · Critical", value: 2},
        {label: "3 · Error", value: 3},
        {label: "4 · Warning", value: 4},
        {label: "5 · Notice", value: 5},
        {label: "6 · Informational", value: 6},
        {label: "7 · Debug", value: 7}
    ]

    signal filtersChanged(var filters)
    signal resetHostRequested()
    signal exportRequested()

    implicitHeight: filterLayout.implicitHeight + Theme.spacing24
    color: Theme.contentPanelSurface
    border.color: root.validationMessage !== "" ? Theme.alertError : Theme.contentPanelBorder
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall

    function currentFilters(hostOverride) {
        const protocols = protocolBox.currentIndex === 1 ? ["udp"]
                        : protocolBox.currentIndex === 2 ? ["tcp"] : []
        const hosts = hostOverride === undefined
                    ? root.selectedHosts.slice()
                    : (String(hostOverride || "").trim() === ""
                       ? [] : [String(hostOverride).trim()])
        return {
            "host": hosts.length === 1 ? hosts[0] : "",
            "hosts": hosts,
            "search": "",
            "severities": root.selectedSeverities.slice(),
            "protocols": protocols,
            "from_time": fromField.text.trim(),
            "to_time": toField.text.trim(),
            "per_host": latestPerHost.value
        }
    }

    function emitFilters() {
        if (root.resetting)
            return
        const base = currentFilters()
        if (root.backend !== null
                && typeof root.backend.buildLogFilters === "function") {
            const result = root.backend.buildLogFilters(base, smartSearch.text)
            if (!result || result.ok !== true) {
                root.validationMessage = String(
                    result && result.message ? result.message : "Invalid smart filter."
                )
                return
            }
            root.validationMessage = ""
            root.filtersChanged(result.filters)
            return
        }
        base.search = smartSearch.text.trim()
        root.validationMessage = ""
        root.filtersChanged(base)
    }

    function resetFilters() {
        root.resetting = true
        debounce.stop()
        smartSearch.clear()
        root.selectedSeverities = []
        root.selectedHosts = []
        protocolBox.currentIndex = 0
        fromField.clear()
        toField.clear()
        latestPerHost.value = 0
        root.chosenHost = ""
        root.validationMessage = ""
        root.resetting = false
        if (root.selectedHost !== "")
            root.resetHostRequested()
        root.emitFilters()
    }

    onSelectedHostChanged: {
        root.chosenHost = String(root.selectedHost || "")
        root.selectedHosts = root.chosenHost === "" ? [] : [root.chosenHost]
    }

    Component.onCompleted: {
        root.chosenHost = String(root.selectedHost || "")
        root.selectedHosts = root.chosenHost === "" ? [] : [root.chosenHost]
    }

    Timer {
        id: debounce
        interval: 320
        repeat: false
        onTriggered: root.emitFilters()
    }

    GridLayout {
        id: filterLayout
        objectName: "syslogFilterLayout"
        anchors.fill: parent
        anchors.margins: Theme.spacing12
        columns: root.wideLayout ? 6 : (root.twoColumnLayout ? 2 : 1)
        columnSpacing: Theme.spacing8
        rowSpacing: Theme.spacing8

        Item {
            Layout.row: 0
            Layout.column: 0
            Layout.columnSpan: root.wideLayout || root.twoColumnLayout ? 2 : 1
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: smartSearch.implicitHeight

            StandardTextField {
                id: smartSearch
                objectName: "syslogMessageSearch"
                anchors.fill: parent
                readOnly: true
                rightPadding: 38
                placeholderText: "Click to build a Smart Filter…"
            }
            ThemedIcon {
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing12
                anchors.verticalCenter: parent.verticalCenter
                z: 11
                iconSource: AppAssets.actionFilter
                iconSize: Theme.iconSizeSmall
                iconColor: Theme.accentColor
            }
            MouseArea {
                anchors.fill: parent
                z: 12
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: smartFilterBuilder.openFor(smartSearch.text)
            }
        }

        SyslogMultiSelectFilter {
            id: hostBox
            objectName: "syslogHostFilterChip"
            Layout.row: root.wideLayout ? 0 : 1
            Layout.column: root.wideLayout ? 2 : 0
            Layout.fillWidth: !root.wideLayout
            Layout.preferredWidth: root.wideLayout ? 190 : Theme.inputMinimumWidth
            options: root.hostFilterOptions
            selectedValues: root.selectedHosts
            allText: "All connected hosts"
            pluralText: "hosts"
            accessibleName: "Syslog hosts"
            onSelectionChanged: values => {
                root.selectedHosts = values
                root.chosenHost = values.length === 1 ? String(values[0]) : ""
                root.emitFilters()
            }
        }

        SyslogMultiSelectFilter {
            id: severityBox
            objectName: "syslogSeverityFilter"
            Layout.row: root.wideLayout ? 0 : (root.twoColumnLayout ? 1 : 2)
            Layout.column: root.wideLayout ? 3 : (root.twoColumnLayout ? 1 : 0)
            Layout.fillWidth: !root.wideLayout
            Layout.preferredWidth: root.wideLayout ? 174 : Theme.inputMinimumWidth
            options: root.severityFilterOptions
            selectedValues: root.selectedSeverities
            allText: "All severities"
            pluralText: "severities"
            accessibleName: "Syslog severities"
            onSelectionChanged: values => {
                root.selectedSeverities = values
                root.emitFilters()
            }
        }

        StandardComboBox {
            id: protocolBox
            objectName: "syslogProtocolFilter"
            Layout.row: root.wideLayout ? 0 : (root.twoColumnLayout ? 2 : 3)
            Layout.column: root.wideLayout ? 4 : 0
            Layout.fillWidth: !root.wideLayout
            Layout.preferredWidth: root.wideLayout ? 140 : Theme.inputMinimumWidth
            model: ["All protocols", "UDP", "TCP"]
            onActivated: root.emitFilters()
        }

        RowLayout {
            Layout.row: root.wideLayout ? 0 : (root.twoColumnLayout ? 4 : 7)
            Layout.column: root.wideLayout ? 5 : 0
            Layout.columnSpan: root.wideLayout ? 1 : (root.twoColumnLayout ? 2 : 1)
            Layout.fillWidth: !root.wideLayout
            spacing: Theme.spacing4

            StandardButton {
                objectName: "syslogSmartFilterHelpButton"
                Layout.preferredWidth: implicitHeight
                Layout.maximumWidth: implicitHeight
                type: "Icon"
                icon.source: AppAssets.statusInfo
                tooltip: "Smart filter syntax help"
                onClicked: smartFilterHelp.open()
            }
            StandardButton {
                objectName: "syslogExportExcelButton"
                Layout.fillWidth: !root.wideLayout
                text: "Export Excel"
                type: "Secondary"
                icon.source: AppAssets.actionDownload
                tooltip: "Export the logs currently displayed after all filters"
                enabled: root.displayedCount > 0
                onClicked: root.exportRequested()
            }
            StandardButton {
                objectName: "syslogResetFiltersButton"
                Layout.fillWidth: !root.wideLayout
                text: "Reset"
                type: "Secondary"
                enabled: smartSearch.text !== "" || root.selectedSeverities.length > 0
                         || protocolBox.currentIndex > 0 || fromField.text !== ""
                         || toField.text !== "" || latestPerHost.value > 0
                         || root.selectedHosts.length > 0
                onClicked: root.resetFilters()
            }
        }

        StandardTextField {
            id: fromField
            objectName: "syslogFromTimeFilter"
            Layout.row: root.wideLayout ? 1 : (root.twoColumnLayout ? 3 : 4)
            Layout.column: 0
            Layout.fillWidth: true
            labelText: "From (UTC)"
            placeholderText: "2026-08-26T18:00"
            onEditingFinished: root.emitFilters()
            onAccepted: root.emitFilters()
        }

        StandardTextField {
            id: toField
            objectName: "syslogToTimeFilter"
            Layout.row: root.wideLayout ? 1 : (root.twoColumnLayout ? 3 : 5)
            Layout.column: root.wideLayout || root.twoColumnLayout ? 1 : 0
            Layout.fillWidth: true
            labelText: "To (UTC)"
            placeholderText: "2026-08-26T19:00"
            onEditingFinished: root.emitFilters()
            onAccepted: root.emitFilters()
        }

        StandardSpinBox {
            id: latestPerHost
            objectName: "syslogLatestPerHostFilter"
            Layout.row: root.wideLayout ? 1 : (root.twoColumnLayout ? 2 : 6)
            Layout.column: root.wideLayout ? 2 : (root.twoColumnLayout ? 1 : 0)
            Layout.fillWidth: true
            Layout.preferredWidth: root.wideLayout ? 190 : Theme.inputMinimumWidth
            labelText: "Latest N per host (0 = all)"
            from: 0
            to: 500
            value: 0
            onValueChanged: debounce.restart()
        }

        Text {
            Layout.row: root.wideLayout ? 1 : (root.twoColumnLayout ? 5 : 8)
            Layout.column: root.wideLayout ? 3 : 0
            Layout.columnSpan: root.wideLayout ? 3 : (root.twoColumnLayout ? 2 : 1)
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            visible: root.validationMessage !== ""
            text: root.validationMessage
            color: Theme.alertError
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            wrapMode: Text.WordWrap
        }
    }

    SyslogSmartFilterHelp { id: smartFilterHelp }
    SyslogSmartFilterBuilder {
        id: smartFilterBuilder
        onApplyRequested: expression => {
            smartSearch.text = expression
            root.emitFilters()
        }
    }
}
