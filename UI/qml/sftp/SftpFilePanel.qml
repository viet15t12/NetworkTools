
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    required property var backend
    required property var fileModel
    required property string currentPath
    readonly property bool backendAvailable: backend !== null && backend !== undefined
    readonly property bool remoteDisconnected: remoteSide
                                               && (!backendAvailable || !backend.connected)
    property bool remoteSide: false
    property bool activePane: false
    property int selectedIndex: -1
    property var selectedIndices: []
    property int selectionAnchor: -1
    readonly property int selectedCount: selectedIndices.length
    property string editMode: ""
    readonly property bool pathInputFocused: pathField.inputActiveFocus
    readonly property bool canGoBack: backendAvailable
        && (remoteSide ? backend.remoteCanGoBack : backend.localCanGoBack)
    readonly property bool canGoForward: backendAvailable
        && (remoteSide ? backend.remoteCanGoForward : backend.localCanGoForward)

    signal activated()

    color: Theme.contentPanelSurface
    border.color: activePane ? Theme.accentColor : Theme.contentPanelBorder
    border.width: activePane ? 2 : Theme.borderWidth
    radius: Theme.radiusSmall
    enabled: backendAvailable && (!remoteSide || backend.connected)
    opacity: enabled ? 1.0 : 0.55

    function selectedItem() {
        return fileModel && isSelected(selectedIndex)
            ? fileModel.get(selectedIndex) : null
    }
    function selectedRows() {
        return selectedIndices.slice()
    }
    function isSelected(index) {
        return selectedIndices.indexOf(index) >= 0
    }
    function clearSelection() {
        selectedIndices = []
        selectedIndex = -1
        selectionAnchor = -1
    }
    function selectSingle(index) {
        selectedIndices = [index]
        selectedIndex = index
        selectionAnchor = index
    }
    function toggleSelection(index) {
        const next = selectedIndices.slice()
        const position = next.indexOf(index)
        if (position >= 0)
            next.splice(position, 1)
        else
            next.push(index)
        next.sort(function(left, right) { return left - right })
        selectedIndices = next
        selectedIndex = position >= 0
            ? (next.length > 0 ? next[next.length - 1] : -1)
            : index
        selectionAnchor = index
    }
    function selectRange(index, preserveExisting) {
        const anchor = selectionAnchor >= 0 ? selectionAnchor : index
        const next = preserveExisting ? selectedIndices.slice() : []
        const first = Math.min(anchor, index)
        const last = Math.max(anchor, index)
        for (let row = first; row <= last; ++row) {
            if (next.indexOf(row) < 0)
                next.push(row)
        }
        next.sort(function(left, right) { return left - right })
        selectedIndices = next
        selectedIndex = index
        selectionAnchor = anchor
    }
    function updateSelection(index, modifiers) {
        const controlPressed = (modifiers & Qt.ControlModifier) !== 0
        const shiftPressed = (modifiers & Qt.ShiftModifier) !== 0
        if (shiftPressed)
            selectRange(index, controlPressed)
        else if (controlPressed)
            toggleSelection(index)
        else
            selectSingle(index)
    }
    function selectAll() {
        const next = []
        for (let row = 0; row < fileList.count; ++row)
            next.push(row)
        selectedIndices = next
        selectedIndex = next.length > 0 ? next[0] : -1
        selectionAnchor = selectedIndex
    }
    function openContextAt(item, localX, localY) {
        const point = item.mapToItem(null, localX, localY)
        fileContextMenu.openAt(point.x, point.y)
    }
    function openContextForSelection() {
        const item = selectedIndex >= 0 ? fileList.itemAtIndex(selectedIndex) : null
        if (item)
            openContextAt(item, Math.min(item.width - 8, 180), item.height / 2)
        else {
            const point = fileList.mapToItem(null, Theme.spacing12, Theme.spacing12)
            fileContextMenu.openAt(point.x, point.y)
        }
    }
    function fileTypeIcon(name) {
        return AppAssets.fileTypeIcon(name)
    }
    function refresh() {
        if (!backendAvailable)
            return
        clearSelection()
        if (remoteSide)
            backend.refreshRemote()
        else
            backend.refreshLocal()
    }
    function goUp() {
        if (!backendAvailable)
            return
        clearSelection()
        if (remoteSide)
            backend.remoteGoUp()
        else
            backend.localGoUp()
    }
    function goBack() {
        if (!backendAvailable || !canGoBack)
            return
        clearSelection()
        if (remoteSide)
            backend.remoteGoBack()
        else
            backend.localGoBack()
    }
    function goForward() {
        if (!backendAvailable || !canGoForward)
            return
        clearSelection()
        if (remoteSide)
            backend.remoteGoForward()
        else
            backend.localGoForward()
    }
    function openPath(path) {
        if (!backendAvailable)
            return
        clearSelection()
        if (remoteSide)
            backend.openRemoteDirectory(path)
        else
            backend.openLocalDirectory(path)
    }
    function openSelected() {
        if (!backendAvailable)
            return
        const item = selectedItem()
        if (!item)
            return
        if (selectedCount > 1) {
            transferSelected()
        } else if (item.isDirectory) {
            openPath(item.path)
        } else if (remoteSide) {
            backend.downloadFile(selectedIndex)
        } else {
            backend.uploadFile(selectedIndex)
        }
    }
    function transferSelected() {
        if (!backendAvailable || !backend.connected || selectedCount === 0)
            return
        const rows = selectedRows()
        if (remoteSide)
            backend.downloadEntries(rows)
        else
            backend.uploadEntries(rows)
    }
    function beginEdit(mode) {
        if (!backendAvailable)
            return
        if (mode === "rename" && selectedCount !== 1)
            return
        editMode = mode
        const item = selectedItem()
        entryDialog.value = mode === "rename" && item ? item.name : ""
        entryDialog.titleText = mode === "rename" ? "Rename entry" : "Create folder"
        entryDialog.acceptText = mode === "rename" ? "Rename" : "Create"
        entryDialog.open()
    }
    function requestDelete() {
        if (selectedCount === 0)
            return
        const item = selectedItem()
        const targetText = selectedCount === 1 && item
            ? "\"" + item.name + "\""
            : selectedCount + " selected entries"
        deleteDialog.messageText = "Delete " + targetText + "?\n\n"
            + "Directories must be empty; recursive deletion is disabled."
        deleteDialog.open()
    }

    onCurrentPathChanged: pathField.text = currentPath
    Component.onCompleted: pathField.text = currentPath

    Connections {
        target: root.fileModel
        function onModelReset() {
            root.clearSelection()
        }
    }

    SftpFileContextMenu {
        id: fileContextMenu
        objectName: root.remoteSide
                    ? "sftpRemoteFileContextMenu" : "sftpLocalFileContextMenu"
        parent: Window.window ? Window.window.contentItem : root
        selectedCount: root.selectedCount
        singleDirectory: root.selectedCount === 1
                         && root.selectedItem()
                         && root.selectedItem().isDirectory
        remoteSide: root.remoteSide
        connected: root.backendAvailable && root.backend.connected
        onPrimaryRequested: root.openSelected()
        onRenameRequested: root.beginEdit("rename")
        onDeleteRequested: root.requestDelete()
        onCreateFolderRequested: root.beginEdit("create")
        onSelectAllRequested: root.selectAll()
        onRefreshRequested: root.refresh()
    }

    SftpEntryDialog {
        id: entryDialog
        objectName: root.remoteSide
                    ? "sftpRemoteEntryDialog" : "sftpLocalEntryDialog"
        onAccepted: {
            if (!root.backendAvailable)
                return
            if (root.editMode === "rename")
                root.backend.renameEntry(root.remoteSide, root.selectedIndex, value)
            else
                root.backend.createDirectory(root.remoteSide, value)
        }
    }

    SftpMessageDialog {
        id: deleteDialog
        titleText: "Delete entry"
        confirmation: true
        acceptText: "Delete"
        onAccepted: {
            if (!root.backendAvailable)
                return
            root.backend.deleteEntries(root.remoteSide, root.selectedRows())
            root.clearSelection()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing8

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: root.remoteSide ? "REMOTE" : "LOCAL"
                color: Theme.textPrimary
                font.bold: true
                font.family: Theme.fontFamily
            }
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                text: root.remoteSide
                      ? (root.backendAvailable
                         ? root.backend.statusMessage
                         : "SFTP backend unavailable")
                      : "Local filesystem"
                elide: Text.ElideRight
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
            }
        }

        RowLayout {
            Layout.fillWidth: true
            StandardTextField {
                id: pathField
                objectName: root.remoteSide ? "sftpRemotePathField" : "sftpLocalPathField"
                Layout.fillWidth: true
                placeholderText: root.remoteSide ? "/" : "Local path"
                onAccepted: {
                    root.activated()
                    root.openPath(text)
                }
            }
            IconButton {
                objectName: root.remoteSide ? "sftpRemoteBack" : "sftpLocalBack"
                iconSource: AppAssets.navigationChevronLeft
                tooltip: "Back (Alt+Left / Mouse Back)"
                enabled: root.canGoBack
                onClicked: { root.activated(); root.goBack() }
            }
            IconButton {
                objectName: root.remoteSide ? "sftpRemoteForward" : "sftpLocalForward"
                iconSource: AppAssets.navigationChevronRight
                tooltip: "Forward (Alt+Right / Mouse Forward)"
                enabled: root.canGoForward
                onClicked: { root.activated(); root.goForward() }
            }
            IconButton {
                objectName: root.remoteSide ? "sftpRemoteUp" : "sftpLocalUp"
                iconSource: AppAssets.navigationUp
                tooltip: "Up (Alt+Up)"
                onClicked: { root.activated(); root.goUp() }
            }
            IconButton {
                objectName: root.remoteSide ? "sftpRemoteRefresh" : "sftpLocalRefresh"
                iconSource: AppAssets.actionRefresh
                tooltip: "Refresh (F5 / Ctrl+R)"
                onClicked: { root.activated(); root.refresh() }
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: Theme.spacing8
            StandardButton {
                objectName: root.remoteSide ? "sftpRemoteNewFolderButton"
                                            : "sftpLocalNewFolderButton"
                width: Math.ceil(expandedImplicitWidth)
                text: "New folder"
                onClicked: root.beginEdit("create")
            }
            StandardButton {
                objectName: root.remoteSide ? "sftpRemoteRenameButton"
                                            : "sftpLocalRenameButton"
                width: Math.ceil(expandedImplicitWidth)
                text: "Rename"
                icon.source: AppAssets.actionEdit
                enabled: root.selectedCount === 1
                onClicked: root.beginEdit("rename")
            }
            StandardButton {
                objectName: root.remoteSide ? "sftpRemoteDeleteButton"
                                            : "sftpLocalDeleteButton"
                width: Math.ceil(expandedImplicitWidth)
                text: "Delete"
                type: "Danger"
                icon.source: AppAssets.actionDelete
                enabled: root.selectedCount > 0
                onClicked: {
                    root.requestDelete()
                }
            }
            StandardButton {
                objectName: root.remoteSide ? "sftpRemoteTransferButton"
                                            : "sftpLocalTransferButton"
                width: Math.ceil(expandedImplicitWidth)
                text: (root.remoteSide ? "Download" : "Upload")
                      + (root.selectedCount > 1 ? " (" + root.selectedCount + ")" : "")
                type: "Primary"
                icon.source: root.remoteSide
                             ? AppAssets.actionDownload
                             : AppAssets.actionUpload
                enabled: root.selectedCount > 0
                         && root.backendAvailable
                         && root.backend.connected
                onClicked: {
                    root.transferSelected()
                }
            }
        }

        DataTableHeader {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.tableHeaderHeight

            RowLayout {
                anchors.fill: parent
                spacing: Theme.spacing8
                DataTableCell { Layout.preferredWidth: 22; header: true; text: "" }
                DataTableCell { Layout.fillWidth: true; header: true; text: "Name" }
                DataTableCell { Layout.preferredWidth: 104; header: true; text: "Type" }
                DataTableCell { Layout.preferredWidth: 76; header: true; text: "Size" }
                DataTableCell { Layout.preferredWidth: 128; header: true; text: "Modified" }
            }
        }

        ListView {
            id: fileList
            objectName: root.remoteSide
                        ? "sftpRemoteFileList" : "sftpLocalFileList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 0
            model: root.fileModel
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: DataTableRow {
                id: row
                objectName: (root.remoteSide ? "sftpRemoteRow" : "sftpLocalRow") + index
                required property int index
                required property string name
                required property string path
                required property bool isDirectory
                required property string sizeText
                required property string typeText
                required property string modified
                readonly property string typeIconSource: row.isDirectory
                    ? "" : root.fileTypeIcon(row.name)
                width: fileList.width
                height: Theme.tableRowHeight
                rowIndex: index
                selected: root.isSelected(index)

                RowLayout {
                    anchors.fill: parent
                    spacing: Theme.spacing8
                    Image {
                        Layout.preferredWidth: 22
                        Layout.preferredHeight: Theme.iconSizeNormal
                        source: row.isDirectory
                                ? AppAssets.fileFolder
                                : row.typeIconSource !== ""
                                  ? row.typeIconSource
                                  : AppAssets.fileGeneric
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                    }
                    Text {
                        Layout.fillWidth: true
                        text: row.name
                        elide: Text.ElideRight
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                    }
                    Text {
                        Layout.preferredWidth: 104
                        text: row.typeText
                        elide: Text.ElideRight
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                    Text {
                        Layout.preferredWidth: 76
                        text: row.sizeText
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                    Text {
                        Layout.preferredWidth: 128
                        text: row.modified
                        elide: Text.ElideRight
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: function(mouse) {
                        root.activated()
                        if (mouse.button === Qt.RightButton) {
                            if (!root.isSelected(row.index))
                                root.selectSingle(row.index)
                            root.openContextAt(row, mouse.x, mouse.y)
                        } else {
                            root.updateSelection(row.index, mouse.modifiers)
                        }
                    }
                    onDoubleClicked: function(mouse) {
                        if (mouse.button !== Qt.LeftButton)
                            return
                        root.activated()
                        root.selectSingle(row.index)
                        root.openSelected()
                    }
                }
            }

            EmptyState {
                anchors.fill: parent
                visible: fileList.count === 0
                title: root.remoteDisconnected
                    ? "Connect to an SFTP server"
                    : "This directory is empty"
                description: root.remoteDisconnected
                    ? "Enter a connection above to browse the remote file system."
                    : "No files or folders are available at this path."
            }
        }
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        gesturePolicy: TapHandler.WithinBounds
        onTapped: root.activated()
    }
}
