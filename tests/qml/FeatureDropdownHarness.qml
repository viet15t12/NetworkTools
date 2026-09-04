pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 220
    height: 220
    visible: true

    FeatureDropdown {
        objectName: "featureDropdownUnderTest"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        hiddenFeatures: [
            { "label": "Routing", "globalIndex": 0, "implemented": true },
            { "label": "VLAN", "globalIndex": 1, "implemented": false },
            { "label": "DHCP", "globalIndex": 2, "implemented": true }
        ]
        visible: true
    }
}
