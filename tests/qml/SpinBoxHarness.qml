import QtQuick
import QtQuick.Controls.Basic
import UI

ApplicationWindow {
    id: root
    width: 360
    height: 160
    visible: true

    StandardSpinBox {
        id: testSpinBox
        x: 48
        y: 32
        width: 240
        labelText: "Test value"
        from: 0
        to: 100
        value: 50
        stepSize: 10
    }
}
