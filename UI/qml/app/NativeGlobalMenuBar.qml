pragma ComponentBehavior: Bound

import QtQml
import QtQml.Models
import Qt.labs.platform 1.1 as Platform
import UI

Platform.MenuBar {
    id: root

    required property var registry
    property var menuDefinitions: MenuDefinition.menus

    signal commandInvoked(string commandId)

    function platformRole(nativeRole) {
        switch (String(nativeRole || "none")) {
        case "about":
            return Platform.MenuItem.AboutRole
        case "preferences":
            return Platform.MenuItem.PreferencesRole
        case "quit":
            return Platform.MenuItem.QuitRole
        default:
            return Platform.MenuItem.NoRole
        }
    }

    objectName: "nativeGlobalMenuBar"

    Component.onCompleted: MenuDefinition.validate(root.registry)

    Instantiator {
        id: menuInstantiator
        model: root.menuDefinitions

        delegate: Platform.Menu {
            id: nativeMenu
            required property int index
            required property var modelData

            title: modelData.title
            visible: MenuDefinition.hasVisibleCommand(
                         root.registry, modelData.items
                     )

            Instantiator {
                id: itemInstantiator
                model: nativeMenu.modelData.items

                delegate: Platform.MenuItem {
                    id: nativeItem
                    required property int index
                    required property var modelData

                    readonly property bool isSeparator:
                        modelData.type === "separator"
                    readonly property var command: isSeparator
                                                   ? null
                                                   : MenuDefinition.commandFor(
                                                         root.registry,
                                                         modelData.commandId
                                                     )

                    objectName: isSeparator
                                ? "nativeMenuSeparator" + index
                                : "nativeMenuItem" + String(
                                      modelData.commandId
                                  ).split(".").map(function(part) {
                                      return part.charAt(0).toUpperCase()
                                              + part.slice(1)
                                  }).join("")
                    separator: isSeparator
                    text: command !== null ? command.text : ""
                    enabled: isSeparator || (command !== null && command.enabled)
                    visible: MenuDefinition.entryVisible(
                                 root.registry,
                                 nativeMenu.modelData.items,
                                 index
                             )
                    checkable: command !== null && command.checkable
                    checked: command !== null && command.checked
                    shortcut: command !== null && command.visible
                              ? command.shortcut : ""
                    role: command !== null
                          ? root.platformRole(command.nativeRole)
                          : Platform.MenuItem.NoRole
                    icon.name: command !== null ? command.iconName : ""
                    icon.source: command !== null ? command.iconSource : ""

                    onTriggered: {
                        if (nativeItem.command === null || root.registry === null)
                            return
                        const commandId = String(nativeItem.command.commandId)
                        if (root.registry.trigger(commandId))
                            root.commandInvoked(commandId)
                    }
                }

                onObjectAdded: function(index, object) {
                    nativeMenu.insertItem(index, object)
                }
                onObjectRemoved: function(index, object) {
                    nativeMenu.removeItem(object)
                }
            }
        }

        onObjectAdded: function(index, object) {
            root.insertMenu(index, object)
        }
        onObjectRemoved: function(index, object) {
            root.removeMenu(object)
        }
    }
}
