pragma ComponentBehavior: Bound

import QtQml

QtObject {
    id: root

    required property string commandId
    required property string text
    property url iconSource: ""
    property string iconName: ""
    property var shortcut: ""
    property bool enabled: true
    property bool visible: true
    property bool checkable: false
    property bool checked: false
    property string nativeRole: "none"
    property string scope: "window"
    property string description: ""
    property var handler: null

    function invoke() {
        if (!root.enabled || typeof root.handler !== "function")
            return false
        const result = root.handler()
        return result === undefined ? true : result !== false
    }
}
