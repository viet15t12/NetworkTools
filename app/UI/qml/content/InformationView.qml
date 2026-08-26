pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "informationView"

    property string currentHostIp: ""
    property string configText: ""
    property string configPath: ""
    property string loadError: ""
    property string viewMode: "snapshot"
    property var commitHistory: []
    property var commitHistoryLabels: []
    property string selectedCommitId: ""
    property string selectedCommitDateTime: ""
    property string diffText: ""
    property string diffError: ""
    property string diffBaseCommitId: ""
    property string diffTargetCommitId: ""
    property string diffBaseDateTime: ""
    property string diffTargetDateTime: ""
    property int diffAdditions: 0
    property int diffDeletions: 0
    property int diffVersionSpan: 0
    property bool isLoadingHistory: false
    property bool isLoadingCommit: false
    property bool isLoadingDiff: false
    property string lastLoadedHost: ""
    property string lastReloadReason: ""
    readonly property bool isViewLoading: root.isLoadingHistory
                                          || root.isLoadingCommit
                                          || root.isLoadingDiff
                                          || informationConfigViewer.highlightingInProgress
    readonly property bool compactLayout: width < Theme.compactWorkspaceBreakpoint
    readonly property string displayedText: root.viewMode === "diff"
                                                    ? root.diffText
                                                    : root.configText
    readonly property string displayedError: root.viewMode === "diff"
                                                     ? root.diffError
                                                     : root.loadError
    readonly property string diffSummary: root.diffVersionSpan <= 0
                                                  ? ""
                                                  : root.diffAdditions + " additions · "
                                                    + root.diffDeletions + " deletions · "
                                                    + root.diffVersionSpan
                                                    + (root.diffVersionSpan === 1
                                                       ? " version" : " versions")

    color: Theme.contentBackground

    // Xóa toàn bộ dữ liệu của host cũ trước khi tải lịch sử host mới.
    function clearContent() {
        root.configText = ""
        root.configPath = ""
        root.loadError = ""
        root.selectedCommitId = ""
        root.selectedCommitDateTime = ""
        root.diffText = ""
        root.diffError = ""
        root.diffBaseCommitId = ""
        root.diffTargetCommitId = ""
        root.diffBaseDateTime = ""
        root.diffTargetDateTime = ""
        root.diffAdditions = 0
        root.diffDeletions = 0
        root.diffVersionSpan = 0
    }

    // Đọc một Git blob lịch sử; thao tác này không checkout hay gửi lệnh thiết bị.
    function loadCommit(commitId) {
        const host = String(root.currentHostIp || "").trim()
        const requestedCommit = String(commitId || "").trim()
        if (host === "" || requestedCommit === "")
            return false
        root.isLoadingCommit = true
        const payload = dbManager.getRunningConfigAtCommit(host, requestedCommit)
        root.applyCommitPayload(requestedCommit, payload)
        root.isLoadingCommit = false
        return true
    }

    // So sánh hai endpoint bất kỳ; hai commit không liền kề tạo Diff tích lũy
    // cho toàn bộ khoảng phiên bản Git nằm giữa chúng.
    function loadDiff() {
        const host = String(root.currentHostIp || "").trim()
        const baseIndex = diffBaseComboBox.currentIndex
        const targetIndex = diffTargetComboBox.currentIndex
        if (host === "" || baseIndex < 0 || targetIndex < 0
                || baseIndex >= root.commitHistory.length
                || targetIndex >= root.commitHistory.length)
            return false

        const baseCommit = String(root.commitHistory[baseIndex].commitId || "")
        const targetCommit = String(root.commitHistory[targetIndex].commitId || "")
        root.isLoadingDiff = true
        const payload = dbManager.getRunningConfigDiff(host, baseCommit, targetCommit)
        root.applyDiffPayload(baseCommit, targetCommit, payload)
        root.isLoadingDiff = false
        return true
    }

    function applyDiffPayload(baseCommit, targetCommit, payload) {
        const ok = payload && payload.ok === true
        if (ok) {
            root.diffText = payload.diff ? String(payload.diff) : ""
            root.diffBaseCommitId = String(payload.baseCommitId || baseCommit)
            root.diffTargetCommitId = String(payload.targetCommitId || targetCommit)
            root.diffBaseDateTime = String(payload.baseDateTime || "")
            root.diffTargetDateTime = String(payload.targetDateTime || "")
            root.diffAdditions = Number(payload.additions || 0)
            root.diffDeletions = Number(payload.deletions || 0)
            root.diffVersionSpan = Number(payload.versionSpan || 0)
            root.diffError = ""
        } else {
            root.diffText = ""
            root.diffBaseCommitId = String(baseCommit || "")
            root.diffTargetCommitId = String(targetCommit || "")
            root.diffBaseDateTime = ""
            root.diffTargetDateTime = ""
            root.diffAdditions = 0
            root.diffDeletions = 0
            root.diffVersionSpan = 0
            root.diffError = payload && payload.message
                           ? String(payload.message)
                           : "Compare running-config versions failed."
        }
    }

    function setViewMode(mode) {
        const requestedMode = String(mode || "snapshot")
        if (requestedMode === "diff" && root.commitHistory.length >= 2) {
            root.viewMode = "diff"
            return root.loadDiff()
        }
        root.viewMode = "snapshot"
        return true
    }

    // Ánh xạ payload snapshot backend vào ConfigTextViewer hiện có.
    function applyCommitPayload(requestedCommit, payload) {
        const ok = payload && payload.ok === true
        root.configPath = payload && payload.path ? String(payload.path) : ""
        if (ok) {
            root.configText = payload && payload.content ? String(payload.content) : ""
            root.selectedCommitId = String(payload.commitId || requestedCommit)
            root.selectedCommitDateTime = String(payload.dateTime || "")
            root.loadError = ""
        } else {
            root.configText = ""
            root.loadError = payload && payload.message ? String(payload.message) : "Load committed running-config failed."
        }
    }

    // Tải lại tối đa 100 commit và luôn đưa lựa chọn về HEAD mới nhất.
    function reloadData(reason) {
        const host = String(root.currentHostIp || "").trim()
        root.lastReloadReason = String(reason || "manual")
        root.clearContent()
        root.commitHistory = []
        root.commitHistoryLabels = []
        commitHistoryComboBox.currentIndex = -1
        diffBaseComboBox.currentIndex = -1
        diffTargetComboBox.currentIndex = -1
        root.lastLoadedHost = host
        if (host === "")
            return false

        root.isLoadingHistory = true
        const payload = dbManager.getRunningConfigHistory(host)
        root.applyHistoryPayload(payload)
        root.isLoadingHistory = false
        return true
    }

    // Tạo model nhãn cho StandardComboBox từ metadata commit mới nhất trước.
    function applyHistoryPayload(payload) {
        if (!payload || payload.ok !== true) {
            root.viewMode = "snapshot"
            root.loadError = payload && payload.message ? String(payload.message) : "Load running-config history failed."
            return
        }
        root.commitHistory = payload.commits || []
        const labels = []
        for (let index = 0; index < root.commitHistory.length; ++index)
            labels.push(String(root.commitHistory[index].displayText || ""))
        root.commitHistoryLabels = labels
        if (root.commitHistory.length < 2)
            root.viewMode = "snapshot"
        if (root.commitHistory.length > 0) {
            commitHistoryComboBox.currentIndex = 0
            diffBaseComboBox.currentIndex = root.commitHistory.length > 1 ? 1 : 0
            diffTargetComboBox.currentIndex = 0
            root.loadCommit(root.commitHistory[0].commitId)
            if (root.viewMode === "diff") {
                if (root.commitHistory.length > 1)
                    root.loadDiff()
                else
                    root.viewMode = "snapshot"
            }
        }
    }

    Connections {
        target: typeof cli !== "undefined" ? cli : null
        function onRunningConfigFinished(host, ok, message) {
            if (ok && String(host || "") === String(root.currentHostIp || "").trim())
                root.reloadData()
        }
    }

    Connections {
        target: typeof dbManager !== "undefined" ? dbManager : null
        function onRunningConfigUpdated(host) {
            if (String(host || "") === String(root.currentHostIp || "").trim())
                root.reloadData()
        }
    }

    onCurrentHostIpChanged: reloadData()
    Component.onCompleted: {
        if (root.lastLoadedHost !== String(root.currentHostIp || "").trim())
            root.reloadData()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compactLayout ? Theme.spacing12 : Theme.spacing24
        spacing: Theme.spacing12

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing12

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 3

                Text {
                    text: "Information"
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeLarge
                    font.bold: true
                }

                Text {
                    Layout.fillWidth: true
                    text: root.currentHostIp === ""
                          ? "No device selected"
                          : root.currentHostIp + (root.configPath !== "" ? " · " + root.configPath : "")
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    elide: Text.ElideLeft
                }
            }

            StandardButton {
                objectName: "informationReloadButton"
                text: "Reload UI"
                icon.source: AppAssets.actionBackup
                type: "Secondary"
                autoCompact: false
                Layout.minimumWidth: expandedImplicitWidth
                tooltip: "Reload running-config history"
                enabled: String(root.currentHostIp || "").trim() !== ""
                         && !root.isLoadingHistory
                         && !root.isLoadingCommit
                onClicked: root.reloadData()
            }

            StandardButton {
                objectName: "informationCopyAllButton"
                Layout.preferredWidth: 104
                text: informationConfigViewer.copyFeedbackVisible ? "Copied" : "Copy All"
                icon.source: AppAssets.actionCopy
                type: "Secondary"
                tooltip: "Copy all displayed configuration"
                enabled: root.displayedText !== ""
                onClicked: informationConfigViewer.copyAll()
            }
        }

        Rectangle {
            objectName: "informationVersionCard"
            Layout.fillWidth: true
            Layout.preferredHeight: versionControls.implicitHeight + Theme.spacing16
            radius: Theme.radiusSmall
            color: Theme.inputBackground
            border.color: Theme.inputBorderColor
            border.width: Theme.borderWidth

            ColumnLayout {
                id: versionControls
                objectName: "informationVersionControls"
                anchors.fill: parent
                anchors.margins: Theme.spacing8
                spacing: Theme.spacing8

                GridLayout {
                    id: primaryVersionLayout
                    objectName: "informationPrimaryVersionLayout"
                    Layout.fillWidth: true
                    columns: root.compactLayout ? 2 : 5
                    columnSpacing: Theme.spacing8
                    rowSpacing: Theme.spacing8

                    StandardButton {
                        objectName: "informationSnapshotModeButton"
                        Layout.row: 0
                        Layout.column: 0
                        Layout.fillWidth: root.compactLayout
                        Layout.preferredWidth: root.compactLayout ? 80 : 96
                        text: "Snapshot"
                        type: root.viewMode === "snapshot" ? "Primary" : "Secondary"
                        onClicked: root.setViewMode("snapshot")
                    }

                    StandardButton {
                        objectName: "informationCompareModeButton"
                        Layout.row: 0
                        Layout.column: 1
                        Layout.fillWidth: root.compactLayout
                        Layout.preferredWidth: root.compactLayout ? 80 : 96
                        text: "Compare"
                        type: root.viewMode === "diff" ? "Primary" : "Secondary"
                        tooltip: root.commitHistory.length < 2
                                 ? "At least two Git versions are required"
                                 : "Compare two endpoints across the selected Git history range"
                        enabled: root.commitHistory.length >= 2
                                 && !root.isLoadingHistory
                        onClicked: root.setViewMode("diff")
                    }

                    Rectangle {
                        visible: !root.compactLayout
                        Layout.row: 0
                        Layout.column: 2
                        Layout.preferredWidth: Theme.borderWidth
                        Layout.preferredHeight: Theme.itemHeight
                        color: Theme.borderColor
                    }

                    StandardComboBox {
                        id: commitHistoryComboBox
                        objectName: "informationCommitHistoryComboBox"
                        visible: root.viewMode === "snapshot"
                        Layout.row: root.compactLayout ? 1 : 0
                        Layout.column: root.compactLayout ? 0 : 3
                        Layout.columnSpan: root.compactLayout ? 2 : 1
                        Layout.fillWidth: true
                        Layout.maximumWidth: 520
                        labelText: "Version"
                        model: root.commitHistoryLabels
                        emptyText: "No backup history"
                        enabled: String(root.currentHostIp || "").trim() !== ""
                                 && root.commitHistory.length > 0
                                 && !root.isLoadingHistory
                                 && !root.isLoadingCommit
                        onActivated: function(index) {
                            if (index >= 0 && index < root.commitHistory.length)
                                root.loadCommit(root.commitHistory[index].commitId)
                        }
                    }

                    Item {
                        visible: !root.compactLayout
                        Layout.row: 0
                        Layout.column: 4
                        Layout.fillWidth: true
                    }

                    RowLayout {
                        visible: root.viewMode === "diff" && root.diffVersionSpan > 0
                        Layout.row: root.compactLayout ? 1 : 0
                        Layout.column: root.compactLayout ? 0 : 3
                        Layout.columnSpan: 2
                        Layout.fillWidth: root.compactLayout
                        Layout.alignment: Qt.AlignRight
                        spacing: Theme.spacing4

                        Rectangle {
                            objectName: "informationDiffAdditionsBadge"
                            Layout.preferredWidth: additionsText.implicitWidth + Theme.spacing16
                            Layout.preferredHeight: 24
                            radius: Theme.radiusRound
                            color: Theme.alertSuccessSubtle
                            Text {
                                id: additionsText
                                anchors.centerIn: parent
                                text: "+" + root.diffAdditions
                                color: Theme.alertSuccess
                                font.family: Theme.monoFontFamily
                                font.pixelSize: Theme.fontSizeSmall
                                font.bold: true
                            }
                        }

                        Rectangle {
                            objectName: "informationDiffDeletionsBadge"
                            Layout.preferredWidth: deletionsText.implicitWidth + Theme.spacing16
                            Layout.preferredHeight: 24
                            radius: Theme.radiusRound
                            color: Theme.alertErrorSubtle
                            Text {
                                id: deletionsText
                                anchors.centerIn: parent
                                text: "−" + root.diffDeletions
                                color: Theme.alertError
                                font.family: Theme.monoFontFamily
                                font.pixelSize: Theme.fontSizeSmall
                                font.bold: true
                            }
                        }

                        Text {
                            text: root.diffVersionSpan
                                  + (root.diffVersionSpan === 1 ? " version" : " versions")
                            color: Theme.textSecondary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeCaption
                        }
                    }
                }

                GridLayout {
                    objectName: "informationDiffRevisionPicker"
                    visible: root.viewMode === "diff"
                    Layout.fillWidth: true
                    columns: root.compactLayout ? 1 : 3
                    columnSpacing: Theme.spacing12
                    rowSpacing: Theme.spacing8

                    StandardComboBox {
                        id: diffBaseComboBox
                        objectName: "informationDiffBaseComboBox"
                        Layout.row: 0
                        Layout.column: 0
                        Layout.fillWidth: true
                        labelText: "Original (older)"
                        model: root.commitHistoryLabels
                        emptyText: "Original version"
                        enabled: root.commitHistory.length >= 2 && !root.isLoadingDiff
                        onActivated: root.loadDiff()
                    }

                    ThemedIcon {
                        visible: !root.compactLayout
                        Layout.row: 0
                        Layout.column: 1
                        Layout.alignment: Qt.AlignBottom
                        Layout.bottomMargin: (Theme.itemHeight - Theme.iconSizeNormal) / 2
                        iconSource: AppAssets.navigationChevronRight
                        iconSize: Theme.iconSizeNormal
                        iconColor: Theme.textSecondary
                    }

                    StandardComboBox {
                        id: diffTargetComboBox
                        objectName: "informationDiffTargetComboBox"
                        Layout.row: root.compactLayout ? 1 : 0
                        Layout.column: root.compactLayout ? 0 : 2
                        Layout.fillWidth: true
                        labelText: "Modified (newer)"
                        model: root.commitHistoryLabels
                        emptyText: "Modified version"
                        enabled: root.commitHistory.length >= 2 && !root.isLoadingDiff
                        onActivated: root.loadDiff()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusSmall
            color: Theme.contentPanelSurface
            border.color: Theme.contentPanelBorder
            border.width: Theme.borderWidth

            ConfigTextViewer {
                id: informationConfigViewer
                objectName: "informationConfigViewer"
                anchors.fill: parent
                anchors.margins: Theme.spacing12
                text: root.displayedText
                wrapLongLines: true
                smoothVerticalScrolling: true
                syntaxMode: root.viewMode === "diff" ? "diff" : "configuration"
                sourceLabel: root.viewMode === "diff"
                             ? "Configuration Diff · " + root.diffBaseCommitId.slice(0, 7)
                               + " → " + root.diffTargetCommitId.slice(0, 7)
                             : (root.selectedCommitDateTime !== ""
                                ? "Running configuration · " + root.selectedCommitDateTime
                                  + " · " + root.selectedCommitId.slice(0, 7)
                                : "Running configuration")
                loading: root.isLoadingHistory || root.isLoadingCommit || root.isLoadingDiff
                loadingText: root.viewMode === "diff"
                             ? "Comparing Git versions..."
                             : "Loading running-config history..."
                errorText: root.displayedError
                emptyText: root.viewMode === "diff"
                           ? "The selected versions have identical running-config content."
                           : (root.currentHostIp === ""
                              ? "Choose a device to view its running-config backup."
                              : "No running-config data is available.")
            }
        }
    }
}
