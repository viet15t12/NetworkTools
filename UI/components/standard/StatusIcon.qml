pragma ComponentBehavior: Bound

import QtQuick
import UI

ThemedIcon {
    id: root

    property string statusType: "info"
    readonly property string normalizedStatusType: String(root.statusType || "info").toLowerCase()

    readonly property color accentColor: {
        if (root.normalizedStatusType === "success") return Theme.notificationSuccessAccent
        if (root.normalizedStatusType === "error") return Theme.notificationErrorAccent
        if (root.normalizedStatusType === "warning") return Theme.notificationWarningAccent
        return Theme.notificationInfoAccent
    }

    readonly property color contentBackgroundColor: {
        if (root.normalizedStatusType === "success") return Theme.notificationSuccessBackground
        if (root.normalizedStatusType === "error") return Theme.notificationErrorBackground
        if (root.normalizedStatusType === "warning") return Theme.notificationWarningBackground
        return Theme.notificationInfoBackground
    }

    iconSource: {
        if (root.normalizedStatusType === "success") return AppAssets.statusSuccess
        if (root.normalizedStatusType === "error") return AppAssets.statusError
        if (root.normalizedStatusType === "warning") return AppAssets.statusWarning
        return AppAssets.statusInfo
    }
    iconColor: root.accentColor
}
