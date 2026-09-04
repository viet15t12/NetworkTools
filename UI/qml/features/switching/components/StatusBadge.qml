pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    property string value: "unknown"
    readonly property string normalizedValue: String(value || "unknown").toLowerCase()
    readonly property bool positive: normalizedValue === "up"
                                     || normalizedValue === "active"
                                     || normalizedValue === "synchronized"
    readonly property bool negative: normalizedValue === "down"
                                     || normalizedValue === "err-disabled"
                                     || normalizedValue === "suspend"
    readonly property bool pending: normalizedValue === "pending_apply"
                                    || normalizedValue === "pending_delete"
    implicitWidth: badgeRow.implicitWidth + Theme.spacing16
    implicitHeight: 24
    radius: Theme.radiusRound
    color: positive ? Theme.alertSuccessSubtle
         : negative ? Theme.alertErrorSubtle
         : pending ? Theme.alertWarningSubtle
         : Theme.alertInfoSubtle

    RowLayout {
        id: badgeRow
        anchors.centerIn: parent
        spacing: Theme.spacing4

        Rectangle {
            Layout.preferredWidth: 6
            Layout.preferredHeight: 6
            radius: 3
            color: root.positive ? Theme.alertSuccess
                 : root.negative ? Theme.alertError
                 : root.pending ? Theme.alertWarning
                 : Theme.textSecondary
        }

        Text {
            id: label
            text: root.normalizedValue.replace(/_/g, " ").replace(/^./, function(letter) {
                return letter.toUpperCase()
            })
            color: root.positive ? Theme.alertSuccess
                 : root.negative ? Theme.alertError
                 : root.pending ? Theme.alertWarning
                 : Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
        }
    }
}
