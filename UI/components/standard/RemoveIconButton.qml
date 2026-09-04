pragma ComponentBehavior: Bound

import QtQuick.Layouts
import UI

StandardButton {
    id: root

    type: "Icon"
    tooltip: "Remove"
    icon.source: AppAssets.actionClose
    Layout.preferredWidth: 34
}
