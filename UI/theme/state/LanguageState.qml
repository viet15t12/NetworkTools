pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick

QtObject {
    id: root

    property var backend: null
    readonly property string language: backend !== null
                                       ? String(backend.language || "en")
                                       : "en"
    readonly property bool isVietnamese: language === "vi"

    function text(source) {
        // Reading language makes bindings refresh when the backend emits
        // languageChanged, while unknown/technical text remains untouched.
        const activeLanguage = root.language
        const value = String(source || "")
        return root.backend !== null && activeLanguage !== ""
                ? root.backend.translate(value)
                : value
    }

    function setLanguage(value) {
        if (root.backend !== null)
            root.backend.setLanguage(String(value || "en"))
    }
}
