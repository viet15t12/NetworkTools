import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 800
    height: 600
    visible: true

    property bool doNotDisturb: false
    property string lastActionId: ""
    property string lastActionData: ""
    readonly property int toastCount: toastManager.toastCount
    readonly property real notificationPanelHeight: notificationPanel.height

    function clearHistory() {
        historyModel.clear()
    }

    function addHistory(message, type) {
        historyModel.insert(0, {
            "msgText": message,
            "msgType": type,
            "timestamp": "10:31:00",
            "actionLabel": "",
            "actionId": "",
            "actionData": "",
            "sourceText": ""
        })
    }

    function addActionHistory(message) {
        historyModel.insert(0, {
            "msgText": message,
            "msgType": "error",
            "timestamp": "10:32:00",
            "actionLabel": "Open Settings",
            "actionId": "open-settings",
            "actionData": "external_tools",
            "sourceText": "External Tools"
        })
    }

    ListModel {
        id: historyModel
        ListElement {
            msgText: "History notification"
            msgType: "info"
            timestamp: "10:30:00"
            actionLabel: ""
            actionId: ""
            actionData: ""
            sourceText: ""
        }
    }

    ToastManager {
        id: toastManager
        objectName: "testToastManager"
        Component.onCompleted: showToast("Toast notification", "info")
    }

    NotificationPanel {
        id: notificationPanel
        objectName: "testNotificationCenter"
        model: historyModel
        doNotDisturb: root.doNotDisturb
        onToggleDndRequested: root.doNotDisturb = !root.doNotDisturb
        onClearAllRequested: historyModel.clear()
        onActionTriggered: function(actionId, actionData, notificationIndex) {
            root.lastActionId = actionId
            root.lastActionData = actionData
            historyModel.remove(notificationIndex)
        }
        onDismissRequested: notificationIndex => historyModel.remove(notificationIndex)
        Component.onCompleted: open()
    }
}
