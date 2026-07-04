"""
Registry module — lazy-loaded local instrument lookup.

The registry parquet file is loaded on first access, not at import time.
Run RegistryUpdater().update() once to build the file from TSETMC data.
"""
from .manager import RegistryManager

# Lazy-loaded singleton — does NOT call load() at import time.
# load() is called automatically on first lookup().
registry = RegistryManager()

__all__ = ["registry", "RegistryManager"]
