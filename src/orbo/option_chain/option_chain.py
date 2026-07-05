"""
OptionChain — organized view of all listed option contracts.

Fetches from TSETMC's GetInstrumentOptionMarketWatch endpoint and
provides a clean, queryable interface grouped by underlying and expiry.

Analytics (Black-Scholes, Greeks, IV surface) are NOT here.
They belong in the separate orbo-quant library that reads from this class.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from orbo.clients.option import TSETMCOptionClient, MARKET_ALL
from orbo.constants import LOGGER_NAME
from orbo.data.transformers import option_chain_to_dataframe

logger = logging.getLogger(LOGGER_NAME)


class OptionChain:
    """
    Full option chain snapshot from TSETMC.

    Provides one row per call/put pair per strike per underlying,
    grouped by expiry date. Supports filtering by underlying symbol
    and refreshing to get the latest prices.

    Examples
    --------
    Fetch and display::

        chain = OptionChain.fetch()                # all markets
        chain = OptionChain.fetch(market_id=1)     # TSE only

        chain.underlyings                          # list of available underlyings
        chain.expiries("اهرم")                    # expiry dates for one underlying

        df = chain.chain                           # full DataFrame
        df = chain.filter("اهرم")                 # one underlying
        df = chain.for_expiry("اهرم", "1405-04-31") # one expiry

    Refresh during live session::

        chain.refresh()                            # re-fetches everything

    Note
    ----
    Greeks, implied volatility, and Black-Scholes pricing are in orbo-quant:

        import orbo_quant as oq
        result = oq.black_scholes(chain.filter("اهرم"), r=0.25)
    """

    def __init__(self, df: pd.DataFrame, market_id: int = MARKET_ALL) -> None:
        self._df        = df
        self._market_id = market_id

    # ── Factory methods ─────────────────────────────────────────────────────

    @classmethod
    def fetch(cls, market_id: int = MARKET_ALL) -> "OptionChain":
        """
        Fetch a fresh option chain snapshot from TSETMC.

        Parameters
        ----------
        market_id : int
            0 = all markets (default), 1 = TSE (بورس), 2 = OTC (فرابورس)

        Returns
        -------
        OptionChain
        """
        with TSETMCOptionClient() as client:
            records = client.get_chain(market_id=market_id)

        df = option_chain_to_dataframe(records)
        logger.info("OptionChain fetched: %d rows, %d underlyings",
                    len(df), df["underlying_symbol"].nunique() if not df.empty else 0)
        return cls(df, market_id=market_id)

    # ── Query interface ─────────────────────────────────────────────────────

    @property
    def chain(self) -> pd.DataFrame:
        """Full option chain DataFrame — all underlyings, all expiries."""
        return self._df.copy()

    @property
    def underlyings(self) -> list[str]:
        """Sorted list of all underlying symbols available in this snapshot."""
        if self._df.empty:
            return []
        return sorted(self._df["underlying_symbol"].unique().tolist())

    def expiries(self, underlying: str) -> list[str]:
        """
        Return expiry dates available for a given underlying.

        Parameters
        ----------
        underlying : str
            Underlying symbol, e.g. "اهرم".

        Returns
        -------
        list[str]
            Jalali date strings sorted ascending, e.g. ["1405-04-31", "1405-05-28"].
        """
        subset = self._df[self._df["underlying_symbol"] == underlying]
        if subset.empty:
            return []
        return sorted(subset["expiry_jalali"].dropna().unique().tolist())

    def filter(self, underlying: str) -> pd.DataFrame:
        """
        Return all strike rows for one underlying (all expiries).

        Parameters
        ----------
        underlying : str
            Underlying symbol, e.g. "اهرم".

        Returns
        -------
        pd.DataFrame
            Sorted ascending by expiry_jalali, then strike.
        """
        subset = self._df[self._df["underlying_symbol"] == underlying].copy()
        return subset.reset_index(drop=True)

    def for_expiry(self, underlying: str, expiry_jalali: str) -> pd.DataFrame:
        """
        Return the strike chain for one underlying and one expiry date.

        Parameters
        ----------
        underlying : str
            Underlying symbol, e.g. "اهرم".
        expiry_jalali : str
            Jalali expiry date in YYYY-MM-DD format, e.g. "1405-04-31".

        Returns
        -------
        pd.DataFrame
            One row per strike, sorted ascending. Columns include
            strike, dte, call_*/put_* prices, OI, bid/ask, etc.
        """
        subset = self._df[
            (self._df["underlying_symbol"] == underlying) &
            (self._df["expiry_jalali"]     == expiry_jalali)
        ].copy()
        return subset.sort_values("strike").reset_index(drop=True)

    def summary(self) -> pd.DataFrame:
        """
        High-level summary: one row per (underlying, expiry) showing
        the number of strikes and total open interest.

        Returns
        -------
        pd.DataFrame
            Columns: underlying_symbol, expiry_jalali, dte,
                     n_strikes, call_oi_total, put_oi_total.
        """
        if self._df.empty:
            return pd.DataFrame()

        rows = []
        for (underlying, expiry), group in self._df.groupby(
            ["underlying_symbol", "expiry_jalali"]
        ):
            rows.append({
                "underlying_symbol": underlying,
                "expiry_jalali":     expiry,
                "dte":               int(group["dte"].iloc[0]) if "dte" in group else None,
                "n_strikes":         len(group),
                "call_oi_total":     int(group["call_oi"].sum()) if "call_oi" in group else 0,
                "put_oi_total":      int(group["put_oi"].sum())  if "put_oi" in group else 0,
            })
        return pd.DataFrame(rows).sort_values(
            ["underlying_symbol", "expiry_jalali"]
        ).reset_index(drop=True)

    # ── Live refresh ────────────────────────────────────────────────────────

    def refresh(self) -> "OptionChain":
        """
        Re-fetch the option chain from TSETMC and update this instance.

        Since TSETMC sends a full snapshot every ~3 seconds (not an
        incremental diff), a full re-fetch is the correct strategy.

        Returns self so you can chain: chain.refresh().filter("اهرم")
        """
        with TSETMCOptionClient() as client:
            records = client.get_chain(market_id=self._market_id)

        self._df = option_chain_to_dataframe(records)
        logger.info("OptionChain refreshed: %d rows", len(self._df))
        return self

    # ── Dunder ──────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._df)

    def __repr__(self) -> str:
        if self._df.empty:
            return "OptionChain(empty)"
        return (
            f"OptionChain("
            f"underlyings={len(self.underlyings)}, "
            f"rows={len(self._df)}"
            f")"
        )
