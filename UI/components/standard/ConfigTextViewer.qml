pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Item {
    id: root

    property string text: ""
    property string sourceLabel: "Configuration text"
    property string emptyText: "No configuration data is available."
    property string errorText: ""
    property bool loading: false
    property string loadingText: "Loading configuration..."
    property string searchText: ""
    property string syntaxMode: "configuration"
    property int defaultFontPixelSize: Theme.fontSizeNormal
    property int minimumZoomPercent: 25
    property int maximumZoomPercent: 500
    property int defaultZoomPercent: 100
    property int zoomPercent: defaultZoomPercent
    property int fontPixelSize: Math.max(
        1, Math.round(defaultFontPixelSize * zoomPercent / 100)
    )
    readonly property var zoomLevels: [
        25, 33, 50, 67, 75, 80, 90, 100, 110,
        125, 150, 175, 200, 250, 300, 400, 500
    ]
    property int currentMatchIndex: -1
    property var matchPositions: []
    property var matchLengths: []
    property int textRevision: 0
    property int searchedTextRevision: -1
    property string searchedQuery: ""
    property var lineStarts: [0]
    property int lineSelectionAnchor: -1
    property int maximumSearchMatches: 10000
    property bool searchResultsTruncated: false
    property bool syntaxHighlightingEnabled: true
    property int syntaxHighlightCharacterLimit: 1000000
    property int highlightingChunkLineCount: 250
    property bool highlightingInProgress: false
    property bool highlightingReady: false
    property bool highlightingSkippedForLargeText: false
    property string highlightedBody: ""
    property string plainHtmlBody: ""
    property string pendingHighlightSource: ""
    property int pendingHighlightOffset: 0
    property var pendingHighlightOutput: []
    property bool verticalScrollSnapInProgress: false
    property real verticalWheelRemainder: 0
    property int wheelScrollLineCount: 3
    property bool wrapLongLines: false
    property bool smoothVerticalScrolling: false
    property var occurrencePositions: []
    property int maximumOccurrenceMarkers: 500
    property int maximumOccurrenceSelectionLength: 256

    property color syntaxIpAddressColor: Theme.syntaxIpAddress
    property color syntaxPrefixColor: Theme.syntaxPrefix
    property color syntaxMaskColor: Theme.syntaxMask
    property color syntaxWildcardColor: Theme.syntaxWildcard
    property color syntaxInterfaceColor: Theme.syntaxInterface
    property color syntaxNumberColor: Theme.syntaxNumber
    property color syntaxBooleanColor: Theme.syntaxBoolean
    property color syntaxDateTimeColor: Theme.syntaxDateTime
    property color syntaxPermitColor: Theme.syntaxPermit
    property color syntaxDenyColor: Theme.syntaxDeny
    property color syntaxInsideColor: Theme.syntaxInside
    property color syntaxOutsideColor: Theme.syntaxOutside
    property color syntaxCommentColor: Theme.syntaxComment
    property color diffAdditionColor: Theme.syntaxPermit
    property color diffDeletionColor: Theme.syntaxDeny
    property color diffHunkColor: Theme.accentColor
    property color diffHeaderColor: Theme.textSecondary

    // Converting a QML color to an HTML color inside highlightLine() is
    // surprisingly expensive for large configurations.  Keep the converted
    // palette as bindings so a theme change still invalidates it once, rather
    // than repeating the conversion for every token.
    readonly property string syntaxTextHtmlColor: htmlColor(Theme.textPrimary)
    readonly property string syntaxIpAddressHtmlColor: htmlColor(syntaxIpAddressColor)
    readonly property string syntaxPrefixHtmlColor: htmlColor(syntaxPrefixColor)
    readonly property string syntaxMaskHtmlColor: htmlColor(syntaxMaskColor)
    readonly property string syntaxWildcardHtmlColor: htmlColor(syntaxWildcardColor)
    readonly property string syntaxInterfaceHtmlColor: htmlColor(syntaxInterfaceColor)
    readonly property string syntaxNumberHtmlColor: htmlColor(syntaxNumberColor)
    readonly property string syntaxBooleanHtmlColor: htmlColor(syntaxBooleanColor)
    readonly property string syntaxDateTimeHtmlColor: htmlColor(syntaxDateTimeColor)
    readonly property string syntaxPermitHtmlColor: htmlColor(syntaxPermitColor)
    readonly property string syntaxDenyHtmlColor: htmlColor(syntaxDenyColor)
    readonly property string syntaxInsideHtmlColor: htmlColor(syntaxInsideColor)
    readonly property string syntaxOutsideHtmlColor: htmlColor(syntaxOutsideColor)
    readonly property string syntaxCommentHtmlColor: htmlColor(syntaxCommentColor)
    readonly property var syntaxTokenPattern: /\b(?:\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?|(?:\d{1,3}\.){3}\d{1,3}(?:\/\d{1,2})?|(?:interface|GigabitEthernet|FastEthernet|Ethernet|Loopback|Serial|Vlan|Tunnel|Port-channel)[^\s]*|permit|deny|inside|outside|yes|no|true|false|up|down|\d+|[A-Za-z][A-Za-z0-9_-]*)\b/gi

    readonly property int matchCount: matchPositions.length
    readonly property int occurrenceCount: occurrencePositions.length
    readonly property int lineCount: lineStarts.length
    readonly property string displayText: String(root.text || "")
                                          .replace(/\r\n|\r|\u2028|\u2029/g, "\n")
    readonly property string highlightedText: root.preformattedDocument(root.highlightedBody)
    readonly property string plainRichText: root.preformattedDocument(root.plainHtmlBody)
    // State, not a binding: assigning rich text changes QTextDocument geometry.
    // Keeping that geometry out of the dependency chain prevents a feedback loop.
    property string renderedText: ""
    readonly property int renderedDocumentLength: configTextArea.length
    readonly property string selectedText: configTextArea.selectedText
    readonly property bool contextMenuVisible: configTextContextMenu.visible
    readonly property bool searchInputActiveFocus: searchField.inputActiveFocus
    readonly property bool copyFeedbackVisible: viewerClipboardCopyButton.copied
    readonly property real desiredCodeLineHeight: Math.max(
        1, Math.ceil(Math.max(codeFontMetrics.height, codeFontMetrics.lineSpacing)) + 2
    )
    readonly property real codeVerticalPadding: 2
    readonly property real codeViewportHeight: textScroll.contentItem
                                                ? Math.max(0, textScroll.contentItem.height)
                                                : 0
    readonly property real codeRowsViewportHeight: Math.max(
        0, root.codeViewportHeight - root.codeVerticalPadding * 2
    )
    readonly property int visibleWholeLineCapacity: Math.max(
        1, Math.floor(root.codeRowsViewportHeight / root.desiredCodeLineHeight)
    )
    // Chia vùng nhìn thành số hàng nguyên. Mỗi mức Zoom vì vậy luôn giữ trọn
    // glyph ở hàng đầu/cuối thay vì để một phần dòng lọt dưới viewport.
    readonly property real codeLineHeight: root.codeRowsViewportHeight >= root.desiredCodeLineHeight
                                           ? root.codeRowsViewportHeight / root.visibleWholeLineCapacity
                                           : root.desiredCodeLineHeight
    readonly property real verticalScrollContentY: textScroll.contentItem
                                                   ? textScroll.contentItem.contentY
                                                   : 0
    readonly property bool syntaxHighlightingActive: syntaxHighlightingEnabled
                                                      && highlightingReady
                                                      && !highlightingSkippedForLargeText
                                                      && text !== ""
    readonly property string syntaxPaletteKey: [
        String(syntaxIpAddressColor),
        String(syntaxPrefixColor),
        String(syntaxMaskColor),
        String(syntaxWildcardColor),
        String(syntaxInterfaceColor),
        String(syntaxNumberColor),
        String(syntaxBooleanColor),
        String(syntaxDateTimeColor),
        String(syntaxPermitColor),
        String(syntaxDenyColor),
        String(syntaxInsideColor),
        String(syntaxOutsideColor),
        String(syntaxCommentColor),
        String(diffAdditionColor),
        String(diffDeletionColor),
        String(diffHunkColor),
        String(diffHeaderColor),
        root.syntaxMode
    ].join("|")

    signal copyAllSucceeded(string copiedText)

    function rebuildLineStarts() {
        const value = root.normalizeLineBreaks(root.text)
        const starts = [0]
        for (let index = 0; index < value.length; index++) {
            const code = value.charCodeAt(index)
            if (code === 10) {
                starts.push(index + 1)
            } else if (code === 13 && (index + 1 >= value.length || value.charCodeAt(index + 1) !== 10)) {
                starts.push(index + 1)
            }
        }
        root.lineStarts = starts
    }

    function runSearchNow() {
        searchDebounce.stop()
        const query = root.normalizeLineBreaks(root.searchText)
        const haystack = root.displayText
        const positions = []
        const lengths = []
        root.searchResultsTruncated = false
        root.currentMatchIndex = -1
        root.searchedQuery = query
        root.searchedTextRevision = root.textRevision

        if (query === "" || haystack === "") {
            root.matchPositions = positions
            root.matchLengths = lengths
            configTextArea.deselect()
            return
        }

        const normalizedText = haystack.toLocaleLowerCase()
        const normalizedQuery = query.toLocaleLowerCase()
        let position = 0
        while (position <= normalizedText.length - normalizedQuery.length) {
            const matchPosition = normalizedText.indexOf(normalizedQuery, position)
            if (matchPosition < 0)
                break
            positions.push(matchPosition)
            lengths.push(normalizedQuery.length)
            if (positions.length >= root.maximumSearchMatches) {
                root.searchResultsTruncated = true
                break
            }
            position = matchPosition + Math.max(1, normalizedQuery.length)
        }
        root.matchPositions = positions
        root.matchLengths = lengths
    }

    function normalizeLineBreaks(value) {
        return String(value || "").replace(/\r\n|\r|\u2028|\u2029/g, "\n")
    }

    function safeDocumentPosition(position) {
        const requestedPosition = Math.round(Number(position) || 0)
        return Math.max(0, Math.min(root.renderedDocumentLength, requestedPosition))
    }

    function rebuildSelectionOccurrences() {
        const query = root.normalizeLineBreaks(root.selectedText)
        const positions = []
        if (query === "" || query.indexOf("\n") >= 0
                || query.length > root.maximumOccurrenceSelectionLength) {
            root.occurrencePositions = positions
            return
        }

        const haystack = root.displayText.toLocaleLowerCase()
        const needle = query.toLocaleLowerCase()
        const selectedStart = Math.min(
            configTextArea.selectionStart,
            configTextArea.selectionEnd
        )
        const selectedEnd = Math.max(
            configTextArea.selectionStart,
            configTextArea.selectionEnd
        )
        let position = 0
        while (position <= haystack.length - needle.length) {
            const matchPosition = haystack.indexOf(needle, position)
            if (matchPosition < 0)
                break
            const matchEnd = matchPosition + needle.length
            if (matchPosition !== selectedStart || matchEnd !== selectedEnd)
                positions.push({ "start": matchPosition, "length": needle.length })
            if (positions.length >= root.maximumOccurrenceMarkers)
                break
            position = matchPosition + Math.max(1, needle.length)
        }
        root.occurrencePositions = positions
    }

    function ensureSearchCurrent() {
        if (root.searchedQuery !== root.normalizeLineBreaks(root.searchText)
                || root.searchedTextRevision !== root.textRevision)
            root.runSearchNow()
    }

    function escapeHtml(value) {
        const text = String(value || "")
        // Configuration lines overwhelmingly contain no HTML metacharacters.
        // Avoid allocating three intermediate strings for every token in the
        // highlighter's hottest path.
        if (text.indexOf("&") < 0 && text.indexOf("<") < 0 && text.indexOf(">") < 0)
            return text
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
    }

    function htmlColor(value) {
        const colorText = String(value || "")
        if (/^#[0-9a-fA-F]{8}$/.test(colorText))
            return "#" + colorText.slice(3)
        return colorText
    }

    function isIpv4Token(token) {
        return /^(?:\d{1,3}\.){3}\d{1,3}(?:\/\d{1,2})?$/.test(String(token || ""))
    }

    function isLikelySubnetMask(token) {
        const octets = String(token || "").split(".")
        if (octets.length !== 4 || Number(octets[0]) !== 255)
            return false
        let bits = ""
        for (let index = 0; index < octets.length; index++) {
            const octet = Number(octets[index])
            if (!Number.isInteger(octet) || octet < 0 || octet > 255)
                return false
            bits += ("00000000" + octet.toString(2)).slice(-8)
        }
        return /^1+0*$/.test(bits)
    }

    function addressSyntaxColor(token, lowerLine, matchIndex, addressOrdinal) {
        const value = String(token || "")
        if (value.indexOf("/") >= 0)
            return root.syntaxPrefixHtmlColor

        const before = lowerLine.slice(0, matchIndex)
        if (/\b(?:wildcard|wildcard-mask)\s*$/.test(before))
            return root.syntaxWildcardHtmlColor
        if (/\b(?:mask|subnet-mask)\s*$/.test(before))
            return root.syntaxMaskHtmlColor
        if (addressOrdinal > 0 && lowerLine.indexOf("ip address") >= 0)
            return root.syntaxMaskHtmlColor
        if (addressOrdinal > 0 && lowerLine.indexOf("network") >= 0)
            return root.syntaxWildcardHtmlColor
        if (root.isLikelySubnetMask(value))
            return root.syntaxMaskHtmlColor
        return root.syntaxIpAddressHtmlColor
    }

    function syntaxColorForToken(token, lowerLine, matchIndex, addressOrdinal, ipv4Token) {
        const value = String(token || "")
        const lower = value.toLowerCase()

        if (/^\d{4}-\d{2}-\d{2}/.test(value))
            return root.syntaxDateTimeHtmlColor
        if (ipv4Token)
            return root.addressSyntaxColor(value, lowerLine, matchIndex, addressOrdinal)
        if (/^(?:interface|gigabitethernet|fastethernet|ethernet|loopback|serial|vlan|tunnel|port-channel)/i.test(value))
            return root.syntaxInterfaceHtmlColor
        if (lower === "permit")
            return root.syntaxPermitHtmlColor
        if (lower === "deny")
            return root.syntaxDenyHtmlColor
        if (lower === "inside")
            return root.syntaxInsideHtmlColor
        if (lower === "outside")
            return root.syntaxOutsideHtmlColor
        if (lower === "yes" || lower === "no" || lower === "true" || lower === "false"
                || lower === "up" || lower === "down")
            return root.syntaxBooleanHtmlColor
        if (/^\d+$/.test(value))
            return root.syntaxNumberHtmlColor
        return root.syntaxTextHtmlColor
    }

    function tokenHasLetters(token) {
        return /[A-Za-z]/.test(String(token || ""))
    }

    function highlightLine(line) {
        const value = String(line || "")
        if (root.syntaxMode === "diff") {
            let diffColor = root.syntaxTextHtmlColor
            if (value.startsWith("@@"))
                diffColor = root.htmlColor(root.diffHunkColor)
            else if (value.startsWith("+++") || value.startsWith("---"))
                diffColor = root.htmlColor(root.diffHeaderColor)
            else if (value.startsWith("+"))
                diffColor = root.htmlColor(root.diffAdditionColor)
            else if (value.startsWith("-"))
                diffColor = root.htmlColor(root.diffDeletionColor)
            else if (value.startsWith(" "))
                return root.escapeHtml(value.charAt(0)) + root.highlightConfigurationLine(value.slice(1))
            return '<span style="color:' + diffColor + '">' + root.escapeHtml(value) + "</span>"
        }
        return root.highlightConfigurationLine(value)
    }

    function preformattedDocument(body) {
        const whitespaceMode = root.wrapLongLines ? "pre-wrap" : "pre"
        return '<pre style="margin:0;line-height:' + root.codeLineHeight
                + 'px;white-space:' + whitespaceMode + '">' + String(body || "") + "</pre>"
    }

    function rebuildPlainHtml() {
        const trailingLineKeeper = /\n$/.test(root.displayText) ? "&#8203;" : ""
        root.plainHtmlBody = root.escapeHtml(root.displayText) + trailingLineKeeper
    }

    function highlightConfigurationLine(line) {
        const value = String(line || "")
        if (/^\s*[!#]/.test(value)) {
            return '<span style="color:' + root.syntaxCommentHtmlColor + '">'
                    + root.escapeHtml(value) + "</span>"
        }

        const lowerLine = value.toLowerCase()
        const tokenPattern = root.syntaxTokenPattern
        tokenPattern.lastIndex = 0
        const output = []
        let cursor = 0
        let addressOrdinal = 0
        let match = tokenPattern.exec(value)
        while (match !== null) {
            output.push(root.escapeHtml(value.slice(cursor, match.index)))
            const token = match[0]
            const ipv4Token = root.isIpv4Token(token)
            const tokenColor = root.syntaxColorForToken(
                token, lowerLine, match.index, addressOrdinal, ipv4Token
            )
            const tokenWeight = root.tokenHasLetters(token) ? ";font-weight:600" : ""
            output.push(
                '<span style="color:' + tokenColor + tokenWeight + '">'
                + root.escapeHtml(token) + "</span>"
            )
            if (ipv4Token)
                addressOrdinal += 1
            cursor = match.index + token.length
            match = tokenPattern.exec(value)
        }
        output.push(root.escapeHtml(value.slice(cursor)))
        return output.join("")
    }

    function scheduleHighlighting() {
        highlightChunkTimer.stop()
        root.highlightingInProgress = false
        root.highlightingReady = false
        root.highlightedBody = ""
        root.startHighlighting()
    }

    function startHighlighting() {
        highlightChunkTimer.stop()
        root.highlightingReady = false
        root.highlightedBody = ""
        root.highlightingSkippedForLargeText = false
        root.pendingHighlightSource = root.normalizeLineBreaks(root.text)
        root.pendingHighlightOffset = 0
        root.pendingHighlightOutput = []

        if (!root.syntaxHighlightingEnabled || root.pendingHighlightSource === "") {
            root.highlightingInProgress = false
            return false
        }
        if (root.pendingHighlightSource.length > root.syntaxHighlightCharacterLimit) {
            root.highlightingInProgress = false
            root.highlightingSkippedForLargeText = true
            return false
        }

        root.highlightingInProgress = true
        highlightChunkTimer.start()
        return true
    }

    function finishHighlighting() {
        highlightChunkTimer.stop()
        const trailingLineKeeper = /\n$/.test(root.pendingHighlightSource) ? "&#8203;" : ""
        root.highlightedBody = root.pendingHighlightOutput.join("\n") + trailingLineKeeper
        root.pendingHighlightSource = ""
        root.pendingHighlightOutput = []
        root.highlightingInProgress = false
        root.highlightingReady = true
    }

    function processHighlightChunk() {
        if (!root.highlightingInProgress)
            return

        const source = root.pendingHighlightSource
        let linesProcessed = 0
        while (linesProcessed < root.highlightingChunkLineCount
                && root.pendingHighlightOffset <= source.length) {
            const newlineIndex = source.indexOf("\n", root.pendingHighlightOffset)
            let line = ""
            if (newlineIndex < 0) {
                line = source.slice(root.pendingHighlightOffset)
                root.pendingHighlightOffset = source.length + 1
            } else {
                line = source.slice(root.pendingHighlightOffset, newlineIndex)
                root.pendingHighlightOffset = newlineIndex + 1
            }
            if (line.length > 0 && line.charAt(line.length - 1) === "\r")
                line = line.slice(0, -1)
            root.pendingHighlightOutput.push(root.highlightLine(line))
            linesProcessed += 1
        }

        if (root.pendingHighlightOffset > source.length)
            root.finishHighlighting()
    }

    function revealPosition(position) {
        const flickable = textScroll.contentItem
        if (!flickable || !configTextArea.positionToRectangle)
            return
        const target = configTextArea.positionToRectangle(root.safeDocumentPosition(position))
        const topMargin = root.codeLineHeight
        const bottomMargin = root.codeLineHeight * 2
        if (target.y < flickable.contentY + topMargin) {
            root.setVerticalScrollPosition(target.y - topMargin)
        } else if (target.y + target.height > flickable.contentY + flickable.height - bottomMargin) {
            root.setVerticalScrollPosition(
                target.y + target.height - flickable.height + bottomMargin
            )
        }
    }

    function maximumLineAlignedContentY() {
        const flickable = textScroll.contentItem
        if (!flickable)
            return 0
        const maximumContentY = Math.max(0, flickable.contentHeight - flickable.height)
        let lineIndex = Math.max(
            0,
            Math.min(root.lineCount - 1, Math.floor(maximumContentY / root.codeLineHeight))
        )
        while (lineIndex > 0
                && root.verticalScrollPositionForLine(lineIndex) > maximumContentY)
            lineIndex -= 1
        while (lineIndex + 1 < root.lineCount
                && root.verticalScrollPositionForLine(lineIndex + 1) <= maximumContentY)
            lineIndex += 1
        return root.verticalScrollPositionForLine(lineIndex)
    }

    function verticalScrollPositionForLine(lineIndex) {
        const safeIndex = Math.max(
            0, Math.min(root.lineCount - 1, Math.round(Number(lineIndex) || 0))
        )
        if (!configTextArea.positionToRectangle || root.lineStarts.length === 0)
            return safeIndex * root.codeLineHeight
        const firstRectangle = configTextArea.positionToRectangle(
            root.safeDocumentPosition(Number(root.lineStarts[0]))
        )
        const lineRectangle = configTextArea.positionToRectangle(
            root.safeDocumentPosition(Number(root.lineStarts[safeIndex]))
        )
        // Flickable.contentY is pixel-aligned by Qt on desktop render targets.
        // Round the measured rich-text position once so the requested and
        // actual viewport positions cannot drift by a fractional pixel.
        return Math.max(0, Math.round(lineRectangle.y - firstRectangle.y))
    }

    function nearestVerticalScrollLine(value) {
        const requestedPosition = Math.max(0, Number(value) || 0)
        const estimatedIndex = Math.max(
            0,
            Math.min(root.lineCount - 1, Math.round(requestedPosition / root.codeLineHeight))
        )
        let nearestIndex = estimatedIndex
        let nearestDistance = Math.abs(
            root.verticalScrollPositionForLine(estimatedIndex) - requestedPosition
        )
        const firstCandidate = Math.max(0, estimatedIndex - 2)
        const lastCandidate = Math.min(root.lineCount - 1, estimatedIndex + 2)
        for (let index = firstCandidate; index <= lastCandidate; index++) {
            const distance = Math.abs(
                root.verticalScrollPositionForLine(index) - requestedPosition
            )
            if (distance < nearestDistance) {
                nearestIndex = index
                nearestDistance = distance
            }
        }
        return nearestIndex
    }

    function lineAlignedContentY(value) {
        const requestedLine = root.nearestVerticalScrollLine(value)
        return Math.min(
            root.verticalScrollPositionForLine(requestedLine),
            root.maximumLineAlignedContentY()
        )
    }

    function setVerticalScrollPosition(value) {
        const flickable = textScroll.contentItem
        if (!flickable)
            return false
        const alignedValue = root.smoothVerticalScrolling
                           ? Math.max(
                                 0,
                                 Math.min(
                                     Number(value || 0),
                                     Math.max(0, flickable.contentHeight - flickable.height)
                                 )
                             )
                           : root.lineAlignedContentY(value)
        if (Math.abs(flickable.contentY - alignedValue) < 0.01)
            return false
        root.verticalScrollSnapInProgress = true
        flickable.contentY = alignedValue
        root.verticalScrollSnapInProgress = false
        return true
    }

    function snapVerticalScroll() {
        if (root.verticalScrollSnapInProgress)
            return false
        return root.setVerticalScrollPosition(root.verticalScrollContentY)
    }

    function scrollByLines(lineCount) {
        const currentLine = root.nearestVerticalScrollLine(root.verticalScrollContentY)
        const targetLine = Math.max(
            0,
            Math.min(root.lineCount - 1, currentLine + Number(lineCount || 0))
        )
        return root.setVerticalScrollPosition(root.verticalScrollPositionForLine(targetLine))
    }

    function handleVerticalWheel(angleDeltaY, pixelDeltaY) {
        const angleDelta = Number(angleDeltaY || 0)
        const pixelDelta = Number(pixelDeltaY || 0)
        const usesAngleDelta = angleDelta !== 0
        const delta = usesAngleDelta ? angleDelta : pixelDelta
        if (delta === 0)
            return false

        const threshold = usesAngleDelta ? 120 : Math.max(1, root.codeLineHeight)
        if (root.verticalWheelRemainder !== 0
                && Math.sign(root.verticalWheelRemainder) !== Math.sign(delta))
            root.verticalWheelRemainder = 0
        root.verticalWheelRemainder += delta
        const steps = root.verticalWheelRemainder > 0
                    ? Math.floor(root.verticalWheelRemainder / threshold)
                    : Math.ceil(root.verticalWheelRemainder / threshold)
        if (steps !== 0) {
            root.verticalWheelRemainder -= steps * threshold
            root.scrollByLines(-steps * (usesAngleDelta ? root.wheelScrollLineCount : 1))
        }
        return true
    }

    function selectMatch(index) {
        if (index < 0 || index >= root.matchPositions.length)
            return false
        const start = Number(root.matchPositions[index])
        const length = index < root.matchLengths.length
                     ? Number(root.matchLengths[index])
                     : root.normalizeLineBreaks(root.searchText).length
        root.currentMatchIndex = index
        configTextArea.select(
            root.safeDocumentPosition(start),
            root.safeDocumentPosition(start + length)
        )
        root.revealPosition(start)
        return true
    }

    function findNext() {
        root.ensureSearchCurrent()
        if (root.matchCount === 0)
            return false
        return root.selectMatch((root.currentMatchIndex + 1) % root.matchCount)
    }

    function findPrevious() {
        root.ensureSearchCurrent()
        if (root.matchCount === 0)
            return false
        const previous = root.currentMatchIndex < 0
                       ? root.matchCount - 1
                       : (root.currentMatchIndex - 1 + root.matchCount) % root.matchCount
        return root.selectMatch(previous)
    }

    function selectLine(lineIndex) {
        if (lineIndex < 0 || lineIndex >= root.lineStarts.length)
            return false
        const start = Number(root.lineStarts[lineIndex])
        let end = lineIndex + 1 < root.lineStarts.length
                ? Number(root.lineStarts[lineIndex + 1])
                : root.displayText.length
        const value = root.displayText
        while (end > start && (value.charAt(end - 1) === "\n" || value.charAt(end - 1) === "\r"))
            end -= 1
        configTextArea.select(
            root.safeDocumentPosition(start),
            root.safeDocumentPosition(end)
        )
        configTextArea.forceActiveFocus()
        root.revealPosition(start)
        return true
    }

    function lineIndexForPosition(position) {
        const safePosition = Math.max(
            0, Math.min(root.displayText.length, Number(position || 0))
        )
        let low = 0
        let high = root.lineStarts.length - 1
        while (low <= high) {
            const middle = Math.floor((low + high) / 2)
            if (Number(root.lineStarts[middle]) <= safePosition)
                low = middle + 1
            else
                high = middle - 1
        }
        return Math.max(0, Math.min(root.lineCount - 1, high))
    }

    function lineIndexAtSelectionMarginY(viewportY) {
        const mappedPoint = lineSelectionMouseArea.mapToItem(
            configTextArea,
            lineSelectionMouseArea.width + configTextArea.leftPadding,
            Math.max(0, Math.min(lineSelectionMouseArea.height - 1, Number(viewportY || 0)))
        )
        return root.lineIndexForPosition(configTextArea.positionAt(mappedPoint.x, mappedPoint.y))
    }

    function selectionMarginYForLine(lineIndex) {
        if (lineIndex < 0 || lineIndex >= root.lineStarts.length)
            return -1
        const linePosition = Number(root.lineStarts[lineIndex])
        const lineRectangle = configTextArea.positionToRectangle(
            root.safeDocumentPosition(linePosition)
        )
        const mappedPoint = configTextArea.mapToItem(
            lineSelectionMouseArea,
            lineRectangle.x,
            lineRectangle.y + lineRectangle.height / 2
        )
        return mappedPoint.y
    }

    function selectLineRange(firstLineIndex, lastLineIndex) {
        if (root.lineCount <= 0)
            return false
        const firstLine = Math.max(0, Math.min(root.lineCount - 1, Number(firstLineIndex || 0)))
        const lastLine = Math.max(0, Math.min(root.lineCount - 1, Number(lastLineIndex || 0)))
        const startLine = Math.min(firstLine, lastLine)
        const endLine = Math.max(firstLine, lastLine)
        const start = Number(root.lineStarts[startLine])
        let end = endLine + 1 < root.lineStarts.length
                ? Number(root.lineStarts[endLine + 1])
                : root.displayText.length
        const value = root.displayText
        while (end > start && (value.charAt(end - 1) === "\n" || value.charAt(end - 1) === "\r"))
            end -= 1
        configTextArea.select(
            root.safeDocumentPosition(start),
            root.safeDocumentPosition(end)
        )
        configTextArea.forceActiveFocus()
        root.revealPosition(start)
        return true
    }

    function selectLineAtSelectionMarginY(viewportY, extendSelection) {
        const lineIndex = root.lineIndexAtSelectionMarginY(viewportY)
        if (!extendSelection || root.lineSelectionAnchor < 0)
            root.lineSelectionAnchor = lineIndex
        return root.selectLineRange(root.lineSelectionAnchor, lineIndex)
    }

    function setZoomPercent(percent) {
        const requestedPercent = Math.round(Number(percent))
        if (!Number.isFinite(requestedPercent))
            return false
        const normalizedPercent = root.nearestZoomLevel(requestedPercent)
        if (root.zoomPercent === normalizedPercent)
            return false
        root.zoomPercent = normalizedPercent
        return true
    }

    function nearestZoomLevel(percent) {
        const requestedPercent = Math.max(
            root.minimumZoomPercent,
            Math.min(root.maximumZoomPercent, Math.round(Number(percent)))
        )
        let nearestLevel = root.defaultZoomPercent
        let nearestDistance = Number.POSITIVE_INFINITY
        for (let index = 0; index < root.zoomLevels.length; index++) {
            const level = Number(root.zoomLevels[index])
            if (level < root.minimumZoomPercent || level > root.maximumZoomPercent)
                continue
            const distance = Math.abs(level - requestedPercent)
            if (distance < nearestDistance) {
                nearestLevel = level
                nearestDistance = distance
            }
        }
        return nearestLevel
    }

    function zoomIn() {
        for (let index = 0; index < root.zoomLevels.length; index++) {
            const level = Number(root.zoomLevels[index])
            if (level > root.zoomPercent)
                return root.setZoomPercent(level)
        }
        return false
    }

    function zoomOut() {
        for (let index = root.zoomLevels.length - 1; index >= 0; index--) {
            const level = Number(root.zoomLevels[index])
            if (level < root.zoomPercent)
                return root.setZoomPercent(level)
        }
        return false
    }

    function resetZoom() {
        return root.setZoomPercent(root.defaultZoomPercent)
    }

    function focusSearch() {
        searchField.forceActiveFocus()
        searchField.selectAll()
    }

    function copyAll() {
        return viewerClipboardCopyButton.copyText()
    }

    function updateRenderedText() {
        // QTextDocument normalises RichText while assigning TextArea.text.
        // Updating imperatively prevents that internal write from feeding
        // back into a declarative text binding.
        const nextText = root.syntaxHighlightingActive
                       ? root.highlightedText : root.plainRichText
        if (root.renderedText !== nextText)
            root.renderedText = nextText
        if (configTextArea.text !== nextText)
            configTextArea.text = nextText
    }

    function updateRenderedGeometry() {
        root.updateRenderedText()
        Qt.callLater(root.snapVerticalScroll)
    }

    function copySelection() {
        return viewerSelectionCopyButton.copyText()
    }

    function findSelectedText() {
        const query = root.normalizeLineBreaks(root.selectedText)
        if (query === "") {
            root.focusSearch()
            return false
        }
        const selectedPosition = Math.min(
            configTextArea.selectionStart,
            configTextArea.selectionEnd
        )
        root.searchText = query
        root.runSearchNow()
        root.currentMatchIndex = root.matchPositions.indexOf(selectedPosition)
        root.focusSearch()
        return true
    }

    function activateFindShortcut() {
        if (configTextArea.activeFocus && root.selectedText !== "")
            return root.findSelectedText()
        root.focusSearch()
        return true
    }

    onTextChanged: {
        // Occurrence delegates retain QTextDocument offsets. Tear them down
        // before the text binding can replace a long document with a shorter
        // snapshot/Diff; otherwise their geometry bindings briefly address
        // positions that only existed in the previous document.
        selectionOccurrenceDebounce.stop()
        root.occurrencePositions = []
        root.lineSelectionAnchor = -1
        configTextArea.deselect()
        configTextArea.cursorPosition = 0
        root.textRevision += 1
        rebuildLineStarts()
        rebuildPlainHtml()
        searchDebounce.restart()
        scheduleHighlighting()
    }
    onSearchTextChanged: searchDebounce.restart()
    onSelectedTextChanged: selectionOccurrenceDebounce.restart()
    onMinimumZoomPercentChanged: setZoomPercent(root.zoomPercent)
    onMaximumZoomPercentChanged: setZoomPercent(root.zoomPercent)
    onDefaultZoomPercentChanged: resetZoom()
    onZoomPercentChanged: setZoomPercent(root.zoomPercent)
    onWrapLongLinesChanged: updateRenderedGeometry()
    onCodeLineHeightChanged: Qt.callLater(root.updateRenderedGeometry)
    onSyntaxHighlightingEnabledChanged: scheduleHighlighting()
    onSyntaxPaletteKeyChanged: scheduleHighlighting()
    onHighlightedBodyChanged: updateRenderedText()
    onPlainHtmlBodyChanged: updateRenderedText()
    onSyntaxHighlightingActiveChanged: updateRenderedText()
    Component.onCompleted: {
        rebuildLineStarts()
        rebuildPlainHtml()
        resetZoom()
        runSearchNow()
        startHighlighting()
        rebuildSelectionOccurrences()
        updateRenderedText()
    }

    FontMetrics {
        id: codeFontMetrics
        font.family: "Consolas"
        font.pixelSize: root.fontPixelSize
    }

    Timer {
        id: searchDebounce
        interval: 180
        repeat: false
        onTriggered: root.runSearchNow()
    }

    Timer {
        id: selectionOccurrenceDebounce
        interval: 80
        repeat: false
        onTriggered: root.rebuildSelectionOccurrences()
    }

    Timer {
        id: highlightChunkTimer
        interval: 1
        repeat: true
        onTriggered: root.processHighlightChunk()
    }

    CopyButton {
        id: viewerClipboardCopyButton
        objectName: "configViewerCopyButton"
        visible: false
        textToCopy: root.text
        copyTooltip: "Copy all"
        onCopySucceeded: function(copiedText) { root.copyAllSucceeded(copiedText) }
    }

    CopyButton {
        id: viewerSelectionCopyButton
        objectName: "configViewerSelectionCopyButton"
        visible: false
        textToCopy: root.selectedText
        copyTooltip: "Copy selection"
    }

    Shortcut {
        sequence: "Ctrl+F"
        context: Qt.WindowShortcut
        enabled: root.visible && root.enabled
        onActivated: root.activateFindShortcut()
    }

    Shortcut {
        sequence: "Ctrl+C"
        context: Qt.WindowShortcut
        enabled: root.visible && root.enabled
                 && configTextArea.activeFocus && root.selectedText !== ""
        onActivated: root.copySelection()
    }

    Shortcut {
        sequence: "Ctrl+="
        context: Qt.WindowShortcut
        enabled: root.visible && root.enabled
        onActivated: root.zoomIn()
    }

    Shortcut {
        sequence: "Ctrl+-"
        context: Qt.WindowShortcut
        enabled: root.visible && root.enabled
        onActivated: root.zoomOut()
    }

    Shortcut {
        sequence: "Ctrl+0"
        context: Qt.WindowShortcut
        enabled: root.visible && root.enabled
        onActivated: root.resetZoom()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.spacing8

        Rectangle {
            id: textFrame
            objectName: "configViewerContent"
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.inputBackground
            border.color: Theme.inputBorderColor
            border.width: Theme.borderWidth
            radius: Theme.radiusSmall
            // The whole-line selection margin intentionally sits just outside
            // the framed text surface, like an editor selection gutter.
            clip: false

            Text {
                anchors.centerIn: parent
                width: Math.max(0, parent.width - Theme.spacing32)
                visible: root.loading
                text: root.loadingText
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            Text {
                anchors.centerIn: parent
                width: Math.max(0, parent.width - Theme.spacing32)
                visible: !root.loading && root.errorText !== ""
                text: root.errorText
                color: Theme.alertWarning
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            Text {
                anchors.centerIn: parent
                width: Math.max(0, parent.width - Theme.spacing32)
                visible: !root.loading && root.errorText === "" && root.text === ""
                text: root.emptyText
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeNormal
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: -18
                anchors.topMargin: Theme.borderWidth
                anchors.rightMargin: Theme.borderWidth
                anchors.bottomMargin: Theme.borderWidth
                spacing: Theme.spacing4
                visible: !root.loading && root.errorText === "" && root.text !== ""

                Item {
                    id: lineSelectionMargin
                    objectName: "configViewerLineSelectionMargin"
                    Layout.fillHeight: true
                    Layout.minimumWidth: 14
                    Layout.preferredWidth: 14
                    Layout.maximumWidth: 14

                    MouseArea {
                        id: lineSelectionMouseArea
                        objectName: "configViewerLineSelectionMouseArea"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.ArrowCursor
                        onPressed: function(mouse) {
                            root.selectLineAtSelectionMarginY(mouse.y, false)
                        }
                        onPositionChanged: function(mouse) {
                            if (pressed)
                                root.selectLineAtSelectionMarginY(mouse.y, true)
                        }
                        onReleased: {
                            root.lineSelectionAnchor = -1
                        }

                        WheelHandler {
                            target: null
                            acceptedModifiers: Qt.ControlModifier
                            onWheel: function(event) {
                                if (event.angleDelta.y > 0)
                                    root.zoomIn()
                                else if (event.angleDelta.y < 0)
                                    root.zoomOut()
                                event.accepted = true
                            }
                        }

                        WheelHandler {
                            enabled: !root.smoothVerticalScrolling
                            target: null
                            acceptedModifiers: Qt.NoModifier
                            onWheel: function(event) {
                                if (root.handleVerticalWheel(event.angleDelta.y, event.pixelDelta.y))
                                    event.accepted = true
                            }
                        }
                    }

                    ToolTip {
                        visible: lineSelectionMouseArea.containsMouse && !lineSelectionMouseArea.pressed
                        text: "Drag to select whole lines"
                        delay: 500
                    }
                }

                ScrollView {
                    id: textScroll
                    objectName: "configViewerScrollView"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ScrollBar.horizontal.policy: root.wrapLongLines
                                                 ? ScrollBar.AlwaysOff
                                                 : ScrollBar.AsNeeded
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    Connections {
                        target: textScroll.contentItem
                        function onContentYChanged() {
                            if (!root.smoothVerticalScrolling)
                                root.snapVerticalScroll()
                        }
                    }

                    TextArea {
                        id: configTextArea
                        objectName: "configViewerTextArea"
                        text: ""
                        readOnly: true
                        selectByMouse: true
                        persistentSelection: true
                        textFormat: TextEdit.RichText
                        wrapMode: root.wrapLongLines
                                  ? TextEdit.WrapAtWordBoundaryOrAnywhere
                                  : TextEdit.NoWrap
                        color: Theme.textPrimary
                        selectedTextColor: Theme.selectionForeground
                        selectionColor: Theme.selectionBackground
                        font.family: "Consolas"
                        font.pixelSize: root.fontPixelSize
                        leftPadding: Theme.spacing8
                        rightPadding: Theme.spacing8
                        topPadding: root.codeVerticalPadding
                        bottomPadding: root.codeVerticalPadding
                        background: null

                        Repeater {
                            id: selectionOccurrenceRepeater
                            objectName: "configViewerOccurrenceRepeater"
                            model: root.occurrencePositions

                            delegate: Rectangle {
                                required property var modelData
                                objectName: "configViewerOccurrenceMarker"

                                readonly property rect startGeometry: configTextArea.positionToRectangle(
                                    root.safeDocumentPosition(Number(modelData.start))
                                )
                                readonly property rect endGeometry: configTextArea.positionToRectangle(
                                    root.safeDocumentPosition(
                                        Number(modelData.start) + Number(modelData.length)
                                    )
                                )

                                x: startGeometry.x
                                y: startGeometry.y
                                width: Math.max(2, endGeometry.x - startGeometry.x)
                                height: startGeometry.height
                                radius: 2
                                color: "transparent"
                                border.color: Theme.accentColor
                                border.width: Theme.borderWidth
                                opacity: 0.8
                                z: 10
                            }
                        }

                        Accessible.role: Accessible.StaticText
                        Accessible.name: root.sourceLabel

                        WheelHandler {
                            objectName: "configViewerZoomWheelHandler"
                            target: null
                            acceptedModifiers: Qt.ControlModifier
                            onWheel: function(event) {
                                if (event.angleDelta.y > 0)
                                    root.zoomIn()
                                else if (event.angleDelta.y < 0)
                                    root.zoomOut()
                                event.accepted = true
                            }
                        }

                        WheelHandler {
                            objectName: "configViewerLineScrollWheelHandler"
                            enabled: !root.smoothVerticalScrolling
                            target: null
                            acceptedModifiers: Qt.NoModifier
                            onWheel: function(event) {
                                if (root.handleVerticalWheel(event.angleDelta.y, event.pixelDelta.y))
                                    event.accepted = true
                            }
                        }

                        MouseArea {
                            id: contextMenuMouseArea
                            anchors.fill: parent
                            acceptedButtons: Qt.RightButton
                            propagateComposedEvents: true
                            onPressed: function(mouse) {
                                const menuPosition = contextMenuMouseArea.mapToItem(
                                    root, mouse.x, mouse.y
                                )
                                configTextContextMenu.openAt(menuPosition.x, menuPosition.y)
                                mouse.accepted = true
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            id: viewerBottomToolbar
            objectName: "configViewerBottomToolbar"
            Layout.fillWidth: true
            spacing: Theme.spacing4

            StandardTextField {
                id: searchField
                objectName: "configViewerSearchField"
                Layout.minimumWidth: 180
                Layout.preferredWidth: 300
                Layout.maximumWidth: 420
                placeholderText: "Find in configuration (Ctrl+F)"
                text: root.searchText
                enabled: !root.loading && root.errorText === "" && root.text !== ""
                onTextEdited: function(value) { root.searchText = value }
                onAccepted: root.findNext()
                onReverseAccepted: root.findPrevious()
            }

            Text {
                Layout.preferredWidth: 72
                text: {
                    if (root.searchText === "") return ""
                    if (root.matchCount === 0) return "No matches"
                    const current = root.currentMatchIndex < 0 ? "–" : String(root.currentMatchIndex + 1)
                    return current + " / " + root.matchCount + (root.searchResultsTruncated ? "+" : "")
                }
                color: root.searchText !== "" && root.matchCount === 0
                       ? Theme.alertWarning
                       : Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                horizontalAlignment: Text.AlignHCenter
            }

            StandardButton {
                objectName: "configViewerPreviousButton"
                type: "Icon"
                tooltip: "Previous match (Shift+Enter)"
                icon.source: AppAssets.navigationChevronUp
                enabled: root.matchCount > 0
                onClicked: root.findPrevious()
            }

            StandardButton {
                objectName: "configViewerNextButton"
                type: "Icon"
                tooltip: "Next match (Enter)"
                icon.source: AppAssets.navigationChevronDown
                enabled: root.matchCount > 0
                onClicked: root.findNext()
            }

            Item { Layout.fillWidth: true }

            Text {
                visible: root.highlightingInProgress || root.highlightingSkippedForLargeText
                text: root.highlightingInProgress
                      ? "Highlighting…"
                      : "Plain text · large file"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeCaption
            }

            Text {
                text: "Zoom"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }

            StandardButton {
                objectName: "configViewerZoomOutButton"
                Layout.preferredWidth: 34
                type: "Secondary"
                text: "−"
                tooltip: "Zoom out (Ctrl+-)"
                enabled: root.zoomPercent > root.minimumZoomPercent
                onClicked: root.zoomOut()
            }

            StandardButton {
                objectName: "configViewerZoomPercentButton"
                Layout.minimumWidth: 64
                Layout.preferredWidth: 64
                Layout.maximumWidth: 64
                type: "Secondary"
                text: root.zoomPercent + "%"
                tooltip: root.zoomPercent === root.defaultZoomPercent
                         ? "Default zoom is 100%"
                         : "Reset zoom to 100% (Ctrl+0)"
                onClicked: root.resetZoom()
            }

            StandardButton {
                objectName: "configViewerZoomInButton"
                Layout.preferredWidth: 34
                type: "Secondary"
                text: "+"
                tooltip: "Zoom in (Ctrl+=)"
                enabled: root.zoomPercent < root.maximumZoomPercent
                onClicked: root.zoomIn()
            }

        }
    }

    ConfigTextContextMenu {
        id: configTextContextMenu
        objectName: "configViewerContextMenu"
        hasSelection: root.selectedText !== ""
        onCopyRequested: root.copySelection()
        onFindRequested: root.findSelectedText()
    }
}
