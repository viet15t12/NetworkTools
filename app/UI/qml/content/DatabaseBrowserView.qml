pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    color: Theme.contentBackground

    property string activeTable: ""
    property var tableData: ({ "columns": [], "rows": [], "message": "" })
    property bool editMode: false
    readonly property var toolsBackend: typeof externalTools !== "undefined" && externalTools !== null
                                        ? externalTools
                                        : null

    function reloadTable() {
        if (toolsBackend === null) {
            tableData = { "columns": [], "rows": [], "message": "Database backend is unavailable." }
            editMode = false
            return
        }
        if (activeTable === "") {
            tableData = { "columns": [], "rows": [], "message": "Select a table." }
            editMode = false
            return
        }
        tableData = toolsBackend.getTableRows(activeTable)
        if (!tableData.editable)
            editMode = false
    }

    function saveCell(rowData, columnName, value) {
        if (toolsBackend === null || !editMode || !tableData.editable
                || rowData === undefined || rowData === null
                || rowData.__rowid__ === undefined)
            return
        const oldValue = rowData[columnName] === undefined || rowData[columnName] === null ? "" : String(rowData[columnName])
        if (oldValue === value)
            return
        const result = toolsBackend.updateTableCell(activeTable, rowData.__rowid__, columnName, value)
        if (result.ok) {
            reloadTable()
        } else {
            tableData = Object.assign({}, tableData, {
                "message": result.message || "Update failed."
            })
        }
    }

    function cellText(rowData, columnName) {
        if (rowData === undefined || rowData === null || columnName === "")
            return ""
        const value = rowData[columnName]
        return value === undefined || value === null ? "" : String(value)
    }

    onToolsBackendChanged: reloadTable()
    onActiveTableChanged: reloadTable()
    Component.onCompleted: reloadTable()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    text: root.activeTable !== "" ? root.activeTable : "Database Browser"
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeLarge
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Text {
                    text: root.tableData.message || "device_network.db"
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            StandardButton {
                text: "View"
                type: root.editMode ? "Secondary" : "Primary"
                onClicked: root.editMode = false
            }

            StandardButton {
                text: "Edit"
                type: root.editMode ? "Primary" : "Secondary"
                enabled: root.tableData.editable === true
                tooltip: root.tableData.editable === true ? "" : "This table cannot be edited with rowid."
                onClicked: root.editMode = true
            }

            StandardButton {
                text: "Reload UI"
                icon.source: AppAssets.actionDatabaseReload
                type: "Secondary"
                autoCompact: false
                Layout.minimumWidth: expandedImplicitWidth
                onClicked: root.reloadTable()
            }
        }

        DataTableFrame {
            Layout.fillWidth: true
            Layout.fillHeight: true

            EmptyState {
                anchors.fill: parent
                visible: (root.tableData.columns || []).length === 0
                title: root.activeTable === "" ? "No table selected" : "No columns"
                description: root.activeTable === ""
                    ? "Select a database table from the left panel."
                    : "The selected table does not expose any columns."
            }

            ScrollView {
                id: tableScroll
                anchors.fill: parent
                anchors.margins: Theme.spacing8
                visible: (root.tableData.columns || []).length > 0
                clip: true

                Column {
                    width: Math.max(tableScroll.availableWidth,
                                    (root.tableData.columns || []).length * 160 + Theme.spacing24)

                    DataTableHeader {
                        width: parent.width
                        height: Theme.tableHeaderHeight

                        Row {
                            anchors.fill: parent

                            Repeater {
                                model: root.tableData.columns || []

                                delegate: DataTableCell {
                                    required property string modelData
                                    width: 160
                                    height: parent ? parent.height : Theme.tableHeaderHeight
                                    header: true
                                    text: modelData
                                }
                            }
                        }
                    }

                    ListView {
                        id: tableRows
                        width: parent.width
                        height: Math.max(0, tableScroll.availableHeight - Theme.tableHeaderHeight)
                        clip: true
                        model: root.tableData.rows || []

                        delegate: DataTableRow {
                            id: tableRowDelegate
                            required property int index
                            required property var modelData
                            property var rowData: modelData
                            width: ListView.view.width
                            height: Theme.tableRowHeight
                            rowIndex: index
                            interactive: false

                            Row {
                                anchors.fill: parent

                                Repeater {
                                    model: root.tableData.columns || []

                                    delegate: Item {
                                        id: cellDelegate
                                        required property string modelData
                                        property string columnName: modelData
                                        width: 160
                                        height: parent ? parent.height : Theme.tableRowHeight

                                        DataTableCell {
                                            anchors.fill: parent
                                            text: root.cellText(
                                                tableRowDelegate.rowData,
                                                cellDelegate.columnName
                                            )
                                            visible: !root.editMode
                                        }

                                        TextField {
                                            id: editField
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacing2
                                            visible: root.editMode
                                            text: root.cellText(
                                                tableRowDelegate.rowData,
                                                cellDelegate.columnName
                                            )
                                            color: Theme.textPrimary
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fontSizeSmall
                                            selectByMouse: true
                                            selectionColor: Theme.selectionBackground
                                            selectedTextColor: Theme.selectionForeground
                                            verticalAlignment: TextInput.AlignVCenter
                                            leftPadding: Theme.spacing8
                                            rightPadding: Theme.spacing8

                                            background: Rectangle {
                                                color: editField.activeFocus
                                                       ? Theme.inputBackground : "transparent"
                                                border.width: editField.activeFocus
                                                              ? Theme.borderWidth : 0
                                                border.color: Theme.inputBorderFocusColor
                                                radius: Theme.radiusSmall
                                            }

                                            onAccepted: root.saveCell(
                                                tableRowDelegate.rowData,
                                                cellDelegate.columnName,
                                                text
                                            )
                                            onEditingFinished: root.saveCell(
                                                tableRowDelegate.rowData,
                                                cellDelegate.columnName,
                                                text
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
