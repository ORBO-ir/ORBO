

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from orbo.clients.static import StaticDataClient
from orbo.registry.transformer import transform_registry





REGISTRY_PATH = Path(".orbo/registry.parquet")


class RegistryUpdater:
    """
    Downloads the latest MarketMap and rebuilds registry.parquet.
    """

    def update(self) -> Path:

        client = StaticDataClient()

        try:
            data = client.get_marketmap()

        finally:
            client.close()

        records = transform_registry(data)
        
        df = pd.DataFrame([asdict(r) for r in records])

        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

        df.to_parquet(REGISTRY_PATH, index=False)

        return REGISTRY_PATH
