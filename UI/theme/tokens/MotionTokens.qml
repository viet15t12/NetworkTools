pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick

QtObject {
    readonly property int animationDurationFast: 120
    readonly property int animationDurationMedium: 150
    readonly property int animationDurationSlow: 250
    readonly property int viewLoadDispatchDelay: 16
    readonly property int loaderRotationDuration: 760
}
