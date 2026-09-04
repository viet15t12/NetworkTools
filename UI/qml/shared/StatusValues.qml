pragma Singleton

import QtQml

QtObject {
    readonly property string disconnected: "disconnected"
    readonly property string waiting: "waiting"
    readonly property string connected: "connected"

    readonly property string pendingApply: "pending_apply"
    readonly property string pendingDelete: "pending_delete"
    readonly property string synchronizedValue: "synchronized"
    readonly property string skipped: "skipped"
}
