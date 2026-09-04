pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI
import "../../../../components/utils/ValidationUtils.js" as V

// Migrated from BaseCard to ProcessCard (UI-P1-05 rename).
ProcessCard {
    id: card
    showArea: true
    processIdLabel: "Process ID"
    processIdPlaceholder: "e.g., 1"
    helpTitle: "OSPF process parameters"
    helpText: "Process ID: local OSPF process number, 1-65535; it does not need to match neighboring routers.\n\n" +
              "Router ID: unique 32-bit identifier written as an IPv4 address, for example 1.1.1.1. Leave empty to let IOS select it.\n\n" +
              "Reference BW: reference bandwidth in Mbps used to calculate OSPF cost; use the same value throughout the domain.\n\n" +
              "Passive Default: suppresses OSPF hellos on every interface unless explicitly enabled.\n\n" +
              "Default Originate: advertises a default route; Always advertises it even when no default route exists locally.\n\n" +
              "AuthenticationCFG: enables message-digest authentication for configured areas; matching keys are still required on interfaces."

    property int processUid: 0
    property var payload: ({})
    property var distance: ({})
    property var tuning: ({})
    property alias referenceBandwidthText: refBwField.text

    signal cardChanged()

    ListModel { id: areasModel }
    ListModel { id: redistributeModel }
    ListModel { id: passiveInterfacesModel }
    ListModel { id: interfaceSettingsModel }

    property alias areas: areasModel
    property alias redistribute: redistributeModel
    property alias passiveInterfaces: passiveInterfacesModel
    property alias interfaceSettings: interfaceSettingsModel

    // ── Xử lý dữ liệu khởi tạo ──────────────────────────────────────────────
    onPayloadChanged: {
        if (!payload) return

        processId = payload.process_id !== undefined ? String(payload.process_id) : ""
        routerId  = payload.router_id  !== undefined ? String(payload.router_id)  : ""

        refBwField.text = payload.reference_bandwidth !== undefined && payload.reference_bandwidth > 0
            ? String(payload.reference_bandwidth) : ""

        passiveDefaultCheck.checked  = payload.passive_default          === true || payload.passive_default          === 1
        defaultOriginateCheck.checked = payload.default_originate       === true || payload.default_originate        === 1
        defaultAlwaysCheck.checked    = payload.default_originate_always === true || payload.default_originate_always === 1

        distance = payload.distance || ({})
        tuning = payload.tuning || ({})

        networks.clear()
        const netList = payload.networks || []
        for (let i = 0; i < netList.length; i++) {
            networks.append({
                network:  netList[i].network  || "",
                wildcard: netList[i].wildcard || "",
                // Area 0 is valid.  Using `value || ""` turned the numeric
                // zero loaded from SQLite into an empty field, so a saved
                // Routing Group immediately failed validation as an
                // "incomplete" network row.
                area:     netList[i].area !== undefined && netList[i].area !== null
                          && String(netList[i].area).trim() !== ""
                          ? String(netList[i].area) : "0"
            })
        }

        areas.clear()
        const areaList = payload.areas || []
        for (let a = 0; a < areaList.length; a++) {
            const rangeList = areaList[a].ranges || []
            const normalizedRanges = []
            for (let rangeIndex = 0; rangeIndex < rangeList.length; rangeIndex++) {
                normalizedRanges.push({
                    ip: rangeList[rangeIndex].ip || "",
                    mask: rangeList[rangeIndex].mask || "",
                    advertise: rangeList[rangeIndex].advertise === undefined
                               ? true
                               : (rangeList[rangeIndex].advertise === true
                                  || rangeList[rangeIndex].advertise === 1),
                    cost: rangeList[rangeIndex].cost !== undefined
                          && rangeList[rangeIndex].cost !== null
                          ? String(rangeList[rangeIndex].cost) : ""
                })
            }
            areas.append({
                area_id: areaList[a].area_id !== undefined ? String(areaList[a].area_id) : "",
                area_type: areaList[a].area_type || "normal",
                no_summary: areaList[a].no_summary === true || areaList[a].no_summary === 1,
                authentication: areaList[a].authentication || "",
                ranges: normalizedRanges
            })
        }
        authenticationCfgCheck.checked = payload.authentication_cfg === true
                || payload.authentication_cfg === 1
                || areaList.some(area => String(area.authentication || "") !== "")

        redistribute.clear()
        const redistList = payload.redistribute || []
        for (let r = 0; r < redistList.length; r++) {
            redistribute.append({
                protocol: redistList[r].protocol || "static",
                process_id: redistList[r].process_id !== undefined ? String(redistList[r].process_id) : "",
                subnets: redistList[r].subnets === undefined ? true : (redistList[r].subnets === true || redistList[r].subnets === 1),
                metric: redistList[r].metric !== undefined ? String(redistList[r].metric) : "",
                metric_type: redistList[r].metric_type !== undefined ? String(redistList[r].metric_type) : "",
                route_map: redistList[r].route_map || ""
            })
        }

        passiveInterfaces.clear()
        const passiveList = payload.passive_interfaces || []
        for (let p = 0; p < passiveList.length; p++) {
            passiveInterfaces.append({
                interface_name: passiveList[p].interface_name || "",
                passive: passiveList[p].passive === undefined ? true : (passiveList[p].passive === true || passiveList[p].passive === 1)
            })
        }

        interfaceSettings.clear()
        const ifaceList = payload.interface_settings || []
        for (let s = 0; s < ifaceList.length; s++) {
            interfaceSettings.append({
                interface_name: ifaceList[s].interface_name || "",
                area: ifaceList[s].area !== undefined ? String(ifaceList[s].area) : "",
                cost: ifaceList[s].cost !== undefined ? String(ifaceList[s].cost) : "",
                priority: ifaceList[s].priority !== undefined ? String(ifaceList[s].priority) : "1",
                hello_interval: ifaceList[s].hello_interval !== undefined ? String(ifaceList[s].hello_interval) : "",
                dead_interval: ifaceList[s].dead_interval !== undefined ? String(ifaceList[s].dead_interval) : "",
                mtu_ignore: ifaceList[s].mtu_ignore === true || ifaceList[s].mtu_ignore === 1,
                bfd: ifaceList[s].bfd === true || ifaceList[s].bfd === 1,
                network_type: ifaceList[s].network_type || "",
                auth_type: ifaceList[s].auth_type || "",
                auth_key: ifaceList[s].auth_key || ""
            })
        }
    }

    // ── Dirty Flag signature ─────────────────────────────────────────────────
    function signatureData() {
        const netList = []
        for (let i = 0; i < networks.count; i++) {
            const row = networks.get(i)
            const networkText = String(row.network || "").trim()
            const wildcardText = String(row.wildcard || "").trim()
            const areaText = String(row.area || "").trim()
            netList.push({
                network:  networkText,
                wildcard: wildcardText,
                area:     networkText !== "" || wildcardText !== ""
                          ? (areaText === "" ? "0" : areaText) : areaText
            })
        }
        const state = {
            process_id:               String(processId).trim(),
            router_id:                String(routerId).trim(),
            reference_bandwidth:      refBwField.text.trim(),
            passive_default:          passiveDefaultCheck.checked,
            default_originate:        defaultOriginateCheck.checked,
            default_originate_always: defaultAlwaysCheck.checked,
            authentication_cfg:       authenticationCfgCheck.checked,
            networks:                 netList,
            distance:                 distance,
            tuning:                   tuning,
            areas:                    modelToArray(areas),
            redistribute:             modelToArray(redistribute),
            passive_interfaces:       modelToArray(passiveInterfaces),
            interface_settings:       modelToArray(interfaceSettings)
        }
        return JSON.stringify(state)
    }

    function modelToArray(model) {
        const rows = []
        // ListModel.get() returns a QObject-backed role object. Passing that
        // object through a QVariant slot leaves Python unable to convert it to
        // a mapping. JSON round-tripping creates a plain, deeply copied JS
        // object, including nested area ranges.
        for (let i = 0; i < model.count; i++)
            rows.push(JSON.parse(JSON.stringify(model.get(i))))
        return rows
    }

    onProcessIdChanged: card.cardChanged()
    onRouterIdChanged:  card.cardChanged()

    Connections {
        target: networks
        function onCountChanged() { card.cardChanged() }
        function onDataChanged()  { card.cardChanged() }
    }

    Connections {
        target: areas
        function onCountChanged() { card.cardChanged() }
        function onDataChanged()  { card.cardChanged() }
    }

    Connections {
        target: redistribute
        function onCountChanged() { card.cardChanged() }
        function onDataChanged()  { card.cardChanged() }
    }

    Connections {
        target: passiveInterfaces
        function onCountChanged() { card.cardChanged() }
        function onDataChanged()  { card.cardChanged() }
    }

    Connections {
        target: interfaceSettings
        function onCountChanged() { card.cardChanged() }
        function onDataChanged()  { card.cardChanged() }
    }

    // ── Validate ─────────────────────────────────────────────────────────────
    function validate(strictValidation) {
        const pIdStr = String(processId).trim()
        if (pIdStr === "")
            return { ok: false, message: "OSPF Process ID is required." }
        if (!V.isValidOspfProcessId(pIdStr))
            return { ok: false, message: "OSPF Process ID must be an integer between 1 and 65535." }

        const rIdStr = String(routerId).trim()
        if (rIdStr !== "" && !V.isValidIPv4(rIdStr))
            return { ok: false, message: "Router ID must be a valid IPv4 address." }

        const bwStr = refBwField.text.trim()
        if (bwStr !== "") {
            if (!/^\d+$/.test(bwStr) || Number(bwStr) < 1)
                return { ok: false, message: "Reference bandwidth must be a positive integer (Mbps)." }
        }

        for (let i = 0; i < networks.count; i++) {
            const row  = networks.get(i)
            const net  = String(row.network).trim()
            const wcard = String(row.wildcard).trim()
            const a    = String(row.area).trim()

            if (net === "" && wcard === "" && (a === "" || a === "0"))
                continue

            if (net === "" || wcard === "")
                return { ok: false, message: "Network row %1 in Process %2 is incomplete.".arg(i + 1).arg(pIdStr) }

            if (!V.isValidIPv4(net) || !V.isValidWildcard(wcard))
                return { ok: false, message: "Network and Wildcard must be valid IPv4 formats in Process %1.".arg(pIdStr) }
        }

        return { ok: true, message: "" }
    }

    // ── Snapshot để lưu ──────────────────────────────────────────────────────
    function snapshotForSave() {
        const netList = []
        for (let i = 0; i < networks.count; i++) {
            const row = networks.get(i)
            const n = String(row.network).trim()
            const w = String(row.wildcard).trim()
            const enteredArea = String(row.area).trim()
            const a = enteredArea === "" ? "0" : enteredArea
            if (n !== "" && w !== "")
                netList.push({ network: n, wildcard: w, area: a })
        }

        const bwStr = refBwField.text.trim()

        const areaPayload = modelToArray(areas)
        if (authenticationCfgCheck.checked) {
            if (areaPayload.length === 0)
                areaPayload.push({area_id: "0", area_type: "normal",
                                  no_summary: false,
                                  authentication: "message-digest", ranges: []})
            else {
                for (let areaIndex = 0; areaIndex < areaPayload.length; areaIndex++) {
                    if (String(areaPayload[areaIndex].authentication || "") === "")
                        areaPayload[areaIndex].authentication = "message-digest"
                }
            }
        } else {
            for (let clearIndex = 0; clearIndex < areaPayload.length; clearIndex++)
                areaPayload[clearIndex].authentication = ""
        }

        return {
            ospf_id:                  payload && payload.ospf_id !== undefined ? payload.ospf_id : 0,
            // Keep the exact input until backend validation. Parsing here used
            // to silently turn values such as "10abc" into 10.
            process_id:               String(processId).trim(),
            router_id:                String(routerId).trim(),
            reference_bandwidth:      bwStr === "" ? 0 : bwStr,
            passive_default:          passiveDefaultCheck.checked,
            default_originate:        defaultOriginateCheck.checked,
            default_originate_always: defaultAlwaysCheck.checked && defaultOriginateCheck.checked,
            authentication_cfg:       authenticationCfgCheck.checked,
            networks:                 netList,
            distance:                 distance,
            tuning:                   tuning,
            areas:                    areaPayload,
            redistribute:             modelToArray(redistribute),
            passive_interfaces:       modelToArray(passiveInterfaces),
            interface_settings:       modelToArray(interfaceSettings)
        }
    }

    // ── UI riêng của OSPF ────────────────────────────────────────────────────
    GridLayout {
        Layout.fillWidth: true
        columns: card.width < 760 ? 2 : 5
        columnSpacing: Theme.spacing16
        rowSpacing: Theme.spacing8

        StandardTextField {
            id: refBwField
            objectName: "ospfReferenceBandwidthField"
            Layout.fillWidth: true
            Layout.minimumWidth: 140
            labelText: "Reference BW"
            placeholderText: "e.g. 1000"
            onTextChanged: card.cardChanged()
        }

        StandardCheckBox {
            id: passiveDefaultCheck
            text: "Passive Default"
            Layout.alignment: Qt.AlignBottom
            onCheckedChanged: card.cardChanged()
        }

        StandardCheckBox {
            id: defaultOriginateCheck
            text: "Default Originate"
            Layout.alignment: Qt.AlignBottom
            onCheckedChanged: {
                if (!checked) defaultAlwaysCheck.checked = false
                card.cardChanged()
            }
        }

        StandardCheckBox {
            id: defaultAlwaysCheck
            text: "Always"
            enabled: defaultOriginateCheck.checked
            Layout.alignment: Qt.AlignBottom
            onCheckedChanged: card.cardChanged()
        }

        StandardCheckBox {
            id: authenticationCfgCheck
            text: "AuthenticationCFG"
            Layout.alignment: Qt.AlignBottom
            onCheckedChanged: card.cardChanged()
        }
    }
}
