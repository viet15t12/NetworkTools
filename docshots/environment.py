"""Process environment required before importing Qt."""

from __future__ import annotations

import os


def configure_qt_environment() -> None:
    """Select deterministic headless Qt rendering before QApplication exists."""

    defaults = {
        "QT_QPA_PLATFORM": "offscreen",
        "QT_SCALE_FACTOR": "1",
        "QT_AUTO_SCREEN_SCALE_FACTOR": "0",
        "QT_SCREEN_SCALE_FACTORS": "1",
        "QT_FONT_DPI": "96",
        "QT_QUICK_BACKEND": "software",
        "QSG_RHI_BACKEND": "software",
        "QML_DISABLE_DISK_CACHE": "1",
    }
    for name, value in defaults.items():
        os.environ[name] = value


__all__ = ["configure_qt_environment"]
