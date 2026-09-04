pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

// Bọc toàn bộ form bằng FormLayout
FormLayout {
    id: staticRoutingForm

    // Gắn dữ liệu vào Public API của FormLayout
    title: "Static Routes"
    hostIp: currentHostIp
    isDirty: hasPendingLocalChanges
    // Lỗi của form này được hiển thị ở Footer theo thiết kế cũ, nên ta để trống errorMessage trên Header
    errorMessage: ""

    property string currentHostIp: ""
    property bool isLoading: false
    property bool isSaving: false
    property bool hasPendingLocalChanges: false
    property bool hasPendingStaticChanges: false
    property string lastError: ""
    property bool defaultRouteEnabled: false
    property bool suppressDirty: false
    property string loadedDefaultRouteText: ""
    property string loadedStaticRoutesSignature: "[]"
    property int viewPushRevision: 0

    ListModel {
        id: routeModel
    }

    function notify(message, type) {
        if (typeof statusBar !== "undefined") {
            statusBar.showMessage(message, type)
        }
    }

    function markDirty() {
        if (staticRoutingForm.isLoading || staticRoutingForm.isSaving || staticRoutingForm.suppressDirty)
            return
        staticRoutingForm.refreshDirtyFlag()
    }

    function normalizeRouteText(text) {
        return String(text || "").trim()
    }

    function currentDefaultRouteText() {
        if (typeof defaultRouteCard === "undefined")
            return ""
        return normalizeRouteText(defaultRouteCard.routeText)
    }

    function staticRoutesSignature() {
        const normalized = []
        for (let i = 0; i < routeModel.count; i++) {
            const row = routeModel.get(i)
            normalized.push({
                routeId: row.routeId !== undefined ? Number(row.routeId) : 0,
                network: normalizeRouteText(row.network),
                mask: normalizeRouteText(row.mask),
                nexthop: normalizeRouteText(row.nexthop),
                ad: normalizeRouteText(row.ad)
            })
        }
        return JSON.stringify(normalized)
    }

    function hasDefaultChanges() {
        const current = staticRoutingForm.defaultRouteEnabled ? currentDefaultRouteText() : ""
        return current !== loadedDefaultRouteText
    }

    function hasStaticChanges() {
        return staticRoutesSignature() !== loadedStaticRoutesSignature
    }

    function canSaveDefaultOnly() {
        return !staticRoutingForm.isSaving && !staticRoutingForm.isLoading && hasDefaultChanges()
    }

    function canSaveStaticOnly() {
        return !staticRoutingForm.isSaving && !staticRoutingForm.isLoading && hasStaticChanges()
    }

    function refreshDirtyFlag() {
        const staticChanged = hasStaticChanges()
        staticRoutingForm.hasPendingStaticChanges = staticChanged
        staticRoutingForm.hasPendingLocalChanges = hasDefaultChanges() || staticChanged
    }

    function cancelDefaultChanges() {
        if (typeof defaultRouteCard === "undefined")
            return

        staticRoutingForm.suppressDirty = true
        defaultRouteCard.routeText = loadedDefaultRouteText
        staticRoutingForm.defaultRouteEnabled = loadedDefaultRouteText !== ""
        staticRoutingForm.suppressDirty = false
        staticRoutingForm.refreshDirtyFlag()
    }

    function showValidation(message) {
        notify(message, "error")
    }

    function isValidIPv4(ip) {
        const parts = String(ip).split(".")
        if (parts.length !== 4) return false
        for (let i = 0; i < 4; i++) {
            if (parts[i] === "") return false
            const num = parseInt(parts[i], 10)
            if (isNaN(num) || num < 0 || num > 255) return false
        }
        return true
    }

    function setRowErrors(index, networkError, maskError, nexthopError) {
        routeModel.setProperty(index, "networkError", networkError)
        routeModel.setProperty(index, "maskError", maskError)
        routeModel.setProperty(index, "nexthopError", nexthopError)
    }

    function canAddStaticRow() {
        for (let i = 0; i < routeModel.count; i++) {
            const row = routeModel.get(i)
            const network = String(row.network || "").trim()
            const mask = String(row.mask || "").trim()
            const nexthop = String(row.nexthop || "").trim()

            if (network === "" && mask === "" && nexthop === "") {
                setRowErrors(i, true, true, true)
                showValidation("A static route row is empty. Fill Network, Subnet Mask, and Next-hop before adding a new row.")
                return false
            }

            const missingNetwork = network === ""
            const missingMask = mask === ""
            const missingNexthop = nexthop === ""

            setRowErrors(i, missingNetwork, missingMask, missingNexthop)

            if (missingNetwork || missingMask || missingNexthop) {
                showValidation("Static route information is missing. Fill Network, Subnet Mask, and Next-hop before adding a new row.")
                return false
            }
        }
        return true
    }

    function buildRoutesPayload(strictValidation) {
        const routes = []
        let hasMissingRequired = false
        let hasSpaceError = false
        let hasIpv4Error = false

        for (let i = 0; i < routeModel.count; i++) {
            const row = routeModel.get(i)
            const network = String(row.network || "").trim()
            const mask = String(row.mask || "").trim()
            const nexthop = String(row.nexthop || "").trim()
            const adText = String(row.ad || "").trim()

            if (network === "" && mask === "" && nexthop === "") {
                setRowErrors(i, false, false, false)
                continue
            }

            const missingNetwork = network === ""
            const missingMask = mask === ""
            const missingNexthop = nexthop === ""
            setRowErrors(i, missingNetwork, missingMask, missingNexthop)

            if (missingNetwork || missingMask || missingNexthop) {
                hasMissingRequired = true
                continue
            }

            // Kiểm tra dấu cách
            const networkHasSpace = network.includes(" ")
            const maskHasSpace = mask.includes(" ")
            const nexthopHasSpace = nexthop.includes(" ")
            if (networkHasSpace || maskHasSpace || nexthopHasSpace) {
                setRowErrors(i, networkHasSpace, maskHasSpace, nexthopHasSpace)
                hasSpaceError = true
                continue
            }

            // Kiểm tra IPv4 hợp lệ
            const networkInvalid = !isValidIPv4(network)
            const maskInvalid = !isValidIPv4(mask)
            const nexthopInvalid = !isValidIPv4(nexthop)
            if (networkInvalid || maskInvalid || nexthopInvalid) {
                setRowErrors(i, networkInvalid, maskInvalid, nexthopInvalid)
                hasIpv4Error = true
                continue
            }

            let adValue = parseInt(adText)
            if (isNaN(adValue) || adValue < 1 || adValue > 255) {
                adValue = 1
            }

            routes.push({
                id: row.routeId !== undefined ? Number(row.routeId) : (row.id !== undefined ? Number(row.id) : 0),
                network: network,
                mask: mask,
                nexthop: nexthop,
                ad: adValue,
                edited: row.edited === true
            })
        }

        if (hasSpaceError) {
            staticRoutingForm.lastError = "IP fields cannot contain spaces."
            if (strictValidation) {
                showValidation("Highlighted fields contain spaces. Remove the spaces and try again.")
            }
            return null
        }

        if (hasIpv4Error) {
            staticRoutingForm.lastError = "Invalid IP address. Use x.x.x.x, with each octet from 0 to 255."
            if (strictValidation) {
                showValidation("Highlighted fields are not valid IPv4 addresses. Use x.x.x.x, with each octet from 0 to 255.")
            }
            return null
        }

        if (hasMissingRequired) {
            staticRoutingForm.lastError = "Static route requires Network, Mask, and Next-hop."
            if (strictValidation) {
                showValidation("A static route row is missing Network, Mask, or Next-hop. Fill the highlighted fields.")
            }
            return null
        }

        return routes
    }

    function saveToDatabase(manual) {
        if (staticRoutingForm.isLoading || staticRoutingForm.isSaving)
            return false

        const host = String(staticRoutingForm.currentHostIp || "").trim()
        if (host === "") {
            if (manual)
                notify("Select a device tab before saving Static/Default routing.", "warning")
            return false
        }

        const routesPayload = buildRoutesPayload(manual)
        if (routesPayload === null)
            return false

        if (staticRoutingForm.defaultRouteEnabled && currentDefaultRouteText() !== "") {
            const defText = currentDefaultRouteText()
            if (defText.includes(" ")) {
                if (manual) {
                    showValidation("Default route next-hop cannot contain spaces.")
                }
                return false
            }
            if (!isValidIPv4(defText)) {
                if (manual) {
                    showValidation("Default route next-hop is not a valid IPv4 address. Use x.x.x.x, with each octet from 0 to 255.")
                }
                return false
            }
        }

        staticRoutingForm.isSaving = true
        const ok = dbManager.saveStaticRouting(
            host,
            staticRoutingForm.defaultRouteEnabled ? currentDefaultRouteText() : "",
            JSON.stringify(routesPayload)
        )
        staticRoutingForm.isSaving = false

        if (ok) {
            staticRoutingForm.lastError = ""
            staticRoutingForm.hasPendingLocalChanges = false
            staticRoutingForm.hasPendingStaticChanges = false
            staticRoutingForm.loadFromDatabase()
            if (manual)
                notify("Static/Default routing saved for host " + host, "success")
            return true
        }

        staticRoutingForm.lastError = "Save static/default routing failed."
        if (manual)
            notify(staticRoutingForm.lastError, "error")
        return false
    }

    function saveDefaultOnly() {
        if (staticRoutingForm.isLoading || staticRoutingForm.isSaving) return false
        if (!staticRoutingForm.hasDefaultChanges()) return false

        const host = String(staticRoutingForm.currentHostIp || "").trim()
        if (host === "") {
            notify("Select a device tab before saving Default route.", "warning")
            return false
        }

        const current = dbManager.getStaticRouting(host)
        const currentOk = current && (current.ok === undefined || current.ok === true)
        if (!currentOk) {
            staticRoutingForm.lastError = "Cannot load current static routes before saving default."
            notify(staticRoutingForm.lastError, "error")
            return false
        }

        const routesPayload = current.routes ? current.routes : []
        const defaultValue = staticRoutingForm.defaultRouteEnabled ? currentDefaultRouteText() : ""

        if (staticRoutingForm.defaultRouteEnabled && defaultValue !== "") {
            if (defaultValue.includes(" ")) {
                showValidation("Default route next-hop cannot contain spaces.")
                return false
            }
            if (!isValidIPv4(defaultValue)) {
                showValidation("Default route next-hop is not a valid IPv4 address. Use x.x.x.x, with each octet from 0 to 255.")
                return false
            }
        }

        staticRoutingForm.isSaving = true
        const ok = dbManager.saveStaticRouting(host, defaultValue, JSON.stringify(routesPayload))
        staticRoutingForm.isSaving = false

        if (ok) {
            staticRoutingForm.lastError = ""
            staticRoutingForm.hasPendingLocalChanges = false
            staticRoutingForm.hasPendingStaticChanges = false
            staticRoutingForm.loadFromDatabase()
            notify("Saved Default route for host " + host, "success")
            return true
        }

        staticRoutingForm.lastError = "Save Default route failed."
        notify(staticRoutingForm.lastError, "error")
        return false
    }

    function saveStaticOnly() {
        if (staticRoutingForm.isLoading || staticRoutingForm.isSaving) return false

        const host = String(staticRoutingForm.currentHostIp || "").trim()
        if (host === "") {
            notify("Select a device tab before saving Static routes.", "warning")
            return false
        }

        const device = dbManager.getDeviceByHost(host)
        if (!device || !device.ip) {
            notify("Selected host is not in the device database: " + host, "error")
            return false
        }

        const routesPayload = buildRoutesPayload(true)
        if (routesPayload === null) return false

        staticRoutingForm.isSaving = true
        const ok = dbManager.saveStaticRoutes(host, JSON.stringify(routesPayload))
        staticRoutingForm.isSaving = false

        if (ok) {
            staticRoutingForm.lastError = ""
            staticRoutingForm.hasPendingLocalChanges = false
            staticRoutingForm.hasPendingStaticChanges = false
            staticRoutingForm.loadFromDatabase()
            notify("Saved Static routes for host " + host, "success")
            return true
        }

        staticRoutingForm.lastError = "Save Static routes failed."
        notify(staticRoutingForm.lastError, "error")
        return false
    }

    function loadFromDatabase() {
        routeModel.clear()
        staticRoutingForm.lastError = ""
        staticRoutingForm.loadedDefaultRouteText = ""
        staticRoutingForm.loadedStaticRoutesSignature = "[]"
        staticRoutingForm.hasPendingLocalChanges = false
        staticRoutingForm.hasPendingStaticChanges = false

        const host = String(staticRoutingForm.currentHostIp || "").trim()
        if (host === "")
            return

        staticRoutingForm.isLoading = true

        const payload = dbManager.getStaticRouting(host)
        const ok = payload && (payload.ok === undefined || payload.ok === true)

        if (!ok) {
            staticRoutingForm.lastError = payload && payload.message ? String(payload.message) : "Load static/default routing failed."
            notify(staticRoutingForm.lastError, "error")
            staticRoutingForm.isLoading = false
            return
        }

        const routes = payload.routes ? payload.routes : []
        for (let i = 0; i < routes.length; i++) {
            const r = routes[i]
            routeModel.append({
                id: r.id !== undefined ? r.id : 0,
                routeId: r.id !== undefined ? r.id : 0,
                network: r.network ? String(r.network) : "",
                mask: r.mask ? String(r.mask) : "",
                nexthop: r.nexthop ? String(r.nexthop) : "",
                ad: r.ad !== undefined ? String(r.ad) : "1",
                originalNetwork: r.network ? String(r.network) : "",
                originalMask: r.mask ? String(r.mask) : "",
                originalNexthop: r.nexthop ? String(r.nexthop) : "",
                originalAd: r.ad !== undefined ? String(r.ad) : "1",
                syncStatus: r.sync_status !== undefined ? String(r.sync_status) : StatusValues.pendingApply,
                edited: false,
                canEdit: r.id !== undefined ? false : true,
                networkError: false,
                maskError: false,
                nexthopError: false
            })
        }

        staticRoutingForm.loadedStaticRoutesSignature = staticRoutingForm.staticRoutesSignature()
        staticRoutingForm.refreshDirtyFlag()
        staticRoutingForm.isLoading = false
        staticRoutingForm.viewPushRevision++
    }

    onCurrentHostIpChanged: loadFromDatabase()
    Component.onCompleted: loadFromDatabase()

    // ── NỘI DUNG CHÍNH (Body) ──
    StaticRoutingRoutesCard {
        form: staticRoutingForm
        routeModel: routeModel
    }

    // ── FOOTER (Nút Bấm) ──
    footer: [
        Text {
            text: "Static routes are saved independently for the selected host."
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSmall
            font.family: Theme.fontFamily
            Layout.fillWidth: true
            elide: Text.ElideRight
        },
        StandardButton {
            text: "Reload UI"
            icon.source: AppAssets.actionDatabaseReload
            type: "Secondary"
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            onClicked: {
                staticRoutingForm.loadFromDatabase()
                notify("Static routes reloaded for host " + staticRoutingForm.currentHostIp, "info")
            }
        },
        ViewPushButton {
            id: viewPushButton
            text: "View & Push"
            type: "Primary"
            controllerName: "routing"
            moduleName: "static"
            hostIp: staticRoutingForm.currentHostIp
            ownerForm: staticRoutingForm
            refreshKey: staticRoutingForm.viewPushRevision
            onPushCompleted: function(ok, message) {
                if (ok)
                    staticRoutingForm.loadFromDatabase()
            }
        }
    ]

}
