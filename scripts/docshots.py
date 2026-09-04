#!/usr/bin/env python3
"""Render documentation screenshots from the real CAMS QML module."""

from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from docshots.environment import configure_qt_environment

configure_qt_environment()

from docshots.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
