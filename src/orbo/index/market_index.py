"""
MarketIndex — access data for a single TSE/OTC market index.

TSETMC publishes dozens of sector and composite indices.
This module provides a clean API to fetch and analyze them.
"""
from __future__ import annotations

import logging

import pandas as pd

from orbo.clients.index import TSETMCIndexClient, MARKET_ALL, MARKET_TSE, MARKET_OTC
from orbo.constants import LOGGER_NAME
from orbo.data.transformers import (
    index_snapshot_to_dataframe,
    index_history_to_dataframe,
    index_today_to_dataframe,
    index_companies_to_dataframe,
)
from orbo.exceptions import OrboNotFoundError

logger = logging.getLogger(LOGGER_NAME)


# ── Module-level helpers ─────────────────────────────────────────────────────

def index_snapshot(market_id: int = MARKET_ALL) -> pd.DataFrame:
    """
    Fetch a live snapshot of all selected market indices.

    Parameters
    ----------
    market_id : int
        0 = all markets (default), 1 = TSE (بورس), 2 = OTC (فرابورس)

    Returns
    -------
    pd.DataFrame
        Columns: ins_code, name, time, value, high, low, change, change_pct.
        One row per index, sorted by name.

    Examples
    --------
        df = orbo.index_snapshot()
        df = orbo.index_snapshot(market_id=1)   # TSE only
        print(df[df["name"].str.contains("شاخص كل")])
    """
    with TSETMCIndexClient() as client:
        records = client.get_snapshot(market_id=market_id)
    return index_snapshot_to_dataframe(records)


def find_index(name: str, market_id: int = MARKET_ALL) -> "MarketIndex":
    """
    Find an index by name and return a MarketIndex object.

    Fetches the full index list and searches by name substring.
    The first match is returned — if you get the wrong result,
    use a more specific substring.

    Parameters
    ----------
    name : str
        Search term — matched as a substring of the index name.
        Example: "شاخص كل", "سيمان", "بانك"
    market_id : int
        0 = all (default), 1 = TSE, 2 = OTC

    Returns
    -------
    MarketIndex

    Raises
    ------
    OrboNotFoundError
        If no index name contains the search term.

    Examples
    --------
        idx = orbo.find_index("شاخص كل")
        idx = orbo.find_index("سيمان")
        idx = orbo.find_index("فلزات اساسي")
    """
    with TSETMCIndexClient() as client:
        records = client.get_snapshot(market_id=market_id)

    for r in records:
        if name in (r.get("lVal30") or ""):
            ins_code    = str(r["insCode"])
            index_name  = r["lVal30"]
            logger.debug("find_index('%s') → %s (%s)", name, index_name, ins_code)
            return MarketIndex(ins_code, _name=index_name)

    raise OrboNotFoundError(
        f"No index found containing '{name}'. "
        "Call orbo.index_snapshot() to see all available indices."
    )


# ── MarketIndex class ────────────────────────────────────────────────────────

class MarketIndex:
    """
    Data access for a single TSETMC market index.

    Parameters
    ----------
    ins_code : str
        Index instrument code. Use find_index() or index_snapshot() to
        discover codes, or read them directly from the TSETMC website.

    Examples
    --------
    By inscode::

        idx = orbo.MarketIndex("32097828799138957")  # شاخص کل

    By name (easier)::

        idx = orbo.find_index("شاخص كل")
        idx = orbo.find_index("سيمان")

    Fetch data::

        df = idx.history()     # full historical daily values
        df = idx.today()       # today's intraday time series
        df = idx.companies()   # constituent companies with live prices

    Analyse with DailyStatsEngine::

        from orbo import DailyStatsEngine
        stats = DailyStatsEngine().compute(idx.history())
        print(stats.descriptive)
        print(stats.distribution)
    """

    def __init__(self, ins_code: str | int, *, _name: str | None = None) -> None:
        self._ins_code = str(ins_code)
        self._name     = _name   # populated by find_index(); None if unknown

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def ins_code(self) -> str:
        """Index instrument code."""
        return self._ins_code

    @property
    def name(self) -> str | None:
        """Index name (available when resolved via find_index())."""
        return self._name

    # ── Data methods ─────────────────────────────────────────────────────────

    def history(self) -> pd.DataFrame:
        """
        Fetch the complete daily value history since inception.

        Returns
        -------
        pd.DataFrame
            Columns: date (Jalali), value, low, high.
            Sorted ascending by date (oldest first).
            Can be passed directly to DailyStatsEngine().compute().

        Note
        ----
        The column name is "value" (not "close") to reflect that index
        values are not prices. DailyStatsEngine accepts "close" — rename
        the column if needed: df.rename(columns={"value": "close"}).
        """
        with TSETMCIndexClient() as client:
            records = client.get_history(self._ins_code)
        return index_history_to_dataframe(records)

    def today(self) -> pd.DataFrame:
        """
        Fetch today's intraday time series for this index.

        Published at ~25-minute intervals during the trading session.
        High and low reflect running intraday extremes.

        Returns
        -------
        pd.DataFrame
            Columns: time, value, high, low, change_pct.
            Sorted ascending by time.
        """
        with TSETMCIndexClient() as client:
            records = client.get_today(self._ins_code)
        return index_today_to_dataframe(records)

    def companies(self) -> pd.DataFrame:
        """
        Fetch the constituent companies of this index with live prices.

        Returns
        -------
        pd.DataFrame
            Columns: ins_code, symbol, name, close, last_price, prev_close,
                     change, low, high, trade_count, volume, value.
            Sorted by symbol.
        """
        with TSETMCIndexClient() as client:
            records = client.get_companies(self._ins_code)
        return index_companies_to_dataframe(records)

    def stats(self) -> "DailyStatsResult":
        """
        Compute return series and distribution statistics on the
        full historical index values.

        Renames "value" → "close" internally so DailyStatsEngine works.

        Returns
        -------
        DailyStatsResult
        """
        from orbo.engines.daily_stats import DailyStatsEngine
        df = self.history().rename(columns={"value": "close"})
        return DailyStatsEngine().compute(df)

    # ── Dunder ──────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"MarketIndex("
            f"ins_code={self._ins_code!r}, "
            f"name={self._name!r})"
        )
