"""
Registry module — lazy-loaded local instrument lookup.

Quick start
-----------
    import orbo
    orbo.bootstrap()          # run once after installation
    rec = orbo.ticker("فملی")  # then look up symbols instantly
"""
from orbo.registry.manager import RegistryManager
from orbo.registry.updater import RegistryUpdater

# Singleton — loaded lazily on first lookup()
registry = RegistryManager()

__all__ = ["registry", "RegistryManager", "RegistryUpdater"]
