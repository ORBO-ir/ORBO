from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

PROJECT_DIR = PACKAGE_DIR.parent

DATA_DIR = PROJECT_DIR / ".orbo"

CACHE_DIR = DATA_DIR / "cache"

LOG_DIR = DATA_DIR / "logs"

REGISTRY_PATH = DATA_DIR / "registry.parquet"

SETTINGS_PATH = DATA_DIR / "settings.json"


def ensure_data_dirs() -> None:

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
