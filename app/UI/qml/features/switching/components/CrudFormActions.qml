pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

RowLayout {
    id: root
    property int formMode: 0
    property bool hasSelection: false
    property bool dirty: false
    property bool valid: true
    property bool saving: false
    property bool allowCreate: true
    property bool allowEdit: true
    property bool allowDelete: false
    property bool allowRefresh: true
    property bool allowEditorActions: true

    signal addRequested()
    signal editRequested()
    signal deleteRequested()
    signal saveRequested()
    signal cancelRequested()
    signal refreshRequested()

    spacing: Theme.spacing8

    StandardButton {
        objectName: "crudAddButton"
        text: "Add"
        icon.source: AppAssets.actionAdd
        autoCompact: false
        Layout.minimumWidth: expandedImplicitWidth
        visible: root.formMode === 0 && root.allowCreate
        enabled: !root.saving
        tooltip: "Add a new entry"
        onClicked: root.addRequested()
    }
    StandardButton {
        objectName: "crudEditButton"
        text: "Edit"
        icon.source: AppAssets.actionEdit
        autoCompact: false
        Layout.minimumWidth: expandedImplicitWidth
        visible: root.formMode === 0 && root.allowEdit
        enabled: root.hasSelection && !root.saving
        tooltip: "Edit the selected entry"
        onClicked: root.editRequested()
    }
    StandardButton {
        objectName: "crudDeleteButton"
        text: "Delete"
        icon.source: AppAssets.actionDelete
        type: "Danger"
        autoCompact: false
        Layout.minimumWidth: expandedImplicitWidth
        visible: root.formMode === 0 && root.allowDelete
        enabled: root.hasSelection && !root.saving
        tooltip: "Delete the selected entry"
        onClicked: root.deleteRequested()
    }
    StandardButton {
        objectName: "crudReloadButton"
        text: "Reload UI"
        icon.source: AppAssets.actionDatabaseReload
        autoCompact: false
        Layout.minimumWidth: expandedImplicitWidth
        visible: root.formMode === 0 && root.allowRefresh
        enabled: !root.saving
        tooltip: "Reload data"
        onClicked: root.refreshRequested()
    }
    StandardButton {
        objectName: "crudCancelButton"
        text: "Cancel"
        icon.source: AppAssets.actionClear
        type: "Text"
        autoCompact: false
        Layout.minimumWidth: expandedImplicitWidth
        visible: root.formMode !== 0 && root.allowEditorActions
        enabled: !root.saving
        tooltip: "Cancel changes"
        onClicked: root.cancelRequested()
    }
    StandardButton {
        objectName: "crudSaveButton"
        text: root.saving ? "Saving..." : "Save"
        icon.source: AppAssets.actionSave
        type: "Primary"
        autoCompact: false
        Layout.minimumWidth: expandedImplicitWidth
        visible: root.formMode !== 0 && root.allowEditorActions
        enabled: root.dirty && root.valid && !root.saving
        tooltip: "Save changes"
        onClicked: root.saveRequested()
    }
}
