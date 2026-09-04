import QtQuick
import UI

Item {
    property alias subnetResult: subnetField.text
    property alias wildcardResult: wildcardField.text

    StandardNetworkField {
        id: subnetField
        inputKind: "subnet"
        Component.onCompleted: {
            text = "/24"
            normalizeNetworkText()
        }
    }

    StandardNetworkField {
        id: wildcardField
        inputKind: "wildcard"
        Component.onCompleted: {
            text = "-/24"
            normalizeNetworkText()
        }
    }
}
