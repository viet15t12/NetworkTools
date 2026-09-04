pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Controls
import UI

ApplicationWindow {
    id: rootWindow
    flags: Qt.Window | Qt.FramelessWindowHint
    visible: true

    minimumWidth: Theme.windowMinWidth
    minimumHeight: Theme.windowMinHeight

    // ─────────────────────────────────────────────────────────────────────
    // WINDOW STATE TRACKING (VS Code Style - Simplified for QML)
    // ─────────────────────────────────────────────────────────────────────

    // Track normal state bounds (when not maximize/minimize/fullscreen)
    property int normalX:      0
    property int normalY:      0
    property int normalWidth:  Theme.windowDefaultWidth
    property int normalHeight: Theme.windowDefaultHeight

    // ─────────────────────────────────────────────────────────────────────
    // PERSISTENT SETTINGS (Like VS Code)
    // ─────────────────────────────────────────────────────────────────────
    // UI-P0-02: Persistence lives in the Python QSettings bridge because the
    // PyQt runtime does not ship the optional QtCore QML plugin dependency.
    // Keep safe defaults so the component remains loadable in design tooling.
    readonly property var persistentWindowSettings:
        typeof windowSettings !== "undefined" ? windowSettings : null

    function storedWindowValue(name, fallbackValue) {
        const backend = rootWindow.persistentWindowSettings
        return backend ? backend[name] : fallbackValue
    }

    // ─────────────────────────────────────────────────────────────────────
    // SMART RESTORE LOGIC (VS Code Style - Simplified)
    // ─────────────────────────────────────────────────────────────────────

    /**
     * Validates if the bounds are within visible screen area
     * Since QML's Screen object doesn't expose multiple screens,
     * we validate against the primary screen's available geometry
     */
    function validateBounds(x, y, width, height) {
        // Get available desktop area
        const availableWidth = Screen.desktopAvailableWidth
        const availableHeight = Screen.desktopAvailableHeight
        const screenX = Screen.virtualX
        const screenY = Screen.virtualY

        // Minimum constraint
        const constrainedW = Math.max(Theme.windowMinWidth, Math.min(width, availableWidth - 100))
        const constrainedH = Math.max(Theme.windowMinHeight, Math.min(height, availableHeight - 100))

        // Ensure window is within screen bounds
        const constrainedX = Math.max(screenX, Math.min(x, screenX + availableWidth - constrainedW))
        const constrainedY = Math.max(screenY, Math.min(y, screenY + availableHeight - constrainedH))

        return {
            x: constrainedX,
            y: constrainedY,
            width: constrainedW,
            height: constrainedH
        }
    }

    /**
     * Restore window state from saved settings with smart fallback
     */
    function restoreWindowState() {
        if (storedWindowValue("isFirstLaunch", true)) {
            // First launch: center window on primary screen
            const availableWidth = Screen.desktopAvailableWidth
            const availableHeight = Screen.desktopAvailableHeight
            const screenX = Screen.virtualX
            const screenY = Screen.virtualY

            rootWindow.width  = Theme.windowDefaultWidth
            rootWindow.height = Theme.windowDefaultHeight
            rootWindow.x = screenX + Math.round((availableWidth  - rootWindow.width)  / 2)
            rootWindow.y = screenY + Math.round((availableHeight - rootWindow.height) / 2)

            normalX      = rootWindow.x
            normalY      = rootWindow.y
            normalWidth  = rootWindow.width
            normalHeight = rootWindow.height

            if (rootWindow.persistentWindowSettings)
                rootWindow.persistentWindowSettings.markLaunched()
            rootWindow.showMaximized()

        } else {
            // Subsequent launches: restore from settings with validation
            const bounds = validateBounds(
                storedWindowValue("savedX", 0),
                storedWindowValue("savedY", 0),
                storedWindowValue("savedWidth", Theme.windowDefaultWidth),
                storedWindowValue("savedHeight", Theme.windowDefaultHeight)
            )

            rootWindow.x      = bounds.x
            rootWindow.y      = bounds.y
            rootWindow.width  = bounds.width
            rootWindow.height = bounds.height

            normalX      = bounds.x
            normalY      = bounds.y
            normalWidth  = bounds.width
            normalHeight = bounds.height

            // Restore maximize/normal state
            if (storedWindowValue("isMaximized", true)) {
                rootWindow.showMaximized()
            }
        }
    }

    /**
     * Save current window state to persistent storage
     */
    function saveWindowState() {
        if (rootWindow.persistentWindowSettings) {
            rootWindow.persistentWindowSettings.saveState(
                normalX,
                normalY,
                normalWidth,
                normalHeight,
                visibility === Window.Maximized || visibility === Window.FullScreen
            )
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // WINDOW STATE CHANGE HANDLERS
    // ─────────────────────────────────────────────────────────────────────

    // Track normal bounds when in windowed mode (like VS Code)
    onXChanged: {
        if (visibility === Window.Windowed) {
            normalX = rootWindow.x
        }
    }

    onYChanged: {
        if (visibility === Window.Windowed) {
            normalY = rootWindow.y
        }
    }

    onWidthChanged: {
        if (visibility === Window.Windowed) {
            normalWidth = rootWindow.width
        }
    }

    onHeightChanged: {
        if (visibility === Window.Windowed) {
            normalHeight = rootWindow.height
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // INITIALIZATION & CLEANUP
    // ─────────────────────────────────────────────────────────────────────

    Component.onCompleted: {
        restoreWindowState()
    }

    onClosing: {
        saveWindowState()
    }
}
