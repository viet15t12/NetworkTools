pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import "../../../../components/utils/ValidationUtils.js" as V

// Migrated from BaseCard to ProcessCard (UI-P1-05 rename).
ProcessCard {
    id: card
    showArea: false
    processIdLabel: "AS Number"
    processIdPlaceholder: "e.g., 100"
    helpTitle: "EIGRP process parameters"
    helpText: "AS Number: EIGRP autonomous-system number; neighbors must use the same value.\n\n" +
              "Router ID: unique identifier in IPv4 notation. Leave empty to let IOS select it.\n\n" +
              "Auto Summary: summarizes routes at classful boundaries; normally keep disabled in modern networks.\n\n" +
              "Passive Default: prevents neighbor formation on all interfaces unless overridden.\n\n" +
              "BFD All Interfaces: enables fast failure detection where supported.\n\n" +
              "Stub / Stub Options / Leak Map: limits queries and controls which routes a stub router advertises.\n\n" +
              "Metric Weights: K1-K5 values, entered as six integers such as 0 1 0 1 0 0.\n\n" +
              "Active Timer: seconds before an active route is declared stuck-in-active.\n\n" +
              "Distance Internal/External: administrative distance. Variance enables unequal-cost load balancing; Maximum Paths limits installed paths."

    property int processUid: 0
    property var payload: ({})
    property alias networks: networksModel
    property alias interfaceSettings: interfaceSettingsModel
    property alias passiveInterfaces: passiveInterfacesModel
    property alias distributeLists: distributeListsModel
    property alias offsetLists: offsetListsModel
    property alias redistribute: redistributeModel
    property alias keyChains: keyChainsModel

    signal cardChanged()

    ListModel { id: networksModel }
    ListModel { id: interfaceSettingsModel }
    ListModel { id: passiveInterfacesModel }
    ListModel { id: distributeListsModel }
    ListModel { id: offsetListsModel }
    ListModel { id: redistributeModel }
    ListModel { id: keyChainsModel }

    function appendRows(model, rows, mapper) {
        model.clear()
        const list = rows || []
        for (let i = 0; i < list.length; i++)
            model.append(mapper(list[i]))
    }

    onPayloadChanged: {
        if (!payload)
            return

        processId = payload.as_number !== undefined ? String(payload.as_number) : ""
        routerId = payload.router_id !== undefined ? String(payload.router_id) : ""
        timersActiveField.text = payload.timers_active_time > 0 ? String(payload.timers_active_time) : ""
        bfdAllCheck.checked = payload.bfd_all_interfaces === true || payload.bfd_all_interfaces === 1
        autoSummaryCheck.checked = payload.auto_summary === true || payload.auto_summary === 1
        passiveDefaultCheck.checked = payload.passive_default === true || payload.passive_default === 1
        stubEnabledCheck.checked = payload.stub_enabled === true || payload.stub_enabled === 1
        stubOptionsField.text = payload.stub_options || ""
        stubLeakMapField.text = payload.stub_leak_map || ""
        varianceField.text = payload.variance > 0 ? String(payload.variance) : ""
        maxPathsField.text = payload.maximum_paths > 0 ? String(payload.maximum_paths) : ""

        const weights = String(payload.metric_weights || "").trim()
        useMetricCheck.checked = weights !== "" && weights !== "0 1 0 1 0 0"
        metricField.text = useMetricCheck.checked ? weights : "0 1 0 1 0 0"

        distInternalField.text = payload.distance_internal > 0 ? String(payload.distance_internal) : ""
        distExternalField.text = payload.distance_external > 0 ? String(payload.distance_external) : ""

        appendRows(networksModel, payload.networks, function(row) {
            return {
                network: row.network || "",
                wildcard: row.wildcard || "",
                interface_name: row.interface_name || ""
            }
        })
        appendRows(interfaceSettingsModel, payload.interface_settings, function(row) {
            return {
                interface_name: row.interface_name || "",
                bandwidth: row.bandwidth > 0 ? String(row.bandwidth) : "",
                delay: row.delay > 0 ? String(row.delay) : "",
                hello_interval: row.hello_interval > 0 ? String(row.hello_interval) : "",
                hold_time: row.hold_time > 0 ? String(row.hold_time) : "",
                auth_key_chain: row.auth_key_chain || "",
                summary_ip: row.summary_ip || "",
                summary_mask: row.summary_mask || "",
                split_horizon: row.split_horizon === true || row.split_horizon === 1,
                bandwidth_percent: row.bandwidth_percent > 0 ? String(row.bandwidth_percent) : "",
                next_hop_self: row.next_hop_self === true || row.next_hop_self === 1,
                bfd: row.bfd === true || row.bfd === 1,
                bfd_tx: row.bfd_tx > 0 ? String(row.bfd_tx) : "",
                bfd_rx: row.bfd_rx > 0 ? String(row.bfd_rx) : "",
                bfd_multiplier: row.bfd_multiplier > 0 ? String(row.bfd_multiplier) : ""
            }
        })
        appendRows(passiveInterfacesModel, payload.passive_interfaces, function(row) {
            return { interface_name: row.interface_name || "", mode: row.mode || "passive" }
        })
        appendRows(distributeListsModel, payload.distribute_lists, function(row) {
            return { list_name: row.list_name || "", direction: row.direction || "in", interface_name: row.interface_name || "" }
        })
        appendRows(offsetListsModel, payload.offset_lists, function(row) {
            return { list_name: row.list_name || "", direction: row.direction || "in", value: row.value > 0 ? String(row.value) : "", interface_name: row.interface_name || "" }
        })
        appendRows(redistributeModel, payload.redistribute, function(row) {
            return {
                protocol: row.protocol || "",
                route_map: row.route_map || "",
                metric_bw: row.metric_bw > 0 ? String(row.metric_bw) : "",
                metric_delay: row.metric_delay > 0 ? String(row.metric_delay) : "",
                metric_reliability: row.metric_reliability > 0 ? String(row.metric_reliability) : "",
                metric_load: row.metric_load > 0 ? String(row.metric_load) : "",
                metric_mtu: row.metric_mtu > 0 ? String(row.metric_mtu) : ""
            }
        })
        appendRows(keyChainsModel, payload.key_chains, function(row) {
            return {
                chain_name: row.chain_name || "",
                key_id: row.key_id > 0 ? String(row.key_id) : "",
                key_string: row.key_string || "",
                accept_lifetime: row.accept_lifetime || "",
                send_lifetime: row.send_lifetime || ""
            }
        })
    }

    function modelToArray(model) {
        const rows = []
        for (let i = 0; i < model.count; i++) {
            const row = model.get(i)
            rows.push(JSON.parse(JSON.stringify(row)))
        }
        return rows
    }

    function signatureData() {
        return JSON.stringify(snapshotForSave())
    }

    onProcessIdChanged: card.cardChanged()
    onRouterIdChanged: card.cardChanged()

    Connections {
        target: networksModel
        function onCountChanged() { card.cardChanged() }
        function onDataChanged() { card.cardChanged() }
    }
    Connections {
        target: interfaceSettingsModel
        function onCountChanged() { card.cardChanged() }
        function onDataChanged() { card.cardChanged() }
    }
    Connections {
        target: passiveInterfacesModel
        function onCountChanged() { card.cardChanged() }
        function onDataChanged() { card.cardChanged() }
    }
    Connections {
        target: distributeListsModel
        function onCountChanged() { card.cardChanged() }
        function onDataChanged() { card.cardChanged() }
    }
    Connections {
        target: offsetListsModel
        function onCountChanged() { card.cardChanged() }
        function onDataChanged() { card.cardChanged() }
    }
    Connections {
        target: redistributeModel
        function onCountChanged() { card.cardChanged() }
        function onDataChanged() { card.cardChanged() }
    }
    Connections {
        target: keyChainsModel
        function onCountChanged() { card.cardChanged() }
        function onDataChanged() { card.cardChanged() }
    }

    function positiveIntOrZero(text) {
        const value = parseInt(String(text || "").trim(), 10)
        return isNaN(value) ? 0 : value
    }

    function intStringOrEmpty(value) {
        const str = String(value || "").trim()
        if (str === "")
            return ""
        const n = parseInt(str, 10)
        return isNaN(n) ? "" : String(n)
    }

    function validatePositiveOptional(text, label) {
        const raw = String(text || "").trim()
        if (raw === "")
            return { ok: true, message: "" }
        const value = parseInt(raw, 10)
        if (isNaN(value) || value < 1)
            return { ok: false, message: "%1 must be a positive integer.".arg(label) }
        return { ok: true, message: "" }
    }

    function validate(strictValidation) {
        const asStr = String(processId).trim()
        if (asStr === "")
            return { ok: false, message: "EIGRP AS Number is required." }
        if (!V.isValidAsNumber(asStr))
            return { ok: false, message: "EIGRP AS Number must be an integer between 1 and 65535." }

        const rIdStr = String(routerId).trim()
        if (rIdStr !== "" && !V.isValidIPv4(rIdStr))
            return { ok: false, message: "Router ID must be a valid IPv4 address." }

        if (useMetricCheck.checked) {
            const metricCheck = V.parseMetricWeights(metricField.text)
            if (!metricCheck.ok)
                return { ok: false, message: metricCheck.reason }
        }

        const checks = [
            validatePositiveOptional(timersActiveField.text, "Active timer"),
            validatePositiveOptional(distInternalField.text, "EIGRP internal distance"),
            validatePositiveOptional(distExternalField.text, "EIGRP external distance"),
            validatePositiveOptional(varianceField.text, "Variance"),
            validatePositiveOptional(maxPathsField.text, "Maximum paths")
        ]
        for (let c = 0; c < checks.length; c++) {
            if (!checks[c].ok)
                return checks[c]
        }

        for (let i = 0; i < networksModel.count; i++) {
            const row = networksModel.get(i)
            const net = String(row.network || "").trim()
            const wildcard = String(row.wildcard || "").trim()
            if (net === "")
                continue
            if (!V.isValidIPv4(net))
                return { ok: false, message: "Network must be a valid IPv4 address in AS %1.".arg(asStr) }
            if (wildcard !== "" && !V.isValidWildcard(wildcard))
                return { ok: false, message: "Wildcard must be a valid IPv4 wildcard in AS %1.".arg(asStr) }
        }

        return { ok: true, message: "" }
    }

    function snapshotForSave() {
        const netRows = []
        for (let i = 0; i < networksModel.count; i++) {
            const row = networksModel.get(i)
            const network = String(row.network || "").trim()
            if (network !== "") {
                netRows.push({
                    network: network,
                    wildcard: String(row.wildcard || "").trim(),
                    interface_name: String(row.interface_name || "").trim()
                })
            }
        }

        return {
            eigrp_id: payload && payload.eigrp_id !== undefined ? payload.eigrp_id : 0,
            as_number: intStringOrEmpty(processId),
            router_id: String(routerId).trim(),
            timers_active_time: positiveIntOrZero(timersActiveField.text),
            bfd_all_interfaces: bfdAllCheck.checked,
            auto_summary: autoSummaryCheck.checked,
            passive_default: passiveDefaultCheck.checked,
            metric_weights: useMetricCheck.checked ? metricField.text.trim() : "0 1 0 1 0 0",
            distance_internal: positiveIntOrZero(distInternalField.text),
            distance_external: positiveIntOrZero(distExternalField.text),
            variance: positiveIntOrZero(varianceField.text),
            maximum_paths: positiveIntOrZero(maxPathsField.text),
            stub_enabled: stubEnabledCheck.checked,
            stub_options: stubOptionsField.text.trim(),
            stub_leak_map: stubLeakMapField.text.trim(),
            action: payload && payload.action !== undefined ? payload.action : 15,
            action_Cfg: payload && payload.action_Cfg !== undefined ? String(payload.action_Cfg) : "1111111",
            networks: netRows,
            interface_settings: modelToArray(interfaceSettingsModel),
            passive_interfaces: modelToArray(passiveInterfacesModel),
            distribute_lists: modelToArray(distributeListsModel),
            offset_lists: modelToArray(offsetListsModel),
            redistribute: modelToArray(redistributeModel),
            key_chains: modelToArray(keyChainsModel)
        }
    }

    GridLayout {
        Layout.fillWidth: true
        columns: card.width < 760 ? 2 : 4
        columnSpacing: Theme.spacing16
        rowSpacing: Theme.spacing8

        StandardCheckBox { id: autoSummaryCheck; text: "Auto Summary"; Layout.alignment: Qt.AlignBottom; onCheckedChanged: card.cardChanged() }
        StandardCheckBox { id: passiveDefaultCheck; text: "Passive Default"; Layout.alignment: Qt.AlignBottom; onCheckedChanged: card.cardChanged() }
        StandardCheckBox { id: bfdAllCheck; text: "BFD All Interfaces"; Layout.alignment: Qt.AlignBottom; onCheckedChanged: card.cardChanged() }
        StandardCheckBox { id: stubEnabledCheck; text: "Stub"; Layout.alignment: Qt.AlignBottom; onCheckedChanged: card.cardChanged() }
        StandardCheckBox { id: useMetricCheck; text: "Custom Metrics"; Layout.alignment: Qt.AlignBottom; onCheckedChanged: card.cardChanged() }

        StandardTextField {
            id: metricField
            Layout.fillWidth: true
            Layout.minimumWidth: 160
            labelText: "Metric Weights"
            placeholderText: "0 1 0 1 0 0"
            visible: useMetricCheck.checked
            onTextChanged: card.cardChanged()
        }

        StandardTextField { id: timersActiveField; Layout.fillWidth: true; labelText: "Active Timer"; placeholderText: "optional"; onTextChanged: card.cardChanged() }
        StandardTextField { id: distInternalField; Layout.fillWidth: true; labelText: "Distance Internal"; placeholderText: "90"; onTextChanged: card.cardChanged() }
        StandardTextField { id: distExternalField; Layout.fillWidth: true; labelText: "Distance External"; placeholderText: "170"; onTextChanged: card.cardChanged() }
        StandardTextField { id: varianceField; Layout.fillWidth: true; labelText: "Variance"; placeholderText: "optional"; onTextChanged: card.cardChanged() }
        StandardTextField { id: maxPathsField; Layout.fillWidth: true; labelText: "Maximum Paths"; placeholderText: "optional"; onTextChanged: card.cardChanged() }
        StandardTextField { id: stubOptionsField; Layout.fillWidth: true; labelText: "Stub Options"; placeholderText: "connected summary"; enabled: stubEnabledCheck.checked; onTextChanged: card.cardChanged() }
        StandardTextField { id: stubLeakMapField; Layout.fillWidth: true; labelText: "Stub Leak Map"; placeholderText: "optional"; enabled: stubEnabledCheck.checked; onTextChanged: card.cardChanged() }
    }
}
