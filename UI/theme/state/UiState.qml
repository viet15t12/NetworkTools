pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick

QtObject {
    property bool windowLock: false

    property int _lockTimestamp: 0

    onWindowLockChanged: {
        if (windowLock) {
            _lockTimestamp = Date.now()
            _watchdogTimer.restart()
        } else {
            _watchdogTimer.stop()
        }
    }

    property Timer _watchdogTimer: Timer {
        interval: 30000
        repeat: false
        onTriggered: {
            if (UiState.windowLock) {
                UiState.windowLock = false
            }
        }
    }
}
