pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root

    property string message: ""
    property string severity: "info"
    property bool busy: false
    default property alias actions: actionLayout.data

    readonly property string normalizedSeverity: {
        const value = String(root.severity || "info").toLowerCase()
        return ["success", "warning", "error"].indexOf(value) !== -1 ? value : "info"
    }
    readonly property color accentColor: normalizedSeverity === "success" ? Theme.alertSuccess
                                                : normalizedSeverity === "warning" ? Theme.alertWarning
                                                : normalizedSeverity === "error" ? Theme.alertError
                                                : Theme.alertInfo
    readonly property color surfaceColor: normalizedSeverity === "success" ? Theme.alertSuccessSubtle
                                                 : normalizedSeverity === "warning" ? Theme.alertWarningSubtle
                                                 : normalizedSeverity === "error" ? Theme.alertErrorSubtle
                                                 : Theme.alertInfoSubtle

    visible: message !== ""
    implicitHeight: Math.max(Theme.itemHeight, messageRow.implicitHeight + Theme.spacing8)
    color: surfaceColor
    border.color: accentColor
    border.width: Theme.borderWidth
    radius: Theme.radiusSmall

    RowLayout {
        id: messageRow
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing8
        anchors.rightMargin: Theme.spacing8
        spacing: Theme.spacing8

        LoadingSpinner {
            Layout.preferredWidth: Theme.iconSizeSmall
            Layout.preferredHeight: Theme.iconSizeSmall
            running: root.busy
            visible: root.busy
            spinnerColor: root.accentColor
        }

        StatusIcon {
            Layout.preferredWidth: Theme.iconSizeSmall
            Layout.preferredHeight: Theme.iconSizeSmall
            visible: !root.busy
            statusType: root.normalizedSeverity
            iconSize: Theme.iconSizeSmall
        }

        Text {
            Layout.fillWidth: true
            text: root.message
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            elide: Text.ElideRight
        }

        RowLayout {
            id: actionLayout
            spacing: Theme.spacing4
        }
    }
}
