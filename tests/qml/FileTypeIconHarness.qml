import QtQuick
import UI

QtObject {
    readonly property url dockerIcon: AppAssets.fileTypeIcon("Dockerfile")
    readonly property url environmentIcon: AppAssets.fileTypeIcon(".env.production")
    readonly property url licenseIcon: AppAssets.fileTypeIcon("LICENSE.md")
    readonly property url pythonIcon: AppAssets.fileTypeIcon("requirements.txt")
    readonly property url packetCaptureIcon: AppAssets.fileTypeIcon("capture.pcapng")
    readonly property url reactTypeScriptIcon: AppAssets.fileTypeIcon("DevicePanel.tsx")
    readonly property url spreadsheetIcon: AppAssets.fileTypeIcon("inventory.xlsx")
    readonly property url textIcon: AppAssets.fileTypeIcon("notes.txt")
    readonly property url unknownIcon: AppAssets.fileTypeIcon("README_WITHOUT_EXTENSION")
}
