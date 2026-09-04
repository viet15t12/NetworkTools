pragma ComponentBehavior: Bound
pragma Singleton

import QtQml

QtObject {
    function commandFor(registry, commandId) {
        return registry !== null && registry !== undefined
                ? registry.command(String(commandId)) : null
    }

    function commandVisible(registry, commandId) {
        const action = commandFor(registry, commandId)
        return action !== null && action.visible
    }

    function hasVisibleCommand(registry, entries) {
        for (let index = 0; index < entries.length; index++) {
            if (entries[index].type === "command"
                    && commandVisible(registry, entries[index].commandId)) {
                return true
            }
        }
        return false
    }

    function entryVisible(registry, entries, entryIndex) {
        if (entryIndex < 0 || entryIndex >= entries.length)
            return false
        const entry = entries[entryIndex]
        if (entry.type === "command")
            return commandVisible(registry, entry.commandId)
        if (entry.type !== "separator")
            return false

        let commandBefore = false
        for (let before = entryIndex - 1; before >= 0; before--) {
            if (entries[before].type === "separator")
                break
            if (commandVisible(registry, entries[before].commandId)) {
                commandBefore = true
                break
            }
        }
        if (!commandBefore)
            return false

        for (let after = entryIndex + 1; after < entries.length; after++) {
            if (entries[after].type === "separator")
                break
            if (commandVisible(registry, entries[after].commandId))
                return true
        }
        return false
    }

    function validate(registry) {
        if (registry === null || registry === undefined)
            return false
        let valid = true
        for (let menuIndex = 0; menuIndex < menus.length; menuIndex++) {
            const entries = menus[menuIndex].items
            for (let entryIndex = 0; entryIndex < entries.length; entryIndex++) {
                const entry = entries[entryIndex]
                if (entry.type === "command"
                        && commandFor(registry, entry.commandId) === null) {
                    console.error(
                        "MenuDefinition references missing command: "
                        + entry.commandId
                    )
                    valid = false
                }
            }
        }
        return valid
    }

    readonly property var menus: [
        {
            "menuId": "file",
            "title": qsTr("File"),
            "items": [
                { "type": "command", "commandId": "project.new" },
                { "type": "command", "commandId": "project.open" },
                { "type": "separator" },
                { "type": "command", "commandId": "workspace.save" },
                { "type": "command", "commandId": "workspace.snapshot.create" },
                { "type": "command", "commandId": "workspace.snapshot.history" },
                { "type": "separator" },
                { "type": "command", "commandId": "workspace.close" },
                { "type": "separator" },
                { "type": "command", "commandId": "app.quit" }
            ]
        },
        {
            "menuId": "view",
            "title": qsTr("View"),
            "items": [
                { "type": "command", "commandId": "view.reload" },
                { "type": "command", "commandId": "view.sidebar.toggle" },
                { "type": "separator" },
                { "type": "command", "commandId": "view.dashboard" },
                { "type": "command", "commandId": "view.sftp" },
                { "type": "command", "commandId": "view.systemLogs" },
                { "type": "command", "commandId": "view.database" },
                { "type": "command", "commandId": "settings.open" }
            ]
        },
        {
            "menuId": "help",
            "title": qsTr("Help"),
            "items": [
                { "type": "command", "commandId": "help.shortcuts" },
                { "type": "separator" },
                { "type": "command", "commandId": "app.about" }
            ]
        }
    ]
}
