pragma ComponentBehavior: Bound

import UI

DataTableRow {
    width: parent ? parent.width : implicitWidth
    alternateColor: Theme.contentBackground
}
