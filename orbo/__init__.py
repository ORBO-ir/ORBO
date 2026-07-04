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

from orbo.registry import registry
from orbo.intraday import IntradaySession, fetch_intraday_range
from orbo.instrument import Instrument, LiveSnapshot


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
