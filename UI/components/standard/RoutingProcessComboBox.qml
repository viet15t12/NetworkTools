pragma ComponentBehavior: Bound

import QtQuick.Layouts
import UI

StandardComboBox {
    id: root

    property var form: null
    property string protocol: "Routing"

    Layout.fillWidth: true
    labelText: protocol + " Process"
    model: root.form ? root.form.processOptions : []
    currentIndex: root.form ? root.form.selectedNetworkProcessIndex : -1
    enabled: !root.form || root.form.processCount > 0

    onCurrentIndexChanged: {
        if (root.form && currentIndex >= 0)
            root.form.selectedNetworkProcessIndex = currentIndex
    }
}
