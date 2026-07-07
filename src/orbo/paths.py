"""
User-facing filesystem paths for ORBO.

All persistent data (registry, cache, logs) lives under ~/.orbo/
so that it is writable regardless of how the package was installed.
"""
from __future__ import annotations

from pathlib import Path

# ── User data directory (~/.orbo/) ──────────────────────────────────────────
# Using the home directory ensures this works whether orbo was installed
# via pip (read-only site-packages), conda, or in editable mode.
DATA_DIR    = Path.home() / ".orbo"
CACHE_DIR   = DATA_DIR / "cache"
LOG_DIR     = DATA_DIR / "logs"

REGISTRY_PATH = DATA_DIR / "registry.parquet"
SETTINGS_PATH = DATA_DIR / "settings.json"


def ensure_data_dirs() -> None:
    """Create ~/.orbo/ subdirectories if they don't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
