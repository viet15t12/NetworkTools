pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import UI

Window {
    id: root

    objectName: "aboutWindow"
    title: qsTr("About CAMS")
    width: 500
    height: 340
    minimumWidth: 500
    maximumWidth: 500
    minimumHeight: 340
    maximumHeight: 340
    color: "transparent"
    modality: Qt.ApplicationModal
    flags: Qt.Dialog | Qt.FramelessWindowHint

    property bool ownsWindowLock: false
    readonly property string repositoryUrl: "https://github.com/viet15t12/NetworkTools.git"

    function open() {
        if (!root.visible) {
            root.ownsWindowLock = !UiState.windowLock
            UiState.windowLock = true
        }

        const owner = root.transientParent
        if (owner) {
            root.x = owner.x + Math.round((owner.width - root.width) / 2)
            root.y = owner.y + Math.round((owner.height - root.height) / 2)
        } else {
            root.x = Screen.virtualX
                     + Math.round((Screen.desktopAvailableWidth - root.width) / 2)
            root.y = Screen.virtualY
                     + Math.round((Screen.desktopAvailableHeight - root.height) / 2)
        }
        root.show()
        root.requestActivate()
    }

    function releaseWindowLock() {
        if (root.ownsWindowLock)
            UiState.windowLock = false
        root.ownsWindowLock = false
    }

    onVisibleChanged: if (!visible) root.releaseWindowLock()
    onClosing: root.releaseWindowLock()

    Shortcut {
        sequence: "Escape"
        enabled: root.visible
        onActivated: root.close()
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 10
        color: Theme.contentPanelSurface
        border.color: root.active ? Theme.contentPanelBorder : Theme.textDisabled
        border.width: Theme.borderWidth
        radius: Theme.radiusLarge

        DragHandler {
            onActiveChanged: if (active) root.startSystemMove()
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.spacing24
            spacing: Theme.spacing16

            DialogTitleBar {
                Layout.fillWidth: true
                title: qsTr("About CAMS")
                subtitle: qsTr("Centralized network management and automation workspace")
                closeTooltip: qsTr("Close About CAMS")
                onCloseRequested: root.close()
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Theme.spacing24

                ThemedIcon {
                    Layout.alignment: Qt.AlignTop
                    iconSource: AppAssets.brandLogo
                    iconSize: 72
                    preserveOriginalColors: true
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    spacing: Theme.spacing8

                    Text {
                        text: "CAMS v1.0"
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeLarge
                        font.weight: Font.DemiBold
                    }

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Developed by the 3TM Research Team\n"
                                   + "PTIT – Ho Chi Minh City Campus")
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeNormal
                        lineHeight: 1.25
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "<a href=\"" + root.repositoryUrl + "\">"
                              + root.repositoryUrl + "</a>"
                        textFormat: Text.RichText
                        linkColor: Theme.accentColor
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        elide: Text.ElideRight
                        onLinkActivated: link => Qt.openUrlExternally(link)

                        HoverHandler {
                            cursorShape: Qt.PointingHandCursor
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true

                Item { Layout.fillWidth: true }

                StandardButton {
                    text: qsTr("Close")
                    type: "Primary"
                    onClicked: root.close()
                }
            }
        }
    }
}
