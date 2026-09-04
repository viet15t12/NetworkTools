pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick

QtObject {
    id: root

    readonly property bool defaultShowStatusBar: true
    readonly property bool defaultShowPythonStatus: true
    readonly property bool defaultShowNetwork: true
    readonly property bool defaultShowNetworkName: true
    readonly property string defaultVirtualLabServerUrl: ""
    readonly property string defaultVirtualLabUsername: ""
    readonly property string defaultVirtualLabPassword: ""
    readonly property bool defaultShowRam: true
    readonly property bool defaultShowRamBar: true
    readonly property bool defaultShowRamText: true
    readonly property bool defaultRamWarningEnabled: true
    readonly property bool defaultRamBlinkOnHigh: true
    readonly property int defaultRamWarningThreshold: 85
    readonly property bool defaultShowDate: true
    readonly property bool defaultShowTime: true
    readonly property bool defaultShowNotifications: true
    readonly property int defaultDateTimeFormatMode: 0
    readonly property string defaultCustomDateFormat: "dd/MM/yyyy"
    readonly property string defaultCustomTimeFormat: "HH:mm"

    property bool _loadingSettings: true
    property var backend: null

    property bool showStatusBar: defaultShowStatusBar
    property bool showPythonStatus: defaultShowPythonStatus
    property bool showNetwork: defaultShowNetwork
    property bool showNetworkName: defaultShowNetworkName
    property string virtualLabServerUrl: defaultVirtualLabServerUrl
    property string virtualLabUsername: defaultVirtualLabUsername
    property string virtualLabPassword: defaultVirtualLabPassword
    property bool showRam: defaultShowRam
    property bool showRamBar: defaultShowRamBar
    property bool showRamText: defaultShowRamText
    property bool ramWarningEnabled: defaultRamWarningEnabled
    property bool ramBlinkOnHigh: defaultRamBlinkOnHigh
    property int ramWarningThreshold: defaultRamWarningThreshold
    property bool showDate: defaultShowDate
    property bool showTime: defaultShowTime
    property bool showNotifications: defaultShowNotifications
    property int dateTimeFormatMode: defaultDateTimeFormatMode
    property string customDateFormat: defaultCustomDateFormat
    property string customTimeFormat: defaultCustomTimeFormat

    readonly property bool hasVisibleContent: showPythonStatus
                                              || showNetwork
                                              || (showRam && (showRamBar || showRamText))
                                              || showDate
                                              || showTime
                                              || showNotifications
    readonly property bool isVisible: showStatusBar && hasVisibleContent
    readonly property bool hasCustomSettings: showStatusBar !== defaultShowStatusBar
                                             || showPythonStatus !== defaultShowPythonStatus
                                             || showNetwork !== defaultShowNetwork
                                             || showNetworkName !== defaultShowNetworkName
                                             || virtualLabServerUrl !== defaultVirtualLabServerUrl
                                             || virtualLabUsername !== defaultVirtualLabUsername
                                             || virtualLabPassword !== defaultVirtualLabPassword
                                             || showRam !== defaultShowRam
                                             || showRamBar !== defaultShowRamBar
                                             || showRamText !== defaultShowRamText
                                             || ramWarningEnabled !== defaultRamWarningEnabled
                                             || ramBlinkOnHigh !== defaultRamBlinkOnHigh
                                             || normalizedThreshold(ramWarningThreshold) !== defaultRamWarningThreshold
                                             || showDate !== defaultShowDate
                                             || showTime !== defaultShowTime
                                             || showNotifications !== defaultShowNotifications
                                             || normalizedFormatMode(dateTimeFormatMode) !== defaultDateTimeFormatMode
                                             || customDateFormat !== defaultCustomDateFormat
                                             || customTimeFormat !== defaultCustomTimeFormat

    function hasPersistentSettings() {
        return backend !== null
    }

    function normalizedThreshold(value) {
        const numberValue = Number(value)
        if (isNaN(numberValue))
            return defaultRamWarningThreshold
        return Math.max(1, Math.min(100, numberValue))
    }

    function normalizedFormatMode(value) {
        return value === 1 ? 1 : 0
    }

    function loadPersistentSettings() {
        _loadingSettings = true
        if (hasPersistentSettings()) {
            showStatusBar = backend.showStatusBar
            showPythonStatus = backend.showPythonStatus
            showNetwork = backend.showNetwork
            showNetworkName = backend.showNetworkName
            virtualLabServerUrl = backend.virtualLabServerUrl
            virtualLabUsername = backend.virtualLabUsername
            virtualLabPassword = backend.virtualLabPassword
            showRam = backend.showRam
            showRamBar = backend.showRamBar
            showRamText = backend.showRamText
            ramWarningEnabled = backend.ramWarningEnabled
            ramBlinkOnHigh = backend.ramBlinkOnHigh
            ramWarningThreshold = normalizedThreshold(backend.ramWarningThreshold)
            showDate = backend.showDate
            showTime = backend.showTime
            showNotifications = backend.showNotifications
            dateTimeFormatMode = normalizedFormatMode(backend.dateTimeFormatMode)
            customDateFormat = backend.customDateFormat
            customTimeFormat = backend.customTimeFormat
        }
        _loadingSettings = false
        savePersistentSettings()
    }

    function savePersistentSettings() {
        if (!hasPersistentSettings())
            return

        backend.showStatusBar = showStatusBar
        backend.showPythonStatus = showPythonStatus
        backend.showNetwork = showNetwork
        backend.showNetworkName = showNetworkName
        backend.virtualLabServerUrl = virtualLabServerUrl.trim()
        backend.virtualLabUsername = virtualLabUsername.trim()
        backend.virtualLabPassword = virtualLabPassword
        backend.showRam = showRam
        backend.showRamBar = showRamBar
        backend.showRamText = showRamText
        backend.ramWarningEnabled = ramWarningEnabled
        backend.ramBlinkOnHigh = ramBlinkOnHigh
        backend.ramWarningThreshold = normalizedThreshold(ramWarningThreshold)
        backend.showDate = showDate
        backend.showTime = showTime
        backend.showNotifications = showNotifications
        backend.dateTimeFormatMode = normalizedFormatMode(dateTimeFormatMode)
        backend.customDateFormat = customDateFormat
        backend.customTimeFormat = customTimeFormat
    }

    function resetDefaults() {
        if (hasPersistentSettings())
            backend.resetDefaults()

        _loadingSettings = true
        showStatusBar = defaultShowStatusBar
        showPythonStatus = defaultShowPythonStatus
        showNetwork = defaultShowNetwork
        showNetworkName = defaultShowNetworkName
        virtualLabServerUrl = defaultVirtualLabServerUrl
        virtualLabUsername = defaultVirtualLabUsername
        virtualLabPassword = defaultVirtualLabPassword
        showRam = defaultShowRam
        showRamBar = defaultShowRamBar
        showRamText = defaultShowRamText
        ramWarningEnabled = defaultRamWarningEnabled
        ramBlinkOnHigh = defaultRamBlinkOnHigh
        ramWarningThreshold = defaultRamWarningThreshold
        showDate = defaultShowDate
        showTime = defaultShowTime
        showNotifications = defaultShowNotifications
        dateTimeFormatMode = defaultDateTimeFormatMode
        customDateFormat = defaultCustomDateFormat
        customTimeFormat = defaultCustomTimeFormat
        _loadingSettings = false
        savePersistentSettings()
    }

    onBackendChanged: loadPersistentSettings()
    onShowStatusBarChanged: if (!_loadingSettings) savePersistentSettings()
    onShowPythonStatusChanged: if (!_loadingSettings) savePersistentSettings()
    onShowNetworkChanged: if (!_loadingSettings) savePersistentSettings()
    onShowNetworkNameChanged: if (!_loadingSettings) savePersistentSettings()
    onVirtualLabServerUrlChanged: if (!_loadingSettings) savePersistentSettings()
    onVirtualLabUsernameChanged: if (!_loadingSettings) savePersistentSettings()
    onVirtualLabPasswordChanged: if (!_loadingSettings) savePersistentSettings()
    onShowRamChanged: if (!_loadingSettings) savePersistentSettings()
    onShowRamBarChanged: if (!_loadingSettings) savePersistentSettings()
    onShowRamTextChanged: if (!_loadingSettings) savePersistentSettings()
    onRamWarningEnabledChanged: if (!_loadingSettings) savePersistentSettings()
    onRamBlinkOnHighChanged: if (!_loadingSettings) savePersistentSettings()
    onRamWarningThresholdChanged: if (!_loadingSettings) savePersistentSettings()
    onShowDateChanged: if (!_loadingSettings) savePersistentSettings()
    onShowTimeChanged: if (!_loadingSettings) savePersistentSettings()
    onShowNotificationsChanged: if (!_loadingSettings) savePersistentSettings()
    onDateTimeFormatModeChanged: if (!_loadingSettings) savePersistentSettings()
    onCustomDateFormatChanged: if (!_loadingSettings) savePersistentSettings()
    onCustomTimeFormatChanged: if (!_loadingSettings) savePersistentSettings()

    Component.onCompleted: loadPersistentSettings()
}
