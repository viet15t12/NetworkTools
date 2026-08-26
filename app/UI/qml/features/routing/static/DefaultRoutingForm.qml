pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

FormLayout {
    id: form
    title: "Default Routes"
    hostIp: currentHostIp
    isDirty: hasPendingLocalChanges
    errorMessage: lastError

    property string currentHostIp: ""
    property bool isLoading: false
    property bool isSaving: false
    property bool hasPendingLocalChanges: false
    property string loadedSignature: "[]"
    property string lastError: ""
    property int viewPushRevision: 0

    ListModel { id: routeModel }

    function notify(message, type) {
        if (typeof statusBar !== "undefined") statusBar.showMessage(message, type)
    }
    function signature() {
        const values = []
        for (let i = 0; i < routeModel.count; i++) {
            const row = routeModel.get(i)
            values.push({ id: Number(row.routeId || 0), nexthop: String(row.nexthop || "").trim() })
        }
        return JSON.stringify(values)
    }
    function markDirty() { hasPendingLocalChanges = signature() !== loadedSignature }
    function isValidIPv4(value) {
        const parts = String(value || "").trim().split(".")
        if (parts.length !== 4) return false
        for (let i = 0; i < parts.length; i++) {
            if (parts[i] === "" || !/^\d+$/.test(parts[i])) return false
            const number = Number(parts[i])
            if (number < 0 || number > 255) return false
        }
        return true
    }
    function addRoute() {
        for (let i = 0; i < routeModel.count; i++) {
            if (String(routeModel.get(i).nexthop || "").trim() === "") {
                notify("Complete the empty default route first.", "warning")
                return
            }
        }
        routeModel.append({
            routeId: 0, nexthop: "", originalNexthop: "",
            syncStatus: StatusValues.pendingApply, canEdit: true
        })
        markDirty()
    }
    function saveRoutes() {
        if (isLoading || isSaving) return false
        const host = String(currentHostIp || "").trim()
        if (host === "") {
            notify("Select a device before saving Default routes.", "warning")
            return false
        }
        const payload = []
        const seen = ({})
        for (let i = 0; i < routeModel.count; i++) {
            const row = routeModel.get(i)
            const nextHop = String(row.nexthop || "").trim()
            if (!isValidIPv4(nextHop)) {
                lastError = "Every default route requires a valid next-hop IPv4 address."
                notify(lastError, "error")
                return false
            }
            if (seen[nextHop]) {
                lastError = "Duplicate default-route next-hop: " + nextHop
                notify(lastError, "error")
                return false
            }
            seen[nextHop] = true
            payload.push({ id: Number(row.routeId || 0), nexthop: nextHop })
        }
        isSaving = true
        const ok = dbManager.saveDefaultRoutes(host, JSON.stringify(payload))
        isSaving = false
        if (!ok) {
            lastError = "Save Default routes failed."
            notify(lastError, "error")
            return false
        }
        lastError = ""
        loadFromDatabase()
        notify("Saved Default routes for host " + host, "success")
        return true
    }
    function loadFromDatabase() {
        routeModel.clear()
        lastError = ""
        loadedSignature = "[]"
        hasPendingLocalChanges = false
        const host = String(currentHostIp || "").trim()
        if (host === "") return
        isLoading = true
        const result = dbManager.getDefaultRoutes(host)
        if (!result || result.ok === false) {
            lastError = result && result.message ? String(result.message) : "Load Default routes failed."
            isLoading = false
            return
        }
        const rows = result.routes || []
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]
            routeModel.append({
                routeId: Number(row.id || 0),
                nexthop: String(row.nexthop || ""),
                originalNexthop: String(row.nexthop || ""),
                syncStatus: String(row.sync_status || StatusValues.pendingApply),
                canEdit: false
            })
        }
        loadedSignature = signature()
        hasPendingLocalChanges = false
        isLoading = false
        viewPushRevision++
    }

    onCurrentHostIpChanged: loadFromDatabase()
    Component.onCompleted: loadFromDatabase()

    Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: 24
        Layout.rightMargin: 24
        implicitHeight: routesLayout.implicitHeight + 16
        radius: 8
        color: Theme.contentPanelSurface
        border.color: Theme.contentPanelBorder
        border.width: Theme.borderWidth

        ColumnLayout {
            id: routesLayout
            anchors.fill: parent
            anchors.margins: 8
            spacing: Theme.spacing8
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: "Default Routes"
                    color: Theme.textPrimary
                    font.bold: true
                    font.family: Theme.fontFamily
                }
                StandardButton { text: "+ Add"; type: "Primary"; onClicked: form.addRoute() }
                StandardButton {
                    text: form.isSaving ? "Saving..." : "Save Default"
                    type: "Primary"
                    icon.source: AppAssets.actionSave
                    enabled: form.hasPendingLocalChanges && !form.isSaving
                    onClicked: form.saveRoutes()
                }
            }
            Text {
                visible: routeModel.count === 0
                text: "No default routes. Use + Add to create one."
                color: Theme.textSecondary
                font.family: Theme.fontFamily
            }
            Repeater {
                model: routeModel
                delegate: DefaultRouteRow {
                    required property int index
                    required property int routeId
                    required property string nexthop
                    required property string originalNexthop
                    required property string syncStatus
                    required property bool canEdit
                    Layout.fillWidth: true
                    rowRouteId: routeId
                    rowNextHop: nexthop
                    rowSyncStatus: syncStatus
                    rowCanEdit: canEdit
                    onNextHopChanged: function(value) { routeModel.setProperty(index, "nexthop", value); form.markDirty() }
                    onChangeClicked: routeModel.setProperty(index, "canEdit", true)
                    onCancelClicked: {
                        if (routeId <= 0) routeModel.remove(index)
                        else {
                            routeModel.setProperty(index, "nexthop", originalNexthop)
                            routeModel.setProperty(index, "canEdit", false)
                        }
                        form.markDirty()
                    }
                    onDeleteClicked: { routeModel.remove(index); form.markDirty() }
                    onAccepted: { if (form.hasPendingLocalChanges) form.saveRoutes() }
                }
            }
        }
    }

    footer: [
        Text {
            Layout.fillWidth: true
            text: "A router can have multiple default routes with different next hops."
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        },
        StandardButton {
            text: "Reload UI"
            type: "Secondary"
            icon.source: AppAssets.actionDatabaseReload
            autoCompact: false
            Layout.minimumWidth: expandedImplicitWidth
            onClicked: form.loadFromDatabase()
        },
        ViewPushButton {
            controllerName: "routing"
            moduleName: "static"
            hostIp: form.currentHostIp
            ownerForm: form
            refreshKey: form.viewPushRevision
            onPushCompleted: function(ok, message) { if (ok) form.loadFromDatabase() }
        }
    ]
}
