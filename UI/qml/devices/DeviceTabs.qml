pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

Rectangle {
    id: root
    width: parent.width
    height: Theme.tabBarHeight
    color: Theme.tabBarBackground

    Rectangle {
        anchors.bottom: parent.bottom; width: parent.width; height: 1
        color: Theme.borderColor; z: 10
    }

    // Quản lý trạng thái và lịch sử điều hướng Tab nội bộ (chỉ lưu trên RAM)
    property var activeHistory: []
    property var closedTabsHistory: []
    property int nextTabId: 100
    property int tabCount: tabModel.count

    property int currentFMain: 0
    property int currentFText: -1
    property string activeUid: ""
    property string activeDeviceType: ""
    property bool activeContentLoading: false
    property int contextTargetIndex: -1
    readonly property bool shortcutsEnabled: root.visible && !UiState.windowLock

    // Cờ kiểm soát vòng đời khởi tạo của thanh Tabs
    property bool isInitialized: false
    
    signal openNewDeviceRequested()
    signal activeTabChanged(string uid)

    ListModel {
        id: tabModel
    }

    // Thiết lập trạng thái rỗng cho toàn bộ Tabs khi ứng dụng bắt đầu
    function initializeTabs(validIps) {
        if (isInitialized) return 
        isInitialized = true
        
        tabModel.clear()
        activeHistory = []
        closedTabsHistory = []
        root.currentFMain = 0
        root.currentFText = -1
        root.activeUid = ""
        root.activeDeviceType = ""
    }

    function cleanTitle(value) {
        return String(value || "").replace(/[\x00-\x1F\x7F]/g, "").replace(/^[#>`'"]+|[#>`'"]+$/g, "").trim()
    }

    function syncActiveContentLoading() {
        const activeIndex = getActiveIndex()
        for (let i = 0; i < tabModel.count; i++) {
            const shouldLoad = i === activeIndex && root.activeContentLoading
            if (tabModel.get(i).contentLoading !== shouldLoad)
                tabModel.setProperty(i, "contentLoading", shouldLoad)
        }
    }

    function shouldOpenSessionForStatus(status) {
        return String(status || "").toLowerCase() === "connected"
    }

    function notifySessionResult(result) {
        if (!result || !result.message)
            return
        const type = result.severity || (result.ok ? "success" : "error")
        if (typeof statusBar !== "undefined")
            statusBar.showMessage(String(result.message), type)
    }

    function ensureSessionForTab(uid, status) {
        const host = String(uid || "").trim()
        if (host === "" || !shouldOpenSessionForStatus(status))
            return
        if (typeof cli === "undefined")
            return
        if (cli.hasDeviceSession && cli.hasDeviceSession(host))
            return
        const idx = findIndexByUid(host)
        if (idx !== -1 && tabModel.get(idx).sessionState === "opening")
            return

        if (idx !== -1)
            tabModel.setProperty(idx, "sessionState", "opening")

        if (cli.openDeviceSessionAsync) {
            const accepted = cli.openDeviceSessionAsync(host)
            if (!accepted && idx !== -1)
                tabModel.setProperty(idx, "sessionState", "error")
            return
        }

        if (idx !== -1)
            tabModel.setProperty(idx, "sessionState", "error")
        notifySessionResult({"ok": false, "severity": "error", "message": "Async session backend is not available."})
    }

    // Mở Tab mới hoặc Focus vào Tab đã tồn tại dựa trên IP (uid)
    function openTab(ip, name, deviceType, status) {
        const cleanName = cleanTitle(name)
        for (let i = 0; i < tabModel.count; i++) {
            if (tabModel.get(i).uid === ip) {
                if (cleanName !== "")
                    tabModel.setProperty(i, "title", cleanName)
                tabModel.setProperty(i, "deviceType", deviceType || tabModel.get(i).deviceType || "unknown")
                tabModel.setProperty(i, "status", status || tabModel.get(i).status || "disconnected")
                selectTab(i)
                ensureSessionForTab(ip, status || tabModel.get(i).status)
                return
            }
        }

        const displayName = cleanName !== "" ? cleanName : ip
        tabModel.append({
            uid:      ip,
            title:    displayName,
            isActive: false,
            deviceType: deviceType || "unknown",
            status:   status || "disconnected",
            sessionState: "pending",
            contentLoading: false,
            fMain:    0,
            fText:    -1
        })
        selectTab(tabModel.count - 1)
        ensureSessionForTab(ip, status || "disconnected")
    }

    function findIndexByUid(uid) {
        for (let i = 0; i < tabModel.count; i++) {
            if (tabModel.get(i).uid === uid) return i
        }
        return -1
    }

    function getActiveIndex() {
        for (let i = 0; i < tabModel.count; i++) {
            if (tabModel.get(i).isActive) return i
        }
        return -1
    }

    function setFeatureForActiveTab(mIdx, tIdx) {
        const idx = getActiveIndex()
        if (idx !== -1) {
            tabModel.setProperty(idx, "fMain", mIdx)
            tabModel.setProperty(idx, "fText", tIdx)
            root.currentFMain = mIdx
            root.currentFText = tIdx
        }
    }

    function updateDeviceMetadata(devices) {
        if (!devices) return

        for (let i = 0; i < devices.length; i++) {
            const device = devices[i]
            const uid = device && device.ip ? String(device.ip) : ""
            if (uid === "") continue

            const idx = findIndexByUid(uid)
            if (idx === -1) continue

            const current = tabModel.get(idx)
            const cleanName = cleanTitle(device.name)
            const displayName = cleanName !== ""
                              ? cleanName
                              : uid

            tabModel.setProperty(idx, "title", displayName)
            tabModel.setProperty(idx, "deviceType", device.type || current.deviceType || "unknown")
            const nextStatus = device.status || current.status || "disconnected"
            tabModel.setProperty(idx, "status", nextStatus)
            ensureSessionForTab(uid, nextStatus)
        }
    }

    // Cập nhật giao diện và ghi nhận lịch sử khi chuyển đổi Tab
    function selectTab(idx) {
        if (idx < 0 || idx >= tabModel.count) return
        const uid = tabModel.get(idx).uid

        for (let i = 0; i < tabModel.count; i++) {
            tabModel.setProperty(i, "isActive", i === idx)
        }

        root.currentFMain = tabModel.get(idx).fMain
        root.currentFText = tabModel.get(idx).fText
        root.activeDeviceType = tabModel.get(idx).deviceType || "unknown"

        // Chỉ lưu vào lịch sử nếu chuyển sang một Tab khác
        if (activeHistory.length === 0 || activeHistory[activeHistory.length - 1] !== uid) {
            activeHistory.push(uid)
        }

        activeTabChanged(uid)
        root.activeUid = uid
        Qt.callLater(root.syncActiveContentLoading)
    }

    // Đóng Tab và tự động Focus lại Tab vừa sử dụng trước đó (Fallback)
    function closeTab(idx) {
        const tab = tabModel.get(idx)
        const wasActive = tab.isActive
        const uid = tab.uid

        closedTabsHistory.push({
            title: tab.title,
            uid:   tab.uid,
            deviceType: tab.deviceType,
            status: tab.status,
            sessionState: tab.sessionState || "closed",
            contentLoading: false,
            fMain: tab.fMain,
            fText: tab.fText
        })
        tabModel.remove(idx)

        // Nếu Tab đang được chọn bị đóng, tìm Tab gần nhất trong lịch sử để Focus
        if (wasActive && tabModel.count > 0) {
            let nextUid = ""
            while (activeHistory.length > 0) {
                const last = activeHistory.pop()
                if (last !== uid && findIndexByUid(last) !== -1) {
                    nextUid = last
                    activeHistory.push(nextUid)
                    break
                }
            }
            
            if (nextUid !== "") selectTab(findIndexByUid(nextUid))
            else selectTab(tabModel.count - 1)
        }

        // Xóa sạch trạng thái nếu không còn Tab nào
        if (tabModel.count === 0) {
            root.currentFMain = 0
            root.currentFText = -1
            root.activeUid = ""
            root.activeDeviceType = ""
        }
    }

    function closeTabByUid(uid) {
        const idx = findIndexByUid(uid)
        if (idx !== -1) closeTab(idx)
    }

    // Mở tab theo uid — nếu đã có thì focus, chưa có thì không làm gì
    // (khác openTab là không cần name)
    function openTabByUid(uid) {
        const idx = findIndexByUid(uid)
        if (idx !== -1) selectTab(idx)
    }

    function closeCurrentTab() {
        const idx = getActiveIndex()
        if (idx !== -1) closeTab(idx)
    }

    function closeOtherTabs(idx) {
        if (idx < 0 || idx >= tabModel.count)
            return
        const targetUid = tabModel.get(idx).uid
        for (let row = tabModel.count - 1; row >= 0; --row) {
            if (tabModel.get(row).uid !== targetUid)
                closeTab(row)
        }
        selectTab(findIndexByUid(targetUid))
    }

    function closeTabsToRight(idx) {
        if (idx < 0 || idx >= tabModel.count)
            return
        for (let row = tabModel.count - 1; row > idx; --row)
            closeTab(row)
        selectTab(Math.min(idx, tabModel.count - 1))
    }

    function closeAllTabs() {
        for (let row = tabModel.count - 1; row >= 0; --row)
            closeTab(row)
    }

    function openTabContext(idx, sceneX, sceneY) {
        if (idx < 0 || idx >= tabModel.count)
            return
        selectTab(idx)
        contextTargetIndex = idx
        tabContextMenu.openAt(sceneX, sceneY)
    }

    function openContextForActiveTab() {
        const idx = getActiveIndex()
        if (idx < 0)
            return
        const item = tabListView.itemAtIndex(idx)
        if (!item)
            return
        const point = item.mapToItem(null, Math.min(item.width - 8, 180), item.height / 2)
        openTabContext(idx, point.x, point.y)
    }

    function reopenLastClosedTab() {
        if (closedTabsHistory.length === 0) return
        const lastClosed = closedTabsHistory.pop()
        
        tabModel.append({
            uid:      lastClosed.uid,
            title:    lastClosed.title,
            isActive: false,
            deviceType: lastClosed.deviceType || "unknown",
            status:   lastClosed.status || "disconnected",
            sessionState: "pending",
            contentLoading: false,
            fMain:    lastClosed.fMain,
            fText:    lastClosed.fText
        })
        
        selectTab(tabModel.count - 1)
        ensureSessionForTab(lastClosed.uid, lastClosed.status || "disconnected")
    }

    function nextTab() {
        if (tabModel.count <= 1) return
        const idx = getActiveIndex()
        selectTab((idx + 1) % tabModel.count)
    }

    function prevTab() {
        if (tabModel.count <= 1) return
        const idx = getActiveIndex()
        selectTab((idx - 1 + tabModel.count) % tabModel.count)
    }

    // Match Chrome: Ctrl+1..8 selects that numbered tab; Ctrl+9 selects the
    // rightmost tab so it remains useful when more than nine devices are open.
    function selectNumberedTab(number) {
        if (tabModel.count === 0)
            return false
        const index = number === 9 ? tabModel.count - 1 : number - 1
        if (index < 0 || index >= tabModel.count)
            return false
        selectTab(index)
        return true
    }

    function moveTab(fromIdx, toIdx) {
        tabModel.move(fromIdx, toIdx, 1)
    }

    DeviceTabContextMenu {
        id: tabContextMenu
        parent: Window.window ? Window.window.contentItem : root
        canCloseOthers: tabModel.count > 1
        canCloseToRight: root.contextTargetIndex >= 0
                         && root.contextTargetIndex < tabModel.count - 1
        canReopenClosed: root.closedTabsHistory.length > 0
        onCloseRequested: root.closeTab(root.contextTargetIndex)
        onCloseOthersRequested: root.closeOtherTabs(root.contextTargetIndex)
        onCloseToRightRequested: root.closeTabsToRight(root.contextTargetIndex)
        onCloseAllRequested: root.closeAllTabs()
        onReopenClosedRequested: root.reopenLastClosedTab()
        onNewDeviceRequested: root.openNewDeviceRequested()
    }

    ListView {
        id: tabListView
        objectName: "deviceTabList"
        anchors.fill: parent
        orientation: ListView.Horizontal
        interactive: true
        clip: true
        model: tabModel

        move: Transition {
            NumberAnimation { properties: "x,y"; duration: Theme.animationDurationMedium; easing.type: Easing.OutQuad }
        }

        delegate: DeviceTabItem {
            onMoveRequested:   function(fromIdx, toIdx) { root.moveTab(fromIdx, toIdx) }
            onSelectRequested: function(idx) { root.selectTab(idx) }
            onCloseRequested:  function(idx) { root.closeTab(idx) }
            onContextMenuRequested: function(idx, sceneX, sceneY) {
                root.openTabContext(idx, sceneX, sceneY)
            }
        }
    }

    Connections {
        target: typeof cli !== "undefined" ? cli : null
        function onDeviceSessionFinished(host, ok, message) {
            const idx = root.findIndexByUid(String(host || ""))
            if (idx === -1)
                return
            tabModel.setProperty(idx, "sessionState", ok ? "connected" : "error")
        }
        function onSessionStateChanged(host, state, message) {
            const idx = root.findIndexByUid(String(host || ""))
            if (idx !== -1)
                tabModel.setProperty(idx, "sessionState", String(state || "closed"))
        }
    }

    onActiveContentLoadingChanged: syncActiveContentLoading()

    Shortcut { sequence: "Ctrl+T"; enabled: root.shortcutsEnabled; onActivated: root.openNewDeviceRequested() }
    Shortcut { sequence: "Ctrl+W"; enabled: root.shortcutsEnabled; onActivated: root.closeCurrentTab() }
    Shortcut { sequence: "Ctrl+F4"; enabled: root.shortcutsEnabled; onActivated: root.closeCurrentTab() }
    Shortcut { sequence: "Ctrl+Shift+T"; enabled: root.shortcutsEnabled; onActivated: root.reopenLastClosedTab() }
    Shortcut { sequence: "Ctrl+Tab"; enabled: root.shortcutsEnabled; onActivated: root.nextTab() }
    Shortcut { sequence: "Ctrl+Shift+Tab"; enabled: root.shortcutsEnabled; onActivated: root.prevTab() }
    Shortcut { sequence: "Ctrl+1"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(1) }
    Shortcut { sequence: "Ctrl+2"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(2) }
    Shortcut { sequence: "Ctrl+3"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(3) }
    Shortcut { sequence: "Ctrl+4"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(4) }
    Shortcut { sequence: "Ctrl+5"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(5) }
    Shortcut { sequence: "Ctrl+6"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(6) }
    Shortcut { sequence: "Ctrl+7"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(7) }
    Shortcut { sequence: "Ctrl+8"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(8) }
    Shortcut { sequence: "Ctrl+9"; enabled: root.shortcutsEnabled; onActivated: root.selectNumberedTab(9) }
    Shortcut { sequence: "Ctrl+K, Ctrl+W"; enabled: root.shortcutsEnabled; onActivated: root.closeAllTabs() }
    Shortcut { sequence: "Shift+F10"; enabled: root.shortcutsEnabled; onActivated: root.openContextForActiveTab() }
}
