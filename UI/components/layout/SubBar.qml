pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

// ─────────────────────────────────────────────────────────────────────────────
// SubBar
// Thanh điều hướng phụ (Tab bar) generic dùng chung cho các View.
// Thay thế cho việc tự vẽ RowLayout + Repeater rải rác ở nhiều file.
//
// Cách dùng:
// SubBar {
//     tabs: ["Info", "Static", "OSPF", "EIGRP", "BGP"]
//     activeTab: "Info"
//     onTabClicked: (tabName) => {
//         activeTab = tabName
//         // logic chuyển màn hình...
//     }
// }
// ─────────────────────────────────────────────────────────────────────────────
Rectangle {
    id: root

    // ── Public API ───────────────────────────────────────────────────────────
    property var    tabs: []          // Array string chứa tên các tab
    property string activeTab: ""     // Tên tab đang được chọn
    property int leftPadding: 0
    property var disabledTabs: []     // Array string chứa tab chưa implement

    signal tabClicked(string tabName)

    function isTabDisabled(tabName) {
        return disabledTabs.indexOf(tabName) !== -1
    }

    function displayTabText(tabName) {
        switch (tabName) {
        case "Info": return "Info"
        case "Static": return "Static"
        case "OSPF": return "OSPF"
        case "EIGRP": return "EIGRP"
        case "BGP": return "BGP"
        case "Pool": return "Pool"
        case "Excluded": return "Excluded"
        case "Helper": return "Helper"
        case "Standard": return "Standard"
        case "Extended": return "Extended"
        case "Dynamic": return "Dynamic"
        case "Reflexive": return "Reflexive"
        case "MAC": return "MAC"
        case "PAT": return "PAT"
        case "Interfaces": return "Interfaces"
        case "ACL": return "ACL"
        case "Route Map": return "Route Map"
        }
        return tabName
    }

    // ── Kích thước & Background ──────────────────────────────────────────────
    Layout.fillWidth: true
    height: Theme.subBarHeight
    color:  Theme.featureBarBackground

    // ── Divider dưới cùng (đường viền phân cách với nội dung) ───────────────
    Rectangle {
        width:          parent.width
        height:         Theme.borderWidth
        anchors.bottom: parent.bottom
        color:          Theme.borderColor
    }

    // ── Danh sách Tabs ───────────────────────────────────────────────────────
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: root.leftPadding
        spacing:            Theme.spacing8

        Repeater {
            model: root.tabs

            delegate: Rectangle {
                id: tabDelegate
                required property string modelData
                Layout.fillHeight: true
                // Padding 2 bên để tab có không gian click dễ dàng
                implicitWidth: tabText.implicitWidth + Theme.spacing24

                readonly property bool isActive: root.activeTab === modelData
                readonly property bool isDisabled: root.isTabDisabled(modelData)

                color: hoverHandler.hovered && !isActive && !isDisabled
                       ? Theme.sideBarItemHover
                       : "transparent"

                // ── Text ─────────────────────────────────────────────────────
                Text {
                    id: tabText
                    anchors.centerIn: parent
                    text:             root.displayTabText(modelData)
                    font.family:      Theme.fontFamily
                    font.pixelSize:   Theme.fontSizeNormal
                    font.bold:        tabDelegate.isActive
                    color:            tabDelegate.isDisabled ? Theme.textDisabled
                                      : tabDelegate.isActive ? Theme.textPrimary : Theme.textSecondary
                    opacity:          tabDelegate.isDisabled ? 0.55 : 1.0
                }

                // ── Active Indicator (Đường gạch chân) ───────────────────────
                Rectangle {
                    anchors {
                        bottom: parent.bottom
                        horizontalCenter: parent.horizontalCenter
                    }
                    width:   parent.width
                    height:  2
                    color:   Theme.subBarAccentColor
                    visible: tabDelegate.isActive
                }

                // ── Tương tác ────────────────────────────────────────────────
                HoverHandler {
                    id: hoverHandler
                    cursorShape: tabDelegate.isDisabled ? Qt.ArrowCursor : Qt.PointingHandCursor
                }

                TapHandler {
                    enabled: !tabDelegate.isDisabled
                    onTapped: {
                        if (!tabDelegate.isActive) {
                            root.tabClicked(modelData)
                            // Component cha (bên ngoài gọi SubBar) sẽ tự quyết định
                            // có gán lại root.activeTab = modelData hay không thông qua signal
                        }
                    }
                }
            }
        }

        // Spacer đẩy toàn bộ tabs sang trái
        Item { Layout.fillWidth: true }
    }
}
