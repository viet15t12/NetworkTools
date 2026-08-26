pragma ComponentBehavior: Bound

import QtQuick
import UI

SubBar {
    id: root
    activeTab: "Interfaces"
    // Cisco workflow: mark interfaces and define the source ACL before
    // creating translation rules. Route-map remains the optional final step.
    tabs: ["Interfaces", "ACL", "Static", "Dynamic", "PAT", "Route Map", "Info"]
    disabledTabs: ["Info"]
}
