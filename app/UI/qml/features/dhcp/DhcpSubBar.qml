pragma ComponentBehavior: Bound

import QtQuick
import UI

// ─────────────────────────────────────────────────────────────────────────────
// DhcpSubBar
// Kế thừa generic SubBar.
// ─────────────────────────────────────────────────────────────────────────────
SubBar {
    id: root
    activeTab: "Pool"
    tabs: ["Pool", "Excluded", "Helper"]
}
