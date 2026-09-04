pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import UI

Rectangle {
    id: root
    objectName: "sftpConnectionsPanel"
    color: Theme.panelSideBarBackground
    required property var backend
    readonly property var connections: backend ? backend.savedConnections : []
    readonly property var filteredConnections: {
        const query = searchField.text.trim().toLowerCase()
        if (query === "")
            return connections
        return connections.filter(function(profile) {
            return String(profile.name || "").toLowerCase().indexOf(query) >= 0
                || String(profile.host || "").toLowerCase().indexOf(query) >= 0
                || String(profile.username || "").toLowerCase().indexOf(query) >= 0
        })
    }

    function selectProfile(profile) {
        if (backend && profile)
            backend.selectSavedConnection(String(profile.id || ""))
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            color: Theme.panelSideBarBackground
            Text {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                text: "SFTP CONNECTIONS"
                color: Theme.panelSideBarTextSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.capitalization: Font.AllUppercase
                font.weight: Font.Medium
            }
            StandardBadge {
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing8
                anchors.verticalCenter: parent.verticalCenter
                text: String(root.connections.length)
                badgeColor: Theme.accentColor
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.borderWidth
                color: Theme.panelSideBarBorderColor
            }
        }

        SideBarSearch {
            id: searchField
            Layout.fillWidth: true
            Layout.margins: Theme.spacing8
            placeholderText: "Search saved connections..."
        }

        ListView {
            id: profileList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.filteredConnections
            spacing: Theme.spacing4
            leftMargin: Theme.spacing8
            rightMargin: Theme.spacing8
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: profileRow
                required property int index
                required property var modelData
                readonly property bool selected: root.backend
                    && String(root.backend.selectedConnection.id || "") === String(modelData.id || "")
                width: profileList.width - profileList.leftMargin - profileList.rightMargin
                height: 66
                radius: Theme.radiusSmall
                color: selected ? Theme.panelSideBarItemSelected
                                : (profileHover.hovered ? Theme.panelSideBarItemHover : "transparent")
                border.width: Theme.borderWidth
                border.color: selected ? Theme.panelSideBarAccentColor : Theme.panelSideBarBorderColor

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing8
                    spacing: Theme.spacing2
                    Text {
                        Layout.fillWidth: true
                        text: String(profileRow.modelData.name || profileRow.modelData.host || "SFTP")
                        color: Theme.panelSideBarTextPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeNormal
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: String(profileRow.modelData.username || "") + "@"
                              + String(profileRow.modelData.host || "") + ":"
                              + String(profileRow.modelData.port || 22)
                        color: Theme.panelSideBarTextSecondary
                        font.family: Theme.monoFontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        elide: Text.ElideRight
                    }
                }

                HoverHandler { id: profileHover }
                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    onTapped: root.selectProfile(profileRow.modelData)
                    onDoubleTapped: root.selectProfile(profileRow.modelData)
                }
                TapHandler {
                    acceptedButtons: Qt.RightButton
                    onTapped: function(eventPoint) {
                        const point = profileRow.mapToItem(
                            contextMenu.parent,
                            eventPoint.position.x,
                            eventPoint.position.y
                        )
                        contextMenu.openAt(point.x, point.y, profileRow.modelData)
                    }
                }
            }

            EmptyState {
                anchors.fill: parent
                visible: profileList.count === 0
                title: searchField.text.trim() === ""
                       ? "No saved connections"
                       : "No matching connections"
                description: searchField.text.trim() === ""
                    ? "A server is added here after the first successful SFTP connection."
                    : "Try a different host, name, or username."
            }
        }
    }

    SftpConnectionContextMenu {
        id: contextMenu
        parent: Window.window ? Window.window.contentItem : root
        onUseRequested: profile => root.selectProfile(profile)
        onEditRequested: profile => connectionDialog.openFor(profile)
        onDeleteRequested: function(profile) {
            deleteDialog.profileId = String(profile.id || "")
            deleteDialog.messageText = "Remove \"" + String(profile.name || profile.host)
                                     + "\" from saved SFTP connections?"
            deleteDialog.open()
        }
    }

    SftpConnectionDialog {
        id: connectionDialog
        backend: root.backend
    }

    SftpMessageDialog {
        id: deleteDialog
        property string profileId: ""
        titleText: "Delete saved connection"
        confirmation: true
        acceptText: "Delete"
        onAccepted: {
            if (root.backend)
                root.backend.deleteSavedConnection(profileId)
            profileId = ""
        }
    }
}
