from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RegistryRecord:
    """
    Represents a single instrument inside the local registry.
    """

    ins_code: int

    symbol: str

    name: str

    sector: str

    label: str
