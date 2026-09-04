import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 900
    height: 560
    visible: true

    property alias configText: viewer.text
    property alias fontPixelSize: viewer.fontPixelSize
    property alias zoomPercent: viewer.zoomPercent
    property alias searchText: viewer.searchText
    readonly property int currentMatchIndex: viewer.currentMatchIndex
    readonly property int matchCount: viewer.matchCount
    readonly property int occurrenceCount: viewer.occurrenceCount
    readonly property bool highlightingReady: viewer.highlightingReady
    readonly property bool syntaxHighlightingActive: viewer.syntaxHighlightingActive
    readonly property string highlightedText: viewer.highlightedText
    readonly property bool searchHasFocus: viewer.searchInputActiveFocus
    readonly property real codeLineHeight: viewer.codeLineHeight
    readonly property real scrollContentY: viewer.verticalScrollContentY
    readonly property real maximumScrollY: viewer.maximumLineAlignedContentY()

    function focusSearch() {
        viewer.focusSearch()
    }

    function scrollByLines(lineCount) {
        return viewer.scrollByLines(lineCount)
    }

    function setScrollContentY(value) {
        return viewer.setVerticalScrollPosition(value)
    }

    ConfigTextViewer {
        id: viewer
        objectName: "testConfigTextViewer"
        anchors.fill: parent
    }
}
