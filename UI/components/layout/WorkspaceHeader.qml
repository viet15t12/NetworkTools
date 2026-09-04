pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

Item {
    id: root

    property string title: ""
    property string subtitle: ""
    default property alias actions: actionLayout.data

    implicitHeight: Math.max(titleLayout.implicitHeight, actionLayout.Layout.preferredHeight)

    RowLayout {
        anchors.fill: parent
        spacing: Theme.spacing12

        ColumnLayout {
            id: titleLayout
            Layout.fillWidth: true
            spacing: Theme.spacing2

            Text {
                Layout.fillWidth: true
                text: root.title
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeLarge
                font.bold: true
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                visible: root.subtitle !== ""
                text: root.subtitle
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                elide: Text.ElideRight
            }
        }

        Flow {
            id: actionLayout
            objectName: "workspaceHeaderActions"
            spacing: Theme.spacing8
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.preferredWidth: Math.min(
                actionLayout.naturalWidth,
                Math.max(220, root.width * 0.62)
            )
            Layout.minimumWidth: Math.min(actionLayout.naturalWidth, 220)
            Layout.maximumWidth: Layout.preferredWidth

            readonly property real naturalWidth: {
                let total = 0
                let visibleCount = 0
                for (let i = 0; i < children.length; i++) {
                    const child = children[i]
                    if (!child.visible) continue
                    total += Math.max(0, Number(child.implicitWidth || child.width || 0))
                    visibleCount += 1
                }
                return total + Math.max(0, visibleCount - 1) * spacing
            }

            Layout.preferredHeight: Math.max(34, childrenRect.height)
        }
    }
}
