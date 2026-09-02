"""Canonical, working-directory-independent database paths."""

from __future__ import annotations

import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("CAMS_DATA_DIR", APP_DIR / "data")).expanduser().resolve()
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
DEVICE_NETWORK_SCHEMA_DIR = SCHEMA_DIR / "device_network"
INFO_COLLECTED_SCHEMA_DIR = SCHEMA_DIR / "info_collected"
# Compatibility aliases for older imports. They now identify the canonical
# schema directories; database creation no longer writes aggregate SQL files.
DEVICE_NETWORK_SQL = DEVICE_NETWORK_SCHEMA_DIR
INFO_COLLECTED_SQL = INFO_COLLECTED_SCHEMA_DIR
DEVICE_NETWORK_DB = DATA_DIR / "device_network.db"
INFO_COLLECTED_DB = DATA_DIR / "info_collected.db"
APP_STATE_DB = DATA_DIR / "app_state.db"


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def require_database(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(
            f"Database not found: {resolved}. Start the app with `uv run main.py`."
        )
    return resolved
