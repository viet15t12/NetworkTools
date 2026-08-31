pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Dialogs

FileDialog {
    id: root

    signal projectSelected(url projectUrl)

    title: "Open CAMS Project"
    fileMode: FileDialog.OpenFile
    nameFilters: ["CAMS Projects (*.ntp)", "All Files (*)"]
    onAccepted: root.projectSelected(selectedFile)
}
