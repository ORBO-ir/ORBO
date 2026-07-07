"""
RegistryUpdater — downloads the latest instrument list and builds registry.parquet.

This is the only place that writes to ~/.orbo/registry.parquet.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from orbo.clients.static import StaticDataClient
from orbo.paths import REGISTRY_PATH
from orbo.registry.transformer import transform_registry


class RegistryUpdater:
    """
    Build or refresh the local instrument registry from TSETMC data.

    Run once after installation, then periodically to pick up newly
    listed instruments (e.g. weekly or monthly is enough).

    Examples
    --------
        import orbo

        # First-time setup:
        orbo.bootstrap()

        # Or call directly:
        from orbo.registry import RegistryUpdater
        path = RegistryUpdater().update()
        print(f"Registry saved to {path}")
    """

    def __init__(self, path: Path = REGISTRY_PATH) -> None:
        self.path = path

    def update(self) -> Path:
        """
        Download the TSETMC market map and write registry.parquet.

        Returns
        -------
        Path
            The path where registry.parquet was written (~/.orbo/registry.parquet).

        Raises
        ------
        OrboConnectionError
            If TSETMC cannot be reached.
        """
        client = StaticDataClient()
        try:
            data = client.get_marketmap()
        finally:
            client.close()

        records = transform_registry(data)
        df      = pd.DataFrame([asdict(r) for r in records])

        # Ensure the directory exists (creates ~/.orbo/ if needed)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        df.to_parquet(self.path, index=False)
        return self.path
