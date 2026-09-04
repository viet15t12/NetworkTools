"""Application/resource paths exposed to Python and QML."""

import base64

from infrastructure.database.paths import APP_DIR, DATA_DIR
from PyQt6.QtCore import QObject, QUrl, pyqtSlot

QML_MODULE_DIR = APP_DIR / "UI"
TEMPLATES_DIR = APP_DIR / "templates"
FEATURES_DIR = APP_DIR / "features"


class AppPaths(QObject):
    """Expose safe local UI resource URLs to QML."""

    @pyqtSlot(str, result=QUrl)
    def resource(self, relative_path: str) -> QUrl:
        """Resolve one path below the public QML module directory."""
        return QUrl.fromLocalFile(str((QML_MODULE_DIR / relative_path).resolve()))

    @pyqtSlot(result=QUrl)
    def hiddenBrandLogo(self) -> QUrl:
        """Expose the extensionless Easter Egg asset without revealing a file URL."""
        hidden_asset = QML_MODULE_DIR / "resources" / "brand" / ".nqv"
        try:
            encoded = base64.b64encode(hidden_asset.read_bytes()).decode("ascii")
        except OSError:
            return self.resource("resources/brand/logo.svg")
        return QUrl(f"data:image/svg+xml;base64,{encoded}")

    @pyqtSlot(result=QUrl)
    def hiddenPtitLogo(self) -> QUrl:
        """Expose the extensionless PTIT Easter Egg asset as SVG data."""
        hidden_asset = QML_MODULE_DIR / "resources" / "brand" / ".ptit"
        try:
            encoded = base64.b64encode(hidden_asset.read_bytes()).decode("ascii")
        except OSError:
            return self.resource("resources/brand/logo.svg")
        return QUrl(f"data:image/svg+xml;base64,{encoded}")

__all__ = ["APP_DIR", "AppPaths", "DATA_DIR", "FEATURES_DIR", "QML_MODULE_DIR", "TEMPLATES_DIR"]
