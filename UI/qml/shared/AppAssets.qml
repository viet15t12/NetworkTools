pragma ComponentBehavior: Bound
pragma Singleton

import QtQuick

QtObject {
    // This singleton is the only QML file allowed to contain SVG paths.
    // Consumers use the semantic properties below so resource moves stay local.
    function resource(relativePath) {
        if (typeof AppPaths === "undefined" || AppPaths === null)
            return ""
        try {
            return AppPaths.resource(relativePath)
        } catch (error) {
            return ""
        }
    }

    function hiddenBrandLogo() {
        if (typeof AppPaths === "undefined" || AppPaths === null)
            return brandDefaultLogo
        try {
            return AppPaths.hiddenBrandLogo()
        } catch (error) {
            return brandDefaultLogo
        }
    }

    function hiddenPtitLogo() {
        if (typeof AppPaths === "undefined" || AppPaths === null)
            return brandDefaultLogo
        try {
            return AppPaths.hiddenPtitLogo()
        } catch (error) {
            return brandDefaultLogo
        }
    }

    readonly property url actionAdd: resource("resources/actions/add.svg")
    readonly property url actionBackup: resource("resources/actions/backup.svg")
    readonly property url actionClear: resource("resources/actions/clear.svg")
    readonly property url actionClose: resource("resources/actions/close.svg")
    readonly property url actionConnect: resource("resources/actions/connect.svg")
    readonly property url actionCopy: resource("resources/actions/copy.svg")
    readonly property url actionDatabaseReload: resource("resources/actions/database-reload.svg")
    readonly property url actionDelete: resource("resources/actions/delete.svg")
    readonly property url actionDisconnect: resource("resources/actions/disconnect.svg")
    readonly property url actionDownload: resource("resources/actions/download.svg")
    readonly property url actionEdit: resource("resources/actions/edit.svg")
    readonly property url actionFilter: resource("resources/actions/filter.svg")
    readonly property url actionListAdd: resource("resources/actions/list-add.svg")
    readonly property url actionMonitorStart: resource("resources/actions/monitor-start.svg")
    readonly property url actionMonitorStop: resource("resources/actions/monitor-stop.svg")
    readonly property url actionPush: resource("resources/actions/push.svg")
    readonly property url actionRefresh: resource("resources/actions/refresh.svg")
    readonly property url actionSave: resource("resources/actions/save.svg")
    readonly property url actionSearch: resource("resources/actions/search.svg")
    readonly property url actionUpload: resource("resources/actions/upload.svg")
    readonly property url actionVisibilityOff: resource("resources/actions/visibility-off.svg")
    readonly property url actionVisibilityOn: resource("resources/actions/visibility-on.svg")

    readonly property bool nqvMode: typeof nqvEasterEggEnabled !== "undefined"
                                    && nqvEasterEggEnabled === true
    readonly property bool ptitMode: typeof ptitEasterEggEnabled !== "undefined"
                                     && ptitEasterEggEnabled === true
    readonly property url brandDefaultLogo: resource("resources/brand/logo.svg")
    readonly property url brandProjectFileIcon: resource("resources/brand/project-file-icon.svg")
    readonly property url brandLogo: ptitMode ? hiddenPtitLogo()
                                             : (nqvMode ? hiddenBrandLogo()
                                                        : brandDefaultLogo)

    readonly property url brandLogoReadme: resource("resources/brand/logo_readme.svg")
    readonly property url brandName: resource("resources/brand/name.svg")
    readonly property url brandStatsDark: resource("resources/brand/stats-dark.svg")

    readonly property url windowControlClose: resource("resources/window-control-icons-svg/close.svg")
    readonly property url windowControlMinimize: resource("resources/window-control-icons-svg/minimize.svg")
    readonly property url windowControlRestore: resource("resources/window-control-icons-svg/restore.svg")

    readonly property url deviceNetworkDisconnected: resource("resources/devices/network-disconnected.svg")
    readonly property url deviceNetworkEthernet: resource("resources/devices/network-ethernet.svg")
    readonly property url deviceNetworkVirtualLab: resource("resources/devices/virtual-lab.svg")
    readonly property url deviceNetworkVpn: resource("resources/devices/vpn.svg")
    readonly property url deviceNetworkWifi: resource("resources/devices/network-wifi.svg")
    readonly property url deviceRouter: resource("resources/devices/router.svg")
    readonly property url deviceStatusDot: resource("resources/devices/status-dot.svg")
    readonly property url deviceSwitch: resource("resources/devices/switch.svg")

    readonly property url fileGeneric: resource("resources/files/file.svg")
    readonly property url fileFolder: resource("resources/files/folder.svg")
    readonly property url fileTransferDownload: resource("resources/files/transfer-download.svg")
    readonly property url fileTransferUpload: resource("resources/files/transfer-upload.svg")
    readonly property url fileTypeArchive: resource("resources/files/types/zip.svg")
    readonly property url fileTypeAudio: resource("resources/files/types/audio.svg")
    readonly property url fileTypeBinary: resource("resources/files/types/hex.svg")
    readonly property url fileTypeC: resource("resources/files/types/c.svg")
    readonly property url fileTypeCertificate: resource("resources/files/types/certificate.svg")
    readonly property url fileTypeCpp: resource("resources/files/types/cpp.svg")
    readonly property url fileTypeCppHeader: resource("resources/files/types/hpp.svg")
    readonly property url fileTypeCHeader: resource("resources/files/types/h.svg")
    readonly property url fileTypeCss: resource("resources/files/types/css.svg")
    readonly property url fileTypeDatabase: resource("resources/files/types/database.svg")
    readonly property url fileTypeDocker: resource("resources/files/types/docker.svg")
    readonly property url fileTypeEmail: resource("resources/files/types/email.svg")
    readonly property url fileTypeEnvironment: resource("resources/files/types/tune.svg")
    readonly property url fileTypeExecutable: resource("resources/files/types/exe.svg")
    readonly property url fileTypeFont: resource("resources/files/types/font.svg")
    readonly property url fileTypeGit: resource("resources/files/types/git.svg")
    readonly property url fileTypeGo: resource("resources/files/types/go.svg")
    readonly property url fileTypeHtml: resource("resources/files/types/html.svg")
    readonly property url fileTypeImage: resource("resources/files/types/image.svg")
    readonly property url fileTypeJava: resource("resources/files/types/java.svg")
    readonly property url fileTypeJavaScript: resource("resources/files/types/javascript.svg")
    readonly property url fileTypeJson: resource("resources/files/types/json.svg")
    readonly property url fileTypeKey: resource("resources/files/types/key.svg")
    readonly property url fileTypeKotlin: resource("resources/files/types/kotlin.svg")
    readonly property url fileTypeLicense: resource("resources/files/types/license.svg")
    readonly property url fileTypeLog: resource("resources/files/types/log.svg")
    readonly property url fileTypeLua: resource("resources/files/types/lua.svg")
    readonly property url fileTypeMarkdown: resource("resources/files/types/markdown.svg")
    readonly property url fileTypePdf: resource("resources/files/types/pdf.svg")
    readonly property url fileTypePhp: resource("resources/files/types/php.svg")
    readonly property url fileTypePowerPoint: resource("resources/files/types/powerpoint.svg")
    readonly property url fileTypePowerShell: resource("resources/files/types/powershell.svg")
    readonly property url fileTypeProtobuf: resource("resources/files/types/proto.svg")
    readonly property url fileTypePython: resource("resources/files/types/python.svg")
    readonly property url fileTypeReact: resource("resources/files/types/react.svg")
    readonly property url fileTypeReactTypeScript: resource("resources/files/types/react_ts.svg")
    readonly property url fileTypeRuby: resource("resources/files/types/ruby.svg")
    readonly property url fileTypeRust: resource("resources/files/types/rust.svg")
    readonly property url fileTypeSettings: resource("resources/files/types/settings.svg")
    readonly property url fileTypeShell: resource("resources/files/types/console.svg")
    readonly property url fileTypeSpreadsheet: resource("resources/files/types/table.svg")
    readonly property url fileTypeSvelte: resource("resources/files/types/svelte.svg")
    readonly property url fileTypeSvg: resource("resources/files/types/svg.svg")
    readonly property url fileTypeSwift: resource("resources/files/types/swift.svg")
    readonly property url fileTypeText: resource("resources/files/types/document.svg")
    readonly property url fileTypeToml: resource("resources/files/types/toml.svg")
    readonly property url fileTypeTypeScript: resource("resources/files/types/typescript.svg")
    readonly property url fileTypeVideo: resource("resources/files/types/video.svg")
    readonly property url fileTypeVirtualMachine: resource("resources/files/types/virtual.svg")
    readonly property url fileTypeVue: resource("resources/files/types/vue.svg")
    readonly property url fileTypeWord: resource("resources/files/types/word.svg")
    readonly property url fileTypeXml: resource("resources/files/types/xml.svg")
    readonly property url fileTypeYaml: resource("resources/files/types/yaml.svg")

    readonly property url navigationBack: resource("resources/navigation/arrow-left.svg")
    readonly property url navigationChevronLeft: resource("resources/navigation/chevron-left.svg")
    readonly property url navigationChevronDown: resource("resources/navigation/chevron-down.svg")
    readonly property url navigationChevronRight: resource("resources/navigation/chevron-right.svg")
    readonly property url navigationChevronUp: resource("resources/navigation/chevron-up.svg")
    readonly property url navigationListCollapse: resource("resources/navigation/list-collapse.svg")
    readonly property url navigationListExpand: resource("resources/navigation/list-expand.svg")
    readonly property url navigationDown: resource("resources/navigation/arrow-down.svg")
    readonly property url navigationForward: resource("resources/navigation/arrow-right.svg")
    readonly property url navigationUp: resource("resources/navigation/arrow-up.svg")
    readonly property url navigationConsoleSerial: resource("resources/navigation/console-serial.svg")
    readonly property url navigationDashboard: resource("resources/navigation/dashboard.svg")
    readonly property url navigationDatabase: resource("resources/navigation/database.svg")
    readonly property url navigationDatabaseSearch: resource("resources/navigation/database-search.svg")
    readonly property url navigationInterface: resource("resources/navigation/interface.svg")
    readonly property url navigationLogs: resource("resources/navigation/logs.svg")
    readonly property url navigationSettings: resource("resources/navigation/settings.svg")
    readonly property url navigationSftp: resource("resources/navigation/sftp.svg")
    readonly property url navigationSyslog: resource("resources/navigation/syslog.svg")
    readonly property url navigationTerminal: resource("resources/navigation/terminal.svg")
    readonly property url navigationTopology: resource("resources/navigation/topology.svg")

    readonly property url statusDoNotDisturb: resource("resources/status/do-not-disturb.svg")
    readonly property url statusError: resource("resources/status/error.svg")
    readonly property url statusInfo: resource("resources/status/info.svg")
    readonly property url statusNotification: resource("resources/status/notification.svg")
    readonly property url statusNotificationUnread: resource("resources/status/notification-unread.svg")
    readonly property url statusPython: resource("resources/status/python.svg")
    readonly property url statusSuccess: resource("resources/status/success.svg")
    readonly property url statusWarning: resource("resources/status/warning.svg")

    // The information destination and informational status share one SVG.
    readonly property url navigationInformation: statusInfo

    function extensionIn(extension, extensions) {
        return extensions.indexOf(extension) >= 0
    }

    function fileTypeIcon(fileName) {
        const name = String(fileName || "").toLowerCase()
        const dot = name.lastIndexOf(".")
        const extension = dot >= 0 ? name.slice(dot + 1) : ""

        // Name-based associations have priority over the final extension.
        if (name === "dockerfile" || name.indexOf("dockerfile.") === 0
                || name === "containerfile" || name.indexOf("containerfile.") === 0
                || name === ".dockerignore" || name === "docker-compose.yml"
                || name === "docker-compose.yaml" || name === "compose.yml"
                || name === "compose.yaml")
            return fileTypeDocker
        if (name === ".gitignore" || name === ".gitattributes"
                || name === ".gitmodules" || name === ".mailmap"
                || name === "commit_editmsg" || name === "merge_msg"
                || name === "git-rebase-todo")
            return fileTypeGit
        if (name === ".env" || name.indexOf(".env.") === 0)
            return fileTypeEnvironment
        if (name === "license" || name === "licence" || name === "copying"
                || name.indexOf("license.") === 0
                || name.indexOf("licence.") === 0
                || name.indexOf("copying.") === 0)
            return fileTypeLicense
        if (name === "requirements.txt" || name === "constraints.txt"
                || name === "pyproject.toml" || name === "pipfile"
                || name === "pipfile.lock" || name === "setup.py"
                || name === "tox.ini")
            return fileTypePython
        if (extensionIn(name, [".bashrc", ".bash_profile", ".zshrc", ".profile"]))
            return fileTypeShell
        if (extensionIn(name, [".editorconfig", ".npmrc", ".pypirc",
                               ".prettierrc", ".babelrc"]))
            return fileTypeSettings

        if (extension === "svg")
            return fileTypeSvg
        if (extension === "c" || extension === "i" || extension === "mi")
            return fileTypeC
        if (extension === "h")
            return fileTypeCHeader
        if (extensionIn(extension, ["cc", "cpp", "cxx", "c++"]))
            return fileTypeCpp
        if (extensionIn(extension, ["hh", "hpp", "hxx", "h++", "hp", "tcc", "inl"]))
            return fileTypeCppHeader
        if (extensionIn(extension, ["htm", "html", "xhtml", "shtml", "asp", "aspx"]))
            return fileTypeHtml
        if (extensionIn(extension, ["css", "scss", "sass", "less", "styl", "stylus"]))
            return fileTypeCss
        if (extension === "jsx")
            return fileTypeReact
        if (extension === "tsx")
            return fileTypeReactTypeScript
        if (extensionIn(extension, ["js", "mjs", "cjs", "es6", "pac"]))
            return fileTypeJavaScript
        if (extensionIn(extension, ["ts", "mts", "cts"]))
            return fileTypeTypeScript
        if (extensionIn(extension, ["json", "jsonc", "json5", "jsonl", "ndjson",
                                    "geojson", "har", "jsonld", "webmanifest"]))
            return fileTypeJson
        if (extensionIn(extension, ["yaml", "yml"]))
            return fileTypeYaml
        if (extensionIn(extension, ["xml", "xsd", "xsl", "xslt", "plist", "wsdl"]))
            return fileTypeXml
        if (extension === "toml")
            return fileTypeToml
        if (extensionIn(extension, ["md", "markdown", "mdown", "mkd", "mkdn", "rst"]))
            return fileTypeMarkdown
        if (extensionIn(extension, ["txt", "text", "nfo"]))
            return fileTypeText
        if (extension === "log")
            return fileTypeLog
        if (extension === "pdf")
            return fileTypePdf
        if (extensionIn(extension, ["doc", "docx", "docm", "rtf", "odt"]))
            return fileTypeWord
        if (extensionIn(extension, ["ppt", "pptx", "pptm", "pot", "potx",
                                    "pps", "ppsx", "odp"]))
            return fileTypePowerPoint
        if (extensionIn(extension, ["xls", "xlsx", "xlsm", "xlsb", "xlt", "xltx",
                                    "csv", "tsv", "psv", "ods"]))
            return fileTypeSpreadsheet
        if (extensionIn(extension, ["png", "jpg", "jpeg", "gif", "bmp", "webp",
                                    "ico", "tif", "tiff", "avif", "heic", "raw"]))
            return fileTypeImage
        if (extensionIn(extension, ["mp3", "wav", "flac", "aac", "ogg", "m4a",
                                    "wma", "opus", "mid", "midi"]))
            return fileTypeAudio
        if (extensionIn(extension, ["mp4", "mkv", "avi", "mov", "wmv", "webm",
                                    "m4v", "flv", "mpeg", "mpg", "3gp"]))
            return fileTypeVideo
        if (extensionIn(extension, ["zip", "7z", "rar", "tar", "gz", "bz2", "xz",
                                    "tgz", "tbz2", "txz", "zst", "iso", "dmg"]))
            return fileTypeArchive
        if (extensionIn(extension, ["sql", "sqlite", "sqlite3", "db", "db3", "mdb",
                                    "accdb", "dump"]))
            return fileTypeDatabase
        if (extensionIn(extension, ["exe", "msi", "com", "appimage"]))
            return fileTypeExecutable
        if (extensionIn(extension, ["bin", "dat", "hex", "cap", "pcap", "pcapng"]))
            return fileTypeBinary
        if (extensionIn(extension, ["cer", "cert", "crt", "csr", "p12", "pfx"]))
            return fileTypeCertificate
        if (extensionIn(extension, ["key", "pem", "pub", "ppk", "asc", "gpg"]))
            return fileTypeKey
        if (extensionIn(extension, ["ttf", "otf", "woff", "woff2", "eot"]))
            return fileTypeFont
        if (extensionIn(extension, ["eml", "msg", "mbox", "emlx"]))
            return fileTypeEmail
        if (extensionIn(extension, ["vdi", "vbox", "vhd", "vhdx", "vmdk", "ova", "ovf"]))
            return fileTypeVirtualMachine
        if (extensionIn(extension, ["sh", "bash", "zsh", "ksh", "csh", "fish",
                                    "bat", "cmd", "awk", "nu", "xsh"]))
            return fileTypeShell
        if (extensionIn(extension, ["ps1", "psm1", "psd1", "ps1xml", "psc1", "pssc"]))
            return fileTypePowerShell
        if (extensionIn(extension, ["ini", "cfg", "conf", "config", "properties", "cnf"]))
            return fileTypeSettings
        if (extension === "proto")
            return fileTypeProtobuf
        if (extensionIn(extension, ["py", "pyi", "pyw", "pyx", "rpy", "gyp", "gypi"]))
            return fileTypePython
        if (extension === "go")
            return fileTypeGo
        if (extensionIn(extension, ["java", "jav", "jsp"]))
            return fileTypeJava
        if (extensionIn(extension, ["kt", "kts"]))
            return fileTypeKotlin
        if (extension === "swift")
            return fileTypeSwift
        if (extensionIn(extension, ["rs", "ron"]))
            return fileTypeRust
        if (extensionIn(extension, ["php", "php3", "php4", "php5", "phtml"]))
            return fileTypePhp
        if (extensionIn(extension, ["rb", "ruby", "rake", "gemspec"]))
            return fileTypeRuby
        if (extension === "lua")
            return fileTypeLua
        if (extension === "vue")
            return fileTypeVue
        if (extension === "svelte")
            return fileTypeSvelte
        if (extensionIn(extension, ["patch", "diff"]))
            return fileTypeGit
        return ""
    }
}
