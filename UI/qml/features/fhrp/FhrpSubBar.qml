pragma ComponentBehavior: Bound

import QtQuick
import UI

// Protocol navigation stays separate from each protocol page and its draft.
SubBar {
    id: root
    activeTab: "HSRP"
    tabs: ["HSRP", "VRRP", "GLBP"]
}
