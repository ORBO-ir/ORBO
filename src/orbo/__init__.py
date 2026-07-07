"""ORBO — Python SDK for TSETMC (Tehran Stock Exchange) data."""
from orbo.search.instrument_search import search
from orbo.history.history import InstrumentHistory
from orbo.static.manager import StaticDataManager
from orbo.logger import setup_logging
from orbo.models import SearchResult, InstrumentIdentity
from orbo.option_chain import OptionChain
from orbo.index import MarketIndex, index_snapshot, find_index

from orbo.engines import (
    AdjustmentEngine, AdjustedRow,
    TradeSideEngine,
    FootprintEngine,  FootprintResult,
    DailyStatsEngine, DailyStatsResult,
    IntraStatsEngine, IntraStatsResult,
)

from orbo.registry import registry, RegistryUpdater
from orbo.exceptions import RegistryNotInitializedError

from orbo.intraday import IntradaySession, fetch_intraday_range
from orbo.instrument import Instrument, LiveSnapshot


def bootstrap() -> None:
    """
    Build the local instrument registry for the first time.

    Downloads the TSETMC market map and saves it to ~/.orbo/registry.parquet.
    Run once after installation. Re-run periodically to pick up new listings.

    After bootstrap(), orbo.ticker() and orbo.Instrument("symbol") work
    instantly without any API call for symbol resolution.

    Example
    -------
        import orbo
        orbo.bootstrap()          # ~5 seconds, run once
        print(orbo.ticker("فملی"))
    """
    path = RegistryUpdater().update()
    # Reload the in-memory registry so ticker() works immediately
    registry._loaded = False
    registry.load()
    print(f"Registry ready — {len(registry.records):,} instruments loaded from {path}")

def ticker(key: str | int):
    """Look up an instrument by symbol or ins_code from the local registry."""
    return registry.lookup(key)


__all__ = [
    "search",
    "InstrumentHistory",
    "StaticDataManager",
    "setup_logging",
    "SearchResult",
    "InstrumentIdentity",
    "AdjustmentEngine",
    "AdjustedRow",
    "TradeSideEngine",
    "DailyStatsEngine",
    "DailyStatsResult",
    "FootprintEngine",
    "FootprintResult",
    "IntraStatsEngine",
    "IntraStatsResult",
    "ticker",
    "registry",
    "IntradaySession",
    "fetch_intraday_range",
    "Instrument",
    "LiveSnapshot",
    "OptionChain",
    "MarketIndex",
    "index_snapshot",
    "find_index",
]
