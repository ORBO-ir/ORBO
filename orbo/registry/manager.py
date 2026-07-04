from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import RegistryRecord


REGISTRY_PATH = Path(".orbo/registry.parquet")


class RegistryManager:

    def __init__(self, path: Path = REGISTRY_PATH):

        self.path = path

        self.records: dict[int, RegistryRecord] = {}

        self.symbol_index: dict[str, int] = {}

        self._loaded = False

    def load(self):

        if not self.path.exists():
            raise FileNotFoundError(self.path)

        df = pd.read_parquet(self.path)

        self.records.clear()
        self.symbol_index.clear()

        for row in df.itertuples(index=False):

            record = RegistryRecord(
                ins_code=row.ins_code,
                symbol=row.symbol,
                name=row.name,
                sector=row.sector,
                label=row.label,
            )

            self.records[record.ins_code] = record

            self.symbol_index[record.symbol] = record.ins_code

            self.symbol_index[record.label] = record.ins_code
            
            self._loaded = True
    
    def lookup(self, key: str | int) -> RegistryRecord | None:
        
        if not self._loaded:
            self.load()

        if isinstance(key, int):
            return self.records.get(key)

        ins_code = self.symbol_index.get(key)

        if ins_code is None:
            return None
        
        return self.records.get(ins_code)
