"""
RegistryManager — local instrument lookup from a Parquet cache.

The registry is built once by RegistryUpdater.update() (or orbo.bootstrap())
and stored at ~/.orbo/registry.parquet. It is loaded lazily on first use.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from orbo.exceptions import RegistryNotInitializedError
from orbo.paths import REGISTRY_PATH
from orbo.registry.models import RegistryRecord


class RegistryManager:
    """
    Fast local lookup: symbol / ins_code → RegistryRecord.

    The Parquet file is read once and cached in memory. Subsequent
    lookup() calls are dictionary lookups with no I/O.

    Usage
    -----
    The singleton ``orbo.registry`` is created at import time but the
    Parquet file is NOT read until the first lookup():

        orbo.bootstrap()          # build the registry once
        rec = orbo.ticker("فملی") # then look up symbols instantly
    """

    def __init__(self, path: Path = REGISTRY_PATH) -> None:
        self.path         = path
        self.records:      dict[int, RegistryRecord] = {}
        self.symbol_index: dict[str, int]            = {}
        self._loaded      = False

    def load(self) -> None:
        """
        Load registry from Parquet into memory.

        Raises
        ------
        RegistryNotInitializedError
            If the registry file has not been built yet.
            Fix: call orbo.bootstrap() first.
        """
        if not self.path.exists():
            raise RegistryNotInitializedError(
                f"Registry not found at {self.path}\n\n"
                "The registry must be built before first use:\n\n"
                "    import orbo\n"
                "    orbo.bootstrap()   # downloads instrument list from TSETMC\n\n"
                "This only needs to be done once. "
                "Re-run periodically to pick up newly listed instruments."
            )

        df = pd.read_parquet(self.path)

        self.records.clear()
        self.symbol_index.clear()

        for row in df.itertuples(index=False):
            record = RegistryRecord(
                ins_code = row.ins_code,
                symbol   = row.symbol,
                name     = row.name,
                sector   = getattr(row, "sector", None),
                label    = getattr(row, "label", row.symbol),
            )
            self.records[record.ins_code]          = record
            self.symbol_index[record.symbol]       = record.ins_code
            self.symbol_index[str(record.ins_code)] = record.ins_code
            if record.label and record.label != record.symbol:
                self.symbol_index[record.label] = record.ins_code

        self._loaded = True

    def lookup(self, key: str | int) -> RegistryRecord | None:
        """
        Look up an instrument by symbol, label, or ins_code.

        Parameters
        ----------
        key : str | int
            Trading symbol (e.g. "فملی"), display label, or numeric ins_code.

        Returns
        -------
        RegistryRecord | None
            None if not found. Raises RegistryNotInitializedError if the
            registry has not been built yet.

        Raises
        ------
        RegistryNotInitializedError
            If registry.parquet does not exist at ~/.orbo/registry.parquet.
        """
        if not self._loaded:
            self.load()

        if isinstance(key, int):
            return self.records.get(key)

        # Try exact symbol/label match first
        ins_code = self.symbol_index.get(str(key))
        if ins_code is not None:
            return self.records.get(ins_code)

        return None

    def is_ready(self) -> bool:
        """Return True if the registry file exists and can be loaded."""
        return self.path.exists()

    def __repr__(self) -> str:
        if self._loaded:
            return f"RegistryManager(records={len(self.records)}, path={self.path})"
        return f"RegistryManager(loaded=False, path={self.path})"
