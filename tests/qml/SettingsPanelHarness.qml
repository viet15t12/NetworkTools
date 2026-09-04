import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    width: 170
    height: 520
    visible: true

    SettingsPanel {
        objectName: "settingsPanelUnderTest"
        anchors.fill: parent
    }
}
